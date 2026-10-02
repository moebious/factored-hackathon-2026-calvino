#!/usr/bin/env bash
# Validates a commit message (or PR title/description) against the git rules
# in AGENTS.md. Used by the local commit-msg hook and by CI, so both enforce
# exactly the same rules.
#
# Usage: check-commit-msg.sh [--no-subject] FILE   (FILE may be - for stdin)
#   default       check the first line as a Conventional Commits subject
#                 (max 72 chars) and the whole text for AI-tool attribution
#   --no-subject  only check for AI-tool attribution (for PR descriptions)
set -euo pipefail

check_subject=1
if [ "${1:-}" = "--no-subject" ]; then check_subject=0; shift; fi
msg=$(cat "${1:--}")

types='feat|fix|docs|test|refactor|perf|build|ci|chore|style|revert'
# Lowercase start and no trailing period, per the description rules in AGENTS.md.
subject_re="^(${types})(\([a-z0-9-]+\))?!?: [^A-Z].*[^.]$"
attribution_re='Co-Authored-By:.*(Claude|anthropic|Copilot|openai|Cursor|factory|droid)|Claude-Session:|Generated (with|by) \[?(Claude|Copilot|Cursor|Factory|Droid)'
fail=0

if [ "$check_subject" -eq 1 ]; then
    # Ignore comment lines git adds to the editor template.
    subject=$(printf '%s\n' "$msg" | grep -v '^#' | head -n 1)
    if ! printf '%s' "$subject" | grep -qE "$subject_re"; then
        echo "error: not a Conventional Commits subject: '$subject'" >&2
        echo "       expected '<type>(<scope>): <description>', see AGENTS.md" >&2
        fail=1
    elif [ "${#subject}" -gt 72 ]; then
        echo "error: subject is longer than 72 characters: '$subject'" >&2
        fail=1
    fi
fi

if printf '%s' "$msg" | grep -qiE "$attribution_re"; then
    echo "error: contains AI-tool attribution, which AGENTS.md does not allow" >&2
    fail=1
fi

exit "$fail"
