SERVER_URL=${SERVER_URL:-http://localhost:20080}

set -o pipefail
TMP_DIR=/tmp/flare_bypasser_tests/
mkdir -p "$TMP_DIR"


# Standard API tests.
curl -s -XPOST "$SERVER_URL"'/get_cookies' -H 'Content-Type: application/json' \
  --data-raw '{"maxTimeout": 60000, "url": "https://torrentleech.pl/login.php?returnto=%2F"}' \
  >"$TMP_DIR/get_cookies.result" 2>"$TMP_DIR/get_cookies.err" && \
  cat "$TMP_DIR/get_cookies.result" | python3 -c '
import sys, json
res=json.load(sys.stdin)
if "solution" not in res or res["solution"] is None or "cookies" not in res["solution"]:
  sys.exit(1)
' && echo "get_cookies success" || ( echo "get_cookies fail" 1>&2 ; )

curl -s -XPOST "$SERVER_URL"'/get_page' -H 'Content-Type: application/json' \
  --data-raw '{"maxTimeout": 60000, "url": "https://torrentleech.pl/login.php?returnto=%2F"}' \
  >"$TMP_DIR/get_page.result" 2>"$TMP_DIR/get_page.err" && \
  cat "$TMP_DIR/get_page.result" | python3 -c '
import sys, json
res=json.load(sys.stdin)
if "solution" not in res or res["solution"] is None or "cookies" not in res["solution"]:
  sys.exit(1)
' && echo "get_page success" || ( echo "get_page fail" 1>&2 ; )

curl -s -XPOST "$SERVER_URL"'/make_post' -H 'Content-Type: application/json' \
  --data-raw '{"maxTimeout": 60000, "url": "https://torrentleech.pl/login.php?returnto=%2F", "postData": "test=1"}' \
  >"$TMP_DIR/make_post.result" 2>"$TMP_DIR/make_post.err" && \
  cat "$TMP_DIR/make_post.result" | python3 -c '
import sys, json
res=json.load(sys.stdin)
if "solution" not in res or res["solution"] is None or "cookies" not in res["solution"]:
  sys.exit(1)
' && echo "make_post success" || ( echo "make_post fail" 1>&2 ; )


# FlareSolverr API tests.
curl -s -XPOST "$SERVER_URL"'/v1' -H 'Content-Type: application/json' \
  --data-raw '{"maxTimeout": 60000, "url": "https://torrentleech.pl/login.php?returnto=%2F", "cmd" : "request.get"}' \
  >"$TMP_DIR/v1.request.get.result" 2>"$TMP_DIR/v1.request.get.err" && \
  cat "$TMP_DIR/v1.request.get.result" | python3 -c '
import sys, json
res=json.load(sys.stdin)
if "solution" not in res or res["solution"] is None or "cookies" not in res["solution"]:
  sys.exit(1)
' && echo "request.get success" || ( echo "request.get fail" 1>&2 ; )

curl -s -XPOST "$SERVER_URL"'/v1' -H 'Content-Type: application/json' \
  --data-raw '{"maxTimeout": 60000, "url": "https://torrentleech.pl/login.php?returnto=%2F", "cmd" : "request.post", "params": {"postData": "test=1"}}' \
  >"$TMP_DIR/v1.request.post.result" 2>"$TMP_DIR/v1.request.post.err" && \
  cat "$TMP_DIR/v1.request.post.result" | python3 -c '
import sys, json
res=json.load(sys.stdin)
if "solution" not in res or res["solution"] is None or "cookies" not in res["solution"]:
  sys.exit(1)
' && echo "request.post success" || ( echo "request.post fail" 1>&2 ; )
