
"""
This example demonstrates how to use flare-bypasser in conjunction with the httpx module.
this approach allows you to quickly grab a large amount of information from a site (and its pages),
 without waiting for the protection to be bypassed on each page.
"""
import asyncio
import argparse
import flare_bypasser


async def main(solver_url: str, proxy: str):
  async with flare_bypasser.AsyncClient(args.solver_url, proxy=proxy) as client:
    resp1 = await client.get("https://torrentleech.pl/", follow_redirects=True)
    print("PAGE 1: status_code = " + str(resp1.status_code) + "\n>>>>>>\n" + resp1.text[:1000])
    resp2 = await client.get("https://torrentleech.pl/faq.php")
    print("PAGE 2: status_code = " + str(resp2.status_code) + "\n>>>>>>\n" + resp2.text[:1000])

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='flare_bypasser.AsyncClient usage example')
  parser.add_argument("-u", "--solver-url", type=str, default="http://localhost:20080")
  parser.add_argument("-p", "--proxy", type=str, default=None)
  args = parser.parse_args()
  loop = asyncio.new_event_loop()
  loop.run_until_complete(main(args.solver_url, args.proxy))
