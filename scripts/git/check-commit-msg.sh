#!/usr/bin/env bash
# Validates a commit message (or PR title/description) against the git rules
# in AGENTS.md. Used by the local commit-msg hook and by CI, so both enforce
# exactly the same rules.
#
# Usage: check-commit-msg.sh [--scope=docs|--scope=bootstrap] [--no-subject] FILE
#   default       check the first line as a Conventional Commits subject
#                 (max 72 chars) and the whole text for AI-tool attribution
#   --no-subject  only check for AI-tool attribution (for PR descriptions)
#   --scope       only the hook/CI may set this after checking changed paths;
#                 never use it for PR text or an unchecked commit
set -euo pipefail

check_subject=1
scope=none
case "${1:-}" in
    --scope=docs|--scope=bootstrap) scope=${1#--scope=}; shift ;;
esac
if [ "${1:-}" = "--no-subject" ]; then check_subject=0; shift; fi
msg=$(cat "${1:--}")

types='feat|fix|docs|test|refactor|perf|build|ci|chore|style|revert'
# Lowercase start and no trailing period, per the description rules in AGENTS.md.
subject_re="^(${types})(\([a-z0-9-]+\))?!?: [^A-Z].*[^.]$"
attribution_re='Co-Authored-By:.*(Claude|anthropic|Copilot|openai|Cursor|factory|droid)|Claude-Session:|Generated (with|by) \[?(Claude|Copilot|Cursor|Factory|Droid)'
factory_re='^[Cc]o-[Aa]uthored-[Bb]y: factory-droid\[bot\] <138933559\+factory-droid\[bot\]@users\.noreply\.github\.com>$'
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

# Only the exact trailer may be exempted, at the end of a scoped commit.
# PR text always uses --no-subject with no scope and remains attribution-free.
if printf '%s\n' "$msg" | grep -qE "$factory_re"; then
    count=$(printf '%s\n' "$msg" | grep -cE "$factory_re")
    last=$(printf '%s\n' "$msg" | sed '/^[[:space:]]*$/d' | tail -n 1)
    if [ "$scope" = none ] || [ "$check_subject" -eq 0 ] || [ "$count" -ne 1 ] ||
        ! printf '%s\n' "$last" | grep -qE "$factory_re"; then
        echo "error: Factory co-author trailer requires a scoped documentation commit" >&2
        fail=1
    fi
    remaining=$(printf '%s\n' "$msg" | grep -vE "$factory_re" || true)
else
    remaining=$msg
fi
if printf '%s' "$remaining" | grep -qiE "$attribution_re"; then
    echo "error: contains AI-tool attribution outside the permitted trailer" >&2
    fail=1
fi

exit "$fail"
