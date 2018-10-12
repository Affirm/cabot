#!/usr/bin/env bash
#
# Test concurrent activity-counter modification requests to make sure they
# are properly synchronized. If not, we'll get incorrect counts as requests
# clobber each other during DB writes.

set -o pipefail
set -o nounset
set -o errexit

URL='http://web:5001/api/status-checks/activity-counters?id=1000'
NUM_REQS=30
SLEEP_SEC=4
EXPECTED="\"counter.count\": $NUM_REQS"

# Setup the sample check to work with
echo "Setting up sample check"
python manage.py shell < cabot/cabotapp/tests/scripts/setup_sample_check.py

# Get the existing count
echo "Existing count"
curl -s "$URL"

# Increment 50 times
echo "Incrementing $NUM_REQS times in the background"
for NUM in $(seq 1 $NUM_REQS)
do
  curl -s "$URL&action=incr" &
done

# Wait until everything is done
echo "Sleeping for $SLEEP_SEC seconds"
sleep $SLEEP_SEC

# Check the final count
echo "Getting final count"
RESPONSE=$(curl -s "$URL")
echo "$RESPONSE"
ACTUAL=$(egrep -o '"counter.count": [0-9]+' <<< "$RESPONSE")

if [[ "$ACTUAL" = "$EXPECTED" ]]
then
  echo "SUCCESS: got expected response '$EXPECTED'"
else
  echo "FAILURE: got response '$ACTUAL', expected '$EXPECTED'"
  exit 1
fi
