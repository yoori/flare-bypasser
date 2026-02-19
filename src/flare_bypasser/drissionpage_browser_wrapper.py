import asyncio
import shutil
import typing

import cv2
import numpy as np
from DrissionPage import ChromiumOptions, ChromiumPage

from .browser_wrapper import BrowserWrapper
from .browser_wrapper_utils import start_xvfb_display, build_browser_args, make_user_data_dir

class DrissionPageBrowserWrapper(BrowserWrapper):
  """
  DrissionPage based browser wrapper.
  """

  _browser = None
  _page = None
  _user_data_dir: str = None

  def __init__(self, browser, page, user_data_dir: str = None):
    self._browser = browser
    self._page = page
    self._user_data_dir = user_data_dir

  def __del__(self):
    if self._user_data_dir:
      shutil.rmtree(self._user_data_dir, ignore_errors=True)

  @staticmethod
  async def create(proxy: str = None, disable_gpu: bool = False, headless: bool = False):
    user_data_dir = make_user_data_dir()
    start_xvfb_display()


    browser_args = build_browser_args(
      user_data_dir=user_data_dir,
      proxy=proxy,
      disable_gpu=disable_gpu,
      headless=headless,
    )

    options = ChromiumOptions()
    for arg in browser_args:
      options.set_argument(arg)

    def _create_page():
      return ChromiumPage(addr_or_opts=options)

    try:
      page = await asyncio.to_thread(_create_page)
      return DrissionPageBrowserWrapper(page, page, user_data_dir=user_data_dir)
    except BaseException:
      shutil.rmtree(user_data_dir, ignore_errors=True)
      raise

  def get_driver(self):
    return self._page

  async def _run(self, fun, *args, **kwargs):
    return await asyncio.to_thread(fun, *args, **kwargs)

  async def get_outputs(self):
    return None

  async def current_url(self):
    return await self._run(lambda: self._page.url)

  async def close(self):
    page = self._page
    self._page = None
    self._browser = None
    if page is not None:
      await self._run(page.quit)
    if self._user_data_dir:
      shutil.rmtree(self._user_data_dir, ignore_errors=True)
      self._user_data_dir = None

  async def title(self) -> typing.Tuple[str, bool]:
    try:
      page_title = await self._run(lambda: self._page.title)
      return (page_title, True)
    except BaseException:
      return (None, False)

  async def select_count(self, css_selector):
    try:
      elements = await self._run(self._page.eles, f'css:{css_selector}')
      return len(elements)
    except BaseException:
      return 0

  async def get(self, url):
    await self._run(self._page.get, url)

  async def click_coords(self, coords):
    x, y = coords

    def _click():
      actions = self._page.actions
      actions.move_to((int(x), int(y)))
      actions.click()

    await self._run(_click)

  async def get_user_agent(self):
    return await self._run(self._page.run_js, "return navigator.userAgent")

  async def get_dom(self):
    return await self._run(lambda: self._page.html or "")

  async def get_screenshot(self):
    def _shot_bytes():
      return self._page.get_screenshot(as_bytes=True)

    raw = await self._run(_shot_bytes)
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)

  async def save_screenshot(self, image_path):
    await self._run(self._page.get_screenshot, path=image_path)

  async def set_cookies(self, cookies: list[dict]):
    for cookie in cookies:
      await self._run(self._page.set.cookies, cookie)

  async def get_cookies(self) -> list[dict]:
    cookies = await self._run(self._page.cookies, as_dict=False)
    result = []
    for cookie in cookies:
      if isinstance(cookie, dict):
        result.append(cookie)
      else:
        result.append({
          "name": getattr(cookie, "name", None),
          "value": getattr(cookie, "value", None),
          "port": getattr(cookie, "port", None),
          "domain": getattr(cookie, "domain", None),
          "path": getattr(cookie, "path", None),
          "secure": getattr(cookie, "secure", False),
        })
    return result
