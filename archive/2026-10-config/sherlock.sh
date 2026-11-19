#!/bin/bash
# The survivor round, on Sherlock (README, "Run protocol"): one lane of it, LANE=a on Adlerbot or
# LANE=b on SERVER=<address>; start.sh starts both. sherlock.sh <run folder>, the Work board run
# ~/scaffolding/tests-2026-10-config, which holds the log. First a preflight: one trivial
# milestone on the production model, start to finish, so a broken runner stops before any
# result is recorded. Then units from the shared queue (lib.sh) until none is left for this lane:
# Adlerbot's gate of a model (test0/gate.py; lane a), its test 1, its test 2 per language.
# Results go to results/<round>/<lane>/ as they come, and after a stop the same command carries
# on. Finished or stopped, Hermes and the lane's server go back to production.
# Start adlerbot.sh on each server first.
set -u
RUNDIR=${1:?usage: sherlock.sh <run folder under ~/scaffolding>}; mkdir -p "$RUNDIR"
cd "$(dirname "$0")" || exit 1
source ./lib.sh; source ./test1.sh; source ./test2.sh
# One runner a lane: two at once share repos, prompts and results (26 Oct). The lock is taken
# or not; a lock left by a runner killed with -9 is removed by hand (the message says how).
mkdir "$RES/runner.lock" 2>/dev/null || { p=$(cat "$RES/runner.lock/pid" 2>/dev/null)
    echo "another sherlock.sh holds lane $LANE (pid ${p:-unknown}, $(kill -0 "${p:-0}" 2>/dev/null && echo running || echo "not running: if none is, rm -r $RES/runner.lock"))"; exit 1; }
echo $$ > "$RES/runner.lock/pid"
TSV0="$RES/test0.tsv"
[ -f "$TSV0" ] || printf 'name\tmodel\tloaded\tmemory_gb\tswap_mb\treplied\tparsed\ttok_s\tthrough\n' > "$TSV0"
rm -f "$RES/served" "$RES/end"
LIMIT=5400; [ "$LANE" = a ] || LIMIT=10800   # a milestone's backstop (time only breaks ties): the second server's is twice

ENDED=""
lane_event() {  # status note: lane a reports the round; lane b, its own lane
    if [ "$LANE" = a ]; then event "$@"; else event step "lane $LANE" "${@:2}"; fi
}
finish() { local rc=$?; [ -n "$ENDED" ] || { say "LANE STOPPED: the runner exited (status $rc)"; echo "stopped: the runner exited (status $rc)" > "$RES/end"
        lane_event end round failed "stopped, exit $rc"; }
    swift_drop; restore_production; rm -rf "$RES/runner.lock"; wait "${STATUS:-}" 2>/dev/null; python3 "$T/status.py" "$RUNDIR" 2>> "$RES/status.err"; }
trap finish EXIT
trap 'exit 130' INT TERM
lane_event start round running
# The status page (status.py, http://192.168.50.100:18100/tests/2026-10-config/<round>/): every 10 s while the lock is held
( while [ -d "$RES/runner.lock" ]; do python3 "$T/status.py" "$RUNDIR" 2>> "$RES/status.err"; sleep 10; done ) & STATUS=$!
say "runner $$ started: round $ROUND, lane $LANE, model server $SERVER; the round's limit: $(date -r "$DEADLINE" '+%F %T')${SECOND_MODELS:+; models lane b may run: $SECOND_MODELS}"

preflight() {  # proves the runner, Hermes and the lane's server work together; any failure stops the lane
    local p=q27-4; REPO="$ROOT/preflight"
    prompt_for() { echo "Create the file ok.txt containing the single word ok."; }
    check_for() { git -C ~/"$REPO" show HEAD:ok.txt 2>/dev/null | grep -qi ok && echo "ok.txt committed"; }
    say "preflight"; now p
    serve $p || stop_round "preflight: $SERVER did not serve $p (is adlerbot.sh running there?)"
    HMODEL=$(model_of $p)
    new_repo "$REPO"; echo "# Preflight" > ~/"$REPO"/README.md; start_repo "$REPO"
    run_work preflight $p preflight "$REPO" 600 P1
    [ "$RUN" = complete ] || stop_round "preflight failed ($RUN): nothing was tested; see ~/$REPO.reply.txt"
}
gate_unit() {  # name: Adlerbot's gate. Memory and swap are in Adlerbot's results/loads.tsv. Under
    # 15 tok/s, the model is out (owner, 2 Nov).
    local name=$1 model rc out replied parsed speed ok
    grep -q "^$name	" "$TSV0" && return
    model=$(model_of "$name"); say "gate: $name ($model)"; now 0 "$name"
    serve "$name"; rc=$?
    [ $rc = 2 ] && stop_round "Adlerbot did not restart for $name: is adlerbot.sh running there?"
    [ $rc = 3 ] && stop_round "Adlerbot's server did not answer for 20 minutes while asked for $name"
    if [ $rc != 0 ]; then printf '%s\t%s\tno\t\t\t\t\t\tno\n' "$name" "$model" >> "$TSV0"; return; fi
    out=$(capped 4200 python3 "$T/test0/gate.py" "$model" "$URL" 2>> "$RES/test0-calls.log") ||
        stop_round "the gate for $name lost its connection to $SERVER: see results/test0-calls.log"
    IFS=$'\t' read -r replied parsed speed <<< "$out"
    ok=no; [ "$replied" = yes ] && [ "$parsed" = 20 ] && awk -v s="$speed" 'BEGIN{exit !(s >= 15)}' && ok=yes
    printf '%s\t%s\tyes\t\t\t%s\t%s\t%s\t%s\n' "$name" "$model" "$replied" "$parsed" "$speed" "$ok" | tee -a "$TSV0"
}

preflight
while :; do
    past_deadline && break
    next_unit; rc=$?
    [ $rc = 2 ] && break
    if [ $rc = 1 ]; then now wait; sleep 60; beat; continue; fi   # the other lane holds what is left, or a gate or Swift is due
    set -- $UNIT; name=$1 part=$2
    event step "$name $part" running
    case $part in
        gate) gate_unit "$name"; through "$name" || skip_model "$name" ;;
        1) test1 "$name" ;;
        python) test2 "$name" python ;;
        swift) # one Swift run at a time on Sherlock, for both lanes (owner, 2 Nov)
            while ! swift_free; do now wait swift; sleep 60; beat; done
            swift_take; test2 "$name" swift; swift_drop ;;
    esac
    [ -n "${DEADLINE_HIT:-}" ] && break
    finish_unit "$name" "$part"; event step "$name $part" done
done
ENDED=1
if [ -n "${DEADLINE_HIT:-}" ]; then echo "incomplete: the round's 72 h limit came first" > "$RES/end"; lane_event end round failed "incomplete: the round's 72 h limit came first"; say "lane incomplete: 72 h limit"
else echo done > "$RES/end"; lane_event end round done; say "lane done"; [ "$LANE" = a ] && rm -f "$SHARED/deadline"; fi
