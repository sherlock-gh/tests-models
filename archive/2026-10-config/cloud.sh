#!/bin/bash
# The cloud comparison (README, "Cloud comparison"), on Sherlock: one frontier model on the local
# models' tests, with their prompts, checks, 90-minute milestone limit and rules for runs and
# repairs (lib.sh, test1.sh, test2.sh): test 1, then test 2 in Python and Swift, up to 3 runs
# each, the third only when the first two differ. What differs is the agent: each job is one turn
# of Claude Code (a claude-* model) or Codex (a gpt-* model) with its own defaults, fenced to its
# repo by cloud-in as Hermes is by hermes-in. No gate (test 0 checks a local server) and no 72 h
# limit: the owner's plan limits bound the round instead.
# - Turns start only in the night hours (HOURS, 22-7: from 22:00 to 07:00), so the round doesn't
#   use the plan while the owner does. A turn already running finishes.
# - A turn cut off by a usage limit is redone, as the same step, once the limit resets: the wait
#   is neither a repair nor counted against the 90 minutes.
# - No turn starts while the plan's weekly use is at WEEK_MAX percent or more (as the last turn
#   reported it): the round waits for the week to reset, keeping the rest for the owner.
# Never asks Adlerbot for anything. Started from Dr Watson by start-cloud.sh:
#   ROUND=<round> nohup caffeinate -i ./cloud.sh <name> ~/scaffolding/tests-2026-10-config-<name>
# A round of its own, so the blind review (blind.py) sets its complete runs beside the local
# models'. Results in results/<round>/a/; after a stop, the same command carries on.
set -u
NAME=${1:?usage: cloud.sh <name in models.txt> <run folder under ~/scaffolding>}
RUNDIR=${2:?usage: cloud.sh <name in models.txt> <run folder under ~/scaffolding>}; mkdir -p "$RUNDIR"
cd "$(dirname "$0")" || exit 1
export ROUND=${ROUND:?ROUND=roundN} LANE=a ROUND_MODELS="$NAME 1 2"   # ROUND_MODELS: the page's rows (status.py)
HOURS=${HOURS:-22-7} WEEK_MAX=${WEEK_MAX:-80}
source ./lib.sh; source ./test1.sh; source ./test2.sh
HMODEL=$(model_of "$NAME"); [ -n "$HMODEL" ] || { echo "models.txt has no $NAME line"; exit 1; }
case $HMODEL in
    claude-*) AGENT=claude LABEL=Claude-Code SERVED=anthropic HANG=300 ;;   # streams token by token
    gpt-*) AGENT=codex LABEL=Codex SERVED=openai HANG=900 ;;   # reports each step as it ends: longer silences
    *) echo "$NAME ($HMODEL) is neither a claude-* nor a gpt-* model"; exit 1 ;;
esac
AV=$("$HOME/.local/bin/$AGENT" --version 2>/dev/null | awk '{print $NF}')

# lib.sh's model-server, Hermes and 72 h parts, for a cloud agent. Nothing here may reach Adlerbot.
serve() { true; }; ensure_served() { true; }; served_or_stop() { true; }; server_ok() { true; }
rm -f "$SHARED/deadline"; past_deadline() { return 1; }
restore_production() { trap - EXIT INT TERM; stop_jobs; }
stop_jobs() {  # the job running now, with everything it started (its process group)
    local g; g=$(cat "$USAGE/job.pgid" 2>/dev/null) || return 0
    kill -TERM -- "-$g" 2>/dev/null; sleep 5; kill -KILL -- "-$g" 2>/dev/null; rm -f "$USAGE/job.pgid"; true
}
# One Swift build at a time across the cloud rounds, which may run together
SWIFTLOCK=$T/results/swift-cloud.lock
swift_free() { local p; p=$(cat "$SWIFTLOCK/pid" 2>/dev/null) || return 0; kill -0 "$p" 2>/dev/null && [ "$p" != $$ ] && return 1; return 0; }
swift_take() { rm -rf "$SWIFTLOCK"; mkdir "$SWIFTLOCK" && echo $$ > "$SWIFTLOCK/pid"; }
swift_drop() { [ "$(cat "$SWIFTLOCK/pid" 2>/dev/null)" = $$ ] && rm -rf "$SWIFTLOCK"; true; }
event() {
    python3 -c 'import json, sys, time; e, s, st, n, a = sys.argv[1:6]; print(json.dumps({"ts": int(time.time()), "event": e, "step": s, "agent": a, "delegated_by": "owner -> cloud comparison runner", "purpose": "Cloud comparison (tests/2026-10-config)", "status": st, "note": n}))' \
        "$1" "$2" "$3" "${4:-}" "$AGENT" >> "$RUNDIR/events.jsonl"
}
record() {  # run_work's fields, saying what ran: the agent, not Hermes on a local server
    local a out=()
    for a in "$@"; do
        case $a in
            cache_gb=*|context=*) ;;
            thinking=*) out+=("thinking=$AGENT default") ;;
            hermes=*) out+=("agent=$AGENT $AV, fenced by cloud-in") ;;
            server=*) out+=("server=$SERVED") ;;
            *) out+=("$a") ;;
        esac
    done
    python3 -c 'import json,sys; print(json.dumps(dict(a.split("=",1) for a in sys.argv[1:])))' "${out[@]}" >> "$RES/runs.jsonl"
}
why() { python3 "$T/cloud_turn.py" why "$AGENT" "$1" ~/"$2" "$3" "$4" "$USAGE" "$TEST_WHY" || echo "why: could not write why/$1.md"; }

in_hours() { local h a=${HOURS%-*} b=${HOURS#*-}; h=$((10#$(date +%H)))
    if [ "$a" -le "$b" ]; then [ "$h" -ge "$a" ] && [ "$h" -lt "$b" ]; else [ "$h" -ge "$a" ] || [ "$h" -lt "$b" ]; fi; }
hold() {  # trace [until]: wait, beating, until the time given (a reset) has passed, the night hours
    # allow a turn and the weekly use is under WEEK_MAX. The page and Telegram say what it waits for.
    local tr=$1 until=${2:-0} w why said="" saved; saved=$(cat "$RES/now" 2>/dev/null)
    while :; do
        w=$(python3 "$T/cloud_turn.py" week "$USAGE/limits.json" 2>/dev/null)
        if [ "$(date +%s)" -lt "$until" ]; then why="the usage limit, which resets $(date -r "$until" '+%a %H:%M')"
        elif [ -n "$w" ] && [ "${w%% *}" -ge "$WEEK_MAX" ] && [ "$(date +%s)" -lt "${w##* }" ]; then
            why="weekly use at ${w%% *}%, the cap is $WEEK_MAX%; the week resets $(date -r "${w##* }" '+%a %H:%M')"
        elif ! in_hours; then why="the night hours ($HOURS)"
        else break; fi
        [ "$why" != "$said" ] && { say "waiting for $why"; echo "$(date +%T)  waiting for $why" >> "$tr"
            event step waiting running "$why"; echo "w $why" > "$RES/now"; said=$why; }
        sleep 60; beat
    done
    [ -n "$said" ] && echo "$saved" > "$RES/now"; true
}

turn() {  # repo u limit prompt-file: one agent turn, watched. Sets END to timeout | hang (no file
    # change and no output for HANG seconds) or nothing, TURN_RC, and adds its time to WORKED.
    local repo=$1 u=$2 limit=$3 start now pid st s lc la sz sz0=0 ch tr=$2.trace
    start=$(date +%s); END=""; st=$(repo_state "$repo" 2>/dev/null); lc=$start; la=$start
    case $AGENT in
        claude) perl -e 'setpgrp(0, 0); exec @ARGV' "$T/cloud-in" claude ~/"$repo" -p "$(cat "$4")" --model "$HMODEL" \
                    --dangerously-skip-permissions --output-format stream-json --verbose --include-partial-messages \
                    > "$u".stream 2>> ~/"$repo".reply.txt < /dev/null & ;;
        codex) perl -e 'setpgrp(0, 0); exec @ARGV' "$T/cloud-in" codex ~/"$repo" exec --json -m "$HMODEL" \
                    --dangerously-bypass-approvals-and-sandbox "$(cat "$4")" \
                    > "$u".stream 2>> ~/"$repo".reply.txt < /dev/null & ;;
    esac
    pid=$!; echo "$pid" > "$USAGE/job.pgid"
    while kill -0 "$pid" 2>/dev/null; do
        sleep 30; now=$(date +%s); beat
        kill -0 "$pid" 2>/dev/null || break
        ch=same; s=$(repo_state "$repo" 2>/dev/null); [ "$s" != "$st" ] && { st=$s; lc=$now; ch=changed; }
        sz=$(stat -f %z "$u".stream 2>/dev/null || echo 0); [ "$sz" != "$sz0" ] && { sz0=$sz; la=$now; }
        if [ $((now - start)) -ge "$limit" ]; then END=timeout
        elif [ $((now - lc)) -ge "$HANG" ] && [ $((now - la)) -ge "$HANG" ]; then END=hang
        fi
        printf '%s  +%ss  files %s (last change %ss ago)  output %s bytes (last %ss ago)%s\n' "$(date +%T)" \
            $((now - start)) $ch $((now - lc)) "$sz" $((now - la)) "${END:+  -> ended: $END}" >> "$tr"
        [ -n "$END" ] && { stop_jobs; wait "$pid" 2>/dev/null; break; }
    done
    wait "$pid" 2>/dev/null; TURN_RC=$?; rm -f "$USAGE/job.pgid"
    WORKED=$((WORKED + $(date +%s) - start))
}

job() {  # repo label limit prompt-file: the step's turn, as lib.sh's job runs Hermes's. Sets END:
    # done | timeout | hang | crash (the agent reports an error, as an API failure does, or ends
    # without a result). A turn a usage limit cut off is kept as <label>.w<k>.* and redone, from
    # the repo as it stands, once the limit resets. The turn streams to $USAGE/<label>.stream;
    # its result goes to <label>.json and its last message to the repo's .reply.txt. A turn on any
    # model but HMODEL stops the round: it would not be the model under test.
    local repo=$1 label=$2 limit=$3 pf=$4 u=$USAGE/"$2" tr k=0 m r f
    tr=$u.trace; JOB_START=$(date +%s); END=""; WORKED=0; mkdir -p "$USAGE"
    rm -f "$u".json "$u".check "$u".check-err "$u".stream "$u".w*.stream "$u".w*.json "$u".prompt
    echo "$(date +%T)  start: prompt $(wc -c < "$pf" | tr -d ' ') bytes, limit ${limit}s of work" > "$tr"
    while :; do
        hold "$tr"
        if [ "$WORKED" -ge "$limit" ]; then END=timeout; break; fi
        turn "$repo" "$u" $((limit - WORKED)) "$pf"
        python3 "$T/cloud_turn.py" parse "$AGENT" "$u".stream "$u".json ~/"$repo".reply.txt "$USAGE/limits.json" "$AV"
        m=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["model"])' "$u".json 2>/dev/null)
        [ -z "$m" ] || [[ $m == "$HMODEL"* ]] || stop_round "$label ran on $m, not $HMODEL: no result recorded"
        r=$(python3 -c 'import json,sys; u=json.load(open(sys.argv[1])); print(u.get("resets") or 1 if u.get("limited") else "")' "$u".json 2>/dev/null)
        [ -n "$r" ] || break
        k=$((k + 1)); for f in stream json; do mv "$u.$f" "$u.w$k.$f"; done
        echo "$(date +%T)  a usage limit cut the turn off: redone once it resets" >> "$tr"
        say "$label: a usage limit cut the turn off; the step is redone once it resets"
        [ -f "$u".prompt ] || { cat "$pf"; echo "
A usage limit interrupted earlier work on this step; carry on from the repo as it stands."; } > "$u".prompt
        pf=$u.prompt; END=""
        hold "$tr" $(( r > 1 ? r + 60 : $(date +%s) + 1800 ))
    done
    [ -n "$END" ] && return
    END=done
    python3 -c 'import json,sys; u=json.load(open(sys.argv[1])); sys.exit(1 if u.get("failed") else 0 if u.get("completed") else 2)' "$u".json 2>/dev/null
    case $? in 1) END=crash ;; 2) [ "$TURN_RC" != 0 ] && END=crash ;; esac
    echo "$(date +%T)  +$(($(date +%s) - JOB_START))s  $LABEL exited on its own, status $TURN_RC -> $END" >> "$tr"
}

# One runner a round (as sherlock.sh's lock)
mkdir "$RES/runner.lock" 2>/dev/null || { p=$(cat "$RES/runner.lock/pid" 2>/dev/null)
    echo "another runner holds $ROUND (pid ${p:-unknown}, $(kill -0 "${p:-0}" 2>/dev/null && echo running || echo "not running: if none is, rm -r $RES/runner.lock"))"; exit 1; }
echo $$ > "$RES/runner.lock/pid"
echo "$NAME" > "$SHARED/cloud"   # start-cloud.sh: a cloud round, which may run beside another
echo "a $LABEL" > "$SHARED/servers"
rm -f "$RES/end"
LIMIT=5400   # a milestone's backstop, as lane a's (sherlock.sh)
ENDED=""
finish() { local rc=$?; [ -n "$ENDED" ] || { say "STOPPED: the runner exited (status $rc)"; echo "stopped: the runner exited (status $rc)" > "$RES/end"
        event end round failed "stopped, exit $rc"; }
    swift_drop; restore_production; rm -rf "$RES/runner.lock"; wait "${STATUS:-}" 2>/dev/null; python3 "$T/status.py" "$RUNDIR" 2>> "$RES/status.err"; }
trap finish EXIT
trap 'exit 130' INT TERM
event start round running
( while [ -d "$RES/runner.lock" ]; do python3 "$T/status.py" "$RUNDIR" 2>> "$RES/status.err"; sleep 10; done ) & STATUS=$!
say "runner $$ started: $ROUND, $HMODEL through $LABEL $AV; turns from ${HOURS%-*}:00 to ${HOURS#*-}:00, none while weekly use is $WEEK_MAX% or more"

# Preflight: one trivial step, start to finish, so a broken runner, fence or sign-in stops the
# round before any result is recorded
REPO="$ROOT/preflight"
prompt_for() { echo "Create the file ok.txt containing the single word ok."; }
check_for() { git -C ~/"$REPO" show HEAD:ok.txt 2>/dev/null | grep -qi ok && echo "ok.txt committed"; }
say "preflight"; now p
new_repo "$REPO"; echo "# Preflight" > ~/"$REPO"/README.md; start_repo "$REPO"
run_work preflight "$NAME" preflight "$REPO" 600 P1
[ "$RUN" = complete ] || stop_round "preflight failed ($RUN): nothing was tested; see ~/$REPO.reply.txt and $USAGE/preflight-P1-*"

for part in 1 python swift; do
    unit_done "$NAME" "$part" && continue
    claim "$NAME" "$part" || [ "$(unit_owner "$NAME" "$part")" = "$LANE" ] || continue
    event step "$NAME $part" running
    case $part in
        1) test1 "$NAME" ;;
        python) test2 "$NAME" python ;;
        swift) while ! swift_free; do now w "Swift, which the other cloud round is building"; sleep 60; beat; done
            swift_take; test2 "$NAME" swift; swift_drop ;;
    esac
    finish_unit "$NAME" "$part"; event step "$NAME $part" done
done
ENDED=1
echo done > "$RES/end"; event end round done; say "done"
