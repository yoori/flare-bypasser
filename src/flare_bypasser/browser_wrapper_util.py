#!/usr/bin/env python3
import argparse
import asyncio

from .browser_wrapper import BrowserWrapper


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Create a BrowserWrapper, open a page, and save a screenshot."
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
    default="browser_wrapper_screenshot.png",
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


async def run_browser_wrapper_util(args: argparse.Namespace) -> None:
  browser = None
  try:
    browser = await BrowserWrapper.create_by_type(
      wrapper_type=args.wrapper_type,
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
  asyncio.run(run_browser_wrapper_util(args))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
