import argparse
import importlib
import sys
import types


sys.modules.setdefault("cv2", types.SimpleNamespace())


MODULE_NAME = "flare_bypasser.browser_wrapper_util"


def reload_module():
  if MODULE_NAME in sys.modules:
    del sys.modules[MODULE_NAME]
  return importlib.import_module(MODULE_NAME)


def test_main_uses_asyncio_run(monkeypatch):
  module = reload_module()
  args = argparse.Namespace(wrapper_type="drissionpage")
  run_calls = {"count": 0}

  monkeypatch.setattr(module, "parse_args", lambda: args)

  async def fake_run(_args):
    run_calls["count"] += 1

  monkeypatch.setattr(module, "run_browser_wrapper_util", fake_run)

  assert module.main() == 0
  assert run_calls["count"] == 1
