# Test 2, coding (README), sourced by sherlock.sh. For one model and each language, up to 3
# runs; a run builds the app milestone by milestone in a fresh repo holding only SPEC.md
# (~/$ROOT/test2-<model>-<language>-r<n>/app/). Each milestone must end
# in a commit and pass the hidden tests of every milestone so far. A model failure ends the run.
# Writes results/test2.tsv (one line a run) and results/runs.jsonl (one line a milestone).
TSV2="$RES/test2.tsv"; [ -f "$TSV2" ] || printf 'config\tlanguage\trun\tresult\tstopped at\n' > "$TSV2"

t2_title() { grep -m1 "^## $2\. " "$T/test2/$1/SPEC.md" | sed "s/^## //"; }
t2_prompt() {
    local n=${1#M} last
    echo "SPEC.md in this repository specifies a piece of software. Build it one step at a time, following SPEC.md exactly."
    if [ "$LNG" = python ]; then last=6; else last=5; fi
    case $n in
        1) echo "This step: the ground rules and section $(t2_title "$LNG" 1), with its tests." ;;
        "$last") echo "This step: sections $(t2_title "$LNG" "$n") and $(t2_title "$LNG" $((n + 1))), keeping every earlier section working." ;;
        *) echo "This step: section $(t2_title "$LNG" "$n"), with its tests, keeping every earlier section working." ;;
    esac
    [ "$LNG" = swift ] && [ "$n" = 3 ] && echo "Until sections 4 and 5 are built, currentStreak and completionRate may return 0."
}
t2_check() {
    local n=${1#M} h k="" r i
    if [ "$LNG" = python ]; then
        h="$T/test2/python/hidden"
        k=$(awk -v n="$n" '!/^#/ && substr($1,2)+0 <= n {for(i=2;i<=NF;i++) printf "%s%s", (k++ ? " or " : ""), $i}' "$T/test2/python/milestones.txt")
    else
        h=$(mktemp -d) || return 3
        for i in $(seq "$n"); do cp "$T/test2/swift/hidden/M$i.swift" "$h/" || return 3; done
    fi
    capped 1500 bash "$T/test2/check.sh" "$REPO" "$LNG" "$h" "$k"; r=$?   # check.sh caps the tests at 20 min
    [ "$LNG" = swift ] && rm -rf "$h"
    [ $r = 142 ] && { echo "the check itself did not finish in 25 min"; r=3; }
    return $r
}

t2_run() {  # name language run
    local name=$1 rid="test2-$1-$2-r$3" limit n
    prompt_for() { t2_prompt "$@"; }; check_for() { t2_check "$@"; }
    LNG=$2; REPO="$ROOT/$rid/app"
    limit=$LIMIT; if [ "$LNG" = python ]; then n=6; else n=5; fi   # LIMIT (sherlock.sh): a backstop; time only breaks ties
    served_or_stop "$name"; RUNFIX=0; void_run "$rid"
    HMODEL=$(model_of "$name")
    new_repo "$REPO"; cp "$T/test2/$LNG/SPEC.md" ~/"$REPO"/; start_repo "$REPO"
    run_work 2 "$name" "$rid" "$REPO" $limit $(seq -f 'M%g' "$n")
    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$LNG" "$3" "$RUN" "$([ "$RUN" = complete ] || echo "$WHERE")" >> "$TSV2"; run_event "$rid"
    rm -rf ~/"$REPO"/.build   # the build cache: big, and never needed again
}

t2_result() { awk -F'\t' -v n="$1" -v l="$2" -v r="$3" '$1==n && $2==l && $3==r{x=$4} END{print x}' "$TSV2"; }

test2() {  # name language: its runs not yet done; the third only when the first two differ
    local name=$1 lang=$2 r a rerun=""
    for r in 1 2 3; do
        [ -n "$(t2_result "$name" $lang $r)" ] && continue          # done on an earlier start
        a=$(t2_result "$name" $lang 1)
        if [ $r = 3 ] && [ "$a" = "$(t2_result "$name" $lang 2)" ] && [ "$a" != machine-failed ]; then continue; fi
        past_deadline && return
        say "test 2: $name $lang run $r"; now 2 "$name" "$lang" "$r"; t2_run "$name" $lang $r
        [ "$RUN" = machine-failed ] && rerun="$rerun $r"
    done
    for r in $rerun; do   # runs past the repair limit: rerun once
        past_deadline && return
        say "test 2: rerun $name $lang run $r"; now 2 "$name" "$lang" "$r"; t2_run "$name" "$lang" "$r"
    done
}
