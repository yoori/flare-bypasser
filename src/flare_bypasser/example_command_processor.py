import flare_bypasser


class ExampleCommandProcessor(flare_bypasser.BaseCommandProcessor):
  async def process_command(
    self,
    res: flare_bypasser.Response,
    req: flare_bypasser.Request,
    driver: flare_bypasser.BrowserWrapper
  ) -> flare_bypasser.Response:
    res.response = {'somefield': 1}
    return res
