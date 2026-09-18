#!/bin/bash
# A copy of the LAN page whose panel fetch points at a file that does not exist,
# to prove the datasets table renders even when the 2 MB file never arrives.
SRC=/staging/data_catalog
sed 's|panel_web.json?v=|panel_web_DOES_NOT_EXIST.json?v=|' "$SRC/index.html" > "$SRC/test_degraded.html"
curl -s -o /dev/null -w "test_degraded.html HTTP %{http_code}\n" http://localhost:8090/test_degraded.html
