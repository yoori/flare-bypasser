import os
import sys
import re
import typing
import typing_extensions
import datetime
import traceback
import importlib
import logging
import argparse

import fastapi
import pydantic
import flare_bypasser.proxy_controller
import flare_bypasser

USE_GUNICORN = (
  sys.platform not in ['win32', 'cygwin'] and 'FLARE_BYPASS_USE_UVICORN' not in os.environ
)

if USE_GUNICORN:
  import gunicorn.app.wsgiapp
else:
  import uvicorn.main

server = fastapi.FastAPI(
  openapi_url='/docs/openapi.json',
  docs_url='/docs',
  swagger_ui_parameters={"defaultModelsExpandDepth": -1},
  tags_metadata=[]
)

PROXY_ANNOTATION = """Proxy in format: <protocol>://(<user>:<password>@)?<host>:<port> .
Examples: socks5://1.1.1.1:2000, http://user:password@1.1.1.1:8080.
If you use proxy with authorization and use flare-bypasser as package, please,
read instructions - need to install gost."""

custom_command_processors = {}
proxy_controller = None


class HandleCommandResponseSolution(pydantic.BaseModel):
  status: str
  url: str
  cookies: list
  userAgent: typing.Optional[str] = None
  response: typing.Optional[typing.Any] = None


class HandleCommandResponse(pydantic.BaseModel):
  status: str
  message: str
  startTimestamp: float
  endTimestamp: float
  solution: typing.Optional[HandleCommandResponseSolution] = None


async def process_solve_request(
  url: str,
  cmd: str,
  cookies: list = None,
  max_timeout: int = None,  # in msec.
  proxy: str = None,
  params: dict = {}
):
  start_timestamp = datetime.datetime.timestamp(datetime.datetime.now())

  try:
    solve_request = flare_bypasser.Request()
    solve_request.cmd = cmd
    solve_request.cookies = cookies
    solve_request.url = url
    solve_request.max_timeout = max_timeout * 1.0 / 1000
    solve_request.proxy = proxy
    solve_request.params = params

    global custom_command_processors
    global proxy_controller
    solver = flare_bypasser.Solver(
      proxy=proxy,
      command_processors=custom_command_processors,
      proxy_controller=proxy_controller)
    solve_response = await solver.solve(solve_request)

    return HandleCommandResponse(
      status="ok",
      message=solve_response.message,
      startTimestamp=start_timestamp,
      endTimestamp=datetime.datetime.timestamp(datetime.datetime.now()),
      solution=HandleCommandResponseSolution(
        status="ok",
        url=solve_response.url,
        cookies=solve_response.cookies,
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
    typing.List[typing.Dict],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    str,
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
  params: typing_extensions.Annotated[
    typing.Dict[str, typing.Any],
    fastapi.Body(description="Custom parameters for user defined commands.")
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd=cmd,
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=params
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
    typing.List[typing.Dict],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    str,
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd='get_cookies',
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=None
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
    typing.List[typing.Dict],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    str,
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd='get_page',
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=None
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
    typing.List[typing.Dict],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    str,
    fastapi.Body(description=PROXY_ANNOTATION)
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
    }
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
    typing.List[typing.Dict],
    fastapi.Body(description="Cookies to send.")
  ] = None,
  maxTimeout: typing_extensions.Annotated[
    float,
    fastapi.Body(description="Max processing timeout in ms.")
  ] = 60000,
  proxy: typing_extensions.Annotated[
    str,
    fastapi.Body(description=PROXY_ANNOTATION)
  ] = None,
  params: typing_extensions.Annotated[
    typing.Dict,
    fastapi.Body(description="Params for execute custom user command.")
  ] = None,
):
  return await process_solve_request(
    url=url,
    cmd=command,
    cookies=cookies,
    max_timeout=maxTimeout,
    proxy=proxy,
    params=params
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
      logging.info("Loaded user command: " + str(command_name))
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
      logging.info("Loaded user command: " + str(command_name))
      result_command_processors[command_name] = command_processor
  except Exception as e:
    raise Exception(
      "Can't load user command for '" + str(extension) + "': " + str(e)
    )
  return result_command_processors


def server_run():
  try:
    logging.basicConfig(
      format='%(asctime)s [%(name)s] [%(levelname)s]: %(message)s',
      handlers=[logging.StreamHandler(sys.stdout)],
      level=logging.INFO
    )

    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)
    logging.getLogger('undetected_chromedriver').setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(
      description='Start flare_bypass server.',
      epilog='Other arguments will be passed to gunicorn or uvicorn(win32) as is.')
    parser.add_argument("-b", "--bind", type=str, default='127.0.0.1:8000')
    # < parse for pass to gunicorn as is and as "--host X --port X" to uvicorn
    parser.add_argument("--extensions", nargs='*', type=str)
    parser.add_argument("--proxy-listen-start-port", type=int, default=10000)
    parser.add_argument("--proxy-listen-end-port", type=int, default=20000)
    parser.add_argument(
      "--proxy-command", type=str,
      default="gost -L=socks5://127.0.0.1:{{LOCAL_PORT}} -F='{{UPSTREAM_URL}}'"
    )
    args, unknown_args = parser.parse_known_args()
    try:
      host, port = args.bind.split(':')
    except Exception:
      print("Invalid 'bind' argument value: " + str(args.bind), file=sys.stderr, flush=True)
      sys.exit(1)

    # FLARE_BYPASS_COMMANDPROCESSORS format: <command>:<module>.<class>
    # class should have default constructor (without parameters)
    custom_command_processors_str = os.environ.get('FLARE_BYPASS_COMMANDPROCESSORS', None)
    if custom_command_processors_str:
      global custom_command_processors
      custom_command_processors.update(
        parse_class_command_processors(custom_command_processors_str))

    if args.extensions:
      for extension in args.extensions:
        # Expect that extension element has format: <module>.<method>
        custom_command_processors.update(
          parse_entrypoint_command_processors(extension))

    sys.argv = [re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])]
    sys.argv += unknown_args

    # Init ProxyController
    global proxy_controller
    proxy_controller = flare_bypasser.proxy_controller.ProxyController(
      start_port=args.proxy_listen_start_port,
      end_port=args.proxy_listen_end_port,
      command=args.proxy_command)

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
