#!/bin/bash
# Starts a local round, on Sherlock (README, "Rounds"). Sherlock's runner acts on the model hosts
# only through inferctl (:8090, its test tokens), and Hermes asks them for completions (:8080).
# Nobody logs into a model host.
#   ./start.sh <round> [<second host's inferctl name> <its address> <its memory, GB>]
#   PLAN=<folder in test2/plans> ./start.sh ...   for test 2: the build plan every model builds,
#   whose checks validate.sh <plan> must also pass (up to an hour, once a round)
# In the foreground, usually a minute (an hour with a new plan): checks Adlerbot's inferctl lists
# every model in models.txt (Adlerbot runs every gate); finds the models a second host lists whose
# weights leave 16 GB of its memory free; runs validate.sh; starts a lane of sherlock.sh for each
# host, and returns. The round's page http://192.168.50.100:18100/tests/2026-11-models/round<n>/
# shows it; nothing after needs the owner. Run again on a running round, it adds what isn't
# running and leaves what is.
set -u
cd "$(dirname "$0")" || exit 1
ROUND=${1:?usage: start.sh <round> [<second host> <its address> <its memory GB>]} B_NAME=${2:-} B_ADDR=${3:-} B_MEM=${4:-}
[ -z "$B_NAME" ] || [ -n "$B_MEM" ] || { echo "the second host needs its name, address and memory in GB"; exit 1; }
PLAN=${PLAN:-}; [ -z "$PLAN" ] || [ -d "test2/plans/$PLAN" ] || { echo "PLAN must name a folder in test2/plans"; exit 1; }
RUNDIR=~/scaffolding/tests-2026-11-models
say() { echo "$(date '+%T') $*"; }
ictl() { perl -e 'alarm 120; exec @ARGV' python3 ~/.local/lib/lab-test-watchdog/current/inferctl/inferctl.py "$@"; }

say "the hosts' models, and the validation (a minute; with a new build plan, up to an hour)"
S=results/$ROUND; mkdir -p $S/claims $S/a
listed() { awk '!/^#/ && NF >= 5{print $1, $2}' models.txt; }   # the local models: name, model
have=$(ictl models http://192.168.40.110:8090) || { echo "Adlerbot's inferctl did not answer: nothing started"; exit 1; }
missing=$(listed | while read -r n m; do grep -qF "\"$m\"" <<< "$have" || echo "$n ($m)"; done)
[ -z "$missing" ] || { echo "Adlerbot's inferctl lacks: $missing: nothing started"; exit 1; }
{ echo "a Adlerbot 192.168.40.110"; [ -n "$B_NAME" ] && echo "b $B_NAME $B_ADDR"; } > $S/servers
SECOND=""
if [ -n "$B_NAME" ]; then   # lane b: the models the second host lists that leave 16 GB of its memory free
    hb=$(ictl models "http://$B_ADDR:8090") || { echo "$B_NAME's inferctl did not answer: nothing started"; exit 1; }
    SECOND=$(listed | while read -r n m; do
        gb=$(python3 -c 'import json, sys; print(json.loads(sys.argv[1])["models"].get(sys.argv[2]) or "")' "$hb" "$m")
        [ -n "$gb" ] && awk -v g="$gb" -v mem="$B_MEM" 'BEGIN{exit !(g + 16 <= mem)}' && echo "$n"
    done | tr '\n' ' '); SECOND=${SECOND% }
    say "lane b ($B_NAME) may run: ${SECOND:-none}"; [ -n "$SECOND" ] || B_NAME=""
fi
if [ ! -f $S/validated ]; then
    perl -e 'alarm 3600; exec @ARGV' ./validate.sh || { echo "VALIDATION FAILED: the checks are wrong, so no model is judged"; exit 1; }
    date > $S/validated
fi
if [ -n "$PLAN" ] && [ ! -f $S/validated-$PLAN ]; then
    perl -e 'alarm 3600; exec @ARGV' ./validate.sh $PLAN || { echo "VALIDATION FAILED: the checks for $PLAN are wrong, so no model is judged"; exit 1; }
    date > $S/validated-$PLAN
fi

lane() {  # lane host address, unless that lane runs
    local p; p=$(cat $S/$1/runner.lock/pid 2>/dev/null) && kill -0 "$p" 2>/dev/null && { echo "lane $1 runs already"; return 0; }
    mkdir -p "$RUNDIR"
    (ROUND=$ROUND LANE=$1 HOST=$2 SERVER=$3 SECOND_MODELS="$SECOND" PLAN="$PLAN" nohup caffeinate -i ./sherlock.sh "$RUNDIR" >> "$RUNDIR/log.txt" 2>&1 < /dev/null &)
}
lane a adlerbot 192.168.40.110 && say "lane a: on Adlerbot"
[ -n "$B_NAME" ] && lane b "$B_NAME" "$B_ADDR" && say "lane b: on $B_NAME ($B_ADDR)"
# the watch (watch.py): Claude, unattended, on every failure and lane end, whoever's session is open
pgrep -f "watch.py $ROUND\$" >/dev/null || { (nohup python3 watch.py "$ROUND" >> "$S/watch.log" 2>&1 < /dev/null &); say "the watch: $S/watch.log"; }
say "the round runs on its own now: http://192.168.50.100:18100/tests/2026-11-models/${ROUND%%-*}/"
