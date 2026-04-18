#!/bin/bash
# Weekly full batch (rebalances portfolio when batch completes — do not run rebalance again).
# After batch: refresh AI market summary.
#
# Crontab (Sunday 02:00 server time):
#   0 2 * * 0 cd /root/stock_platform && API_URL=https://nestleap.au ADMIN_KEY=your_key ./scripts/weekly-batch.sh >> /var/log/nestleap-weekly.log 2>&1

set -e

API_URL="${API_URL:-https://nestleap.au}"
ADMIN_KEY="${ADMIN_KEY:?Set ADMIN_KEY}"

echo "[$(date -Iseconds)] Starting weekly batch..."
curl -sf -X POST "$API_URL/api/admin/batch/run" \
  -H "X-Admin-Key: $ADMIN_KEY" || { echo "Failed to start batch"; exit 1; }

echo "[$(date -Iseconds)] Waiting for batch to finish..."
while true; do
  sleep 30
  STATUS=$(curl -sf "$API_URL/api/batch/status")
  RUNNING=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['running'])")
  COMPLETED=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['completed'])")
  TOTAL=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")
  echo "[$(date -Iseconds)] Batch progress: $COMPLETED/$TOTAL"
  if [ "$RUNNING" = "False" ]; then
    break
  fi
done

echo "[$(date -Iseconds)] Batch done. Refreshing market summary..."
curl -sf -X POST "$API_URL/api/admin/market-summary" \
  -H "X-Admin-Key: $ADMIN_KEY" > /dev/null || echo "Market summary request failed (non-fatal)"

echo "[$(date -Iseconds)] Weekly job finished."
