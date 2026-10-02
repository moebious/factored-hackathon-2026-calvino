#!/usr/bin/env bash
# Checks that every commit in a range is small enough to review, per the "small
# logical commits" rule in AGENTS.md. Used by the pre-push hook and by CI, so
# both enforce exactly the same limits.
#
# Usage: check-commit-size.sh [--warn] <rev-range>     e.g. origin/main..HEAD
#   default  exit 1 if any commit is too large
#   --warn   print the same findings as warnings and exit 0
#
# A commit is too large when it changes more than COMMIT_MAX_FILES files (default
# 15) or COMMIT_MAX_LINES lines, added plus deleted (default 800). Lock files and
# generated or data-like paths are not counted (see $excludes): they are large
# for reasons that say nothing about reviewability. A commit that really is one
# indivisible change carries a footer line "Size-exception: <reason>" (at least
# 8 characters), which keeps the reason visible in the history.
set -euo pipefail

max_files=${COMMIT_MAX_FILES:-15}
max_lines=${COMMIT_MAX_LINES:-800}
warn=0
if [ "${1:-}" = "--warn" ]; then warn=1; shift; fi
range=${1:?usage: check-commit-size.sh [--warn] <rev-range>}

# Keep in sync with the layout table in AGENTS.md.
excludes=(':(exclude)uv.lock' ':(exclude)package-lock.json' ':(exclude)pnpm-lock.yaml'
          ':(exclude)contracts' ':(exclude)tests/fixtures' ':(exclude)reports')

fail=0
for sha in $(git rev-list --no-merges "$range"); do
    # numstat prints "<added>\t<deleted>\t<path>"; binary files print "-" for both.
    read -r files lines < <(git show --numstat --format= "$sha" -- . "${excludes[@]}" |
        awk -F'\t' 'NF >= 3 { f++; if ($1 != "-") l += $1 + $2 } END { print f + 0, l + 0 }')
    if [ "$files" -le "$max_files" ] && [ "$lines" -le "$max_lines" ]; then continue; fi
    if git log -1 --format=%B "$sha" | grep -qE '^Size-exception: .{8,}'; then continue; fi

    level=error; [ "$warn" -eq 1 ] || fail=1
    [ "$warn" -eq 1 ] && level=warning
    subject=$(git log -1 --format=%s "$sha")
    echo "$level: commit $(git rev-parse --short "$sha") is too large to review: $files files, $lines lines (limits: $max_files files, $max_lines lines)" >&2
    echo "       '$subject'" >&2
    echo "       split it into small logical commits, or add a 'Size-exception: <reason>' footer (see AGENTS.md)" >&2
done
exit "$fail"
