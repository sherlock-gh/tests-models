#!/bin/bash
# Starts one cloud model's round (README, "Cloud comparison") from Dr Watson:
#   ./start-cloud.sh <name in models.txt> <round>      e.g. ./start-cloud.sh sonnet round7
# HOURS (22-7) and WEEK_MAX (80) pass through to cloud.sh. Refuses while a local round's runner is
# alive on Sherlock (it shares Sherlock and the test folder); another cloud round may run beside
# it. Otherwise copies this folder to Sherlock (only Sherlock: Adlerbot plays no part), starts
# cloud.sh there and returns. Run again, it says the round runs already, or carries on a stopped one.
set -u
cd "$(dirname "$0")" || exit 1
NAME=${1:?usage: start-cloud.sh <name> <round>} ROUND=${2:?usage: start-cloud.sh <name> <round>}
HOURS=${HOURS:-22-7} WEEK_MAX=${WEEK_MAX:-80}
grep -q "^$NAME " models.txt || { echo "models.txt has no $NAME"; exit 1; }
DIR=tests-2026-10-config RUN=scaffolding/tests-2026-10-config-$NAME   # under ~ on Sherlock
PAGE=http://192.168.50.100:18100/tests/2026-10-config/$ROUND/
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }

busy=$(capped 60 ssh sherlock "bash -s" <<EOF
cd ~/$DIR 2>/dev/null || exit 0
for f in results/round*/?/runner.lock/pid; do
    r=\${f%%/?/runner.lock/pid}
    [ -f "\$f" ] && kill -0 "\$(cat "\$f")" 2>/dev/null && { [ -f "\$r/cloud" ] && echo "cloud:\${r#results/}" || echo "local:\${r#results/}"; }
done
true
EOF
) || { echo "could not reach Sherlock: nothing started"; exit 1; }
case " $(echo $busy) " in
    *" cloud:$ROUND "*) echo "$ROUND runs already: $PAGE"; exit 0 ;;
    *" local:"*) echo "a local round's runner is alive on Sherlock ($(echo $busy)): start when it ends"; exit 1 ;;
esac
capped 600 rsync -a --exclude results/ --exclude why/ --exclude __pycache__/ ./ "sherlock:$DIR/" ||
    { echo "copy to Sherlock failed: nothing started"; exit 1; }
capped 60 ssh sherlock "mkdir -p ~/$RUN && cd ~/$DIR && (ROUND=$ROUND HOURS=$HOURS WEEK_MAX=$WEEK_MAX nohup caffeinate -i ./cloud.sh $NAME ~/$RUN >> ~/$RUN/log.txt 2>&1 < /dev/null &)" ||
    { echo "could not start cloud.sh on Sherlock"; exit 1; }
sleep 20
capped 30 ssh sherlock "tail -3 ~/$RUN/log.txt"
echo "$ROUND runs on its own now: $PAGE"
