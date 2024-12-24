import os
import sys
import typing
import asyncio
import uuid
import shutil
import logging
import time
import concurrent
import numpy as np
import cssselect

import cv2

import DrissionPage
import DrissionPage.errors

XVFB_DISPLAY = None
logger = logging.getLogger(__name__)


class BrowserWrapper(object):
  _pool: concurrent.futures.ThreadPoolExecutor = None
  _page = None
  _proxy: str = None
  _debug_execution_time: bool
  _select_call_timeout: float = 2  # < 2 seconds

  def get__page():
    return self._page

  def __init__(
    self, page, user_data_dir: str = None,
    proxy: str = None,
    debug_execution_time: bool = True,
    enable_lost_cdp_workaround: bool = True
  ):
    self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    self._page = page
    self._user_data_dir = user_data_dir
    self._proxy = proxy
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
    print("> XXX create", flush=True)
    user_data_dir = os.path.join("/tmp", str(uuid.uuid4()))  # < Each created chrome should be isolated.
    BrowserWrapper.start_xvfb_display()
    chrome_options = DrissionPage.ChromiumOptions()
    if proxy:
      chrome_options.set_argument('--proxy-server', proxy)
    if disable_gpu:
      chrome_options.set_argument('--disable-gpu')
      chrome_options.set_argument('--disable-software-rasterizer')
    if sys.platform == 'win32':
      chrome_options.headless(True)
    else:
      chrome_options.headless(False)

    chrome_options.set_argument('--user-data-dir', user_data_dir)
    # Disable certificates checking
    chrome_options.set_argument('--ignore-certificate-errors')
    chrome_options.set_argument('--ignore-urlfetcher-cert-requests')
    chrome_options.set_argument('--no-sandbox')
    chrome_options.set_browser_path('/usr/bin/chrome')
    #page = DrissionPage.ChromiumPage(addr_or_opts=chrome_options)
    page = DrissionPage.WebPage(chromium_options=chrome_options)
    print("< XXX create", flush=True)
    return BrowserWrapper(page, user_data_dir=user_data_dir, proxy=proxy)

  # Get original driver page impl - can be used only in user command specific implementations
  def get_driver(self):
    return self._page

  async def get_outputs(self):
    return [b'', b'']

  async def current_url(self):
    return self._page.url

  async def close(self):
    if self._page:
      self._page.quit()
      self._page = None
    if self._pool:
      self._pool.shutdown(wait=True)
      self._pool = None
    if self._user_data_dir:
      shutil.rmtree(self._user_data_dir, ignore_errors=True)
      self._user_data_dir = None

  # return (title, loaded flag)
  async def title(self) -> typing.Tuple[str, bool]:
    title_els = await self._call_sync_as_async(
      DrissionPage.WebPage.eles,
      self._page,
      'tag:title'
    )
    if title_els:
      return (str(title_els[0].text), True)
    return (None, False)

  async def select_count(self, css_selector):
    xpath = cssselect.GenericTranslator().css_to_xpath(css_selector)
    logger.info("XXX to select_count by " + str(xpath))
    # css selector in drissionpage have execution time problems - use xpath instead.
    #els = self._page.eles("xpath:" + xpath)
    els = await self._call_sync_as_async(
      DrissionPage.WebPage.eles,
      self._page,
      "xpath:" + xpath
    )
    logger.info("XXX from select_count by " + str(xpath))
    return len(els)

  async def get(self, url):
    print("> XXX get", flush=True)
    await self._call_sync_as_async(
      DrissionPage.WebPage.get,
      self._page,
      url,
      proxies={'http': self._proxy, 'https': self._proxy}
    )
    print("< XXX get", flush=True)

  async def click_coords(self, coords):
    print("XXX click_coords: coords = " + str(coords), flush=True)
    await self._call_sync_as_async(
      DrissionPage.WebPage.run_cdp,
      self._page,
      'Input.dispatchMouseEvent',
      type='mousePressed',
      x=coords[0],
      y=coords[1],
      clickCount=1,
      button='left',
    )
    await self._call_sync_as_async(
      DrissionPage.WebPage.run_cdp,
      self._page,
      'Input.dispatchMouseEvent',
      type='mouseReleased',
      x=coords[0],
      y=coords[1],
      clickCount=1,
      button='left',
      #_ignore=DrissionPage.errors.AlertExistsError,
    )

  async def get_user_agent(self):
    return self._page.user_agent

  async def get_dom(self):
    return self._page.html

  async def get_screenshot(self):  # Return screenshot as cv2 image (numpy array)
    buf = await self._call_sync_as_async(
      DrissionPage.WebPage.get_screenshot,
      self._page,
      as_bytes=True,
    )
    image_buf = np.frombuffer(buf, np.uint8)
    image = cv2.imdecode(image_buf, cv2.IMREAD_COLOR)
    return image

  async def save_screenshot(self, image_path):
    image = await self.get_screenshot()
    cv2.imwrite(image_path, image)

  async def set_cookies(self, cookies: list[dict]):
    # convert {"name": "...", "value": "...", ...} to array of http.cookiejar.Cookie
    set_cookies = []
    for c in cookies:
      add_cookie = http.cookiejar.Cookie(
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

    await self._call_sync_as_async(
      DrissionPage.ChromiumPageWaiter.cookies,
      self._page.set,
      set_cookies,
    )

  async def get_cookies(self) -> list[dict]:
    cookies = await self._call_sync_as_async(
      DrissionPage.WebPage.cookies,
      self._page,
      all_domains=True,
      all_info=True,
    )
    # Adapt cookies for standard representation
    for cookie in cookies:
      if 'expires' in cookie:
        cookie['expires'] = int(cookie['expires'])
      if 'size' in cookie:
        del cookie['size']
    print(">>>>> COOKIES: " + str(cookies))
    return cookies

  async def _call_sync_as_async(self, call, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(self._pool, lambda: call(*args, **kwargs))
