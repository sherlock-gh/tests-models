#!/bin/bash
# A local round of the model tests, on Sherlock (README, "Rounds"): one lane of it, LANE=a on Adlerbot or
# LANE=b on SERVER=<address>; start.sh starts both. sherlock.sh <run folder>, the Work board run
# ~/scaffolding/tests-2026-11-models, which holds the log. First a preflight: one trivial
# milestone on the production model, start to finish, so a broken runner stops before any
# result is recorded. Then units from the shared queue (lib.sh) until none is left for this lane:
# every model's gate (test0/gate.py; lane a), then every model's test 1; without PLAN the lane
# ends there, for test 1's plans to be graded; with PLAN, the plan grading chose, test 2's builds
# (test2.sh) for the models whose tests column holds 2.
# Results go to results/<round>/<lane>/ as they come, and after a stop the same command carries
# on. Finished or stopped, Hermes and the lane's server go back to production.
set -u
RUNDIR=${1:?usage: sherlock.sh <run folder under ~/scaffolding>}; mkdir -p "$RUNDIR"
cd "$(dirname "$0")" || exit 1
source ./lib.sh; source ./test1.sh
[ -n "${PLAN:-}" ] && source ./test2.sh
# One runner a lane: two at once share repos, prompts and results (26 Oct). The lock is taken
# or not; a lock left by a runner killed with -9 is removed by hand (the message says how).
mkdir "$RES/runner.lock" 2>/dev/null || { p=$(cat "$RES/runner.lock/pid" 2>/dev/null)
    echo "another sherlock.sh holds lane $LANE (pid ${p:-unknown}, $(kill -0 "${p:-0}" 2>/dev/null && echo running || echo "not running: if none is, rm -r $RES/runner.lock"))"; exit 1; }
echo $$ > "$RES/runner.lock/pid"
TSV0="$RES/test0.tsv"
[ -f "$TSV0" ] || printf 'name\tmodel\tloaded\tmemory_gb\tswap_mb\treplied\tparsed\ttok_s\tcontext\thermes_job\tthrough\n' > "$TSV0"
rm -f "$RES/served" "$RES/end"
# A milestone isn't timed (time only breaks ties): it ends when its model has changed no file for
# 2 h, 4 h on the second server (QUIET, job in lib.sh), or at the round's 7-day limit. 15 Nov: the
# 90-min limit ended all 8 jobs it ever ended mid-work (none 16 min without a file change), and
# every local test 2 M1 run; jobs that finished on their own went up to 26 min (69 on lane b) without one.
LIMIT=604800 QUIET=7200; [ "$LANE" = a ] || QUIET=14400

ENDED=""
lane_event() {  # status note: lane a reports the round; lane b, its own lane
    if [ "$LANE" = a ]; then event "$@"; else event step "lane $LANE" "${@:2}"; fi
}
finish() { local rc=$?; [ -n "$ENDED" ] || { say "LANE STOPPED: the runner exited (status $rc)"; echo "stopped: the runner exited (status $rc)" > "$RES/end"
        lane_event end round failed "stopped, exit $rc"; }
    restore_production; rm -rf "$RES/runner.lock"; wait "${STATUS:-}" 2>/dev/null; python3 "$T/status.py" "$RUNDIR" 2>> "$RES/status.err"; }
trap finish EXIT
trap 'exit 130' INT TERM
lane_event start round running
# The round's page exists from the start, and the tests index (/tests/, site.py) links it (15 Nov: round 4's wasn't)
python3 "$T/status.py" "$RUNDIR" 2>> "$RES/status.err"; python3 "$T/../site.py" > /dev/null 2>> "$RES/status.err"
# The round's page (status.py, http://192.168.50.100:18100/tests/2026-11-models/round<n>/): every 10 s while the lock is held
( while [ -d "$RES/runner.lock" ]; do python3 "$T/status.py" "$RUNDIR" 2>> "$RES/status.err"; sleep 10; done ) & STATUS=$!
say "runner $$ started: round $ROUND, lane $LANE, model server $SERVER; the round's limit: $(date -r "$DEADLINE" '+%F %T')${SECOND_MODELS:+; models lane b may run: $SECOND_MODELS}"

preflight() {  # proves the runner, Hermes and the lane's server work together; any failure stops the lane
    local p=q27-4; REPO="$ROOT/preflight"
    prompt_for() { echo "Create the file ok.txt containing the single word ok."; }
    check_for() { git -C ~/"$REPO" show HEAD:ok.txt 2>/dev/null | grep -qi ok && echo "ok.txt committed"; }
    say "preflight"; now p
    serve $p || stop_round "preflight: $HOST did not serve $p through inferctl"
    HMODEL=$(model_of $p)
    new_repo "$REPO"; echo "# Preflight" > ~/"$REPO"/README.md; start_repo "$REPO"
    run_work preflight $p preflight "$REPO" 600 P1
    [ "$RUN" = complete ] || stop_round "preflight failed ($RUN): nothing was tested; see ~/$REPO.reply.txt"
}
gate_unit() {  # name: Adlerbot's gate, the smoke test of everything the tests use with this model. In order,
    # each only once the last passed: inferctl serves it by its models.txt name; 20 tool calls parse
    # and it reaches 15 tok/s (owner, 2 Nov); it answers a long prompt in full at 128K, else 64K
    # (test0/ctx.py, 60 min a try, each on a freshly started server, swap no higher after); that
    # context goes into Hermes (ctx_apply.py) and Hermes's own resolver must give it back; then one
    # Hermes job through run_work, as every test runs, that hands its step to a subagent and commits.
    # A fault that isn't the model's (inferctl, Hermes ignoring the context, a subagent that doesn't
    # start, a job that never asks the model, a check that can't run) stops the round.
    local name=$1 model rc out replied parsed speed ctx="" job="-" ok=no n r res pt secs note s0 s1 sid called kids
    grep -q "^$name	" "$TSV0" && return
    model=$(model_of "$name"); say "gate: $name ($model)"; now 0 "$name"
    serve "$name"; rc=$?
    [ $rc = 3 ] && stop_round "inferctl on $HOST failed while asked for $name (see the log line above)"
    if [ $rc != 0 ]; then printf '%s\t%s\tno\t\t\t\t\t\t\t-\tno\n' "$name" "$model" >> "$TSV0"; return; fi
    out=$(capped 4200 python3 "$T/test0/gate.py" "$model" "$URL" 2>> "$RES/test0-calls.log") ||
        stop_round "the gate for $name lost its connection to $SERVER: see results/test0-calls.log"
    IFS=$'\t' read -r replied parsed speed <<< "$out"
    if [ "$replied" = yes ] && [ "$parsed" = 20 ] && awk -v s="$speed" 'BEGIN{exit !(s >= 15)}'; then
        for n in 131072 65536; do
            s0=$(swap_mb); say "gate: $name at $((n / 1024))K tokens"
            r=$(capped 3600 python3 "$T/test0/ctx.py" "$model" "$URL" $n 2>> "$RES/test0-calls.log" | tail -1); s1=$(swap_mb)
            [ -n "$r" ] || r="fail			the try's 60 min ran out"
            IFS=$'\t' read -r res pt secs note <<< "$r"
            say "gate: $name at $((n / 1024))K: $res ($pt prompt tokens, ${secs}s, swap $s0 -> $s1 MB) $note"
            [ "$res" = pass ] && awk -v a="$s0" -v b="$s1" 'BEGIN{exit !(b + 0 <= a + 64)}' && { ctx=$n; break; }   # 64 MB: noise
            serve "$name"; rc=$?   # a server left on a prompt nobody waits for answers the next one late (14 Nov)
            [ $rc = 3 ] && stop_round "inferctl on $HOST failed while asked for $name again"
            [ $rc = 0 ] || stop_round "$name loaded once and then not again: the machine's fault"
        done
    fi
    if [ -n "$ctx" ]; then
        capped 60 python3 "$T/ctx_apply.py" "$model" "$ctx" "$URL" || stop_round "ctx_apply.py could not set $name's context in Hermes"
        r=$(hermes_ctx "$model")
        [ "$r" = "$ctx" ] || stop_round "Hermes would give $name ${r:-no} context, not the gate's $ctx: see results/test0-calls.log"
        REPO="$ROOT/gate-$name" HMODEL=$model
        prompt_for() { echo "Use the delegate_task tool to hand this step to a subagent: create the file gate.txt containing the single word ready. When the subagent is done, check that gate.txt holds ready, then commit it."; }
        check_for() { git -C ~/"$REPO" show HEAD:gate.txt 2>/dev/null | grep -qi ready && echo "gate.txt committed"; }
        new_repo "$REPO"; echo "# Gate" > ~/"$REPO"/README.md; start_repo "$REPO"
        RUNFIX=0; run_work gate "$name" "gate-$name" "$REPO" 1800 G1
        [ "$RUN" = machine-failed ] && stop_round "the gate's Hermes job for $name: machine failure: $REASON"
        sid=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get("session_id", ""))' "$USAGE/$LAST_LABEL.json" 2>/dev/null)
        called=$(sqlite3 ~/.hermes/state.db "select count(*) from messages where session_id='$sid' and tool_calls like '%delegate_task%'" 2>/dev/null)
        kids=$(sqlite3 ~/.hermes/state.db "select count(*) from sessions where parent_session_id='$sid'" 2>/dev/null)
        [ "${called:-0}" -gt 0 ] && [ "${kids:-0}" = 0 ] &&
            stop_round "$name called delegate_task and no subagent started (Hermes session $sid): Hermes's subagents are broken"
        if [ "$RUN" = complete ]; then
            job="complete"; [ "${kids:-0}" -gt 0 ] && job="$job, with a subagent" || job="$job, no subagent used"; ok=yes
        else job="failed: $(cut -c1-120 <<< "$REASON" | tr '\t' ' ')"; fi
    fi
    printf '%s\t%s\tyes\t\t\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$model" "$replied" "$parsed" "$speed" "$ctx" "$job" "$ok" | tee -a "$TSV0"
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
        python|swift) test2 "$name" "$part" ;;   # queued only with PLAN (units, lib.sh)
        *) stop_round "models.txt lists $name for $part, which this runner has no test for yet" ;;
    esac
    [ -n "${DEADLINE_HIT:-}" ] && break
    finish_unit "$name" "$part"; event step "$name $part" done
done
ENDED=1
if [ -n "${DEADLINE_HIT:-}" ]; then echo "incomplete: the round's 7-day limit came first" > "$RES/end"; lane_event end round failed "incomplete: the round's 7-day limit came first"; say "lane incomplete: 7-day limit"
else echo done > "$RES/end"; lane_event end round done; say "lane done"; [ "$LANE" = a ] && rm -f "$SHARED/deadline"; fi
