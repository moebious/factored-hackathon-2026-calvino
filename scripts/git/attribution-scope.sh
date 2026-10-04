#!/usr/bin/env bash
# Classify changed paths for the one permitted Factory commit trailer.
# The hook and CI supply actual staged/committed paths on stdin; caller text
# never decides whether a code commit is documentation-only.
set -euo pipefail

message=$(cat "${1:--}")
subject=$(printf '%s\n' "$message" | head -n 1)
count=0
docs_only=1
bootstrap_only=1
while IFS= read -r path; do
    [ -n "$path" ] || continue
    count=$((count + 1))
    case "$path" in
        *.md|*.mdx) ;;
        *) docs_only=0 ;;
    esac
    case "$path" in
        AGENTS.md|.githooks/commit-msg|.github/workflows/conventions.yml|scripts/git/check-commit-msg.sh|scripts/git/attribution-scope.sh|tests/git/test_git_rules.sh)
            ;;
        *) bootstrap_only=0 ;;
    esac
done

if [ "$count" -eq 0 ]; then
    echo none
elif [ "$docs_only" -eq 1 ]; then
    echo docs
elif [ "$bootstrap_only" -eq 1 ] &&
    [ "$subject" = 'chore(repo): allow factory co-author on docs-only commits' ]; then
    echo bootstrap
else
    echo none
fi
