import zendriver_flare_bypasser as zendriver
from flare_bypasser import BaseCommandProcessor, Request, Response, BrowserWrapper


class MyClickCommandProcessor(BaseCommandProcessor):
  async def preprocess_command(self, req: Request, driver: BrowserWrapper) -> Request:
    # Here we can check some required parameters in req.params and raise error.
    return req

  async def process_command(self, res: Response, req: Request, driver: BrowserWrapper) -> Response:
    nodriver_tab: zendriver.Tab = driver.get_driver()
    dom = await nodriver_tab.get_content()  # get source code of page (actual DOM)
    els = await nodriver_tab.select_all('input[type=submit]')  # find submit button
    if not els:
      raise Exception("MyClickCommandProcessor: no input for click: " + str(dom))
    await els[0].click()  # click submit
    res.response = await nodriver_tab.get_content() # get actual DOM after click and return it in response
    # Expect here "Bledny kod" text in DOM (appears only after click)
    return res


def get_user_commands():
  return {
    'my-click': MyClickCommandProcessor()
  }
