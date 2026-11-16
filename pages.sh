#!/bin/bash
# Pushes the built tests site (~/demo/www/tests: the index, each round page, its why pages, the
# files to reproduce a test) to the gh-pages branch of sherlock-gh/tests-models, which GitHub Pages
# serves at https://sherlock-gh.github.io/tests-models/ once the repo is public (owner, 16 Nov).
# The branch holds only the built site. publish.sh runs it after each site rebuild, and status.py
# after a round page's, at most every 10 min. 5 min at most; a failure is logged to
# ~/tests-site/pages.log and never stops a round. A file matching a secret's pattern is left out.
SRC=~/demo/www/tests DIR=~/tests-site/pages LOG=~/tests-site/pages.log
REMOTE=https://github.com/sherlock-gh/tests-models.git
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
mkdir -p ~/tests-site
mkdir ~/tests-site/pages.lock 2>/dev/null || {   # one push at a time; a lock older than 10 min is stale
    [ -n "$(find ~/tests-site/pages.lock -maxdepth 0 -mmin +10)" ] && rm -rf ~/tests-site/pages.lock && mkdir ~/tests-site/pages.lock || exit 0; }
trap 'rm -rf ~/tests-site/pages.lock' EXIT
capped() { perl -e 'alarm shift; exec @ARGV' "$@"; }
[ -f "$SRC/index.html" ] || { log "not pushed: no site at $SRC (the demo server empties it on restart; run publish.sh)"; exit 0; }
if [ ! -d "$DIR/.git" ]; then
    rm -rf "$DIR" && mkdir -p "$DIR" && git -C "$DIR" init -q -b gh-pages && git -C "$DIR" remote add origin "$REMOTE"
    capped 120 git -C "$DIR" fetch -q origin gh-pages 2>/dev/null && git -C "$DIR" reset -q origin/gh-pages
fi
find "$DIR" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$SRC"/. "$DIR"/
# The site's links are absolute under /tests/; Pages serves it under /tests-models/
find "$DIR" -name '*.html' ! -path '*/.git/*' -exec perl -pi -e 's#(href|src)=(["\x27])/tests/#$1=$2/tests-models/#g' {} +
grep -rlE 'gh[opsu]_[A-Za-z0-9]{30,}|github_pat_|sk-ant-|sk-[A-Za-z0-9]{32,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY' \
    --exclude-dir=.git "$DIR" | while read -r f; do log "left out, a secret's pattern: ${f#"$DIR"/}"; rm -f "$f"; done
touch "$DIR/.nojekyll"   # serve the files as they are
git -C "$DIR" add -A
git -C "$DIR" diff --cached --quiet && exit 0
git -C "$DIR" -c user.name=sherlock-gh -c user.email=sherlock-gh@users.noreply.github.com commit -qm "The tests site, $(date '+%F %T')"
if capped 120 git -C "$DIR" push -q origin gh-pages 2>> "$LOG"; then log "pushed"; else log "push failed (exit $?)"; fi
exit 0
