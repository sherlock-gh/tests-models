#!/bin/bash
# Starts round 5 from Dr Watson (README, "Run protocol" and "Round 5"):
#   ./start.sh   (Adlerbot only: round 5)      or   ./start.sh <second server's ssh alias> <its address>
# In the foreground, about half an hour: copies this folder to Sherlock and the servers; checks
# which models the second server holds and has the memory for; carries over the results
# round 5 builds on; runs validate.sh. Only if
# the validation passes: starts adlerbot.sh on each server and a lane on Sherlock for each, and
# returns. No round deletes a workspace: the blind review reads the complete runs. Nothing after needs the owner: the status page http://192.168.50.100:18100/tests/2026-10-config/<round>/
# shows the round. A second server that holds none of the models gets no lane. Run again on a
# running round, it adds what isn't running (a second lane) and leaves what is.
set -u
cd "$(dirname "$0")" || exit 1
B_SSH=${1:-} B_ADDR=${2:-}
ROUND=round5 PREV=round4
# What round 5 builds on: flash's gate, from round 4's lane a (engine unchanged).
CARRY0="flash"
CARRY1=""   # test 1 runs: not in this repository
DIR=tests-2026-10-config      # under ~ on each host
say() { echo "$(date '+%T') $*"; }
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }
sync_to() { capped 600 rsync -a --exclude results/ --exclude why/ --exclude __pycache__/ ./ "$1:$DIR/"; }

say "copying the test to Sherlock, Adlerbot${B_SSH:+ and $B_SSH}"
sync_to sherlock && sync_to adlerbot || { echo "copy failed: nothing started"; exit 1; }
if [ -n "$B_SSH" ]; then sync_to "$B_SSH" || { say "could not copy to $B_SSH: no second lane"; B_SSH=""; }; fi
# Weights of models dropped from the round, on each server: none in round 5 (settled models keep
# theirs until the owner says)
DROPPED=""
for h in adlerbot $B_SSH; do
    for m in $DROPPED; do capped 120 ssh "$h" "rm -rf ~/.cache/huggingface/hub/models--${m//\//--}" && say "deleted $m on $h"; done
done

# Lane b runs the models the second server holds that leave 16 GB of its memory free; Ollama
# models stay on Adlerbot. Its engine and weights are its own: each machine is tested as it is.
# Weights are counted once, in blobs/ (2 Nov: following the snapshot links counted them twice).
SECOND=""
if [ -n "$B_SSH" ]; then
    have='for m in "$@"; do d=~/.cache/huggingface/hub/models--${m//\//--}; [ -d "$d" ] && echo "$m $(du -sk "$d/blobs" | cut -f1)"; done; echo "memory $(sysctl -n hw.memsize)"'
    ids=$(awk '!/^#/ && $2 ~ /\//{print $2}' models.txt | tr '\n' ' ')   # one line: the login shell there is zsh
    sb=$(capped 300 ssh "$B_SSH" "bash -s -- $ids" <<< "$have")
    mem=$(awk '$1=="memory"{print int($2/1024)}' <<< "$sb")   # KB
    for name in $(awk '!/^#/ && $2 ~ /\//{print $1}' models.txt); do
        kb=$(awk -v m="$(awk -v n="$name" '$1==n{print $2}' models.txt)" '$1==m{print $2}' <<< "$sb")
        if [ -z "$kb" ]; then say "  $name stays on Adlerbot: not on $B_SSH"
        elif [ $((kb + 16777216)) -gt "${mem:-0}" ]; then say "  $name stays on Adlerbot: $((kb / 1048576)) GB of weights, too big for $B_SSH"
        else SECOND="$SECOND $name"; fi
    done
    SECOND=${SECOND# }; say "lane b may run: ${SECOND:-none}"
    [ -n "$SECOND" ] || B_SSH=""
fi

say "on Sherlock: carrying round 4's gate and the blind review's test 1 results over, then the validation (about 20 min, once)"
capped 3600 ssh sherlock "ROUND=$ROUND PREV=$PREV CARRY0='$CARRY0' CARRY1=$(printf %q "$CARRY1") B_NAME='$B_SSH' bash -s" <<'EOF' || { echo "nothing started: see above"; exit 1; }
set -u
cd ~/tests-2026-10-config || exit 1
R=results; S=$R/$ROUND; P=$R/$PREV/a
mkdir -p $S/claims $S/carried $S/a
{ echo "a Adlerbot"; [ -n "$B_NAME" ] && echo "b $B_NAME"; } > $S/servers
if [ ! -f $S/carried/test1.tsv ]; then
    head -1 $P/test0.tsv > $S/a/test0.tsv
    for m in $CARRY0; do
        awk -F'\t' -v m="$m" '$1==m' $P/test0.tsv | tail -1 >> $S/a/test0.tsv
        mkdir -p $S/claims/$m-gate && echo a > $S/claims/$m-gate/lane && touch $S/claims/$m-gate/done
    done
    head -1 $P/test1.tsv > $S/carried/test1.tsv
    [ -z "$CARRY1" ] || printf '%s\n' "$CARRY1" >> $S/carried/test1.tsv
    echo "carried: the gates of $CARRY0, from $PREV; test 1 $(tail -n +2 $S/carried/test1.tsv | cut -f1-3 | tr '\t\n' ' ,')"
fi
if [ ! -f $S/validated ]; then   # once: it uses round 2's work
    ./validate.sh || { echo "VALIDATION FAILED: the checks are wrong, so no model is judged"; exit 1; }
    date > $S/validated
fi
EOF

# The previous round's results, the part kept in the repo: each lane's tables, what it carried, and its page as it ended
mkdir -p rounds/$PREV && capped 300 rsync -am --include='*/' --include='test*.tsv' --exclude='*' "sherlock:$DIR/results/$PREV/" rounds/$PREV/ &&
    capped 120 rsync -a "sherlock:demo/www/tests/2026-10-config/$PREV/index.html" rounds/$PREV/ &&
    say "$PREV's results copied to rounds/$PREV/ (to commit)" || say "could not copy $PREV's results here; they stay on Sherlock in results/$PREV"

start_server() {  # ssh alias: adlerbot.sh, unless it runs, then wait (10 min) until it watches for requests
    capped 660 ssh "$1" "cd ~/$DIR && mkdir -p results && touch results/adlerbot.log && n=\$(wc -c < results/adlerbot.log) &&
        { p=\$(cat results/adlerbot.lock/pid 2>/dev/null) && kill -0 \$p 2>/dev/null && { echo 'adlerbot.sh runs there already'; exit 0; }; true; } &&
        (nohup caffeinate -i ./adlerbot.sh >> results/adlerbot.log 2>&1 < /dev/null &) &&
        until tail -c +\$((n + 1)) results/adlerbot.log | grep -q 'watching'; do
            tail -c +\$((n + 1)) results/adlerbot.log | grep -qE 'could not|another adlerbot.sh' && { tail -c +\$((n + 1)) results/adlerbot.log; exit 1; }; sleep 5; done"
}
start_server adlerbot || { echo "adlerbot.sh did not start on Adlerbot: nothing started (see its results/adlerbot.log)"; exit 1; }
if [ -n "$B_SSH" ] && ! start_server "$B_SSH"; then
    say "adlerbot.sh did not start on $B_SSH (is its own model service stopped?): no second lane"; B_SSH=""; SECOND=""
fi
lane() {  # lane server, unless that lane runs
    capped 60 ssh sherlock "cd ~/$DIR && { p=\$(cat results/$ROUND/$1/runner.lock/pid 2>/dev/null) && kill -0 \$p 2>/dev/null && { echo 'lane $1 runs already'; exit 0; }; true; } && (ROUND=$ROUND LANE=$1 SERVER=$2 SECOND_MODELS='$SECOND' nohup caffeinate -i ./sherlock.sh ~/scaffolding/tests-2026-10-config >> ~/scaffolding/tests-2026-10-config/log.txt 2>&1 < /dev/null &)"
}
lane a 192.168.40.110 && say "lane a: on Adlerbot"
[ -n "$B_SSH" ] && lane b "$B_ADDR" && say "lane b: on $B_SSH ($B_ADDR)"
say "the round runs on its own now: http://192.168.50.100:18100/tests/2026-10-config/$ROUND/"
