#!/bin/bash
# Test 2's milestone check, on Sherlock (test2.sh runs it): check.sh <repo under ~> <python|swift> <hidden dir> [pytest -k expression]
# Runs the hidden tests of this milestone and every earlier one against the committed work, in
# place of the build's own tests. Prints one line. Exit 0: all pass; 1: the work fails them (or
# doesn't build); 3: the check itself couldn't run, which stops the round.
set -u
REPO=$1 LNG=$2 HIDDEN=$3 K=${4:-}
[ -d "$HIDDEN" ] || { echo "no hidden tests at $HIDDEN"; exit 3; }
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }   # the build and tests: 20 min, then the work hangs
W=$(mktemp -d) || exit 3; trap 'rm -rf "$W"' EXIT
git clone -q ~/"$REPO" "$W/w" || { echo "could not clone the repo"; exit 3; }
cd "$W/w" || exit 3
if [ "$LNG" = python ]; then
    export PYTHONDONTWRITEBYTECODE=1 PATH=/Users/Shared/agent-tools/venv/bin:$PATH
    (cd "$HIDDEN" && TARGET="$W/w" capped 1200 python3 -m pytest -q -p no:cacheprovider -k "$K") > "$W/out" 2>&1; rc=$?
    [ $rc = 142 ] && { echo "the tests did not finish in 20 min"; exit 1; }
    [ $rc = 0 ] || tail -60 "$W/out" >&2   # which tests failed and how: the why file shows it
    tail -1 "$W/out"
    # pytest: 1 tests failed, 2 the work errored on collection (its import failed); 3-5 internal,
    # usage, or no tests selected: the check's fault
    case $rc in 0) exit 0 ;; 1|2) exit 1 ;; *) exit 3 ;; esac
else
    # A committed build cache holds the agent's paths and fails every build here (31 Oct): build fresh
    rm -rf .build .swiftpm Tests/HabitKitTests && mkdir -p Tests/HabitKitTests && cp "$HIDDEN"/M*.swift Tests/HabitKitTests/ || exit 3
    capped 1200 swift test > "$W/out" 2>&1; rc=$?
    [ $rc = 142 ] && { echo "the build and tests did not finish in 20 min"; exit 1; }
    { [ $rc = 0 ] && ! grep -qE '^✘' "$W/out"; } || grep -E '^✘|error:' "$W/out" | tail -60 >&2
    grep -m1 -E 'Test run with' "$W/out" || grep -m1 'error:' "$W/out" | cut -c1-200 || echo "build failed"
    case $rc in 0) grep -qE '^✘' "$W/out" && exit 1; exit 0 ;; 1) exit 1 ;; *) exit 3 ;; esac   # 1: build or tests failed
fi
