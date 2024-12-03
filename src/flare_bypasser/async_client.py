import typing
import copy
import json
import re
import httpx


"""
AsyncClient
httpx.AsyncClient wrapper for transient manipulations with sites and
transparent cloud flare protection bypassing.
"""


class AsyncClient(object):
  _solver_url = None
  _http_client: httpx.AsyncClient = None
  _user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  # < base user-agent that will be used before first challenge solve,
  # after it will be replaced with solver actual user-agent
  _max_tries = 2

  class Exception(Exception):
    pass

  def __init__(self, solver_url):
    self._solver_url = solver_url

  async def __aenter__(self):
    self._http_client = httpx.AsyncClient(http2 = True)  # < Cleanup previously opened connections
    await self._http_client.__aenter__()
    return self

  async def __aexit__(self, *args):
    if self._http_client:
      ret = await self._http_client.__aexit__(*args)
      self._http_client = None
      return ret
    return False

  @property
  def http_client(self) -> httpx.AsyncClient:
    return self._http_client

  async def get(self, url, **kwargs) -> httpx.Response:
    return await self._request(httpx.AsyncClient.get, url, **kwargs)

  async def post(self, url, solve_url = None, **kwargs) -> httpx.Response:
    return await self._request(httpx.AsyncClient.post, url, solve_url = solve_url, **kwargs)

  async def _request(self, run_method, url, solve_url = None, headers = {}, **kwargs) -> httpx.Response:
    if not self._http_client:
      self._http_client = httpx.AsyncClient(http2 = True)

    for try_i in range(self._max_tries):
      # request web page
      send_headers = copy.copy(headers)
      send_headers['user-agent'] = self._user_agent
      send_headers['cache-control'] = 'no-cache'  # < Disable cache, because httpx can return cached captcha response.
      response = await run_method(self._http_client, url, headers = send_headers, **kwargs)

      if response.status_code == 403 and response.text:
        # check that it is cloud flare block
        if (
            (
              "Just a moment..." in response.text and
              re.search(r'<\s*title\s*>[^><]*Just a moment\.\.\.[^><]*<\s*/\s*title\s*>', response.text)
            ) or
            (
              "Attention Required!" in response.text and
              re.search(r'<\s*title\s*>[^><]*Attention Required\s*![^><]*<\s*/\s*title\s*>', response.text)
            ) or
            (
              "Captcha Challenge" in response.text and
              re.search(r'<\s*title\s*>[^><]*Captcha Challenge[^><]*<\s*/\s*title\s*>', response.text)
            ) or
            (
              "DDoS-Guard" in response.text and
              re.search(r'<\s*title\s*>[^><]*DDoS-Guard[^><]*<\s*/\s*title\s*>', response.text)
            )):
          await self._solve_challenge(url if not solve_url else solve_url)
        else:
          # Return site original 403(non cloud flare blocking) as is - application should process it.
          return response
      else:
        return response

    raise AsyncClient.Exception(
      "Can't solve challenge: challenge got " + str(self._max_tries) + " times ... (max tries exceded)"
    )

  async def _solve_challenge(self, url):
    async with httpx.AsyncClient(http2 = False) as solver_client:
      solve_send_cookies = []
      if self._http_client:
        for c in self._http_client.cookies.jar:
          # c is http.cookiejar.Cookie
          solve_send_cookies.append({
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "port": c.port,
            "secure": c.secure,
            "expires": c.expires
          })
      solver_response = await solver_client.post(
        self._solver_url + '/get_cookies',
        headers={
          'Content-Type': 'application/json'
        },
        json={
          "maxTimeout": 60000,
          "url": url,
          "cookies": solve_send_cookies,
          # < use for solve original client cookies,
          # it can contains some required information other that cloud flare marker.
        },
        timeout=61.0
      )
      if solver_response.status_code != 200:
        raise AsyncClient.Exception("Solver is unavailable: status_code = " + str(solver_response.status_code))

      response_json = solver_response.json()
      if "solution" not in response_json:
        raise AsyncClient.Exception(
          "Can't solve challenge: no solution in response for '" + str(url) + "':" +
          json.dumps(response_json)
        )

      response_solution_json = response_json["solution"]
      self._user_agent = response_solution_json['userAgent']
      # Update _http_client cookies
      solver_cookies: typing.List[dict] = response_solution_json['cookies']
      for c in solver_cookies:
        self._http_client.cookies.set(
          name=c['name'],
          value=c['value'],
          domain=c.get('domain', ""),
          path=c.get('path', '/')
        )
