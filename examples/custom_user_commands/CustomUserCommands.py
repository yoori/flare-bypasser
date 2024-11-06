from flare_bypasser import BaseCommandProcessor, Request, Response, BrowserWrapper


class MyClickCommandProcessor(BaseCommandProcessor):
  async def preprocess_command(self, req: Request, driver: BrowserWrapper) -> Request:
    # Here we can check some required parameters in req.params and raise error.
    return req

  async def process_command(self, res: Response, req: Request, driver: BrowserWrapper) -> Response:
    nodriver_tab = driver.get_driver()
    dom = await nodriver_tab.get_content()
    els = await nodriver_tab.select_all('input[type=submit]')
    if not els:
      raise Exception("MyClickCommandProcessor: no input for click: " + str(dom))
    await els[0].click()
    res.response = await nodriver_tab.get_content()
    # Expect here "Bledny kod" text in DOM (appears only after click)
    return res


def get_user_commands():
  return {
    'my-click': MyClickCommandProcessor()
  }
