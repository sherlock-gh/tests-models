# Shared by the test scripts, sourced on Sherlock (this folder is copied to ~/tests-2026-11-models).
# Sherlock holds no keys to the model hosts: it acts on them only through inferctl (:8090), and
# Hermes asks them for completions (:8080).
# The round is a Work board run (RUNDIR, ~/scaffolding/<run>): its log is touched while the
# runner is alive and working, so a runner that dies or sticks for 20 min reaches Telegram.
T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# A round runs as lanes, one a model server, at once (README, "Run protocol"): lane a on
# Adlerbot, lane b on SERVER=<address>. Each lane keeps its own results, why files, Hermes
# config and workspaces; the round's shared folder holds the work queue and the deadline.
ROUND=${ROUND:-round1} LANE=${LANE:-a}; export ROUND
SHARED="$T/results/$ROUND"; RES="$SHARED/$LANE"; mkdir -p "$RES"
USAGE=~/.test-usage/2026-11-models/$ROUND-$LANE
ROOT=workspaces/tests/2026-11-models/$ROUND-$LANE    # under ~
export TEST_WHY="$RES/why" TEST_USAGE="$USAGE" TEST_RES="$RES"
SERVER=${SERVER:-192.168.40.110}
URL=http://$SERVER:8080/v1 PROD_URL=http://$SERVER:8080/v1
PROD_MODEL=mlx-community/Qwen3.8-27B-4bit PROD_NAME=q27-4
# The whole round: 7 days from its first start, kept across restarts; removed when it ends.
[ -s "$SHARED/deadline" ] || echo $(( $(date +%s) + 604800 )) > "$SHARED/deadline"; DEADLINE=$(cat "$SHARED/deadline")

RUNFIX=0                                              # repairs in the current run (run_work)
say() { echo "$(date '+%F %T') [$LANE] $*"; }
model_of() { awk -v n="$1" '$1==n{print $2}' "$T/models.txt"; }
cache_of() { awk -v n="$1" '$1==n{print $3}' "$T/models.txt"; }
ctx_of() { awk -F'\t' -v n="$1" '$1==n{print $9}' "$SHARED/a/test0.tsv" 2>/dev/null; }   # measured by the gate; set in Hermes's custom_providers
swap_mb() { capped 60 python3 "$ICTL" server "$CTL" 2>/dev/null | python3 -c 'import json, sys; print(json.load(sys.stdin).get("swap_used_mb", "?"))' 2>/dev/null || echo "?"; }
hermes_ctx() {  # model: the context Hermes gives a test job's model, by Hermes's own resolver and Python
    local py; py=$(sed -n 's/^exec \([^ ]*python3\) .*/\1/p' ~/.hermes/hermes-agent/.hermes/bin/hermes)
    capped 120 "$py" -I "$T/test0/hermes_ctx.py" "$1" "$URL" 2>> "$RES/test0-calls.log" | tail -1
}
sampling_of() { awk -v n="$1" '$1==n{print $4}' "$T/models.txt"; }   # as asked of the server (serve records what it runs)
parts_of() {  # name: its tests from models.txt's tests column, one a line: 1, python, swift (2 is both)
    awk -v n="$1" '$1==n{for(i=5;i<=NF;i++) if($i=="2"){print "python"; print "swift"} else print $i}' "$T/models.txt"
}
listed() { parts_of "$1" | grep -qx "$2"; }
through() { awk -F'\t' -v n="$1" '$1==n && $NF=="yes"{f=1} END{exit !f}' "$SHARED/a/test0.tsv" 2>/dev/null; }   # Adlerbot's gate
beat() { touch "$RUNDIR/log.txt"; }
event() {  # event step status [note]: one line in the Work board's events.jsonl; the Telegram
    # bot reports each step that ends, with its note
    python3 -c 'import json, sys, time; e, s, st, n = sys.argv[1:5]; print(json.dumps({"ts": int(time.time()), "event": e, "step": s, "agent": "hermes", "delegated_by": "owner -> model tests runner", "purpose": "Model tests (tests/2026-11-models)", "status": st, "note": n}))' \
        "$1" "$2" "$3" "${4:-}" >> "$RUNDIR/events.jsonl"
}
capped() { local s=$1; shift; perl -e 'alarm shift; exec @ARGV' "$s" "$@"; }   # seconds command...: killed at the limit
stop_round() {  # why: a fault in the runner or the machine, not the model: stop this lane now
    # (the other lane carries on, and takes over what this one held)
    say "LANE STOPPED: $1"; echo "stopped: $1" > "$RES/end"
    if [ "$LANE" = a ]; then event step "round stopped" failed "$1"; event end round failed "$1"; else event step "lane $LANE" failed "$1"; fi
    ENDED=1; exit 3
}
past_deadline() { [ "$(date +%s)" -ge "$DEADLINE" ] && { say "stopped at the round's 7-day limit"; DEADLINE_HIT=1; return 0; }; return 1; }

server_ok() { curl -sf -m 20 "$URL/models" >/dev/null || { sleep 20; curl -sf -m 20 "$URL/models" >/dev/null; }; }
# The lane's host, through its inferctl (HOST: its name, whose test token Sherlock holds)
HOST=${HOST:-adlerbot} CTL=http://$SERVER:8090 TOKEN=~/.config/inferctl/${HOST:-adlerbot}.test.token
ICTL=~/.local/lib/lab-test-watchdog/current/inferctl/inferctl.py   # run as: capped <s> python3 "$ICTL" ... (capped execs a program, not a function)

serve() {  # name: the lane's host serves it, freshly started (an inferctl switch always restarts
    # the server, and returns once the model answers; 20 min at most), with its published sampling
    # and prompt cache from models.txt (8 GB at most on the second host). What the server then runs
    # (its arguments, memory and the host's swap) goes to server-<name>.json. Returns 1 when the
    # model didn't load or answer (a model result at the gate), 3 when inferctl itself failed.
    local m s c t p k out rc args=(); m=$(model_of "$1"); s=$(sampling_of "$1"); c=$(cache_of "$1"); rm -f "$RES/served"
    [ "$LANE" = a ] || { [ "${c:-0}" -gt 8 ] && c=8; }
    if [ "$s" != - ]; then IFS=/ read -r t p k <<< "$s"; args+=(--set "temp=$t" --set "top_p=$p" --set "top_k=$k"); fi
    [ "${c:-0}" != 0 ] && args+=(--set "prompt_cache_gb=$c")
    # args may be empty (Flash-Next: no settings): ${args[@]+...}, as macOS bash 3.2 calls an empty array unbound under set -u
    out=$(capped 1200 python3 "$ICTL" switch --token-file "$TOKEN" "$CTL" "$m" ${args[@]+"${args[@]}"} 2>&1); rc=$?; beat
    if [ $rc != 0 ] || [ "$(tail -1 <<< "$out")" != "$m" ]; then
        say "serve: $HOST did not serve $1: $(tr '\n' ' ' <<< "$out" | cut -c1-300)"
        grep -q "not serving" <<< "$out" && return 1
        return 3
    fi
    capped 60 python3 "$ICTL" server "$CTL" > "$RES/server-$1.json" 2>&1
    echo "$1" > "$RES/served"
}
ensure_served() { [ "$(cat "$RES/served" 2>/dev/null)" = "$1" ] && server_ok || serve "$1"; }

repo_state() { (cd ~/"$1" && git rev-parse HEAD && find . -path ./.git -prune -o -type f -exec stat -f %m {} + | sort -n | tail -1); }
asking() { netstat -an -p tcp | grep -qE "${SERVER//./\\.}\\.8080 +ESTABLISHED"; }   # a request open now, to this lane's server

# Each job names its model and its lane's server itself (-m; CUSTOM_BASE_URL, which the custom
# provider takes before config.yaml): Hermes's config is production's and never changes, so the
# lanes can't touch each other (2 Nov). HMODEL: the model id, set by the caller.

stop_jobs() { local p="$ROOT/${1:-}"; pkill -f "[${p:0:1}]${p:1}"; true; }   # this lane's only

job() {  # repo label limit prompt-file: one Hermes job, fenced to the repo and watched. Sets END:
    # done | timeout | server (not answering) | hang (no request, no Hermes message, no file change, 5 min) |
    # crash (Hermes says the turn failed, or exited nonzero without recording a completed turn) |
    # invalid (Hermes gave up on the model's invalid tool calls: the model's failure, never a
    # repair; round 2 repaired laguna-xs's 10 times as crashes) | stalled (QUIET set: the model asked
    # all along and no file changed for QUIET s; then, as at the time limit, 30 min to commit). Silences shorter than that
    # while the model is asked are work (a long file written in one go, research: 26 Oct, a 10-min
    # "circles" rule ended working runs). The round's deadline (DEADLINE) ends a job as the time
    # limit does. Each 30-s look goes to $USAGE/<label>.trace (why.py).
    local repo=$1 label=$2 limit=$3 start now pid st s lc lr ch ak hm rc u=$USAGE/"$2" tr
    tr=$u.trace; start=$(date +%s); JOB_START=$start; END=""; mkdir -p "$USAGE"
    rm -f "$u".json "$u".check "$u".check-err     # a redone label must not inherit an earlier attempt's files
    echo "$(date +%T)  start: prompt $(wc -c < "$4" | tr -d ' ') bytes, limit ${limit}s" > "$tr"
    st=$(repo_state "$repo" 2>/dev/null); lc=$start; lr=$start
    CUSTOM_BASE_URL=$URL zsh -lc 'hermes-in "$1" --provider custom -m "$4" -z "$(cat "$2")" --usage-file "$3"' job ~/"$repo" "$4" "$USAGE/$label".json "$HMODEL" \
        >> ~/"$repo".reply.txt 2>&1 < /dev/null &
    pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        sleep 30; now=$(date +%s); beat
        kill -0 "$pid" 2>/dev/null || break          # finished during the sleep: judge it as finished
        ch=same; s=$(repo_state "$repo" 2>/dev/null); [ "$s" != "$st" ] && { st=$s; lc=$now; ch=changed; }
        # The model is being asked if a request is open now, or Hermes wrote a message (a model call
        # or a tool's result) since: a 30-s look at the socket alone missed every 25-s request
        # between 3-min test runs and ended q27-4's working python run 2 as a hang (15 Nov)
        ak=no; asking && { lr=$now; ak=yes; }
        hm=$(sqlite3 -readonly "$HOME/.hermes/state.db" 'select cast(max(timestamp) as int) from messages' 2>/dev/null)
        [ -n "$hm" ] && [ "$hm" -gt "$lr" ] && [ "$hm" -ge "$start" ] && { lr=$hm; ak="${ak/no/msg}"; }
        if ! server_ok; then END=server              # an outage is the machine's, even at the limit
        elif [ $((now - start)) -ge "$limit" ] || [ "$now" -ge "${DEADLINE:-9999999999}" ]; then END=timeout
        elif [ $((now - lc)) -ge 300 ] && [ $((now - lr)) -ge 300 ]; then END=hang
        elif [ -n "${QUIET:-}" ] && [ $((now - lc)) -ge "$QUIET" ]; then END=stalled
        fi
        printf '%s  +%ss  files %s (last change %ss ago)  request open %s (last %ss ago)%s\n' "$(date +%T)" \
            $((now - start)) $ch $((now - lc)) $ak $((now - lr)) "${END:+  -> ended: $END}" >> "$tr"
        [ -n "$END" ] && { stop_jobs "${repo#"$ROOT"/}"; wait "$pid" 2>/dev/null; break; }
    done
    wait "$pid" 2>/dev/null; rc=$?
    [ -n "$END" ] && return
    END=done
    # usage: 0 a completed turn, 1 a failed one, 2 none or unreadable
    python3 -c 'import json,sys; u=json.load(open(sys.argv[1])); sys.exit(1 if u.get("failed") else 0 if u.get("completed") else 2)' "$u".json 2>/dev/null
    case $? in 1) END=crash ;; 2) [ "$rc" != 0 ] && END=crash ;; esac
    [ "$END" = crash ] && gave_up_on_calls "$4" "$start" && END=invalid
    echo "$(date +%T)  +$(($(date +%s) - start))s  Hermes exited on its own, status $rc -> $END" >> "$tr"
}

gave_up_on_calls() {  # prompt-file start: the job's Hermes session ends with Hermes refusing the
    # model's tool call ("Model generated invalid tool call: <name>")
    python3 - "$1" "$2" <<'PY'
import sqlite3, sys, time
from pathlib import Path
prompt, start = Path(sys.argv[1]).read_text().strip(), float(sys.argv[2])
con = sqlite3.connect(f"file:{Path.home() / '.hermes/state.db'}?mode=ro", uri=True)
sid = next((s for s, c in con.execute("select session_id, content from messages where role='user' and timestamp >= ? "
            "order by timestamp", (start - 5,)) if (c or "").strip() == prompt), None)
last = sid and con.execute("select content from messages where session_id=? and role='assistant' order by id desc limit 1",
                           (sid,)).fetchone()
sys.exit(0 if last and (last[0] or "").startswith("Model generated invalid tool call") else 1)
PY
}

why() {  # label repo outcome note: writes why/<label>.md (why.py); prints its one-line summary
    local w; w=$(python3 "$T/why.py" "$1" ~/"$2" "${TMPDIR:-/tmp}/2026-11-models-$ROUND-$LANE.prompt" "$JOB_START" "$(date +%s)" "$3" "$4" 2>&1) ||
        { echo "why.py failed: $(echo "$w" | tail -1)"; return; }
    echo "$w" | tail -1
}

asked() {  # label: the job made at least one model call (Hermes's usage file, api_calls)
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("api_calls", 0) > 0 else 1)' "$USAGE/$1".json 2>/dev/null
}

record() {  # json fields...: one line in results/runs.jsonl
    python3 -c 'import json,sys; print(json.dumps(dict(a.split("=",1) for a in sys.argv[1:])))' "$@" >> "$RES/runs.jsonl"
}

void_run() {  # run-id prefix: a run starting (or redone) moves any earlier milestones of it,
    # from an interrupted or machine-failed attempt, to runs-void.jsonl
    python3 - "$RES" "$1" <<'PY' || stop_round "could not clear earlier milestones of $1"
import json, sys
from pathlib import Path
f = Path(sys.argv[1]) / "runs.jsonl"; p = sys.argv[2]
if f.exists():
    ms = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    old = [m for m in ms if m.get("run", "").startswith(p)]
    if old:
        with open(f.parent / "runs-void.jsonl", "a") as v:
            v.writelines(json.dumps(m) + "\n" for m in old)
        f.write_text("".join(json.dumps(m) + "\n" for m in ms if not m.get("run", "").startswith(p)))
PY
}

# One run of a piece of work: milestones in order, each one Hermes job that must end in a commit
# and pass its check. Model failures end the run; machine failures are repaired (at most 2 a
# milestone, 4 a run: RUNFIX, which the caller zeroes once per run) and the milestone resumes
# from its last commit. A job that reaches the time limit gets one more, of 30 min, to finish the
# task it was on and commit, which is then checked like any other (the limit only stops a run
# that would never end: owner, 14 Nov). The caller defines prompt_for <milestone> (the prompt, on stdout) and
# check_for <milestone> (exit 0 = pass, 1 = the work fails; anything else is a fault in the
# check, which stops the round; note on stdout). Sets RUN to complete | failed | machine-failed,
# and WHERE to the last milestone.
run_work() {  # test name run-id repo limit milestones...
    local test=$1 name=$2 rid=$3 repo=$4 limit=$5 m tries fix t0 note out head0 last lab crc wrap
    local pf="${TMPDIR:-/tmp}/2026-11-models-$ROUND-$LANE.prompt"; shift 5
    RUN=complete; mkdir -p "$USAGE"
    for m in "$@"; do
        WHERE=$m tries=0 fix="" out="" note="" wrap=""; t0=$(date +%s)
        head0=$(git -C ~/"$repo" rev-parse HEAD)
        while :; do
            { prompt_for "$m"; [ "$tries" -gt 0 ] && echo "
Earlier work on this step was interrupted and is committed; carry on from there."
              if [ -n "$wrap" ]; then echo "
This step's time is up. Its work so far is in the repository, perhaps not yet committed: finish only the task you were in the middle of, make sure the tests pass, commit, and stop."
              else echo "
Commit when the step is done."; fi; } > "$pf"
            lab="$rid-$m-$tries${wrap:+w}"
            job "$repo" "$lab" "$([ -n "$wrap" ] && echo 1800 || echo "$limit")" "$pf"
            LAST_LABEL=$lab   # the last job's label: its usage file is $USAGE/$LAST_LABEL.json
            # A job that ended on its own without one model call never reached the model: the
            # runner or Hermes is broken, and every later job would fail the same way.
            [ "$END" = done ] && ! asked "$lab" &&
                stop_round "$rid $m ended without asking the model anything: $(why "$lab" "$repo" "never asked" ""); see why/$lab.md and ~/$repo.reply.txt"
            case $END in
                server|hang|crash)
                    RUNFIX=$((RUNFIX + 1)) fix="$fix $END"
                    (cd ~/"$repo" && git add -A && git -c user.name=runner -c user.email=runner@localhost commit -qm 'runner: work in progress, before a repair') >/dev/null 2>&1
                    if [ "$tries" -ge 2 ] || [ "$RUNFIX" -gt 4 ]; then
                        say "$rid $m: machine failure ($END), no repairs left: $(why "$lab" "$repo" "machine failure: $END" "")"
                        RUN=machine-failed; break
                    fi
                    say "$rid $m: machine failure ($END), repair $((tries + 1)): $(why "$lab" "$repo" "repair: $END" "")"
                    if [ "$END" = server ]; then serve "$name" || stop_round "$HOST did not come back with $name after an outage"; fi
                    tries=$((tries + 1))
                    continue ;;
                done)
                    # Any commit since the milestone began counts, the runner's repair commits included:
                    # work done before a repair is the model's, and a resumed job may find it finished.
                    if [ "$(git -C ~/"$repo" rev-parse HEAD)" = "$head0" ]; then out=fail note="no commit"
                    else
                        check_for "$m" > "$USAGE/$lab".check 2> "$USAGE/$lab".check-err; crc=$?
                        note=$(cat "$USAGE/$lab".check)
                        case $crc in
                            0) out=pass ;;
                            1) out=fail ;;
                            *) stop_round "the check for $rid $m failed to run (exit $crc): $(why "$lab" "$repo" "check fault" "$note"); see why/$lab.md" ;;
                        esac
                    fi ;;
                timeout|stalled)   # either limit gets the 30 min to finish and commit, then the check
                    # (README, Limits; 16 Nov: stalled went straight to fail, uncommitted, in q27-4's python run 3)
                    if [ -z "$wrap" ]; then
                        wrap=1; say "$rid $m: $([ "$END" = stalled ] && echo "no file changed for $((QUIET / 60)) min" || echo "the time limit"); one job of 30 min to finish the task in hand and commit"
                        continue
                    fi
                    out=timeout note="the limit, then the 30 min to finish and commit" ;;
                invalid) out=fail note="Hermes stopped: the model's tool calls were invalid" ;;
                *) out=$END note="" ;;
            esac
            break
        done
        record test="$test" config="$name" model="$(model_of "$name")" cache_gb="$(cache_of "$name")" sampling="$(sampling_of "$name")" \
            context="$(ctx_of "$name")" thinking=off hermes=production server="$SERVER" run="$rid" milestone="$m" \
            outcome="${out:-machine-failed}" repairs="${fix# }" seconds=$(($(date +%s) - t0)) \
            note="${note:-}" usage="$(tr -d '\n' 2>/dev/null < "$USAGE/$lab".json)"
        last=""; [ "$out" = pass ] || [ "$RUN" = machine-failed ] || last=" | $(why "$lab" "$repo" "$out" "${note:-}") | why/$lab.md"
        [ "$RUN" = machine-failed ] && last=" | why/$lab.md"
        say "$rid $m: ${out:-machine-failed} ${note:-}$last"; REASON="$m: ${out:-machine-failed} ${note:-}$last"
        [ "$RUN" = machine-failed ] && return
        [ "$out" = pass ] || { RUN=failed; return; }
    done
}

run_event() {  # run-id: the run's result, which Telegram reports
    if [ "$RUN" = complete ]; then event step "$1" done complete; else event step "$1" failed "$RUN, $REASON"; fi
}
served_or_stop() {  # name: every listed model loaded at the gate, so a load failing now is the machine
    ensure_served "$1" || stop_round "$HOST could not serve $1, which loaded at the gate"
}

new_repo() {  # repo: empty, then the caller adds its files and calls start_repo
    rm -rf ~/"$1" ~/"$1".reply.txt && mkdir -p ~/"$1"
}
# Build output never enters git, whoever commits (31 Oct: a repair commit swept .build in, and
# the check then failed on its stale cache); the agent doesn't see the rule.
start_repo() { (cd ~/"$1" && git init -q && printf '%s\n' .build/ .swiftpm/ __pycache__/ '*.pyc' .pytest_cache/ >> .git/info/exclude &&
    git add -A && git -c user.name=runner -c user.email=runner@localhost commit -qm 'task start'); }

restore_production() {  # on EXIT: stop this round's jobs; the lane's host back to its default model
    trap - EXIT INT TERM
    { stop_jobs
      capped 1200 python3 "$ICTL" reset --token-file "$TOKEN" "$CTL" && say "restored production on $HOST" ||
          say "$HOST did not take inferctl's reset: its default model is not back"
      rm -f "$RES/served"
    } >> "$RES/restore.log" 2>&1
}

# The work queue, shared by the lanes. A unit is a model's gate (lane a: speed counts as
# Adlerbot's), its test 1, or its test 2 in one language, and runs wholly on one server. A lane
# takes the next unit it can run by making claims/<name>-<part> (mkdir: two lanes never take the
# same), and marks it done there. Lane b runs only the models in SECOND_MODELS (on its server
# and fitting its memory, from start.sh), after Adlerbot's gate has passed them. A unit
# whose lane died unfinished is taken over by the other lane and starts over on its server.
CLAIMS="$SHARED/claims"; mkdir -p "$CLAIMS"
units() {  # name part, in order: the gates (lane b's models first), every model's test 1, then, once
    # PLAN names the plan test 1's grading chose, each model's test 2 builds (owner, 16 Nov: all of
    # test 1 finds the best plan before any build; round 4 had built flash-i3 after q27-4's test 1)
    local m all; all=$(awk '!/^#/ && NF{print $1}' "$T/models.txt")
    all=$(for m in $all; do [ -n "$(parts_of "$m")" ] && echo "$m"; done)   # a model with no tests isn't gated
    for m in $(for m in $all; do in_second "$m" && echo "$m"; done) $(for m in $all; do in_second "$m" || echo "$m"; done); do echo "$m gate"; done
    # the tests: lane a takes the models only it can run first, leaving lane b's to lane b (rounds 1
    # and 2 ran Gemma on Adlerbot while Adlerbot-only models waited)
    local own="" shared=""
    for m in $all; do if in_second "$m"; then shared="$shared $m"; else own="$own $m"; fi; done
    [ "$LANE" = a ] && all="$own $shared"
    for m in $all; do listed "$m" 1 && echo "$m 1"; done
    [ -n "${PLAN:-}" ] && for m in $all; do parts_of "$m" | grep -vx 1 | awk -v m="$m" '{print m, $1}'; done
    true
}
in_second() { case " ${SECOND_MODELS:-} " in *" $1 "*) return 0 ;; esac; return 1; }
lane_alive() { local p; p=$(cat "$SHARED/$1/runner.lock/pid" 2>/dev/null) && kill -0 "$p" 2>/dev/null; }
unit_owner() { cat "$CLAIMS/$1-$2/lane" 2>/dev/null; }
unit_done() { [ -f "$CLAIMS/$1-$2/done" ]; }
claim() { mkdir "$CLAIMS/$1-$2" 2>/dev/null && echo "$LANE" > "$CLAIMS/$1-$2/lane"; }
release() { rm -rf "${CLAIMS:?}/$1-$2"; }
finish_unit() { touch "$CLAIMS/$1-$2/done"; }
can_ever() {  # name part: this lane may run it, now or later
    [ "$LANE" = a ] && return 0
    [ "$2" != gate ] && in_second "$1" && { through "$1" || lane_alive a; }
}
can_run_now() {  # name part
    [ "$2" = gate ] || through "$1"
}
next_unit() {  # sets UNIT; 0 a unit to run, 1 none yet (others hold or wait on what is left), 2 nothing left for this lane
    local name part o left=""
    while read -r name part; do
        unit_done "$name" "$part" && continue
        if [ -d "$CLAIMS/$name-$part" ]; then
            o=$(unit_owner "$name" "$part")
            [ "$o" = "$LANE" ] && { UNIT="$name $part"; return 0; }   # ours, cut off by a stop: carry on
            if [ -n "$o" ] && ! lane_alive "$o" && can_ever "$name" "$part"; then
                left=1; can_run_now "$name" "$part" || continue
                say "taking over $name $part from lane $o, which stopped: it starts over here"
                release "$name" "$part"; claim "$name" "$part" && { UNIT="$name $part"; return 0; }
            fi
            left=1; continue
        fi
        can_ever "$name" "$part" || continue
        left=1
        can_run_now "$name" "$part" && claim "$name" "$part" && { UNIT="$name $part"; return 0; }
    done < <(units)
    [ -n "$left" ] && return 1
    return 2
}
skip_model() {  # name: it failed Adlerbot's gate, so none of its tests run
    local part; for part in 1 python swift; do claim "$1" "$part"; [ "$(unit_owner "$1" "$part")" = "$LANE" ] && finish_unit "$1" "$part"; done
}
now() { echo "$*" > "$RES/now"; }   # what this lane does, for the status page
