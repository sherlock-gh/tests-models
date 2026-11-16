# Test 1, project management (README, "Project management"), sourced by sherlock.sh and cloud.sh.
# For one model, up to 3 runs; a run is one task, the problem in test1/problem.md, in a fresh repo
# ~/$ROOT/test1-<model>-r<n>/cleaning/, through four milestones. A model failure ends the run.
# Writes results/test1.tsv (one line a run) and results/runs.jsonl (one line a milestone).
TSV1="$RES/test1.tsv"; [ -f "$TSV1" ] || printf 'config\trun\tresult\tstopped at\n' > "$TSV1"
TASK1=cleaning
# Each step's prompt: its section of test1/prompts.md, then the section "Every step". The prompts say
# to read the skill as a file: "Follow <path>" sent models to Hermes's skill lookup, which found
# nothing, and they stopped. Gaps in the problem go to the owner in questions.md, and every step
# ends in a commit (owner, 12 Nov).
section() { awk -v s="$1" '/^## /{on=(substr($0,4)==s); next} on' "$T/test1/prompts.md" | sed '/./,$!d'; }
t1_prompt() { section "$1"; section "Every step"; }
t1_check() {  # 0 pass, 1 the work falls short, else the check failed (a timeout: the check's fault)
    local r; capped 900 python3 "$T/test1/check.py" ~/"$REPO" "$1"; r=$?
    [ $r = 142 ] && { echo "check timed out"; r=3; }
    return $r
}

t1_run() {  # name run
    local name=$1 rid="test1-$1-r$2"
    prompt_for() { t1_prompt "$@"; }; check_for() { t1_check "$@"; }
    # A fresh server for each run: MLX crashed on its GPU buffer limit after hours of serving
    serve "$name" || stop_round "$SERVER could not serve $name, which loaded at the gate"
    RUNFIX=0; void_run "$rid-"
    HMODEL=$(model_of "$name")
    REPO="$ROOT/$rid/$TASK1"
    new_repo "$REPO"
    cp -R "$T/test1/speckit/." ~/"$REPO"/ && cp "$T/test1/problem.md" ~/"$REPO"/
    start_repo "$REPO"
    run_work 1 "$name" "$rid" "$REPO" "$LIMIT" specify plan tasks estimate   # LIMIT: a backstop
    if [ "$RUN" = complete ]; then printf '%s\t%s\tcomplete\t\n' "$name" "$2" >> "$TSV1"
    else printf '%s\t%s\t%s\t%s\n' "$name" "$2" "$RUN" "$WHERE" >> "$TSV1"; fi
    run_event "$rid"
}

t1_result() { awk -F'\t' -v n="$1" -v r="$2" '$1==n && $2==r{x=$3} END{print x}' "$TSV1" 2>/dev/null; }

test1() {  # name: its runs not yet done. Local models always run 3 (3 of 3 beats 2 of 3, owner,
    # 11 Nov); a cloud model (CLOUD, cloud.sh) skips the third when the first two agree, as each costs plan use
    local name=$1 r rerun=""
    for r in ${RUNS:-1 2 3}; do   # RUNS: only these (owner, 13 Nov: a cloud model's run 1 first, to see its plan use)
        [ -n "$(t1_result "$name" $r)" ] && continue          # done on an earlier start
        if [ -n "${CLOUD:-}" ] && [ -z "${RUNS:-}" ] && [ $r = 3 ] && [ "$(t1_result "$name" 1)" = "$(t1_result "$name" 2)" ] && [ "$(t1_result "$name" 1)" != machine-failed ]; then continue; fi
        past_deadline && return
        say "test 1: $name run $r"; now 1 "$name" "$r"; t1_run "$name" $r
        [ "$RUN" = machine-failed ] && rerun="$rerun $r"
    done
    for r in $rerun; do   # runs past the repair limit: rerun once
        past_deadline && return
        say "test 1: rerun $name run $r"; now 1 "$name" "$r"; t1_run "$name" "$r"
    done
}
