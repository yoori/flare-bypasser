import sys
import logging
import time
import numpy as np
import argparse
import cv2
from pyvirtualdisplay import Display

from DrissionPage import ChromiumPage, ChromiumOptions, WebPage

browser_path = "/usr/bin/chrome"

logger = logging.getLogger(__name__)


class CloudflareBypasser:
  def __init__(self, driver: ChromiumPage, max_retries=-1, log=True):
    self.driver = driver
    self.max_retries = max_retries
    self.log = log

  def search_recursively_shadow_root_with_iframe(self, ele):
    if ele.shadow_root:
      if ele.shadow_root.child().tag == "iframe":
        return ele.shadow_root.child()
    else:
      for child in ele.children():
        result = self.search_recursively_shadow_root_with_iframe(child)
        if result:
          return result
    return None

  def search_recursively_shadow_root_with_cf_input(self, ele):
    if ele.shadow_root:
      if ele.shadow_root.ele("tag:input"):
        return ele.shadow_root.ele("tag:input")
    else:
      for child in ele.children():
        result = self.search_recursively_shadow_root_with_cf_input(child)
        if result:
          return result
    return None

  def locate_cf_button(self):
    button = None
    eles = self.driver.eles("tag:input")
    for ele in eles:
      if "name" in ele.attrs.keys() and "type" in ele.attrs.keys():
        if "turnstile" in ele.attrs["name"] and ele.attrs["type"] == "hidden":
          body = ele.parent().shadow_root.child()("tag:body")
          button = body.shadow_root("tag:input")
          break

    if button:
      return button
    else:
      # If the button is not found, search it recursively
      self.log_message("Basic search failed. Searching for button recursively.")
      ele = self.driver.ele("tag:body")
      iframe = self.search_recursively_shadow_root_with_iframe(ele)
      if iframe:
        button = self.search_recursively_shadow_root_with_cf_input(iframe("tag:body"))
      else:
        self.log_message("Iframe not found. Button search failed.")
      return button

  def log_message(self, message):
    print(message)

  def click_verification_button(self):
    try:
      button = self.locate_cf_button()
      if button:
        self.log_message("Verification button found. Attempting to click.")
        button.click()
      else:
        self.log_message("Verification button not found.")

    except Exception as e:
      logger.exception(f"Error clicking verification button: {e}")

  def is_bypassed(self):
    try:
      title = self.driver.title.lower()
      return "just a moment" not in title
    except Exception as e:
      self.log_message(f"Error checking page title: {e}")
      return False

  def bypass(self):

    try_count = 0

    while not self.is_bypassed():
      if 0 < self.max_retries + 1 <= try_count:
        self.log_message("Exceeded maximum retries. Bypass failed.")
        break

      self.log_message(f"Attempt {try_count + 1}: Verification page detected. Trying to bypass...")
      self.click_verification_button()

      try_count += 1
      time.sleep(2)

    if self.is_bypassed():
      self.log_message("Bypass successful.")
    else:
      self.log_message("Bypass failed.")


def bypass_cloudflare(url: str, retries: int, log: bool, proxy: str = None) -> ChromiumPage:
    # Start Xvfb for Docker
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    options = ChromiumOptions()
    options.set_argument("--auto-open-devtools-for-tabs", "true")
    options.set_argument("--remote-debugging-port=9222")
    options.set_argument("--no-sandbox")  # Necessary for Docker
    options.set_argument("--disable-gpu")  # Optional, helps in some cases
    options.set_argument('--disable-software-rasterizer')
    options.set_argument('--ignore-certificate-errors')
    options.set_argument('--ignore-urlfetcher-cert-requests')
    options.set_argument('--user-data-dir', '/tmp/XXXX')
    if proxy:
      options.set_argument('--proxy-server', proxy)
    options.set_paths(browser_path=browser_path).headless(False)

    driver = WebPage(chromium_options=options)
    try:
      driver.get(url)
      cf_bypasser = CloudflareBypasser(driver, retries, log)
      cf_bypasser.bypass()
      buf = driver.get_screenshot(as_bytes=True)
      image_buf = np.frombuffer(buf, np.uint8)
      image = cv2.imdecode(image_buf, cv2.IMREAD_COLOR)
      cv2.imwrite('/tmp/res2.png', image)
      cookies = driver.cookies(as_dict=True)
      print("COOKIES: " + str(cookies))
      els = driver.eles('css selector:div.cf-error-title span.cf-code-label span')
      print("ELS: " + str(els))
      return driver
    except Exception as e:
      driver.quit()
      display.stop()  # Stop Xvfb
      raise e


def main():
  logging.basicConfig(
    format='%(asctime)s [%(name)s] [%(levelname)s]: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO
  )
  parser = argparse.ArgumentParser(description='DrissionPage based solver util.')
  parser.add_argument("-r", "--retries", type=int, default=3)
  parser.add_argument("-p", "--proxy", type=str, default=None)
  parser.add_argument("-s", "--site", type=str, default='https://mg.ashoo.gold/')
  args = parser.parse_args()
  logger.info("Start")
  bypass_cloudflare(args.site, retries=args.retries, proxy=args.proxy, log=True)


main()
