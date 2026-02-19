#!/usr/bin/env python3
import argparse
import asyncio
import importlib
import importlib.util
import pathlib
import sys
from typing import Type


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
  sys.path.insert(0, str(SRC_DIR))


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description=(
      "Test utility: create a BrowserWrapper, open a page and save a screenshot."
    )
  )
  parser.add_argument(
    "--wrapper-type",
    default="zendriver",
    help=(
      "Wrapper type: 'zendriver', 'nodriver', or full import path "
      "in the form 'module.path:ClassName'."
    ),
  )
  parser.add_argument("--url", required=True, help="Target URL to open.")
  parser.add_argument(
    "--output",
    default="wrapper_test_screenshot.png",
    help="Screenshot output path.",
  )
  parser.add_argument("--proxy", default=None, help="Optional proxy URL.")
  parser.add_argument(
    "--disable-gpu",
    action="store_true",
    help="Pass disable GPU flag to BrowserWrapper.create().",
  )
  parser.add_argument(
    "--headless",
    action="store_true",
    help="Run browser in headless mode.",
  )
  parser.add_argument(
    "--wait-seconds",
    type=float,
    default=3.0,
    help="Additional time to wait after navigation before screenshot.",
  )
  return parser.parse_args()


def _load_class_from_file(module_name: str, file_path: pathlib.Path, class_name: str) -> Type:
  if not file_path.exists():
    raise RuntimeError(f"Wrapper module file doesn't exist: {file_path}")

  spec = importlib.util.spec_from_file_location(module_name, file_path)
  if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load wrapper module from file: {file_path}")

  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)

  try:
    return getattr(module, class_name)
  except AttributeError as exc:
    raise RuntimeError(
      f"Module loaded from '{file_path}' has no class '{class_name}'."
    ) from exc


def resolve_wrapper_class(wrapper_type: str) -> Type:
  if wrapper_type == "zendriver":
    return _load_class_from_file(
      "flare_bypasser_browser_wrapper",
      SRC_DIR / "flare_bypasser" / "browser_wrapper.py",
      "BrowserWrapper",
    )

  if wrapper_type == "nodriver":
    return _load_class_from_file(
      "flare_bypasser_nodriver_browser_wrapper",
      SRC_DIR / "flare_bypasser" / "nodriver_browser_wrapper.py",
      "BrowserWrapper",
    )

  if ":" not in wrapper_type:
    raise ValueError(
      "Invalid wrapper type. Use 'zendriver', 'nodriver' or 'module.path:ClassName'."
    )

  module_name, class_name = wrapper_type.split(":", 1)
  try:
    module = importlib.import_module(module_name)
  except ModuleNotFoundError as exc:
    raise RuntimeError(
      f"Cannot import module '{module_name}' for wrapper type '{wrapper_type}'."
    ) from exc

  try:
    return getattr(module, class_name)
  except AttributeError as exc:
    raise RuntimeError(
      f"Module '{module_name}' has no class '{class_name}'."
    ) from exc


async def run_browser_test(args: argparse.Namespace) -> None:
  wrapper_class = resolve_wrapper_class(args.wrapper_type)

  browser = None
  try:
    browser = await wrapper_class.create(
      proxy=args.proxy,
      disable_gpu=args.disable_gpu,
      headless=args.headless,
    )
    await browser.get(args.url)
    if args.wait_seconds > 0:
      await asyncio.sleep(args.wait_seconds)
    await browser.save_screenshot(args.output)
    print(f"Screenshot saved: {args.output}")
  finally:
    if browser is not None:
      await browser.close()


def main() -> int:
  args = parse_args()
  asyncio.run(run_browser_test(args))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
