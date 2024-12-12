import os
import sys
import typing
import asyncio
import uuid
import shutil
import logging
import time

import cv2

import zendriver_flare_bypasser as zendriver

XVFB_DISPLAY = None
logger = logging.getLogger(__name__)


"""
Trivial wrapper for browser (driver).
Allow to localize driver operations implementation and requirements,
and simplify migration to other driver.
In zendriver(nodriver) we use _reliable_call_driver for calls as workaround for problem:
sometimes, chrome don't reply on CDP call and zendriver hangs on reply waiting.
"""


class BrowserWrapper(object):
  _zendriver_driver: zendriver.Browser = None
  _stopped_process: asyncio.subprocess.Process = None
  _page: zendriver.Tab = None
  _debug_execution_time: bool
  _enable_lost_cdp_workaround: bool
  _select_call_timeout: float = 2  # < 2 seconds

  class FakePosition(object):
    center = None

    def __init__(self, center):
      self.center = tuple(float(x) for x in center)
      # < zendriver expect here only json serializable types

  class FakeNode(object):
    attributes = None
    # Attributes for working __repr__:
    node_name = ''
    child_node_count = None
    node_type = 0

  class FakeElement(zendriver.Element):
    _position = None

    def __init__(self, page: zendriver.Tab, center_coords):
      super(BrowserWrapper.FakeElement, self).__init__(
        BrowserWrapper.FakeNode(),  # zendriver.cdp.dom.Node
        page  # zendriver.Tab
      )
      self._position = BrowserWrapper.FakePosition(center_coords)

    def _make_attrs(self):  # override for exclude exception on __init__
      pass

    # overrides for call only cdp click send in zendriver.Element.mouse_click
    async def get_position(self):
      return self._position

    async def flash(self, duration: typing.Union[float, int] = 0.5):
      pass

  def __init__(
    self, zendriver_driver: zendriver.Browser, user_data_dir: str = None,
    debug_execution_time: bool = True,
    enable_lost_cdp_workaround: bool = True
  ):
    self._zendriver_driver = zendriver_driver
    self._user_data_dir = user_data_dir
    self._debug_execution_time = debug_execution_time
    self._enable_lost_cdp_workaround = enable_lost_cdp_workaround

  def __del__(self):
    if self._user_data_dir:
      shutil.rmtree(self._user_data_dir, ignore_errors=True)

  @staticmethod
  def start_xvfb_display():
    if sys.platform != 'win32':
      global XVFB_DISPLAY
      if XVFB_DISPLAY is None:
        from xvfbwrapper import Xvfb
        XVFB_DISPLAY = Xvfb()
        XVFB_DISPLAY.start()

  @staticmethod
  async def create(proxy = None, disable_gpu = False):
    user_data_dir = os.path.join("/tmp", str(uuid.uuid4()))  # < Each created chrome should be isolated.
    BrowserWrapper.start_xvfb_display()
    browser_args = []
    if proxy:
      browser_args.append("--proxy-server=" + proxy)
    if disable_gpu:
      browser_args += [
        "--disable-gpu",
        "--disable-software-rasterizer"
      ]
    if sys.platform == 'win32':
      browser_args += ["--headless"]

    browser_args += ["--user-data-dir=" + user_data_dir]
    # Disable certificates checking
    browser_args += ["--ignore-certificate-errors", "--ignore-urlfetcher-cert-requests"]
    try:
      config = zendriver.Config(
        sandbox=False,
        browser_args=browser_args
      )
      zendriver_driver = await zendriver.Browser.create(config)
      return BrowserWrapper(zendriver_driver, user_data_dir = user_data_dir)
    finally:
      shutil.rmtree(user_data_dir, ignore_errors=True)

  # Get original driver page impl - can be used only in user command specific implementations
  def get_driver(self) -> zendriver.Tab:
    return self._page

  async def get_outputs(self):
    try:
      if self._zendriver_driver:  # < driver isn't stopped
        stdout_bytes, stderr_bytes = await self._zendriver_driver.communicate()
      elif self._stopped_process:  # < driver stopped, read output of stopped process
        stdout_bytes, stderr_bytes = await self._stopped_process.communicate()
      else:
        return None
      return [stdout_bytes, stderr_bytes]
    except Exception:
      return None

  async def current_url(self):
    return self._page.url

  async def close(self):
    self._page = None
    if self._zendriver_driver:
      self._stopped_process = await self._zendriver_driver.stop()
      self._zendriver_driver = None
    if self._user_data_dir:
      shutil.rmtree(self._user_data_dir, ignore_errors=True)
      self._user_data_dir = None

  # return (title, loaded flag)
  async def title(self) -> typing.Tuple[str, bool]:
    try:
      res = await asyncio.wait_for(
        self._reliable_call_driver(
          zendriver.Tab.select,  # < self._page.select("title", timeout=0)
          self._page,
          "title",
          timeout=0,
          call_name='title:select'
        ),
        self._select_call_timeout  # < title can hangs on page loading (no CDP response), repeat title call in bypasser
      )
      return (res.text, True)
    except zendriver.core.connection.ProtocolException as e:
      if "could not find node with given id" in str(e).lower():
        # DOM tree changed in runtime
        return (None, True)
    except asyncio.TimeoutError as e:
      if "time ran out while waiting for " in str(e).lower():
        # < zendriver timeout on element waiting
        return (None, True)
      # external timeout: page isn't loaded
      return (None, False)

  async def select_count(self, css_selector):
    try:
      return len(
        await asyncio.wait_for(
          self._reliable_call_driver(
            zendriver.Tab.select_all,  # < self._page.select_all(css_selector, timeout=0)
            self._page,
            css_selector,
            timeout=0,
            call_name="select_count(" + str(css_selector) + "):select_all"
          ),
          self._select_call_timeout  # < select can hangs on page loading (no CDP response), repeat select call in bypasser
        )
      )
      # < Select without waiting.
    except zendriver.core.connection.ProtocolException as e:
      if "could not find node with given id" in str(e).lower():
        # DOM tree changed in runtime
        return 0
      raise e from e
    except asyncio.TimeoutError:
      return 0

  async def get(self, url):
    # we work only with one page - close all tabs (excluding first - this close browser)
    for tab_i, tab in enumerate(self._zendriver_driver.tabs):
      if tab_i > 0:
        await tab.close()
    self._page = await self._reliable_call_driver(
      zendriver.Browser.get,
      self._zendriver_driver,  # < self._zendriver_driver.get(url)
      url,
      call_name=("get(" + url + ")"),
      timeout_step=5
    )

  async def click_coords(self, coords):
    # Specific workaround for zendriver
    # click by coordinates without no driver patching.
    fake_node = BrowserWrapper.FakeElement(self._page, coords)
    await self._reliable_call_driver(
      BrowserWrapper.FakeElement.mouse_click,  # < fake_node.mouse_click()
      fake_node,
      call_name='click_coords:mouse_click'
    )

  async def get_user_agent(self):
    return await self._reliable_call_driver(
      zendriver.Tab.evaluate,  # < self._page.evaluate("window.navigator.userAgent")
      self._page,
      "navigator.userAgent",
      call_name='get_user_agent:evaluate'
    )

  async def get_dom(self):
    res_dom = await self._reliable_call_driver(
      zendriver.Tab.get_content,  # < self._page.get_content()
      self._page,
      call_name='get DOM'
    )
    return (res_dom if res_dom is not None else "")  # zendriver return None sometimes (on error)

  async def get_screenshot(self):  # Return screenshot as cv2 image (numpy array)
    tmp_file_path = None
    try:
      while True:
        try:
          tmp_file_path = os.path.join("/tmp", str(uuid.uuid4()) + ".jpg")
          await self._reliable_call_driver(
            zendriver.Tab.save_screenshot,  # < self._page.save_screenshot(tmp_file_path)
            self._page,
            tmp_file_path,
            call_name='get_screenshot:save_screenshot'
          )
          return cv2.imread(tmp_file_path)
        except zendriver.core.connection.ProtocolException as e:
          if "not finished loading yet" not in str(e):
            raise e from e
        await asyncio.sleep(1)
    finally:
      if tmp_file_path is not None and os.path.exists(tmp_file_path):
        os.remove(tmp_file_path)

  async def save_screenshot(self, image_path):
    while True:
      try:
        await self._reliable_call_driver(
          zendriver.Tab.save_screenshot,  # < self._page.save_screenshot(image_path)
          self._page,
          image_path,
          call_name='save_screenshot:save_screenshot'
        )
        return
      except zendriver.core.connection.ProtocolException as e:
        if "not finished loading yet" not in str(e):
          raise
      await asyncio.sleep(1)

  async def set_cookies(self, cookies: list[dict]):
    # convert {"name": "...", "value": "...", ...} to array of http.cookiejar.Cookie
    set_cookies = []
    for c in cookies:
      add_cookie = zendriver.CookieParam(
        name=c.get('name', None),
        value=c.get('value', None),
        source_port=c.get('port', 443),
        domain=c.get('domain', None),
        path=c.get('path', None),
        secure=c.get('secure', False),
        expires = c.get('expires', None),
        same_site=c.get('same_site', None)
      )
      set_cookies.append(add_cookie)
    await self._reliable_call_driver(
      getattr(self._zendriver_driver.cookies.__class__, 'set_all'),
      # < self._zendriver_driver.cookies.set_all(set_cookies)
      self._zendriver_driver.cookies,
      set_cookies,
      call_name='set_cookies:set_all'
    )

  async def get_cookies(self) -> list[dict]:
    # return list of dict have format: {"name": "...", "value": "..."}
    zendriver_cookies = await self._reliable_call_driver(
      getattr(self._zendriver_driver.cookies.__class__, 'get_all'),
      # < self._zendriver_driver.cookies.get_all(requests_cookie_format=True)
      self._zendriver_driver.cookies,
      requests_cookie_format=True,
      call_name='get_cookies:get_all'
    )
    res = []
    # convert array of http.cookiejar.Cookie to expected cookie format
    for cookie in zendriver_cookies:
      res.append({
        "name": cookie.name,
        "value": cookie.value,
        "port": cookie.port,
        "domain": cookie.domain,
        "path": cookie.path,
        "secure": cookie.secure
      })
    return res

  # Wrap call that allow to repeat driver call after timeout_step
  # Used as workaround for case when chrome don't response on CDP request
  # Can be disabled by enable_lost_cdp_workaround flag
  async def _reliable_call_driver(
    self, task_fun, *args, call_name = None, timeout_step = 1, **kwargs
  ):
    if self._debug_execution_time:
      start_time = time.time()
      logger.debug(
        "to call '" + (call_name if call_name else BrowserWrapper._parse_call(task_fun)) +
        "'"
      )
    finished = False
    try:
      if self._enable_lost_cdp_workaround:
        # for understand why we pass lambda to _deffered_call, see _deffered_call description
        res = await BrowserWrapper._wait_first([
          BrowserWrapper._call_zendriver_async(task_fun, *args, fork_i = 0, call_name = call_name, **kwargs),
          BrowserWrapper._deffered_call(
            lambda: BrowserWrapper._call_zendriver_async(task_fun, *args, fork_i = 1, call_name = call_name, **kwargs),
            timeout_step
          ),
          BrowserWrapper._deffered_call(
            lambda: BrowserWrapper._call_zendriver_async(task_fun, *args, fork_i = 2, call_name = call_name, **kwargs),
            2 * timeout_step
          )
        ])
      else:
        res = await task_fun(*args, **kwargs)
      finished = True
    finally:
      if self._debug_execution_time:
        logger.debug(
          "'" + (call_name if call_name else BrowserWrapper._parse_call(task_fun)) +
          "' " + ("finished" if finished else "exception") + ", execution time: " +
          "{:.3f}".format(time.time() - start_time) + " sec"
        )
    return res

  @staticmethod
  async def _call_zendriver_async(
    fun: typing.Callable[typing.Any, typing.Awaitable], *args, fork_i = 0, call_name = None,
    **kwargs
  ):
    try:
      logger.debug(
        "call '" + (call_name if call_name else BrowserWrapper._parse_call(fun)) +
        "': fork #" + str(fork_i) + " started"
      )
      max_tries = 5
      for i in range(max_tries):
        try:
          return await fun(*args, **kwargs)
        except TypeError as e:
          if "target must be set to" in str(e) and i != max_tries - 1:
            # handle exceptions like: TypeError: target must be set to a 'TargetInfo' but got 'NoneType
            # it can appears in zendriver.connection.update_target on all operations,
            # (as result of runtime DOM changes or on page loading)
            continue
          raise
    finally:
      logger.debug(
        "call '" + (call_name if call_name else BrowserWrapper._parse_call(fun)) +
        "': fork #" + str(fork_i) + " finished"
      )

  @staticmethod
  def _parse_call(task):
    res = str(task)
    if res.startswith("<") and res.endswith(">"):
      res = res[1:][:-1]
    if res.startswith("coroutine object "):
      res = res[17:]
    index = res.find(" at 0x")
    if index >= 1:
      res = res[:index]
    return res

  # task is function, that will return coro, this allow to
  # avoid "coroutine ... was never awaited" warning
  # (we create coro only before it await)
  @staticmethod
  async def _deffered_call(task: typing.Callable[typing.Any, typing.Awaitable], timeout: float):
    if timeout > 0:
      await asyncio.sleep(timeout)
    task_coro = task()
    return await task_coro

  @staticmethod
  async def _wait_first(tasks):
    task_features = [asyncio.ensure_future(t) for t in tasks]
    to_cancel_tasks = []
    try:
      finished, to_cancel_tasks = await asyncio.wait(
        task_features, return_when = asyncio.FIRST_COMPLETED
      )
      return await next(iter(finished))
    except asyncio.exceptions.CancelledError:
      # wait first task canceled for get stack in exception
      task_features[0].cancel()
      await task_features[0]
    finally:
      for t in to_cancel_tasks:
        t.cancel()
