#!/bin/bash
# Test 2's milestone check, on Sherlock (test2.sh runs it):
#   check.sh <repo, under ~ or absolute> <python|swift> <milestone> <build plan, a folder in plans/>
# Runs the hidden tests of this milestone and every earlier one against the committed work, in
# place of the build's own tests, from a fresh clone (no build cache). Prints one line, the score
# first: "passed <p> of <n>", n being every hidden test so far (work that doesn't build passes 0).
# Exit 0: all pass; 1: some fail; 3: the check itself couldn't run, which stops the round.
# The tests and builds: 20 min, then the work counts as hanging (0 passed).
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
    # n: the hidden tests collected without the work (the fixture, not collection, imports it)
    n=$(cd "$H" && TARGET="$W/w" python3 -m pytest -q --collect-only -p no:cacheprovider $files 2>/dev/null | grep -c '::') || true
    [ "${n:-0}" -gt 0 ] || { echo "no hidden tests collected"; exit 3; }
    (cd "$H" && TARGET="$W/w" capped 1200 python3 -m pytest -q -p no:cacheprovider --basetemp="$W/t" --junitxml="$W/j.xml" $files) > "$W/out" 2>&1; rc=$?
    [ $rc = 142 ] && { echo "passed 0 of $n: the tests did not finish in 20 min"; exit 1; }
    [ $rc = 0 ] || tail -60 "$W/out" >&2   # which tests failed and how: the why file shows it
    # p: the testcases junit records with no failure, error or skip
    p=$(python3 -c 'import sys, xml.etree.ElementTree as E
print(sum(1 for c in E.parse(sys.argv[1]).iter("testcase") if not len(c)))' "$W/j.xml" 2>/dev/null || echo 0)
    echo "passed $p of $n: $(tail -1 "$W/out")"
    # pytest: 1 tests failed, 2 the work errored on collection; 3-5 internal, usage, or no tests: the check's fault
    case $rc in 0) exit 0 ;; 1|2) exit 1 ;; *) exit 3 ;; esac
else
    n=$(for i in $(seq "$N"); do cat "$H/M$i.swift"; done | grep -cE '^[[:space:]]*@Test')
    [ "$n" -gt 0 ] || { echo "no hidden tests in $H"; exit 3; }
    [ -f "$SWIFT_PKG/Package.swift" ] || { echo "passed 0 of $n: no $SWIFT_PKG/Package.swift"; exit 1; }
    # Each milestone's tests build on their own with M1.swift (its helpers), so a symbol one milestone
    # lacks fails that milestone's tests, not every milestone's (17 Nov: one build of all of them
    # scored 0 for a single missing function). The first build takes minutes; the rest reuse it.
    rm -rf "$SWIFT_PKG/.build" "$SWIFT_PKG/.swiftpm" || exit 3
    p=0 p1=0 rc=0 r=0 sum="" t0=$(date +%s)
    for i in $(seq "$N"); do
        rm -rf "${SWIFT_PKG:?}/$SWIFT_TESTS" && mkdir -p "$SWIFT_PKG/$SWIFT_TESTS" && cp "$H/M1.swift" "$SWIFT_PKG/$SWIFT_TESTS/" || exit 3
        if [ "$i" != 1 ]; then cp "$H/M$i.swift" "$SWIFT_PKG/$SWIFT_TESTS/" || exit 3; fi
        left=$((1200 - $(date +%s) + t0)); [ $left -gt 0 ] || { r=142; break; }
        (cd "$SWIFT_PKG" && capped $left swift test --disable-sandbox) > "$W/out$i" 2>&1; r=$?
        [ $r = 142 ] && break
        if [ $r != 0 ] || grep -qE '^✘|error:' "$W/out$i"; then rc=1; { echo "-- M$i"; grep -E '^✘|error:|failed' "$W/out$i" | tail -30; } >&2; fi
        [ $r -le 1 ] || { rc=$r; break; }
        # Swift Testing's line for each test that passed (not its suites' or the run's summary)
        k=$(grep -E '^✔ Test ' "$W/out$i" | grep -vcE '^✔ Test run with') || true
        if [ "$i" = 1 ]; then p1=$k p=$k; elif [ $((k - p1)) -gt 0 ]; then p=$((p + k - p1)); fi
        sum="$sum M$i $(grep -oE 'Test run with [0-9]+ tests (passed|failed)' "$W/out$i" | tail -1 | awk '{print $NF}' | grep . || echo "did not build"),"
    done
    [ $r = 142 ] && { echo "passed $p of $n: the builds and tests did not finish in 20 min"; exit 1; }
    echo "passed $p of $n:${sum%,}"
    case $rc in 0) exit 0 ;; 1) exit 1 ;; *) exit 3 ;; esac   # 1: a build or a test failed
fi
