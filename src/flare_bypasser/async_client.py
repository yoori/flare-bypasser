import typing
import copy
import unicodedata
import dataclasses
import json
import re
import httpx


@dataclasses.dataclass
class ChallengeCheck:
  keywords: typing.List[str] = None
  regexp: re.Pattern = None
  blocked: bool = False


"""
AsyncClient
httpx.AsyncClient wrapper for transient manipulations with sites and
transparent cloud flare protection bypassing.
"""


class AsyncClient(object):
  _solver_url: str = None
  _http_client: httpx.AsyncClient = None
  _additional_hook = None
  _custom_challenge_selectors: typing.List[str] = None
  _args = []
  _kwargs = {}
  _user_agent: str = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  # < base user-agent that will be used before first challenge solve,
  # after it will be replaced with solver actual user-agent
  _max_tries: int = 2
  _solve_with_empty_cookies: bool = False
  _challenge_checks: typing.List[ChallengeCheck] = []

  class Exception(Exception):
    pass

  class CloudFlareBlocked(Exception):
    pass

  def __init__(
    self,
    solver_url,
    *args,
    additional_hook = None,
    custom_challenge_selectors: typing.List[str] = None,
    max_tries = 2,
    solve_with_empty_cookies: bool = False,  # < If challenge detected solve it with empty cookies.
    **kwargs
  ):
    self._solver_url = solver_url
    self._additional_hook = additional_hook
    self._custom_challenge_selectors = custom_challenge_selectors
    self._max_tries = max_tries
    self._solve_with_empty_cookies = solve_with_empty_cookies
    self._args = args
    self._kwargs = kwargs
    self._challenge_checks = {
      403: [
        ChallengeCheck(
          keywords=['access denied'],
          regexp=re.compile(r'<\s*title\s*>\s*access denied\s[^><]*cloudflare[^><]*<\s*/\s*title\s*>'),
          blocked=True,
        ),
        ChallengeCheck(
          keywords=['ip banned', 'cloudflare'],
          regexp=re.compile(r'<\s*title\s*>\s*access denied\s[^><]*cloudflare[^><]*<\s*/\s*title\s*>'),
          blocked=True,
        ),
        ChallengeCheck(
          keywords=['just a moment...'],
          regexp=re.compile(r'<\s*title\s*>[^><]*just a moment\.\.\.[^><]*<\s*/\s*title\s*>'),
        ),
        ChallengeCheck(
          keywords=['attention required!'],
          regexp=re.compile(r'<\s*title\s*>[^><]*attention required\s*![^><]*<\s*/\s*title\s*>'),
        ),
        ChallengeCheck(
          keywords=['captcha challenge'],
          regexp=re.compile(r'<\s*title\s*>[^><]*captcha challenge[^><]*<\s*/\s*title\s*>'),
        ),
        ChallengeCheck(
          keywords=['ddos-guard'],
          regexp=re.compile(r'<\s*title\s*>[^><]*ddos-guard[^><]*<\s*/\s*title\s*>'),
        ),
      ],
      200: [
        ChallengeCheck(
          keywords=[unicodedata.normalize('NFKC', 'проверка'), unicodedata.normalize('NFKC', 'человек')],
          regexp=re.compile(r'<\s*title\s*>[^><]*проверка[^><]*вы\s+человек[^><]*<\s*/\s*title\s*>'),
        ),
      ],
    }

  async def __aenter__(self):
    self._http_client = None  # < Cleanup previously opened connections
    self._init_client()
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

  async def get(self, url, *args, **kwargs) -> httpx.Response:
    return await self._request(httpx.AsyncClient.get, url, *args, **kwargs)

  async def post(self, url, *args, solve_url = None, **kwargs) -> httpx.Response:
    return await self._request(httpx.AsyncClient.post, url, *args, solve_url = solve_url, **kwargs)

  def _init_client(self):
    if not self._http_client:
      self._http_client = httpx.AsyncClient(http2 = True, *self._args, **self._kwargs)

  async def _request(self, run_method, url, *args, solve_url = None, headers = {}, **kwargs) -> httpx.Response:
    self._init_client()

    for try_i in range(self._max_tries):
      # request web page
      send_headers = copy.copy(headers)
      send_headers['user-agent'] = self._user_agent
      send_headers['cache-control'] = 'no-cache'  # < Disable cache, because httpx can return cached captcha response.
      response = await run_method(self._http_client, url, *args, headers = send_headers, **kwargs)

      solve_challenge: bool = False

      if (
        response.status_code in self._challenge_checks and
        response.headers.get('content-type', '').startswith('text/html') and
        response.text
      ):
        response_text = unicodedata.normalize('NFKC', response.text.lower())

        # check that it is cloud flare block
        for challenge_check in self._challenge_checks[response.status_code]:
          check_regexp: bool = True
          if challenge_check.keywords is not None:
            for kw in challenge_check.keywords:
              if kw not in response_text:
                check_regexp = False
                break

          if (
            check_regexp and
            (challenge_check.regexp is None or re.search(challenge_check.regexp, response_text))
          ):
            if challenge_check.blocked:
              raise AsyncClient.CloudFlareBlocked("IP blocked by cloud flare")
            solve_challenge = True
            break

      if not solve_challenge and self._additional_hook is not None:
        solve_challenge = self._additional_hook(response)

      if solve_challenge:
        await self._solve_challenge(url if not solve_url else solve_url)
        continue  # < Repeat request with cf cookies

      return response

    raise AsyncClient.Exception(
      "Can't solve challenge: challenge got " + str(self._max_tries) + " times ... (max tries exceded)"
    )

  async def _solve_challenge(self, url):
    async with httpx.AsyncClient(http2 = False) as solver_client:
      solve_send_cookies = []
      if not self._solve_with_empty_cookies and self._http_client:
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
      solver_request = {
        "maxTimeout": 60000,
        "url": url,
        "cookies": solve_send_cookies,
        # < use for solve original client cookies,
        # it can contains some required information other that cloud flare marker.
        "proxy": self._kwargs.get('proxy', None),
      }

      if self._custom_challenge_selectors is not None:
        solver_request['custom_challenge_selectors'] = self._custom_challenge_selectors

      solver_response = await solver_client.post(
        self._solver_url + '/get_cookies',
        headers={
          'Content-Type': 'application/json'
        },
        json=solver_request,
        timeout=61.0
      )
      if solver_response.status_code != 200:
        raise AsyncClient.Exception("Solver is unavailable: status_code = " + str(solver_response.status_code))

      response_json = solver_response.json()
      if "solution" not in response_json:
        raise AsyncClient.Exception(
          "Can't solve challenge: no solution in response for '" + str(url) + "': " +
          "response: " + json.dumps(response_json) +
          " on request: " + json.dumps(solver_request)
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
