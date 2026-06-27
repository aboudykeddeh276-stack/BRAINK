#!/usr/bin/env bash
# FUNCTION_BOOTSTRAP_GENERAL_GOVERNANCE_REMOTE
# Purpose: bind the current repository to the GENERAL-GOVERNANCE- GitHub remote
# and push the current governance branch when authenticated credentials exist.

set -euo pipefail

GOVERNANCE_REMOTE_NAME="${GOVERNANCE_REMOTE_NAME:-origin}"
GOVERNANCE_REMOTE_URL="${GOVERNANCE_REMOTE_URL:-https://github.com/aboudykeddeh276-stack/GENERAL-GOVERNANCE-.git}"
GOVERNANCE_BRANCH_NAME="${GOVERNANCE_BRANCH_NAME:-main}"

printf 'GOVERNANCE_BOOTSTRAP_REMOTE_NAME: %s\n' "${GOVERNANCE_REMOTE_NAME}"
printf 'GOVERNANCE_BOOTSTRAP_REMOTE_URL: %s\n' "${GOVERNANCE_REMOTE_URL}"
printf 'GOVERNANCE_BOOTSTRAP_BRANCH_NAME: %s\n' "${GOVERNANCE_BRANCH_NAME}"

if git remote get-url "${GOVERNANCE_REMOTE_NAME}" >/dev/null 2>&1; then
  git remote set-url "${GOVERNANCE_REMOTE_NAME}" "${GOVERNANCE_REMOTE_URL}"
else
  git remote add "${GOVERNANCE_REMOTE_NAME}" "${GOVERNANCE_REMOTE_URL}"
fi

git branch -M "${GOVERNANCE_BRANCH_NAME}"
git push -u "${GOVERNANCE_REMOTE_NAME}" "${GOVERNANCE_BRANCH_NAME}"
