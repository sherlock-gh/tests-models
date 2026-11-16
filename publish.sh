#!/bin/sh
# Publishes the tests' home page, http://192.168.50.100:18100/tests/, with the files to reproduce
# the current test: the Markdown someone needs to recreate it (README.md only names the tests for
# the page). On Sherlock: sh publish.sh. Gathers the files below into ~/tests-site/kit/ under
# tests/ (Hermes's SOUL.md at hosts/sherlock/hermes/), with the commit they come from, and runs
# site.py. Run it again after the demo server restarts (it empties its pages) or when these files
# change. A few seconds, then up to 5 min to push the site to GitHub Pages (pages.sh).
set -eu
cd "$(dirname "$0")"
KIT=~/tests-site/kit
rm -rf "$KIT" && mkdir -p "$KIT/tests" "$KIT/hosts/sherlock/hermes"
for f in README.md 2026-11-models/README.md 2026-11-models/REPRODUCE.md 2026-11-models/test1/problem.md 2026-11-models/test1/prompts.md; do
    mkdir -p "$KIT/tests/$(dirname "$f")" && cp "$f" "$KIT/tests/$f"
done
cp ~/.hermes/SOUL.md "$KIT/hosts/sherlock/hermes/SOUL.md"
echo "$(git log -1 --format='%h, %cs')$(git diff --quiet HEAD -- . || echo ' with uncommitted changes')" > "$KIT/COMMIT"
python3 site.py
bash pages.sh || true   # the public copy, GitHub Pages (pages.sh): logged, never fatal
