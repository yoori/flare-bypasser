import os
import sys
import re
import typing
import typing_extensions
import asyncio
import datetime
import traceback
import importlib
import logging
import argparse

import fastapi
import pydantic
import flare_bypasser.proxy_controller

USE_GUNICORN = (sys.platform not in ['win32', 'cygwin'] and 'FLARE_BYPASS_USE_UVICORN' not in os.environ)

if USE_GUNICORN :
  import gunicorn.app.wsgiapp
else :
  import uvicorn.main

import flare_bypasser

server = fastapi.FastAPI(
  openapi_url = '/docs/openapi.json',
  docs_url = '/docs',
  swagger_ui_parameters = { "defaultModelsExpandDepth": -1 },
  tags_metadata = [
  ]
)

custom_command_processors = {}
proxy_controller = None

class HandleCommandResponseSolution(pydantic.BaseModel) :
  status : str
  url : str
  cookies: list
  userAgent: typing.Optional[str] = None
  response : typing.Optional[typing.Any] = None

class HandleCommandResponse(pydantic.BaseModel) :
  status : str
  message : str
  startTimestamp : float
  endTimestamp : float
  solution : typing.Optional[HandleCommandResponseSolution] = None

@server.post("/v1",
  response_model = HandleCommandResponse,
  tags = ['API'])
async def handle_command(
  url : typing_extensions.Annotated[
    str,
    fastapi.Body(description = "Url")
    ],
  cmd : typing_extensions.Annotated[
    str,
    fastapi.Body(description = "Command for execute")] = None,
  cookies : typing_extensions.Annotated[
    typing.List[typing.Dict],
    fastapi.Body(description = "Cookies")
    ] = None,
  maxTimeout : typing_extensions.Annotated[
    float,
    fastapi.Body(description = "Max timeout in ms")
    ] = 60000,
  proxy : typing_extensions.Annotated[
    str,
    fastapi.Body(description = "Proxy")
    ] = None,
  params : typing_extensions.Annotated[
    typing.Dict[str, typing.Any],
    fastapi.Body(description = "Custom parameters for user defined command")
    ] = None,
  ):
  start_timestamp = datetime.datetime.timestamp(datetime.datetime.now())

  try :
    solve_request = flare_bypasser.Request()
    solve_request.cmd = cmd
    solve_request.cookies = cookies
    solve_request.url = url
    solve_request.max_timeout = maxTimeout * 1.0 / 1000
    solve_request.proxy = proxy
    solve_request.params = params

    global custom_command_processors
    global proxy_controller
    solver = flare_bypasser.Solver(
      proxy = proxy,
      command_processors = custom_command_processors,
      proxy_controller = proxy_controller)
    solve_response = await solver.solve(solve_request)

    return HandleCommandResponse(
      status = "ok",
      message = solve_response.message,
      startTimestamp = start_timestamp,
      endTimestamp = datetime.datetime.timestamp(datetime.datetime.now()),
      solution = HandleCommandResponseSolution(
        status = "ok",
        url = solve_response.url,
        cookies = solve_response.cookies,
        userAgent = solve_response.user_agent,
        message = solve_response.message,
        response = solve_response.response
      )
    )

  except Exception as e :
    print(str(e))
    print(traceback.format_exc(), flush = True)
    return HandleCommandResponse(
      status = "error",
      message = "Error: " + str(e),
      startTimestamp = start_timestamp,
      endTimestamp = datetime.datetime.timestamp(datetime.datetime.now()),
    )

def server_run():
  logging.basicConfig(format = '%(asctime)s [%(name)s] [%(levelname)s] : %(message)s',
    handlers = [logging.StreamHandler(sys.stdout)],
    level = logging.INFO)

  logging.getLogger('urllib3').setLevel(logging.ERROR)
  logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)
  logging.getLogger('undetected_chromedriver').setLevel(logging.WARNING)

  parser = argparse.ArgumentParser(
    description = 'Start flare_bypass server.',
    epilog = 'Other arguments will be passed to gunicorn or uvicorn(win32) as is.')
  parser.add_argument("-b", "--bind", type = str, default = '127.0.0.1:8000')
  parser.add_argument("--proxy-listen-start-port", type = int, default = 10000)
  parser.add_argument("--proxy-listen-end-port", type = int, default = 20000)
  parser.add_argument("--proxy-command", type = str,
    default = "gost -L=socks5://127.0.0.1:{{LOCAL_PORT}} -F='{{UPSTREAM_URL}}'")
  #< parse for pass to gunicorn as is and as "--host X --port X" to uvicorn
  args, unknown_args = parser.parse_known_args()
  try :
    host, port = args.bind.split(':')
  except :
    print("Invalid 'bind' argument value : " + str(args.bind), file = sys.stderr, flush = True)
    sys.exit(1)

  # FLARE_BYPASS_COMMANDPROCESSORS format : <command>:<module>.<class>
  # class should have default constructor (without parameters)
  custom_command_processors_str = os.environ.get('FLARE_BYPASS_COMMANDPROCESSORS', None)
  if custom_command_processors_str :
    global custom_command_processors
    for mod in custom_command_processors_str.split(',;') :
      command_name, import_module_and_class_name = mod.split(':', 1)
      import_module_name, import_class_name = import_module_and_class_name.rsplit('.', 1)
      module = importlib.import_module(import_module_name)
      assert hasattr(module, import_class_name)
      cls = getattr(module, import_class_name)
      custom_command_processors[command_name] = cls()

  sys.argv = [ re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0]) ]
  sys.argv += unknown_args

  # Init ProxyController
  global proxy_controller
  proxy_controller = flare_bypasser.proxy_controller.ProxyController(
    start_port = args.proxy_listen_start_port,
    end_port = args.proxy_listen_end_port,
    command = args.proxy_command)

  if USE_GUNICORN :
    sys.argv += [ '-b', args.bind ]
    sys.argv += ['--worker-class', 'uvicorn.workers.UvicornWorker']
    sys.argv += ['flare_bypasser:server']
    sys.exit(gunicorn.app.wsgiapp.run())
  else :
    sys.argv += [ '--host', host ]
    sys.argv += [ '--port', port ]
    sys.argv += ['flare_bypasser:server']
    sys.exit(uvicorn.main.main())

if __name__ == '__main__':
  server_run()
