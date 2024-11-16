SERVER_URL=${SERVER_URL:-http://localhost:20080}

set -o pipefail
TMP_DIR=/tmp/flare_bypasser_tests/
mkdir -p "$TMP_DIR"

# Standard API tests.
function site_test {
  URL="$1"
  PROXY="$2"
  PROXY_PART=''
  if [ "$PROXY" != "" ] ; then
    PROXY_PART=',"proxy": "'"$PROXY"'"'
  fi
  curl -s -XPOST "$SERVER_URL"'/get_cookies' -H 'Content-Type: application/json' \
    --data-raw '{"maxTimeout": 60000, "url": "'"$URL"'"'"$PROXY_PART"'}' \
    >"$TMP_DIR/get_cookies.result" 2>"$TMP_DIR/get_cookies.err" && \
    cat "$TMP_DIR/get_cookies.result" | python3 -c '
import sys, json
res=json.load(sys.stdin)
if "solution" not in res or res["solution"] is None or "cookies" not in res["solution"]:
  sys.exit(1)
' && echo "$URL: success" || ( echo "$URL: fail, response:" 1>&2 ; cat "$TMP_DIR/get_cookies.result" | sed -r 's/^/  /' >&2 ; exit 1 ; )
  return $?
}

RES=0
site_test 'https://torrentleech.pl/login.php?returnto=%2F' || export RES=1
site_test 'https://xcv.ashoo.org/' || export RES=1
site_test 'https://myg.ashoo.live/' || export RES=1
site_test 'https://hdf3im.lordfilm1.pics/' || export RES=1
site_test 'https://www.ygg.re' 'socks5://91.142.74.232:40001' || export RES=1

exit $RES
