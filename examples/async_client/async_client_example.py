
"""
This example demonstrates how to use flare-bypasser in conjunction with the httpx module.
this approach allows you to quickly grab a large amount of information from a site (and its pages),
 without waiting for the protection to be bypassed on each page.
"""
import typing
import asyncio
import argparse
import flare_bypasser


async def main(
  *,
  urls: typing.List[str],
  solver_url: str,
  text_cut: int = 1000,
  **kwargs,
):
  async with flare_bypasser.AsyncClient(args.solver_url, **kwargs) as client:
    for solve_url_i, solve_url in enumerate(urls):
      resp = await client.get(solve_url, follow_redirects=True)
      print(f"PAGE #{solve_url_i}: url = {solve_url}, status_code = {resp.status_code}\n>>>>>>\n{resp.text[:text_cut]}")

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='flare_bypasser.AsyncClient usage example')
  parser.add_argument("urls", nargs='*', help='One or more url to visit (and solve challenge)')
  parser.add_argument("-u", "--solver-url", type=str, default="http://localhost:20080")
  parser.add_argument("-p", "--proxy", type=str, default=None)
  parser.add_argument("--text-cut", type=int, default=1000)
  parser.add_argument("--solve-with-empty-cookies", action='store_true')
  parser.set_defaults(solve_with_empty_cookies=False)
  args = parser.parse_args()
  loop = asyncio.new_event_loop()
  loop.run_until_complete(
    main(
      urls=(args.urls if args.urls else ['https://torrentleech.pl/', 'https://torrentleech.pl/faq.php']),
      text_cut=args.text_cut,
      solver_url=args.solver_url,
      proxy=args.proxy,
      solve_with_empty_cookies=args.solve_with_empty_cookies,
    )
  )
