#!/bin/bash
# The blind quality review's sets (README, "Run protocol" 5), from Dr Watson:
#   ./fetch.sh 1 | 2        builds a blind set of every complete test 1 (documents) or test 2 (code)
#                           run on Sherlock (blind.py) and copies it to Dr Watson's inbox,
#                           /private/tmp/claude-502/lab-inbox/<set>/, outside the repo, never committed
#   ./fetch.sh key <set>    after grading only: copies that set's key into the inbox beside it
# Opus grades the set without the key and writes grades.jsonl in the set's inbox folder; the key
# then says which model each id is. The sets go only to the inbox, and the inbox is never
# committed. Reads the workspaces on Sherlock; changes none.
set -u
cd "$(dirname "$0")" || exit 1
DIR=tests-2026-10-config      # under ~ on Sherlock
INBOX=/private/tmp/claude-502/lab-inbox
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }

case ${1:-} in
    1|2)
        set_name=$(capped 600 ssh sherlock "cd ~/$DIR && python3 blind.py $1") || { echo "no set built (see above)"; exit 1; }
        # Sherlock names the folder written here, so a name that could leave the inbox stops it; -rt
        # copies no symlinks, which could point a later write out of the inbox
        case $set_name in ""|.*|*[!A-Za-z0-9._-]*) echo "Sherlock gave an unusable set name: nothing copied"; exit 1 ;; esac
        mkdir -p "$INBOX" && capped 600 rsync -rt "sherlock:$DIR/results/blind/$set_name/set/" "$INBOX/$set_name/" ||
            { echo "built $set_name on Sherlock, but could not copy it here"; exit 1; }
        echo "$INBOX/$set_name: $(find "$INBOX/$set_name/runs" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ') runs, to grade by its RUBRIC.md (no key)" ;;
    key)
        [ -n "${2:-}" ] || { echo "usage: ./fetch.sh key <set>"; exit 2; }
        [ -s "$INBOX/$2/grades.jsonl" ] || { echo "$2 has no grades.jsonl yet: the key comes over only after grading"; exit 1; }
        capped 120 rsync -t "sherlock:$DIR/results/blind/$2/key.tsv" "$INBOX/$2/key.tsv" && echo "$INBOX/$2/key.tsv" ;;
    *) echo "usage: ./fetch.sh 1 | 2 | key <set>"; exit 2 ;;
esac
