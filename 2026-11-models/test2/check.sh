#!/bin/bash
# Test 2's milestone check, on Sherlock (test2.sh runs it):
#   check.sh <repo, under ~ or absolute> <python|swift> <milestone> <build plan, a folder in plans/>
# Runs the hidden tests of this milestone and every earlier one against the committed work, in
# place of the build's own tests, from a fresh clone (no build cache). Prints one line.
# Exit 0: all pass; 1: the work fails them (or doesn't build); 3: the check itself couldn't run,
# which stops the round. The tests and build: 20 min, then the work counts as hanging.
set -u
REPO=$1 LNG=$2 N=$3
PLAN=${4:?usage: check.sh <repo> <python|swift> <milestone> <plan>}
P="$(cd "$(dirname "$0")" && pwd)/plans/$PLAN"; H=$P/$LNG/hidden
# The plan's Swift layout: SWIFT_PKG (the package folder) and SWIFT_TESTS (its test target folder)
. "$P/check.conf" 2>/dev/null || { echo "no $P/check.conf"; exit 3; }
[ -d "$H" ] || { echo "no hidden tests at $H"; exit 3; }
case $REPO in /*) ;; *) REPO=~/"$REPO" ;; esac
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }
W=$(mktemp -d "${TMPDIR:-/tmp}/check2.XXXXXX") || exit 3; trap 'rm -rf "$W"' EXIT
git clone -q "$REPO" "$W/w" || { echo "could not clone the repo"; exit 3; }
cd "$W/w" || exit 3
if [ "$LNG" = python ]; then
    export PYTHONDONTWRITEBYTECODE=1 PATH=/Users/Shared/agent-tools/venv/bin:$PATH
    files=$(for i in $(seq "$N"); do echo "test_m$i.py"; done)
    (cd "$H" && TARGET="$W/w" capped 1200 python3 -m pytest -q -p no:cacheprovider --basetemp="$W/t" $files) > "$W/out" 2>&1; rc=$?
    [ $rc = 142 ] && { echo "the tests did not finish in 20 min"; exit 1; }
    [ $rc = 0 ] || tail -60 "$W/out" >&2   # which tests failed and how: the why file shows it
    tail -1 "$W/out"
    # pytest: 1 tests failed, 2 the work errored on collection; 3-5 internal, usage, or no tests: the check's fault
    case $rc in 0) exit 0 ;; 1|2) exit 1 ;; *) exit 3 ;; esac
else
    [ -f "$SWIFT_PKG/Package.swift" ] || { echo "no $SWIFT_PKG/Package.swift"; exit 1; }
    rm -rf "$SWIFT_PKG/.build" "$SWIFT_PKG/.swiftpm" "$SWIFT_PKG/$SWIFT_TESTS" && mkdir -p "$SWIFT_PKG/$SWIFT_TESTS" || exit 3
    for i in $(seq "$N"); do cp "$H/M$i.swift" "$SWIFT_PKG/$SWIFT_TESTS/" || exit 3; done
    (cd "$SWIFT_PKG" && capped 1200 swift test) > "$W/out" 2>&1; rc=$?
    [ $rc = 142 ] && { echo "the build and tests did not finish in 20 min"; exit 1; }
    { [ $rc = 0 ] && ! grep -qE '^✘|error:' "$W/out"; } || grep -E '^✘|error:|failed' "$W/out" | tail -60 >&2
    grep -E 'Executed [0-9]+ tests' "$W/out" | tail -1 | grep . || grep -m1 'error:' "$W/out" | cut -c1-200 || echo "build failed"
    case $rc in 0) exit 0 ;; 1) exit 1 ;; *) exit 3 ;; esac   # 1: the build or a test failed
fi
