import os
import sys
import re
import typing
import typing_extensions
import datetime
import copy
import platform
import uuid
import pathlib
import asyncio
import traceback
import importlib
import logging
import argparse
import urllib3.util
import fastapi
import pydantic

import flare_bypasser

logger = logging.getLogger(__name__)

USE_GUNICORN = (
  sys.platform not in ['win32', 'cygwin'] and 'FLARE_BYPASS_USE_UVICORN' not in os.environ
)

if USE_GUNICORN:
  import gunicorn.app.wsgiapp
else:
  import uvicorn.main


# Remove requirement for Content-Type header presence.
class RemoveContentTypeRequirementMiddleware(object):
  def __init__(self, app):
    self._app = app

  async def __call__(self, scope, receive, send):
    headers = scope["headers"]
    content_type_found = False
    for header_index, header in enumerate(headers):
      if not isinstance(header, tuple) or len(header) != 2:
        # Unexpected headers format - don't make something.
        content_type_found = True
        break
      if header[0].decode('utf-8').lower() == 'content-type':
        headers[header_index] = (b'content-type', b'application/json')
        content_type_found = True
        break
    if not content_type_found:
      headers.append((b'content-type', b'application/json'))

    return await self._app(scope, receive, send)


server = fastapi.FastAPI(
  openapi_url='/docs/openapi.json',
  docs_url='/docs',
  swagger_ui_parameters={"defaultModelsExpandDepth": -1},
  tags_metadata=[]
)

server.add_middleware(RemoveContentTypeRequirementMiddleware)

PROXY_ANNOTATION = """Proxy in format: <protocol>://(<user>:<password>@)?<host>:<port> .
Examples: socks5://1.1.1.1:2000, http://user:password@1.1.1.1:8080.
For flaresolverr compatibility allowed format:
{"url": "<protocol>://<host>:<port>", "username": "<username>", "port": "<port>"}
If you use proxy with authorization and use flare-bypasser as package, please,
read instructions - need to install gost."""

solver_args = {
  'command_processors': {},
  'proxy_controller': None,
  'disable_gpu': False,
  'debug_dir': None
}


request_processing_default_args = {
  'forks': []
}


class ProxyModel(pydantic.BaseModel):
  url: str = pydantic.Field(default=None, description='Proxy url')
  username: str = pydantic.Field(default=None, description='Proxy authorization username')
  password: str = pydantic.Field(default=None, description='Proxy authorization password')


class CookieModel(pydantic.BaseModel):
  name: str = pydantic.Field(description='Cookie name')
  value: str = pydantic.Field(description='Cookie value (empty string if no value)')
  domain: str = pydantic.Field(description='Cookie domain')  # < Is required - we don't allow super cookies usage.
  port: typing.Optional[int] = pydantic.Field(default=None, description='Cookie port')
  path: typing.Optional[str] = pydantic.Field(default='/', description='Cookie path')
  secure: typing.Optional[bool] = pydantic.Field(default=True, description='Cookie is secure')
  expires: typing.Optional[int] = pydantic.Field(
    default=None, description='Cookie expire time in seconds after epoch start'
  )


class DefferedForksModel(pydantic.BaseModel):
  forks: int = pydantic.Field(description='Number of tasks for run after delay')
  delay: float = pydantic.Field(
    description="Delay for start forks after starting (if some fork didn't solve challenge"
  )


class HandleCommandResponseSolution(pydantic.BaseModel):
  status: str
  url: str
  cookies: list[CookieModel] = pydantic.Field(default=[], description='Cookies got after solving')
  userAgent: typing.Optional[str] = None
  response: typing.Optional[typing.Any] = None


class HandleCommandResponse(pydantic.BaseModel):
  status: str
  message: str
  startTimestamp: float
  endTimestamp: float
  solution: typing.Optional[HandleCommandResponseSolution] = None


async def wait_first_non_exception(tasks, return_condition = lambda x: True):
  task_features = [asyncio.ensure_future(t()) for t in tasks]
  to_cancel_tasks = []
  skipped_results = []
  exceptions = []
  try:
    while task_features:
      finished, to_cancel_tasks = await asyncio.wait(task_features, return_when = asyncio.FIRST_COMPLETED)
      for f in finished:
        task_features.remove(f)
      for f in finished:
        try:
          res = await f
          if return_condition(res):
            return (res, skipped_results, exceptions)
          else:
            skipped_results.append(res)
        except Exception as e:
          exceptions.append(e)
          if not task_features:
            raise e
  finally:
    for t in to_cancel_tasks:
      t.cancel()
  return (None, skipped_results, exceptions)


async def deffered_call(task, timeout: float):
  if timeout > 0:
    await asyncio.sleep(timeout)
  return await task()


async def solve(
  solve_request: flare_bypasser.Request,
  proxy: str = None,
  log_prefix: str = '',
  solver_args: dict = {}
):
  logger.info(log_prefix + "Solve start")

  solver = flare_bypasser.Solver(
    proxy=proxy,
    log_prefix=log_prefix,
    **solver_args)
  return await solver.solve(solve_request)


async def process_solve_request(
  url: str,
  cmd: str,
  cookies: list[CookieModel] = None,
  max_timeout: int = None,  # in msec.
  proxy: typing.Union[str, ProxyModel] = None,
  params: dict = {},
  forks: typing.List[DefferedForksModel] = None  # < Forks for solve. Usable for sites with unstable loading.
):
  start_timestamp = datetime.datetime.timestamp(datetime.datetime.now())

  # Adapt proxy format for canonical representation.
  if proxy is not None and not isinstance(proxy, str):
    if proxy.url is not None:
      parsed_proxy = urllib3.util.parse_url(proxy.url)
      proxy = (
        parsed_proxy.scheme + "://" +
        (
          proxy.username + ":" + (proxy.password if proxy.password else '') + '@'
          if proxy.username else ''
        ) +
        parsed_proxy.hostname +
        (":" + str(parsed_proxy.port) if parsed_proxy.port else '')
      )
    else:
      proxy = None

  try:
    solve_request = flare_bypasser.Request()
    solve_request.cmd = cmd
    solve_request.url = url
    solve_request.cookies = [
      (cookie if isinstance(cookie, dict) else cookie.__dict__)
      for cookie in cookies
    ] if cookies else []
    solve_request.max_timeout = max_timeout * 1.0 / 1000
    solve_request.proxy = proxy
    solve_request.params = params

    global solver_args
    local_solver_args = copy.copy(solver_args)
    if local_solver_args['debug_dir']:
      debug_dir = os.path.join(local_solver_args['debug_dir'], str(uuid.uuid4()))
      pathlib.Path(debug_dir).mkdir(parents=True, exist_ok=True)
      local_solver_args['debug_dir'] = debug_dir

    cur_fork_i = 0
    solve_tasks = []
    solve_tasks.append(
      lambda fork_i = cur_fork_i: solve(
        solve_request, proxy = proxy, solver_args = local_solver_args,
        log_prefix=("fork #" + str(fork_i) + ", ")
      )
    )
    cur_fork_i += 1

    if forks is None:
      global request_processing_default_args
      forks = request_processing_default_args['forks']

    if forks:
      for forks_model in forks:
        for i in range(forks_model.forks):
          solve_tasks.append(
            lambda fork_i = cur_fork_i: deffered_call(
              lambda: solve(
                solve_request, proxy = proxy, solver_args = local_solver_args,
                log_prefix=("fork #" + str(fork_i) + ", ")
              ),
              forks_model.delay
            )
          )
          cur_fork_i += 1

    logger.info('Start solve_tasks = ' + str(solve_tasks))
    solve_response, _skipped_results, _exceptions = await wait_first_non_exception(solve_tasks)
    # < solve_response can't be None if no return_condition passed to wait_first_non_exception,
    # only exception expected

    return HandleCommandResponse(
      status="ok",
      message=solve_response.message,
      startTimestamp=start_timestamp,
      endTimestamp=datetime.datetime.timestamp(datetime.datetime.now()),
      solution=HandleCommandResponseSolution(
        status="ok",
        url=solve_response.url,
        cookies=[  # Convert cookiejar.Cookie to CookieModel
          CookieModel(**cookie) for cookie in solve_response.cookies
        ],
        # < pass cookies as dict's (solver don't know about rest model).
        userAgent=solve_response.user_agent,
        message=solve_response.message,
        response=solve_response.response
      )
    )

  except Exception as e:
    print(str(e))
    print(traceback.format_exc(), flush=True)
    return HandleCommandResponse(
      status="error",
      message="Error: " + str(e),
      startTimestamp=start_timestamp,
      endTimestamp=datetime.datetime.timestamp(datetime.datetime.now()),
    )


# Endpoint compatible with flaresolverr API.
@server.post(
  "/v1",
  response_model=HandleCommandResponse,
  tags=['FlareSolverr compatiblity API'],
  response_model_exclude_none=True
)
async def Process_request_in_flaresolverr_format(
  url: typing_extensions.Annotated[
    str,
    fastapi.Body(description="Url for solve challenge.")
  ],
  cmd: typing_extensions.Annotated[
    str,
    fastapi.Body(description="Command for execute")] = None,
  cookies: typing_extensions.Annotated[
    typing.List[CookieModel],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    typing.Union[str, ProxyModel],
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
  params: typing_extensions.Annotated[
    typing.Dict[str, typing.Any],
    fastapi.Body(description="Custom parameters for user defined commands.")
  ] = None,
  forks: typing_extensions.Annotated[
    typing.List[DefferedForksModel],
    fastapi.Body(description="Request processing forking model (usable for web sites with ustable challenge loading).")
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd=cmd,
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=params,
    forks=forks,
  )


# REST API concept methods.
@server.post(
  "/get_cookies", response_model=HandleCommandResponse, tags=['Standard API'],
  response_model_exclude_none=True
)
async def Get_cookies_after_solve(
  url: typing_extensions.Annotated[
    str,
    fastapi.Body(description="Url for solve challenge.")
  ],
  cookies: typing_extensions.Annotated[
    typing.List[CookieModel],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    typing.Union[str, ProxyModel],
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
  forks: typing_extensions.Annotated[
    typing.List[DefferedForksModel],
    fastapi.Body(description="Request processing forking model (usable for web sites with ustable challenge loading).")
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd='get_cookies',
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=None,
    forks=forks,
  )


@server.post(
  "/get_page", response_model=HandleCommandResponse, tags=['Standard API'],
  response_model_exclude_none=True
)
async def Get_cookies_and_page_content_after_solve(
  url: typing_extensions.Annotated[
    str,
    fastapi.Body(description="Url for solve challenge.")
  ],
  cookies: typing_extensions.Annotated[
    typing.List[CookieModel],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    typing.Union[str, ProxyModel],
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
  forks: typing_extensions.Annotated[
    typing.List[DefferedForksModel],
    fastapi.Body(description="Request processing forking model (usable for web sites with ustable challenge loading).")
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd='get_page',
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=None,
    forks=forks,
  )


@server.post(
  "/make_post", response_model=HandleCommandResponse, tags=['Standard API'],
  response_model_exclude_none=True
)
async def Get_cookies_and_POST_request_result(
  url: typing_extensions.Annotated[
    str,
    fastapi.Body(description="Url for solve challenge.")
  ],
  postData: typing_extensions.Annotated[
    str,
    fastapi.Body(description="""Post data that will be passed in request""")
  ],
  cookies: typing_extensions.Annotated[
    typing.List[CookieModel],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    typing.Union[str, ProxyModel],
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
  forks: typing_extensions.Annotated[
    typing.List[DefferedForksModel],
    fastapi.Body(description="Request processing forking model (usable for web sites with ustable challenge loading).")
  ] = None,
  # postDataContentType: typing_extensions.Annotated[
  #   str,
  #   fastapi.Body(description="Content-Type that will be sent.")
  #   ]='',
):
  return await process_solve_request(
    url=url,
    cmd='make_post',
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params={
      'postData': postData,
      # 'postDataContentType': postDataContentType,
    },
    forks=forks,
  )


@server.post(
  "/command/{command}", response_model=HandleCommandResponse, tags=['Standard API'],
  response_model_exclude_none=True
)
async def Process_user_custom_command(
  command: typing_extensions.Annotated[
    str,
    fastapi.Path(description="User command to execute")],
  url: typing_extensions.Annotated[
    str,
    fastapi.Body(description="Url for solve challenge.")
  ],
  cookies: typing_extensions.Annotated[
    typing.List[CookieModel],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    typing.Union[str, ProxyModel],
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
  params: typing_extensions.Annotated[
    typing.Dict,
    fastapi.Body(description="Params for execute custom user command.")
  ] = None,
  forks: typing_extensions.Annotated[
    typing.List[DefferedForksModel],
    fastapi.Body(description="Request processing forking model (usable for web sites with ustable challenge loading).")
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd=command,
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=params,
    forks=forks
  )


def parse_class_command_processors(custom_command_processors_str: str):
  result_command_processors = {}
  for mod in custom_command_processors_str.split(',;'):
    try:
      command_name, import_module_and_class_name = mod.split(':', 1)
      import_module_name, import_class_name = import_module_and_class_name.rsplit('.', 1)
      module = importlib.import_module(import_module_name)
      assert hasattr(module, import_class_name)
      cls = getattr(module, import_class_name)
      logger.info("Loaded user command: " + str(command_name))
      result_command_processors[command_name] = cls()
    except Exception as e:
      raise Exception(
        "Can't load user command '" + str(mod) + "'(by FLARE_BYPASS_COMMANDPROCESSORS): " +
        str(e)
      )
  return result_command_processors


def parse_entrypoint_command_processors(extension: str):
  result_command_processors = {}
  try:
    import_module_name, entry_point = extension.split(':', 1)
    module = importlib.import_module(import_module_name)
    assert hasattr(module, entry_point)
    get_user_commands_method = getattr(module, entry_point)
    user_commands = get_user_commands_method()
    for command_name, command_processor in user_commands.items():
      logger.info("Loaded user command: " + str(command_name))
      result_command_processors[command_name] = command_processor
  except Exception as e:
    raise Exception(
      "Can't load user command for '" + str(extension) + "': " + str(e)
    )
  return result_command_processors


def parse_solve_forks(solve_forks: str):
  res = []
  forks_arr = solve_forks.strip(' "').split(',')
  for fork_str in forks_arr:
    single_fork_arr = fork_str.split(':')
    if single_fork_arr:
      res.append(
        DefferedForksModel(
          delay=float(single_fork_arr[0].strip()),
          forks=(int(single_fork_arr[1].strip()) if len(single_fork_arr) > 1 else 1)
        )
      )
  return res


def init_args_parser():
  parser = argparse.ArgumentParser(
    description='Start flare_bypass server.',
    epilog='Other arguments will be passed to gunicorn or uvicorn(win32) as is.')
  parser.add_argument("-b", "--bind", type=str, default='127.0.0.1:8000')
  # < parse for pass to gunicorn as is and as "--host X --port X" to uvicorn
  parser.add_argument("--extensions", nargs='*', type=str)
  parser.add_argument(
    "--proxy-listen-start-port", type=int, default=10000,
    help="""Port interval start, that can be used for up local proxies on request processing"""
  )
  parser.add_argument(
    "--proxy-listen-end-port", type=int, default=20000,
    help="""Port interval end for up local proxies"""
  )
  parser.add_argument(
    "--proxy-command", type=str,
    default="gost -L=socks5://127.0.0.1:{{LOCAL_PORT}} -F='{{UPSTREAM_URL}}'",
    help="""command template (jinja2), that will be used for up proxy for process request
    with arguments: LOCAL_PORT, UPSTREAM_URL - proxy passed in request"""
  )
  parser.add_argument("--disable-gpu", action='store_true')
  parser.add_argument("--verbose", action='store_true')
  parser.add_argument(
    "--debug-dir", type=str, default=None,
    help="""directory for save intermediate DOM dumps and screenshots on solving,
    for each request will be created unique directory"""
  )
  parser.add_argument("--forks", type=str, default=None)
  parser.set_defaults(disable_gpu=False, debug=False)
  return parser


def init_extensions(args):
  global solver_args

  # FLARE_BYPASS_COMMANDPROCESSORS format: <command>:<module>.<class>
  # class should have default constructor (without parameters)
  custom_command_processors_str = os.environ.get('FLARE_BYPASS_COMMANDPROCESSORS', None)
  if custom_command_processors_str:
    solver_args['command_processors'].update(
      parse_class_command_processors(custom_command_processors_str))

  if args.extensions:
    for extension in args.extensions:
      # Expect that extension element has format: <module>.<method>
      solver_args['command_processors'].update(
        parse_entrypoint_command_processors(extension))


def server_run():
  try:
    logging.basicConfig(
      format='%(asctime)s [%(name)s] [%(levelname)s]: %(message)s',
      handlers=[logging.StreamHandler(sys.stdout)],
      level=logging.INFO
    )

    logging.getLogger('urllib3').setLevel(logging.ERROR)

    logger.info(
      "Start flare_bypass server:\n" +
      "  version: " + str(flare_bypasser.__version__) + "\n" +
      "  python version = " + ".".join([str(x) for x in list(sys.version_info)]) + "\n" +
      "  os = " + " ".join([platform.system(), platform.release(), platform.version()]) + "\n" +
      "  docker = " + os.environ.get('IN_DOCKER', "false") + "\n" +
      "  arch = " + str(platform.machine()) + "\n" +
      "  processor = " + str(platform.processor())
    )

    parser = init_args_parser()
    args, unknown_args = parser.parse_known_args()
    try:
      host, port = args.bind.split(':')
    except Exception:
      print("Invalid 'bind' argument value: " + str(args.bind), file=sys.stderr, flush=True)
      sys.exit(1)

    if args.verbose:
      logging.getLogger('nodriver.core.browser').setLevel(logging.DEBUG)
      logging.getLogger('uc.connection').setLevel(logging.DEBUG)
      logging.getLogger('flare_bypasser.flare_bypasser').setLevel(logging.DEBUG)

    global solver_args

    init_extensions(args)

    global request_processing_default_args
    if args.forks:
      request_processing_default_args['forks'] = parse_solve_forks(args.forks)

    if args.debug_dir:
      logging.getLogger('flare_bypasser.flare_bypasser').setLevel(logging.DEBUG)
    solver_args['debug_dir'] = args.debug_dir

    sys.argv = [re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])]
    sys.argv += unknown_args

    # Init ProxyController
    solver_args['proxy_controller'] = flare_bypasser.proxy_controller.ProxyController(
      start_port=args.proxy_listen_start_port,
      end_port=args.proxy_listen_end_port,
      command=args.proxy_command)

    if args.disable_gpu:
      solver_args['disable_gpu'] = True

    if USE_GUNICORN:
      sys.argv += ['-b', args.bind]
      sys.argv += ['--worker-class', 'uvicorn.workers.UvicornWorker']
      sys.argv += ['flare_bypasser:server']
      sys.exit(gunicorn.app.wsgiapp.run())
    else:
      sys.argv += ['--host', host]
      sys.argv += ['--port', port]
      sys.argv += ['flare_bypasser:server']
      sys.exit(uvicorn.main.main())

  except Exception as e:
    logging.error(str(e))
    sys.exit(1)


if __name__ == '__main__':
  server_run()
