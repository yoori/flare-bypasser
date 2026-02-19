import asyncio
import sys
import types

sys.modules.setdefault("cv2", types.SimpleNamespace())
sys.modules.setdefault(
  "DrissionPage",
  types.SimpleNamespace(ChromiumOptions=object, ChromiumPage=object),
)

from flare_bypasser.drissionpage_browser_wrapper import DrissionPageBrowserWrapper


class DummyOptions:
  def __init__(self):
    self.args = []

  def set_argument(self, arg):
    self.args.append(arg)


class DummyPage:
  pass


def test_create_uses_drission_page_and_cleans_failed_profile(monkeypatch):
  user_data_dirs = iter([
    "/tmp/flare-bypasser-test-profile-1",
    "/tmp/flare-bypasser-test-profile-2",
  ])
  removed_dirs = []

  monkeypatch.setattr(
    "flare_bypasser.drissionpage_browser_wrapper.make_user_data_dir",
    lambda: next(user_data_dirs),
  )
  monkeypatch.setattr(
    "flare_bypasser.drissionpage_browser_wrapper.build_browser_args",
    lambda **_kwargs: ["--headless", "--no-sandbox"],
  )
  monkeypatch.setattr(
    "flare_bypasser.drissionpage_browser_wrapper.start_xvfb_display",
    lambda: None,
  )

  def fake_rmtree(path, ignore_errors=False):
    removed_dirs.append((path, ignore_errors))

  monkeypatch.setattr(
    "flare_bypasser.drissionpage_browser_wrapper.shutil.rmtree",
    fake_rmtree,
  )

  created_options = []

  def options_factory():
    options = DummyOptions()
    created_options.append(options)
    return options

  monkeypatch.setattr(
    "flare_bypasser.drissionpage_browser_wrapper.ChromiumOptions",
    options_factory,
  )

  def failing_page_factory(addr_or_opts=None):
    raise RuntimeError("boom")

  monkeypatch.setattr(
    "flare_bypasser.drissionpage_browser_wrapper.ChromiumPage",
    failing_page_factory,
  )

  try:
    asyncio.run(DrissionPageBrowserWrapper.create())
    assert False, "Expected RuntimeError"
  except RuntimeError:
    pass

  assert removed_dirs == [("/tmp/flare-bypasser-test-profile-1", True)]
  assert created_options[0].args == ["--headless", "--no-sandbox"]

  monkeypatch.setattr(
    "flare_bypasser.drissionpage_browser_wrapper.ChromiumPage",
    lambda addr_or_opts=None: DummyPage(),
  )

  wrapper = asyncio.run(DrissionPageBrowserWrapper.create())
  assert isinstance(wrapper, DrissionPageBrowserWrapper)
  assert isinstance(wrapper.get_driver(), DummyPage)
  assert wrapper._user_data_dir == "/tmp/flare-bypasser-test-profile-2"
