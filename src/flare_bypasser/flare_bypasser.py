import abc
import sys
import logging
import os
import typing
import copy
import random
import datetime
import asyncio
import certifi
import contextlib
import html
import urllib

# Image processing imports
import cv2

from .browser_wrapper import BrowserWrapper
from .proxy_controller import ProxyController

USER_AGENT = None

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
  max_timeout: float = 60  # timeout in sec
  cookies: dict = None
  params: dict = None

  def __init__(self, _dict=None):
    if _dict:
      self.__dict__.update(_dict)


class Response:
  url: str = None
  cookies: list = None
  user_agent: str = None
  message: str = None
  response = None

  def __init__(self, _dict):
    self.__dict__.update(_dict)


class BaseCommandProcessor(object):
  # preprocess url before solve (for example: can replace url with page content for POST request processing)
  @abc.abstractmethod
  async def preprocess_command(self, req: Request, driver: BrowserWrapper) -> Request:
    return req

  @abc.abstractmethod
  async def process_command(
    self, res: Response, req: Request, driver: BrowserWrapper
  ) -> Response:
    return res


"""
Standard commands implementations.
"""


class GetCookiesCommandProcessor(BaseCommandProcessor):
  pass  # Use all default process implementations.


class GetPageCommandProcessor(BaseCommandProcessor):
  async def process_command(
    self, res: Response, req: Request, driver: BrowserWrapper
  ) -> Response:
    res.response = await driver.get_dom()
    return res


class PostCommandProcessor(BaseCommandProcessor):
  async def preprocess_command(self, req: Request, driver: BrowserWrapper) -> Request:
    # prepare page with form for emulate POST.
    if req.params is None or 'postData' not in req.params:
      raise Exception("postData should be defined for POST.")

    postData = req.params['postData']
    post_form = f'<form id="postForm" action="{req.url}" method="POST">'
    query_string = postData if postData[0] != '?' else postData[1:]
    pairs = query_string.split('&')
    for pair in pairs:
      parts = pair.split('=')
      try:
        name = urllib.parse.unquote(parts[0])
      except Exception:
        name = parts[0]
      if name == 'submit':
        continue
      try:
        value = urllib.parse.unquote(parts[1])
      except Exception:
        value = parts[1]
      post_form += f"""<input type="text" name="{html.escape(urllib.parse.quote(name))}"
        value="{html.escape(urllib.parse.quote(value))}"><br>"""
    post_form += '</form>'
    html_content = f"""
      <!DOCTYPE html>
      <html>
      <body>
          {post_form}
          <script>document.getElementById('postForm').submit();</script>
      </body>
      </html>"""

    req.url = "data:text/html;charset=utf-8," + html_content
    return req

  async def process_command(
    self, res: Response, req: Request, driver: BrowserWrapper
  ) -> Response:
    res.response = await driver.get_dom()
    return res


class Solver(object):
  """
  Solver
  """
  _proxy: str = None
  _driver: BrowserWrapper = None
  _command_processors: typing.Dict[str, BaseCommandProcessor] = []
  _proxy_controller: ProxyController = None
  _disable_gpu: bool = False
  _screenshot_i: int = 0
  _debug: bool = True

  class Exception(Exception):
    step = None

    def __init__(self, message: str, step: str = None):
      super().__init__(message)
      self.step = step

  def __init__(
    self, proxy: str = None, command_processors: typing.Dict[str, BaseCommandProcessor] = {},
    proxy_controller=None,
    disable_gpu=False
  ):
    self._proxy = proxy
    self._driver = None
    self._proxy_controller = proxy_controller
    self._command_processors = dict(command_processors) if command_processors else {}
    # init standard commands
    get_cookies_command_processor = GetCookiesCommandProcessor()
    self._command_processors['get_cookies'] = get_cookies_command_processor
    self._command_processors['request.get_cookies'] = get_cookies_command_processor
    get_page_command_processor = GetPageCommandProcessor()
    self._command_processors['get_page'] = get_page_command_processor
    self._command_processors['request.get'] = get_page_command_processor
    make_post_command_processor = PostCommandProcessor()
    self._command_processors['make_post'] = make_post_command_processor
    self._command_processors['request.post'] = make_post_command_processor
    self._disable_gpu = disable_gpu

  async def save_screenshot(self, step_name, image=None, mark_coords=None):
    if self._debug:
      screenshot_file_without_ext = str(self._screenshot_i) + '_' + step_name

      if image is not None:
        cv2.imwrite(screenshot_file_without_ext + ".png", image)
      else:
        await self._driver.save_screenshot(screenshot_file_without_ext + ".png")

      if mark_coords:
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

    try:
      res = await asyncio.wait_for(self._resolve_challenge(req), req.max_timeout)
      logging.info("Solve result: " + str(res))
    except asyncio.TimeoutError:
      raise Exception("Processing timeout (max_timeout=" + str(req.max_timeout) + ")")
    return res

  async def _resolve_challenge(self, req: Request) -> Response:
    start_time: datetime.datetime = datetime.datetime.now()
    step = 'start'
    try:
      use_proxy: str = (req.proxy if req.proxy else self._proxy)
      proxy_holder = None

      step = 'proxy init'
      if use_proxy is not None and '@' in use_proxy:
        if not self._proxy_controller:
          raise Solver.Exception("For use proxy with authorization you should pass proxy_controller into c-tor")
        proxy_holder = self._proxy_controller.get_proxy(use_proxy)
        use_proxy = "socks5://127.0.0.1:" + str(proxy_holder.local_port())
      else:
        proxy_holder = contextlib.nullcontext()

      with proxy_holder:
        try:
          step = 'browser init'
          self._driver: BrowserWrapper = await BrowserWrapper.create(
            use_proxy, disable_gpu = self._disable_gpu
          )
          logging.info(
            'New instance of webdriver has been created to perform the request (proxy=' +
            str(use_proxy) + '), timeout=' + str(req.max_timeout))
          return await self._resolve_challenge_impl(req, start_time)
        finally:
          logging.info('Close webdriver')
          if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logging.debug('A used instance of webdriver has been destroyed')
    except Solver.Exception as e:
      error_message = (
        "Error solving the challenge. On platform " + str(sys.platform) +
        " at step '" + str(e.step) + "': " +
        str(e).replace('\n', '\\n')
      )
      logging.error(error_message)
      raise Solver.Exception(error_message, step=e.step)
    except Exception as e:
      error_message = (
        "Error solving the challenge. On platform " + str(sys.platform) +
        " at step '" + step + "': " +
        str(e).replace('\n', '\\n')
      )
      logging.error(error_message)
      raise Solver.Exception(error_message)

  async def _check_challenge(self):
    driver = self._driver
    page_title = await driver.title()

    # find access denied titles
    for title in _ACCESS_DENIED_TITLES:
      if title == page_title:
        raise Exception(
          'Cloudflare has blocked this request. '
          'Probably your IP is banned for this site, check in your web browser.'
        )

    # find access denied selectors
    for selector in _ACCESS_DENIED_SELECTORS:
      if (await driver.select_count(selector) > 0):
        raise Exception(
          'Cloudflare has blocked this request. '
          'Probably your IP is banned for this site, check in your web browser.'
        )

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

  async def _challenge_wait_and_click_loop(self):
    attempt = 0

    while True:
      logging.info("Challenge step #" + str(attempt))
      await self.save_screenshot('attempt')

      # check that challenge present (wait when it will disappear after click)
      challenge_found = await self._check_challenge()
      if not challenge_found:
        logging.info("Challenge disappeared on step #" + str(attempt))
        break

      # check that need to click,
      # get screenshot of full page (all elements is in shadowroot)
      # clicking can be required few times.
      page_image = await self._driver.get_screenshot()
      click_coord = Solver._get_flare_click_point(page_image)
      if click_coord:
        logging.info("Verify checkbot found, click coordinates: " + str(click_coord))
        await self.save_screenshot('to_verify_click', image=page_image, mark_coords=click_coord)
        # recheck that challenge present - we can be already redirected and
        # need to exclude click on result page
        challenge_found = await self._check_challenge()
        if not challenge_found:
          logging.info("Challenge disappeared on step #" + str(attempt))
          break

        logging.info("Click challenge by coords: " + str(click_coord[0]) + ", " + str(click_coord[1]))
        await self._driver.click_coords(click_coord)
        await asyncio.sleep(1)

        await self.save_screenshot('after_verify_click')

      attempt = attempt + 1
      await asyncio.sleep(_SHORT_TIMEOUT)

  async def _resolve_challenge_impl(self, req: Request, start_time: datetime.datetime) -> Response:
    step = 'solving'
    try:
      res = Response({})

      if req.cmd not in self._command_processors:
        raise Exception("Unknown command: " + req.cmd)

      command_processor = self._command_processors[req.cmd]
      assert command_processor

      step = 'command preprocessing'
      preprocess_res = await command_processor.preprocess_command(copy.deepcopy(req), self._driver)

      step = 'parse command preprocessing result'
      open_url = True
      # < preprocess_command can say, that page opening isn't required (it opened it already).
      if (
        (isinstance(preprocess_res, list) or isinstance(preprocess_res, tuple)) and
        len(preprocess_res) > 1
      ):
        preprocessed_req = preprocess_res[0]
        open_url = preprocess_res[1]
      else:
        preprocessed_req = preprocess_res

      step = 'navigate to url'
      if open_url:
        # navigate to the page
        logging.debug(f'Navigating to... {req.url}')
        await self._driver.get(preprocessed_req.url)

      logging.debug('To make screenshot')
      await self.save_screenshot('evil_logic')

      step = 'set cookies'

      # set cookies if required
      if preprocessed_req.cookies :
        logging.debug('Setting cookies...')
        await self._driver.set_cookies(preprocessed_req.cookies)
        await self._driver.get(preprocessed_req.url)

      step = 'check challenge'
      # find challenge by title
      challenge_found = await self._check_challenge()

      await self.save_screenshot('after_challenge_check')

      if not challenge_found:
        await self.save_screenshot('no_challenge_found')
        logging.info("Challenge not detected!")
        res.message = "Challenge not detected!"
      else:  # first challenge found
        step = 'solve challenge'
        logging.info("Challenge detected, to solve it")

        await self._challenge_wait_and_click_loop()
        res.message = "Challenge solved!"  # expect exception if challenge isn't solved

        logging.info("Challenge solving finished")
        await self.save_screenshot('solving_finish')

      step = 'get cookies'
      res.url = await self._driver.current_url()
      res.cookies = await self._driver.get_cookies()
      logging.info("Cookies got")
      global USER_AGENT
      if USER_AGENT is None:
        step = 'get user-agent'
        USER_AGENT = await self._driver.get_user_agent()
      res.user_agent = USER_AGENT

      step = 'command processing'
      res = await command_processor.process_command(res, req, self._driver)

      await self.save_screenshot('finish')
      logging.info('Solving finished')

      return res
    except Exception as e:
      raise Solver.Exception(str(e), step=step)

  @staticmethod
  def _get_flare_rect_contours_(image):
    image_height, image_width, _ = image.shape
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, mask = cv2.threshold(gray_image, 240, 255, 0)
    # < we can use 230 + closing by filter for more accuracy, but it require much CPU.

    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rect_contours = []
    for c in contours:
      x, y, w, h = cv2.boundingRect(c)

      # ignore small rectangles
      if w < 6 or h < 6:
        continue

      sq = w * h / (image_height * image_width)

      # ignore very big rectangles
      if sq > 0.5:
        continue

      # calculate area difference
      rect_area = w * h
      contour_area = cv2.contourArea(c)
      # eval iou with (with undestanding that contour_area inside rect_area)
      iou = contour_area / rect_area

      # get minimal contour (usualy we have here 3 contours
      if iou > 0.8:
        rect_contours.append((w * h, c))

    # Here 2 rect contours, each can be present as one or 2 contours
    """
    debug_image=image.copy()
    for rc in rect_contours:
      debug_image=cv2.drawContours(debug_image, [rc[1]], -1, (255, 0, 0), 1)
    cv2.imwrite('debug_rect_contours.png', debug_image)
    """

    return rect_contours

  @staticmethod
  def _get_flare_click_point(image):
    rect_contours = Solver._get_flare_rect_contours_(image)

    rect_contours = sorted(rect_contours, key=lambda c_pair: c_pair[0])

    # pack low distance contours (one rect can be present as 2 contours: inner, outer)
    # remove buggest contour
    res_rect_contours = []
    prev_c_pair = None

    for c_pair in rect_contours:  # go from lowest to biggest
      if prev_c_pair is None or abs(c_pair[0] - prev_c_pair[0]) / c_pair[0] > 0.5:
        res_rect_contours.append(c_pair)
        prev_c_pair = c_pair

    rect_contours = res_rect_contours
    # rect contours sorted by area ascending

    """
    debug_image=image.copy()
    for rc in rect_contours:
      print("C: " + str(rc[0]))
      debug_image=cv2.drawContours(debug_image, [rc[1]], -1, (255, 0, 0), 1)
    cv2.imwrite('debug_packed_rect_contours.png', debug_image)
    """

    # Now we should find two rect contours (one inside other) with ratio 1-5%, (now I see: 0.0213).
    if len(rect_contours) > 1:
      for area1_index in range(len(rect_contours)):
        area1 = rect_contours[area1_index][0]
        for check_c in rect_contours[area1_index + 1:]:
          area2 = check_c[0]
          area_ratio = area1 / area2
          # Check area ratio and that area1 inside area2.
          if area_ratio > 0.01 and area_ratio < 0.05:
            # Checkbox found.
            c1_x, c1_y, c1_w, c1_h = cv2.boundingRect(rect_contours[area1_index][1])
            c2_x, c2_y, c2_w, c2_h = cv2.boundingRect(check_c[1])
            if c1_x >= c2_x and c1_x <= c2_x + c2_w and c1_y >= c2_y and c1_y <= c2_y + c2_h:
              x2, y2, w2, h2 = cv2.boundingRect(check_c[1])
              return [random.randint(c1_x + 2, c1_x + c1_w - 2), random.randint(c1_y + 2, c1_y + c1_h - 2)]

    return None


# fix ssl certificates for compiled binaries
# https://github.com/pyinstaller/pyinstaller/issues/7229
# https://stackoverflow.com/questions/55736855/how-to-change-the-cafile-argument-in-the-ssl-module-in-python3
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

if __name__ == '__main__':
  sys.stdout.reconfigure(encoding="utf-8")
  logging.basicConfig(
    format='%(asctime)s [%(name)s] [%(levelname)s]: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO)

  req = Request()
  req.url = 'https://knopka.ashoo.id'

  solver = Solver()
  res = solver.solve(req)
