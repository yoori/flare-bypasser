import os
import sys
import re
import typing
import typing_extensions
import asyncio
import datetime
import traceback
import importlib

import fastapi
import pydantic
import gunicorn.app.wsgiapp

import flare_bypasser

server = fastapi.FastAPI(
  openapi_url = '/docs/openapi.json',
  docs_url = '/docs',
  swagger_ui_parameters = { "defaultModelsExpandDepth": -1 },
  tags_metadata = [
  ]
)

custom_command_processors = {}

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
  ):
  start_timestamp = datetime.datetime.timestamp(datetime.datetime.now())

  try :
    solve_request = flare_bypasser.Request()
    solve_request.cmd = cmd
    solve_request.cookies = cookies
    solve_request.url = url
    solve_request.max_timeout = maxTimeout * 1.0 / 1000
    solve_request.proxy = proxy

    global custom_command_processors
    solver = flare_bypasser.Solver(proxy = proxy, command_processors = custom_command_processors)
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

  sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
  sys.argv.append('--worker-class')
  sys.argv.append('uvicorn.workers.UvicornWorker')
  sys.argv.append('flare_bypasser:server')
  sys.exit(gunicorn.app.wsgiapp.run())

if __name__ == '__main__':
  server_run()
