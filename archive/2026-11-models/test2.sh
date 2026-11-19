# Test 2, the builds (README, "Python and Swift"), sourced by sherlock.sh and cloud.sh. PLAN names the
# build plan (test2/plans/<plan>). For one model and language, up to 3 runs; a run builds that plan's
# app milestone by milestone in a fresh repo holding only the plan
# (~/$ROOT/test2-<model>-<language>-r<n>/app/specs/001-cleaning-scheduling-billing/). After each
# milestone the hidden tests of every milestone so far run (test2/check.sh) and the run goes on to
# the next whatever they say; its score is the hidden tests its last milestone passes (README,
# "Scoring"). Writes results/test2.tsv (one line a run) and results/runs.jsonl.
AUTO=${AUTO:-"No one is available to answer questions: run the step non-interactively."}
TSV2="$RES/test2.tsv"; [ -f "$TSV2" ] || printf 'config\tlanguage\trun\tresult\tstopped at\thidden tests passed\n' > "$TSV2"
P2="$T/test2/plans/${PLAN:?PLAN, the build plan}"
[ -d "$P2" ] || { echo "no build plan $P2"; exit 1; }
. "$P2/check.conf"

t2_steps() { awk -F'\t' -v l="$1" '!/^#/ && $1==l' "$P2/steps.tsv" | wc -l | tr -d ' '; }
t2_prompt() {  # milestone M<n>
    local n=${1#M} app tasks
    eval "app=\$APP_$LNG"
    tasks=$(awk -F'\t' -v l="$LNG" -v n="$n" '!/^#/ && $1==l && $2==n {print $3}' "$P2/steps.tsv")
    echo "specs/001-cleaning-scheduling-billing/ in this repository holds the plan for a piece of software with two apps. Build only $app, one step at a time, following the plan and its contracts exactly; leave the other app's tasks alone."
    echo "This step ($n of $(t2_steps "$LNG")): tasks $tasks in specs/001-cleaning-scheduling-billing/tasks.md, with their tests, keeping every earlier step working."
    [ "$LNG" = swift ] && echo "On this machine swift test runs Swift Testing (import Testing), not XCTest, which isn't installed: write the package's tests with Swift Testing. Run swift build and swift test with --disable-sandbox, as SwiftPM's own sandbox can't start inside this machine's, and allow a first build several minutes."
    echo "$AUTO"
}
t2_check() { local r left=""   # work the model left uncommitted is committed for it, then checked
    [ -n "$(git -C ~/"$REPO" status --porcelain)" ] && left=1 &&
        (cd ~/"$REPO" && git add -A && git -c user.name=runner -c user.email=runner@localhost commit -qm 'runner: the work the model left uncommitted') >/dev/null 2>&1
    capped 1500 bash "$T/test2/check.sh" "$REPO" "$LNG" "${1#M}" "$PLAN" | tr -d '\n'; r=${PIPESTATUS[0]}   # check.sh caps the tests at 20 min
    [ $r = 142 ] && { echo -n "the check itself did not finish in 25 min"; r=3; }
    echo "${left:+; the model left it uncommitted}"
    return $r
}

t2_run() {  # name language run
    local name=$1 rid="test2-$1-$2-r$3"
    prompt_for() { t2_prompt "$@"; }; check_for() { t2_check "$@"; }
    LNG=$2; REPO="$ROOT/$rid/app"
    serve "$name" || stop_round "$SERVER could not serve $name, which loaded at the gate"   # a fresh server each run
    RUNFIX=0; void_run "$rid"
    HMODEL=$(model_of "$name")
    new_repo "$REPO"; mkdir -p ~/"$REPO"/specs && cp -R "$P2/plan" ~/"$REPO"/specs/001-cleaning-scheduling-billing; start_repo "$REPO"
    SCORE=""; SCORED=1 run_work 2 "$name" "$rid" "$REPO" "$LIMIT" $(seq -f 'M%g' "$(t2_steps "$LNG")")   # LIMIT: a backstop; time only breaks ties
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$LNG" "$3" "$RUN" "$([ "$RUN" = complete ] || echo "$WHERE")" "${SCORE#passed }" >> "$TSV2"; run_event "$rid"
    rm -rf ~/"$REPO"/"$SWIFT_PKG"/.build   # the build cache: big, and never needed again
}

t2_number() { [ "$1" = swift ] && echo 3 || echo 2; }   # the pages' numbers: Python is test 2, Swift test 3
t2_result() { awk -F'\t' -v n="$1" -v l="$2" -v r="$3" '$1==n && $2==l && $3==r{x=$4} END{print x}' "$TSV2"; }

test2() {  # name language: its runs not yet done. Local models run all 3; a cloud model (CLOUD) skips
    # the third when the first two agree, as each run uses the owner's plan
    local name=$1 lang=$2 r a rerun=""
    for r in 1 2 3; do
        [ -n "$(t2_result "$name" $lang $r)" ] && continue          # done on an earlier start
        a=$(t2_result "$name" $lang 1)
        if [ -n "${CLOUD:-}" ] && [ $r = 3 ] && [ "$a" = "$(t2_result "$name" $lang 2)" ] && [ "$a" != machine-failed ]; then continue; fi
        past_deadline && return
        say "test $(t2_number $lang): $name $lang run $r ($PLAN)"; now 2 "$name" "$lang" "$r"; t2_run "$name" $lang $r
        [ "$RUN" = machine-failed ] && rerun="$rerun $r"
    done
    for r in $rerun; do   # runs past the repair limit: rerun once
        past_deadline && return
        say "test $(t2_number $lang): rerun $name $lang run $r"; now 2 "$name" "$lang" "$r"; t2_run "$name" "$lang" "$r"
    done
}
