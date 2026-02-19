import abc
import importlib
import typing


class BrowserWrapper(abc.ABC):
  @staticmethod
  @abc.abstractmethod
  async def create(proxy: bool = None, disable_gpu: bool = False, headless: bool = False):
    raise NotImplementedError()

  @abc.abstractmethod
  def get_driver(self):
    raise NotImplementedError()

  @abc.abstractmethod
  async def get_outputs(self):
    raise NotImplementedError()

  @abc.abstractmethod
  async def current_url(self):
    raise NotImplementedError()

  @abc.abstractmethod
  async def close(self):
    raise NotImplementedError()

  @abc.abstractmethod
  async def title(self) -> typing.Tuple[str, bool]:
    raise NotImplementedError()

  @abc.abstractmethod
  async def select_count(self, css_selector):
    raise NotImplementedError()

  @abc.abstractmethod
  async def get(self, url):
    raise NotImplementedError()

  @abc.abstractmethod
  async def click_coords(self, coords):
    raise NotImplementedError()

  @abc.abstractmethod
  async def get_user_agent(self):
    raise NotImplementedError()

  @abc.abstractmethod
  async def get_dom(self):
    raise NotImplementedError()

  @abc.abstractmethod
  async def get_screenshot(self):
    raise NotImplementedError()

  @abc.abstractmethod
  async def save_screenshot(self, image_path):
    raise NotImplementedError()

  @abc.abstractmethod
  async def set_cookies(self, cookies: list[dict]):
    raise NotImplementedError()

  @abc.abstractmethod
  async def get_cookies(self) -> list[dict]:
    raise NotImplementedError()
