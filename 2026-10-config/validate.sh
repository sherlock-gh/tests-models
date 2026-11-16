#!/bin/bash
# Before a round judges any model, on Sherlock (start.sh runs it): test 2's checks
# (test2/check.sh and the hidden tests) and test 1's (test1/check.py) must pass work that is
# right and fail work that is wrong, on the previous round's own finished work (round 3: round
# 2's). Prints one line a case; exits 0 when every case gives
# its expected outcome, else 1, and nothing starts. About 20 min, most of it Swift builds.
set -u
cd "$(dirname "$0")" || exit 1
W=workspaces/tests/2026-10-config   # the workspaces, under ~: round 2's in round2-a/ and round2-b/
QUICK=""; [ "${1:-}" = quick ] && QUICK=1   # validate.sh quick: all but Swift (a few seconds)
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }
bad=0

case_() {  # expected (pass | fail | either) run-id language milestone why
    local want=$1 rid=$2 lng=$3 n=$4 h k="" out rc got i
    [ -n "$QUICK" ] && [ "$lng" = swift ] && return
    [ -d ~/"$W/$rid/app/.git" ] || { echo "MISSING $rid: its workspace is gone"; bad=1; return; }
    if [ "$lng" = python ]; then
        h="$PWD/test2/python/hidden"
        k=$(awk -v n="$n" '!/^#/ && substr($1,2)+0 <= n {for(i=2;i<=NF;i++) printf "%s%s", (k++ ? " or " : ""), $i}' test2/python/milestones.txt)
    else
        h=$(mktemp -d); for i in $(seq "$n"); do cp "test2/swift/hidden/M$i.swift" "$h/"; done
    fi
    out=$(capped 1500 bash test2/check.sh "$W/$rid/app" "$lng" "$h" "$k" 2>&1); rc=$?
    [ "$lng" = swift ] && rm -rf "$h"
    case $rc in 0) got=pass ;; 1) got=fail ;; *) got="a fault in the check (exit $rc)" ;; esac
    # Swift work that is wrong must build and fail a test, never fail on the build cache
    if { [ "$got" = "$want" ] || { [ "$want" = either ] && [ $rc -le 1 ]; }; } &&
        ! grep -qE "PCH was compiled|missing required module 'SwiftShims'" <<< "$out" &&
        { [ "$lng" = python ] || [ "$want" != fail ] || grep -q '^✘' <<< "$out"; }; then
        echo "ok     $rid to M$n: $got, as expected ($5)"
    else
        echo "WRONG  $rid to M$n: $got, expected $want ($5): $(tail -4 <<< "$out" | tr '\n' ' ' | cut -c1-400)"; bad=1
    fi
}

case_ pass   round2-a/test2-flash-python-r2     python 6 "whole app, complete in round 2"
case_ fail   round2-a/test2-laguna-s-python-r1  python 6 "the empty home page has no 0.00 total"
case_ fail   round2-a/test2-gemma31-python-r1   python 2 "--file before the command, where the spec puts it after"
case_ pass   round2-a/test2-laguna-s-swift-r2   swift 5 "complete in round 2"
case_ pass   round2-a/test2-q122-swift-r2       swift 5 "complete in round 2"
case_ fail   round2-a/test2-flash-swift-r3      swift 4 "a missed scheduled day doesn't end the streak"

t1_case() {  # expected (pass | fail) task-repo step slug why: test 1's check on round 2's documents
    local want=$1 repo=$2 st=$3 slug=$4 out rc got
    [ -d ~/"$W/$repo/.git" ] || { echo "MISSING $repo: round 2's workspace is gone"; bad=1; return; }
    out=$(capped 900 python3 test1/check.py ~/"$W/$repo" "$st" "$slug" 2>&1); rc=$?
    case $rc in 0) got=pass ;; 1) got=fail ;; *) got="a fault in the check (exit $rc)" ;; esac
    if [ "$got" = "$want" ]; then echo "ok     $repo $st: $got, as expected ($5)"
    else echo "WRONG  $repo $st: $got, expected $want ($5): $(tail -2 <<< "$out" | tr '\n' ' ' | cut -c1-300)"; bad=1; fi
}
t1_case pass round2-b/test1-laguna-xs-r1/habitkit            specify  habitkit          "filled, only the template's HTML comments left (round 2's check failed it)"
t1_case fail round2-a/test1-laguna-s-r2/expense-tracker      tasks    expense-tracker   "no Dependencies or Implementation Strategy section"
for t in expense-tracker:expense-tracker:tasks habitkit:habitkit:tasks; do
    IFS=: read -r task slug st <<< "$t"
    t1_case pass round2-b/test1-coder-next-r2/$task $st $slug "complete in round 2"
done
exit $bad
