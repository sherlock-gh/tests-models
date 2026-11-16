#!/bin/bash
# Before a round judges any model, on Sherlock (start.sh, and start-cloud.sh for test 2, run it):
#   validate.sh            test 1's check (test1/check.py) must pass complete work and fail work that falls short
#   validate.sh <plan>     test 2's check on that build plan (test2/plans/<plan>) must pass its reference
#                          solution at every milestone and fail two broken copies where they break
#                          (its validate.tsv: language, the milestone that bills, and optionally a sed
#                          script that breaks the bill, for a plan where halves of a cent can't arise)
# Test 1: The spec, plan and tasks cases
# are documents from the October tests' workspaces, whose outcome a person confirmed; the estimate
# cases are test1/fixtures/. Prints one line a case; exits 0 when every case gives its expected
# outcome, else 1, and nothing starts. Test 1: a few seconds; test 2: the Swift builds, up to an hour.
set -u
cd "$(dirname "$0")" || exit 1
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }

if [ -n "${1:-}" ]; then   # test 2 on a build plan
    PLAN=$1 P=test2/plans/$1 bad=0
    [ -d "$P/reference" ] || { echo "WRONG  no reference solution in $P"; exit 1; }
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/validate2.XXXXXX") || exit 1
    t2_case() {  # expected (pass|fail) language milestone why [sed script]: the reference, changed by the script
        local r=$tmp/$RANDOM out rc got
        mkdir -p "$r" && cp -R "$P/reference/." "$r/" && find "$r" -name __pycache__ -prune -exec rm -rf {} +
        [ -n "${5:-}" ] && find "$r" \( -name '*.py' -o -name '*.swift' \) -exec sed -i '' -e "$5" {} +
        (cd "$r" && git init -q && git add -A && git -c user.name=runner -c user.email=runner@localhost commit -qm reference) || { echo "WRONG  could not build the case"; bad=1; return; }
        out=$(capped 1500 bash test2/check.sh "$r" "$2" "$3" "$PLAN" 2>&1); rc=$?
        case $rc in 0) got=pass ;; 1) got=fail ;; *) got="a fault in the check (exit $rc)" ;; esac
        if [ "$got" = "$1" ]; then echo "ok     $PLAN $2 to M$3: $got, as expected ($4)"
        else echo "WRONG  $PLAN $2 to M$3: $got, expected $1 ($4): $(tail -3 <<< "$out" | tr '\n' ' ' | cut -c1-300)"; bad=1; fi
    }
    gap='s/1020, 60, 540/1020, 59, 540/; s/gap = 60/gap = 59/'
    round='s/\* 5 + 2) \/\/ 4/* 5) \/\/ 4/; s/\* 5 + 2) \/ 4/* 5) \/ 4/'
    while IFS=$'\t' read -r lng bill brk; do   # brk: the plan's own break of the bill, where halves of a cent can't arise
        n=$(awk -F'\t' -v l="$lng" '!/^#/ && $1==l' "$P/steps.tsv" | wc -l | tr -d ' ')
        t2_case pass "$lng" "$n" "the reference solution, every milestone"
        t2_case fail "$lng" 1 "the gap between jobs 59 minutes" "$gap"
        if [ -n "$brk" ]; then t2_case fail "$lng" "$bill" "the bill broken: $brk" "$brk"
        else t2_case fail "$lng" "$bill" "halves of a cent rounded down" "$round"; fi
    done < "$P/validate.tsv"
    rm -rf "$tmp"
    exit $bad
fi
W=workspaces/tests/2026-10-config   # under ~: the October tests' round 2 workspaces
bad=0

t1_case() {  # expected (pass | fail) repo step why
    local want=$1 repo=$2 st=$3 out rc got
    [ -d "$repo/.git" ] || { echo "MISSING $repo: the workspace is gone"; bad=1; return; }
    out=$(capped 900 python3 test1/check.py "$repo" "$st" 2>&1); rc=$?
    case $rc in 0) got=pass ;; 1) got=fail ;; *) got="a fault in the check (exit $rc)" ;; esac
    if [ "$got" = "$want" ]; then echo "ok     $repo $st: $got, as expected ($4)"
    else echo "WRONG  $repo $st: $got, expected $want ($4): $(tail -2 <<< "$out" | tr '\n' ' ' | cut -c1-300)"; bad=1; fi
}
t1_case pass ~/$W/round2-b/test1-laguna-xs-r1/habitkit     specify "filled, only the template's HTML comments left"
t1_case fail ~/$W/round2-a/test1-laguna-s-r2/expense-tracker tasks  "no Dependencies or Implementation Strategy section"
for t in expense-tracker habitkit; do
    for st in specify plan tasks; do t1_case pass ~/$W/round2-b/test1-coder-next-r2/$t $st "complete in October"; done
done

# The estimate: each fixture committed as estimate.md in a scratch repo, with questions.md (the open
# questions, which may be empty) or, in the last case, without it
tmp=$(mktemp -d "${TMPDIR:-/tmp}/validate.XXXXXX") || { echo "WRONG  no scratch folder for the estimate cases"; exit 1; }
for f in complete:pass:q incomplete:fail:q complete:fail:noq; do
    e=${f%%:*} want=$(cut -d: -f2 <<< "$f") q=${f##*:}
    r=$tmp/$e-$q; mkdir -p "$r" && cp "test1/fixtures/estimate-$e.md" "$r/estimate.md" &&
        { [ "$q" = noq ] || : > "$r/questions.md"; } &&
        (cd "$r" && git init -q && git add -A && git -c user.name=runner -c user.email=runner@localhost commit -qm fixture) ||
        { echo "WRONG  could not build the $r case"; bad=1; continue; }
    t1_case "$want" "$r" estimate "test1/fixtures/estimate-$e.md$([ "$q" = noq ] && echo ', no questions.md')"
done
rm -rf "$tmp"
exit $bad
