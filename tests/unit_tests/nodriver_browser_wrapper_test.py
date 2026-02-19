import asyncio
import sys
import types

sys.modules.setdefault("cv2", types.SimpleNamespace())

if "nodriver" not in sys.modules:
  class _DummyElement:
    def __init__(self, *_args, **_kwargs):
      pass

  sys.modules["nodriver"] = types.SimpleNamespace(
    Browser=types.SimpleNamespace(create=None),
    Tab=types.SimpleNamespace(),
    Element=_DummyElement,
    Config=None,
    core=types.SimpleNamespace(
      connection=types.SimpleNamespace(ProtocolException=Exception)
    )
  )

from flare_bypasser.nodriver_browser_wrapper import NoDriverBrowserWrapper



class DummyConfig:
  def __init__(self, sandbox=False, browser_args=None):
    self.sandbox = sandbox
    self.browser_args = browser_args


class DummyDriver:
  pass


def test_create_retries_on_known_nodriver_connection_race(monkeypatch):
  attempts = {"count": 0}
  user_data_dirs = iter([
    "/tmp/flare-bypasser-test-profile-1",
    "/tmp/flare-bypasser-test-profile-2",
    "/tmp/flare-bypasser-test-profile-3",
  ])
  removed_dirs = []

  async def fake_create(_config):
    attempts["count"] += 1
    if attempts["count"] < 3:
      raise AttributeError("'NoneType' object has no attribute 'closed'")
    return DummyDriver()

  monkeypatch.setattr(
    "flare_bypasser.nodriver_browser_wrapper.make_user_data_dir",
    lambda: next(user_data_dirs),
  )
  monkeypatch.setattr(
    "flare_bypasser.nodriver_browser_wrapper.build_browser_args",
    lambda **_kwargs: ["--headless"],
  )
  monkeypatch.setattr(
    "flare_bypasser.nodriver_browser_wrapper.NoDriverBrowserWrapper.start_xvfb_display",
    lambda: None,
  )
  monkeypatch.setattr("flare_bypasser.nodriver_browser_wrapper.nodriver.Config", DummyConfig)
  monkeypatch.setattr(
    "flare_bypasser.nodriver_browser_wrapper.nodriver.Browser.create",
    fake_create,
  )

  def fake_rmtree(path, ignore_errors=False):
    removed_dirs.append((path, ignore_errors))

  monkeypatch.setattr(
    "flare_bypasser.nodriver_browser_wrapper.shutil.rmtree",
    fake_rmtree,
  )

  wrapper = asyncio.run(NoDriverBrowserWrapper.create())

  assert isinstance(wrapper, NoDriverBrowserWrapper)
  assert attempts["count"] == 3
  assert wrapper._user_data_dir == "/tmp/flare-bypasser-test-profile-3"
  assert removed_dirs == [
    ("/tmp/flare-bypasser-test-profile-1", True),
    ("/tmp/flare-bypasser-test-profile-2", True),
  ]
