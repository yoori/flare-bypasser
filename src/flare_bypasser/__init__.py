import importlib.metadata

try:
  import cv2  # noqa: F401
except ImportError as ex:
  raise ImportError(
    "Missing required dependency 'cv2'. Install OpenCV package: pip install opencv-python"
  ) from ex

from .flare_bypasser import Request, Response, Solver, BaseCommandProcessor
from .browser_wrapper import BrowserWrapper
from .proxy_controller import ProxyController
from .flare_bypass_server import server, server_run
from .async_client import AsyncClient

try:
  __version__ = importlib.metadata.version(__package__ or __name__)
except importlib.metadata.PackageNotFoundError:
  __version__ = '0.0.0'

__all__ = [
  'Request', 'Response', 'Solver', 'BrowserWrapper', 'BaseCommandProcessor',
  'ProxyController', 'server', 'server_run',
  'AsyncClient'
]
