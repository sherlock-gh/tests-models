# Test 1, project management (README, test1/README.md), sourced by sherlock.sh. For one model,
# up to 3 runs; a run is the tasks in order, each in a fresh repo under
# ~/$ROOT/test1-<model>-r<n>/<task>/. A model failure ends the run.
# Writes results/test1.tsv (one line a run) and results/runs.jsonl (one line a milestone).
TSV1="$RES/test1.tsv"; [ -f "$TSV1" ] || printf 'config\trun\tresult\tstopped at\n' > "$TSV1"
TASKS1="expense-tracker habitkit"
AUTO="No one is available to answer questions: run the step non-interactively."

# The steps' instructions are files in the repo, not Hermes skills: "Follow <path>" sent models
# to Hermes's skill_view, which found no such skill, and they stopped (round 2: q122 and
# devstral, all four runs). So the prompt says to read the file (round 3).
follow() { echo "Read the file $1 in this repository (an instruction file, not one of Hermes's skills) and follow it."; }
t1_prompt() {
    case $1 in
        specify) echo "$(follow .claude/skills/speckit-specify/SKILL.md) The input is the brief in brief.md." ;;
        plan|tasks) follow ".claude/skills/speckit-$1/SKILL.md" ;;
    esac
    echo "$AUTO"
}
t1_check() {  # 0 pass, 1 the work falls short, else the check failed (a timeout: the check's fault)
    local r; capped 900 python3 "$T/test1/check.py" ~/"$REPO" "$1" "$SLUG"; r=$?
    [ $r = 142 ] && { echo "check timed out"; r=3; }
    return $r
}

t1_run() {  # name run
    local name=$1 rid="test1-$1-r$2" task
    prompt_for() { t1_prompt "$@"; }; check_for() { t1_check "$@"; }
    served_or_stop "$name"; RUNFIX=0; void_run "$rid-"
    HMODEL=$(model_of "$name")
    for task in $TASKS1; do
        REPO="$ROOT/$rid/$task"; SLUG=${task#0?-}
        new_repo "$REPO"
        cp -R "$T/test1/speckit/." ~/"$REPO"/ && cp "$T/test1/tasks/$task/brief.md" ~/"$REPO"/
        start_repo "$REPO"
        run_work 1 "$name" "$rid-$task" "$REPO" "$LIMIT" specify plan tasks   # LIMIT (sherlock.sh): a backstop; time only breaks ties
        [ "$RUN" = complete ] || { printf '%s\t%s\t%s\t%s %s\n' "$name" "$2" "$RUN" "$task" "$WHERE" >> "$TSV1"; REASON="$task $REASON"; run_event "$rid"; return; }
    done
    printf '%s\t%s\tcomplete\t\n' "$name" "$2" >> "$TSV1"; run_event "$rid"
}

# A run carried from an earlier round (results/<round>/carried/test1.tsv: round 3 carries laguna-s's
# run 2, a model failure, and redoes run 1, which failed on the check) counts as done here.
t1_result() { cat "$SHARED/carried/test1.tsv" "$TSV1" 2>/dev/null | awk -F'\t' -v n="$1" -v r="$2" '$1==n && $2==r{x=$3} END{print x}'; }

test1() {  # name: its runs not yet done; the third only when the first two differ
    local name=$1 r rerun=""
    for r in 1 2 3; do
        [ -n "$(t1_result "$name" $r)" ] && continue          # done on an earlier start
        if [ $r = 3 ] && [ "$(t1_result "$name" 1)" = "$(t1_result "$name" 2)" ] && [ "$(t1_result "$name" 1)" != machine-failed ]; then continue; fi
        past_deadline && return
        say "test 1: $name run $r"; now 1 "$name" "$r"; t1_run "$name" $r
        [ "$RUN" = machine-failed ] && rerun="$rerun $r"
    done
    for r in $rerun; do   # runs past the repair limit: rerun once
        past_deadline && return
        say "test 1: rerun $name run $r"; now 1 "$name" "$r"; t1_run "$name" "$r"
    done
}
