import os
import sys
import re
import typing
import typing_extensions
import asyncio
import datetime
import traceback

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
  print(">>>>>>>>>>>>>>>>>>> POINT #1", flush = True)

  start_timestamp = datetime.datetime.timestamp(datetime.datetime.now())

  try :
    solve_request = flare_bypasser.Request()
    solve_request.cmd = cmd
    solve_request.cookies = cookies
    solve_request.url = url
    solve_request.max_timeout = maxTimeout * 1.0 / 1000
    solve_request.proxy = proxy

    solver = flare_bypasser.Solver()
    solve_response = await solver.solve(solve_request)

    print("solve_response.message = " + str(solve_response.message), flush = True)
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
  sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
  sys.argv.append('--worker-class')
  sys.argv.append('uvicorn.workers.UvicornWorker')
  sys.argv.append('flare_bypasser:server')
  sys.exit(gunicorn.app.wsgiapp.run())

if __name__ == '__main__':
  server_run()
