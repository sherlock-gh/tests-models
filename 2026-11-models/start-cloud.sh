#!/bin/bash
# Starts one cloud model's round (README, "Rounds"), on Sherlock:
#   ./start-cloud.sh <name in models.txt> <round>      e.g. ./start-cloud.sh sonnet round1-sonnet
#   PARTS="python swift" PLAN=<folder in test2/plans> ./start-cloud.sh <name> <round>   for test 2
#   RUNS=1 ./start-cloud.sh ...   only run 1; RUNS="2 3" later makes both, the third even if 1 and 2 agree
# The hours turns may run are in cloud-hours, which cloud.sh reads before each turn: to change
# them during a round, edit it (no restart). WEEK_MAX (80) passes through to cloud.sh. Local rounds
# and other cloud rounds may run beside it. Starts cloud.sh and returns, in under 15 min (an hour
# with a plan to validate). Run again, it says the round runs already, or carries on a stopped one.
set -u
cd "$(dirname "$0")" || exit 1
NAME=${1:?usage: start-cloud.sh <name> <round>} ROUND=${2:?usage: start-cloud.sh <name> <round>}
WEEK_MAX=${WEEK_MAX:-80} PARTS=${PARTS:-1} PLAN=${PLAN:-} RUNS=${RUNS:-}
case " $PARTS " in *" python "*|*" swift "*) [ -d "test2/plans/$PLAN" ] || { echo "PLAN must name a folder in test2/plans"; exit 1; } ;; esac
grep -q "^$NAME " models.txt || { echo "models.txt has no $NAME"; exit 1; }
RUN=~/scaffolding/tests-2026-11-models-$NAME
PAGE=http://192.168.50.100:18100/tests/2026-11-models/${ROUND%%-*}/
for f in results/round*/?/runner.lock/pid; do   # this cloud round running already
    r=${f%%/?/runner.lock/pid}
    [ "$r" = "results/$ROUND" ] && [ -f "$r/cloud" ] && kill -0 "$(cat "$f")" 2>/dev/null &&
        { echo "$ROUND runs already, with the hours in cloud-hours: $(cat cloud-hours). $PAGE"; exit 0; }
done
# Test 2: its plan's checks must pass the reference and fail broken copies first, once a round (up to an hour)
if [ -n "$PLAN" ]; then
    mkdir -p results/$ROUND
    [ -f results/$ROUND/validated ] || { perl -e 'alarm 3900; exec @ARGV' ./validate.sh $PLAN && date > results/$ROUND/validated; } ||
        { echo "VALIDATION FAILED: the checks for $PLAN are wrong, so nothing started"; exit 1; }
fi
# RUNS names runs to make whatever is done: the unit's claim goes, and the third run isn't skipped
[ -z "$RUNS" ] || rm -rf results/$ROUND/claims/$NAME-1
mkdir -p "$RUN"
(ROUND=$ROUND WEEK_MAX=$WEEK_MAX PARTS="$PARTS" PLAN="$PLAN" RUNS="$RUNS" nohup caffeinate -i ./cloud.sh "$NAME" "$RUN" >> "$RUN/log.txt" 2>&1 < /dev/null &)
sleep 20
tail -3 "$RUN/log.txt"
echo "$ROUND runs on its own now: $PAGE"
