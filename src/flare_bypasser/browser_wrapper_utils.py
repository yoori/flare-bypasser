import os
import sys
import uuid

XVFB_DISPLAY = None


def start_xvfb_display():
  if sys.platform != 'win32':
    global XVFB_DISPLAY
    if XVFB_DISPLAY is None:
      from xvfbwrapper import Xvfb
      XVFB_DISPLAY = Xvfb()
      XVFB_DISPLAY.start()


def build_browser_args(
  user_data_dir: str,
  proxy: str = None,
  disable_gpu: bool = False,
  headless: bool = False,
):
  browser_args = [
    "--disable-features=PrivacySandboxSettings4",
  ]
  if proxy:
    browser_args.append("--proxy-server=" + proxy)
  if disable_gpu:
    browser_args += [
      "--disable-gpu",
      # "--disable-software-rasterizer",
    ]
  if sys.platform == 'win32' or headless:
    browser_args += ["--headless"]

  browser_args += ["--user-data-dir=" + user_data_dir]
  return browser_args


def make_user_data_dir():
  # < Each created chrome should be isolated.
  return os.path.join('/tmp', str(uuid.uuid4()))
