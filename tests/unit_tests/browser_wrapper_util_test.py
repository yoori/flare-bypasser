import argparse
import asyncio
import importlib
import sys
import types


sys.modules.setdefault("cv2", types.SimpleNamespace())


MODULE_NAME = "flare_bypasser.browser_wrapper_util"


def reload_module():
  if MODULE_NAME in sys.modules:
    del sys.modules[MODULE_NAME]
  return importlib.import_module(MODULE_NAME)


def test_main_uses_nodriver_loop(monkeypatch):
  module = reload_module()
  args = argparse.Namespace(wrapper_type="nodriver")
  run_calls = {"count": 0}
  loop_calls = {"count": 0}

  monkeypatch.setattr(module, "parse_args", lambda: args)

  async def fake_run(_args):
    run_calls["count"] += 1

  monkeypatch.setattr(module, "run_browser_wrapper_util", fake_run)

  class DummyLoop:
    def run_until_complete(self, coro):
      loop_calls["count"] += 1
      asyncio.run(coro)

  monkeypatch.setitem(sys.modules, "nodriver", types.SimpleNamespace(loop=lambda: DummyLoop()))

  assert module.main() == 0
  assert run_calls["count"] == 1
  assert loop_calls["count"] == 1


def test_main_falls_back_to_asyncio_run(monkeypatch):
  module = reload_module()
  args = argparse.Namespace(wrapper_type="nodriver")
  run_calls = {"count": 0}

  monkeypatch.setattr(module, "parse_args", lambda: args)

  async def fake_run(_args):
    run_calls["count"] += 1

  monkeypatch.setattr(module, "run_browser_wrapper_util", fake_run)

  if "nodriver" in sys.modules:
    del sys.modules["nodriver"]

  assert module.main() == 0
  assert run_calls["count"] == 1
