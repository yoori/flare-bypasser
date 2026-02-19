MODE=${1:-get_cookies}
SERVER_URL=${SERVER_URL:-http://localhost:20080}

set -o pipefail
TMP_DIR=/tmp/flare_bypasser_tests/
mkdir -p "$TMP_DIR"

# Standard API tests.
function site_test {
  URL="$1"
  PROXY="$2"
  PROXY_PART=''
  if [ "$PROXY" != "" ]
  then
    PRINT_PROXY=" ($PROXY)"
  fi
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  NO_COLOR='\033[0m'
  if [ "$PROXY" != "" ] ; then
    PROXY_PART=',"proxy": "'"$PROXY"'"'
  fi
  curl -s -XPOST "$SERVER_URL"'/'"$MODE" -H 'Content-Type: application/json' \
    --data-raw '{"maxTimeout": 60000, "url": "'"$URL"'"'"$PROXY_PART"'}' \
    >"$TMP_DIR/get_cookies.result" 2>"$TMP_DIR/get_cookies.err" && \
    cat "$TMP_DIR/get_cookies.result" | python3 -c '
import sys, json
res = json.load(sys.stdin)
solved = ("solution" in res and "cookies" in res["solution"])
blocked = ("status" in res and res["status"] == "error" and "message" in res and "Cloudflare has blocked" in res["message"])
cf_clearance_present = False
cookies_count = 0
if solved:
  cookies = res["solution"]["cookies"]
  cookies_count = len(cookies)
  for c in cookies:
    if c["name"] == "cf_clearance":
      cf_clearance_present = True
      break

if not solved and not blocked:
  sys.exit(1)
elif solved:
  print("solved: cf_clearance " + ("present" if cf_clearance_present else ("not present, " + str(cookies_count) + " cookies")))
else:
  print("blocked")
' >"$TMP_DIR/get_cookies.check_result.out" && \
    echo -e "$URL$PRINT_PROXY: ${GREEN}success${NO_COLOR} ($(cat "$TMP_DIR/get_cookies.check_result.out"))" || \
    ( echo -e "$URL$PRINT_PROXY: ${RED}fail${NO_COLOR}, response:" 1>&2 ; cat "$TMP_DIR/get_cookies.result" | sed -r 's/^/  /' >&2 ; echo >&2 ; exit 1 ; )
  return $?
}

RES=0
site_test 'https://torrentleech.pl/login.php?returnto=%2F' || export RES=1
site_test 'https://xcv.ashoo.org/' || export RES=1
site_test 'https://myg.ashoo.live/' || export RES=1
site_test 'https://hdf3im.lordfilm1.pics/' || export RES=1
site_test 'https://www.ygg.re' 'socks5://91.142.74.232:40001' || export RES=1
site_test 'https://ext.to/latest/' 'socks5://91.142.74.232:40001' || export RES=1
site_test 'https://prowlarr.servarr.com/v1/ping' 'socks5://91.142.74.232:40001' || export RES=1 # Expected blocked here.
site_test 'https://extratorrent.st' 'socks5://91.142.74.232:40001' || export RES=1
site_test 'https://1337x.unblockninja.com/cat/Movies/time/desc/1/' 'socks5://91.142.74.232:40001' || export RES=1
site_test 'https://solscan.io/' || export RES=1
site_test 'https://www.ygg.re/engine/search?do=search&order=desc&sort=publish_date&category=al' || export RES=1
site_test 'https://1337x.torrentbay.st/cat/Movies/time/desc/1/' 'socks5://91.142.74.232:40001' || export RES=1
site_test 'http://www.google.nl/' || export RES=1
site_test 'https://www.topps.com/' || export RES=1
site_test 'http://www.comando.la/' 'socks5://91.142.74.232:40001' || export RES=1

exit $RES
