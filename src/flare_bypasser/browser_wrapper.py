import abc
import importlib
import typing


class BrowserWrapper(abc.ABC):
  @staticmethod
  @abc.abstractmethod
  async def create(proxy: bool = None, disable_gpu: bool = False, headless: bool = False):
    raise NotImplementedError()

  @staticmethod
  def resolve_wrapper_class(wrapper_type: str):
    if wrapper_type == 'zendriver':
      module_name = 'flare_bypasser.zendriver_browser_wrapper'
      class_name = 'ZenDriverBrowserWrapper'
    elif wrapper_type == 'nodriver':
      module_name = 'flare_bypasser.nodriver_browser_wrapper'
      class_name = 'NoDriverBrowserWrapper'
    else:
      if ':' not in wrapper_type:
        raise ValueError(
          "Invalid wrapper type. Use 'zendriver', 'nodriver' or 'module.path:ClassName'."
        )
      module_name, class_name = wrapper_type.split(':', 1)

    module = importlib.import_module(module_name)
    wrapper_class = getattr(module, class_name)
    if not issubclass(wrapper_class, BrowserWrapper):
      raise TypeError(
        f"Class '{class_name}' from '{module_name}' is not a BrowserWrapper subclass."
      )
    return wrapper_class

  @staticmethod
  async def create_by_type(
    wrapper_type: str,
    proxy: str = None,
    disable_gpu: bool = False,
    headless: bool = False,
  ):
    wrapper_class = BrowserWrapper.resolve_wrapper_class(wrapper_type)
    return await wrapper_class.create(
      proxy=proxy,
      disable_gpu=disable_gpu,
      headless=headless,
    )

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
