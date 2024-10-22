import abc
import sys
import logging
import os
import typing
import random
import datetime
import asyncio
import certifi

# Image processing imports
import cv2
import numpy as np

from flare_bypasser.browser_wrapper import BrowserWrapper

_ACCESS_DENIED_TITLES = [
  # Cloudflare
  'Access denied',
  # Cloudflare http://bitturk.net/ Firefox
  'Attention Required! | Cloudflare'
]

_ACCESS_DENIED_SELECTORS = [
  # Cloudflare
  'div.cf-error-title span.cf-code-label span',
  # Cloudflare http://bitturk.net/ Firefox
  '#cf-error-details div.cf-error-overview h1'
]

_CHALLENGE_TITLES = [
  # Cloudflare
  'Just a moment...',
  # DDoS-GUARD
  'DDoS-Guard'
]

_CHALLENGE_SELECTORS = [
  # Cloudflare
  '#cf-challenge-running', '.ray_id', '.attack-box', '#cf-please-wait', '#challenge-spinner', '#trk_jschal_js',
  # Custom CloudFlare for EbookParadijs, Film-Paleis, MuziekFabriek and Puur-Hollands
  'td.info #js_info',
  # Fairlane / pararius.com
  'div.vc div.text-box h2'
]

_SHORT_TIMEOUT = 1
_REDIRECT_WAIT_TIMEOUT = 5

"""
Request for process, can be extended and some custom fields used in process_command.
"""
class Request(object):
  url: str = None
  proxy: dict = None
  max_timeout: float = 60 # timeout in sec
  cookies: dict = None
  params: dict = None

  def __init__(self, _dict = None):
    if _dict :
      self.__dict__.update(_dict)

"""
Response, can be extended and some custom fields used in process_command.
"""
class Response:
  url: str = None
  cookies: list = None
  user_agent: str = None
  message: str = None
  response = None

  def __init__(self, _dict):
    self.__dict__.update(_dict)

class BaseCommandProcessor(object) :
  @abc.abstractmethod
  async def process_command(self, res: Response, req: Request, driver: BrowserWrapper) -> Response:
    return None

"""
Solver
"""
class Solver(object) :
  _proxy : str = None
  _driver : BrowserWrapper = None
  _command_processors : typing.Dict[str, BaseCommandProcessor] = []
  _screenshot_i : int = 0
  _debug : bool = True

  def __init__(self, proxy : str = None, command_processors : typing.Dict[str, BaseCommandProcessor] = {}) :
    self._proxy = proxy
    self._driver = None
    self._command_processors = dict(command_processors) if command_processors else {}

  async def save_screenshot(self, step_name, image = None, mark_coords = None) :
    if self._debug :
      screenshot_file_without_ext = str(self._screenshot_i) + '_' + step_name

      if image is not None :
        cv2.imwrite(screenshot_file_without_ext + ".png", image)
      else :
        await self._driver.save_screenshot(screenshot_file_without_ext + ".png")

      if mark_coords :
        image = cv2.imread(screenshot_file_without_ext + ".png")
        image = cv2.circle(image, mark_coords, 5, (255, 0, 0), 2)
        cv2.imwrite(screenshot_file_without_ext + "_mark.png", image)

      dom = await self._driver.get_dom()
      with open(screenshot_file_without_ext + '.html', 'w') as fp:
        fp.write(dom)
      self._screenshot_i += 1

      logging.info("Screenshot saved to '" + screenshot_file_without_ext + "'")

  async def solve(self, req: Request) -> Response:
    # do some validations
    if req.url is None:
      raise Exception("Parameter 'url' should be defined.")

    try :
      async with asyncio.timeout(req.max_timeout):
        res = await self._resolve_challenge(req)
        logging.info("Solve result: " + str(res))
    except asyncio.TimeoutError:
      raise Exception("Processing timeout (max_timeout = " + str(req.max_timeout) + ")")
    return res

  async def _resolve_challenge(self, req: Request) -> Response:
    start_time = datetime.datetime.now()
    try:
      try:
        user_data_dir = os.environ.get('USER_DATA', None)
        use_proxy = (req.proxy if req.proxy else self._proxy)
        self._driver = await BrowserWrapper.create(use_proxy)
        logging.info('New instance of webdriver has been created to perform the request (proxy=' +
          str(use_proxy) + '), timeout = ' + str(req.max_timeout))
        return await self._resolve_challenge_impl(req, start_time)

      except Exception as e:
        error_message = 'Error solving the challenge. ' + str(e).replace('\n', '\\n')
        logging.error(error_message)
        raise Exception(error_message)

    finally:
      logging.info('Close webdriver')
      if self._driver is not None:
        await self._driver.close()
        self._driver = None
        logging.debug('A used instance of webdriver has been destroyed')

  @staticmethod
  def _check_timeout(req: Request, start_time: datetime.datetime, step_name: str):
    if req.max_timeout is not None :
      now = datetime.datetime.now()
      wait_time_sec = (now - start_time).total_seconds()
      if wait_time_sec > req.max_timeout :
        raise FunctionTimedOut("Timed out on " + step_name)

  async def _check_challenge(self) :
    driver = self._driver
    page_title = await driver.title()

    # find access denied titles
    for title in _ACCESS_DENIED_TITLES :
      if title == page_title:
        raise Exception('Cloudflare has blocked this request. '
          'Probably your IP is banned for this site, check in your web browser.')

    # find access denied selectors
    for selector in _ACCESS_DENIED_SELECTORS:
      if (await driver.select_count(selector) > 0) :
        raise Exception('Cloudflare has blocked this request. '
          'Probably your IP is banned for this site, check in your web browser.')

    # find challenge by title
    challenge_found = False
    for title in _CHALLENGE_TITLES:
      if title.lower() == page_title.lower():
        challenge_found = True
        logging.info("Challenge detected. Title found: " + page_title)
        break

    if not challenge_found:
      # find challenge by selectors
      for selector in _CHALLENGE_SELECTORS:
        if (await driver.select_count(selector)) > 0:
          challenge_found = True
          logging.info("Challenge detected. Selector found: " + selector)
          break

    return challenge_found

  async def _resolve_challenge_impl(self, req: Request, start_time : datetime.datetime) -> Response:
    res = Response({})

    # navigate to the page
    logging.debug(f'Navigating to... {req.url}')
    await self._driver.get(req.url)

    logging.debug(f'To make screenshot')
    await self.save_screenshot('evil_logic')

    # set cookies if required
    if req.cookies is not None and len(req.cookies) > 0:
      logging.debug(f'Setting cookies...')
      await self._driver.set_cookies(cookies)
      await self._driver.get(req.url)

    # find challenge by title
    challenge_found = await self._check_challenge()

    await self.save_screenshot('after_challenge_check')

    if not challenge_found :
      await self.save_screenshot('no_challenge_found')
      logging.info("Challenge not detected!")
      res.message = "Challenge not detected!"
    else : # first challenge found
      logging.info("Challenge detected, to solve it")

      attempt = 0

      while True:
        Solver._check_timeout(req, start_time, "challenge loading wait")
        logging.info("Challenge step #" + str(attempt))

        await self.save_screenshot('attempt')

        # check that challenge present (wait when it will disappear after click)
        challenge_found = await self._check_challenge()
        if not challenge_found :
          logging.info("Challenge disappeared on step #" + str(attempt))
          break

        # check that need to click,
        # get screenshot of full page (all elements is in shadowroot)
        # clicking can be required few times.
        page_image = await self._driver.get_screenshot()
        click_coord = Solver._get_flare_click_point(page_image)
        if click_coord :
          logging.info("Verify checkbot found, click coordinates: " + str(click_coord))
          await self.save_screenshot('to_verify_click', image = page_image, mark_coords = click_coord)
          # recheck that challenge present - we can be already redirected and
          # need to exclude click on result page
          challenge_found = await self._check_challenge()
          if not challenge_found :
            logging.info("Challenge disappeared on step #" + str(attempt))
            break

          logging.info("Click challenge by coords: " + str(click_coord[0]) + ", " + str(click_coord[1]))
          await self._driver.click_coords(click_coord)
          await asyncio.sleep(1)

          res.message = "Challenge solved!" #< challenge found and solved once (as minimum)
          await self.save_screenshot('after_verify_click')

        attempt = attempt + 1
        await asyncio.sleep(_SHORT_TIMEOUT)

      logging.info("Challenge solving finished")
      await self.save_screenshot('solving_finish')

    res.url = await self._driver.current_url()
    res.cookies = await self._driver.get_cookies()
    if req.cmd == "request_cookies" :
      pass
    elif req.cmd == "request_page" :
      res.response = await self._driver.get_dom()
    elif req.cmd in self._command_processors :
      # User specific command
      res = await self._command_processors[req.cmd].process_command(res, req, self._driver)
    else :
      raise Exception("Unknown command : " + req.cmd)

    logging.info("Cookies got")
    # TODO: fill res.user_agent

    await self.save_screenshot('finish')
    logging.info('Solving finished')

    return res

  @staticmethod
  def _get_flare_click_point(image) :
    image_height, image_width, _ = image.shape
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, mask = cv2.threshold(gray_image, 240, 255, 0)
    #< we can use 230 + closing by filter for more accuracy, but it require much CPU.

    #cv2.imwrite('masked_image.png', mask) # Check that mask contains outer rect contour if colors will be changed
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rect_contours = []
    for c in contours :
      x, y, w, h = cv2.boundingRect(c)

      # ignore small rectangles
      if w < 6 or h < 6 :
        continue

      sq = w * h / (image_height * image_width)

      # ignore very big rectangles
      if sq > 0.5 :
        continue

      # calculate area difference
      rect_area = w * h
      contour_area = cv2.contourArea(c)
      diff_area = abs(rect_area - contour_area)
      # eval iou with (with undestanding that contour_area inside rect_area)
      iou = contour_area / rect_area

      # get minimal contour (usualy we have here 3 contours
      if iou > 0.8:
        rect_contours.append((w * h, c))

    # Here 2 rect contours, each can be present as one or 2 contours
    """
    debug_image = image.copy()
    for rc in rect_contours :
      debug_image = cv2.drawContours(debug_image, [rc[1]], -1, (255, 0, 0), 1)
    cv2.imwrite('debug_rect_contours.png', debug_image)
    """

    rect_contours = sorted(rect_contours, key = lambda c_pair: c_pair[0])

    # pack low distance contours (one rect can be present as 2 contours : inner, outer)
    # remove buggest contour
    res_rect_contours = []
    prev_c_pair = None

    for c_pair in rect_contours : # go from lowest to biggest
      if prev_c_pair is None or abs(c_pair[0] - prev_c_pair[0]) / c_pair[0] > 0.5 :
        res_rect_contours.append(c_pair)
        prev_c_pair = c_pair

    rect_contours = res_rect_contours
    # rect contours sorted by area ascending

    """
    debug_image = image.copy()
    for rc in rect_contours :
      print("C: " + str(rc[0]))
      debug_image = cv2.drawContours(debug_image, [rc[1]], -1, (255, 0, 0), 1)
    cv2.imwrite('debug_packed_rect_contours.png', debug_image)
    """

    # Now we should find two rect contours (one inside other) with ratio 1-5%, (now I see : 0.0213)
    if len(rect_contours) > 1:
      for area1_index in range(len(rect_contours)) :
        area1 = rect_contours[area1_index][0]
        for check_c in rect_contours[area1_index + 1:] :
          area2 = check_c[0]
          area_ratio = area1 / area2
          # Check area ratio and that area1 inside area2
          if area_ratio > 0.01 and area_ratio < 0.05 :
            # Found !
            c1_x, c1_y, c1_w, c1_h = cv2.boundingRect(rect_contours[area1_index][1])
            c2_x, c2_y, c2_w, c2_h = cv2.boundingRect(check_c[1])
            if c1_x >= c2_x and c1_x <= c2_x + c2_w and c1_y >= c2_y and c1_y <= c2_y + c2_h :
              #print("A1: x = " + str(x) + ", y = " + str(y) + ", w = " + str(w) + ", h = " + str(h))
              x2, y2, w2, h2 = cv2.boundingRect(check_c[1])
              #print("A2: x = " + str(x2) + ", y = " + str(y2) + ", w = " + str(w2) + ", h = " + str(h2))
              return [random.randint(c1_x + 2, c1_x + c1_w - 2), random.randint(c1_y + 2, c1_y + c1_h - 2)]

    return None

# fix ssl certificates for compiled binaries
# https://github.com/pyinstaller/pyinstaller/issues/7229
# https://stackoverflow.com/questions/55736855/how-to-change-the-cafile-argument-in-the-ssl-module-in-python3
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

if __name__ == '__main__':
  sys.stdout.reconfigure(encoding = "utf-8")
  logging.basicConfig(format = '%(asctime)s [%(name)s] [%(levelname)s] : %(message)s',
    handlers = [logging.StreamHandler(sys.stdout)],
    level = logging.INFO)

  req = Request()
  req.url = 'https://knopka.ashoo.id'

  solver = Solver()
  res = solver.solve(req)
