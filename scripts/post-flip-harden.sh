#!/usr/bin/env bash
# Run once, immediately after `gh repo edit --visibility public` (M5 step 2).
# GitHub blocks all of this on a private repo under the Free plan (branch
# protection returns 403 "Upgrade to GitHub Pro or make this repository
# public"); it becomes available the instant the repo flips. This script
# closes that gap in one shot instead of clicking through Settings.
set -euo pipefail

REPO="Blite-HQ/qnexus-mcp"

visibility=$(gh api "repos/${REPO}" --jq .visibility)
if [[ "$visibility" != "public" ]]; then
  echo "error: ${REPO} is still '${visibility}'. Flip it first:" >&2
  echo "  gh repo edit ${REPO} --visibility public --accept-visibility-change-consequences" >&2
  exit 1
fi

echo "==> Secret scanning + push protection"
gh api -X PATCH "repos/${REPO}" --input - <<'JSON'
{
  "security_and_analysis": {
    "secret_scanning": {"status": "enabled"},
    "secret_scanning_push_protection": {"status": "enabled"}
  }
}
JSON

echo "==> Dependabot vulnerability alerts"
gh api -X PUT "repos/${REPO}/vulnerability-alerts"

echo "==> Branch protection on main"
# Conservative default: CI must pass, no force-push, no deletion. Does NOT
# force everything through a PR (enforce_admins=false, no required reviews)
# so Dylan can still push directly during active solo iteration; tighten
# with required_pull_request_reviews once there are other contributors.
gh api -X PUT "repos/${REPO}/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "test (3.10)",
      "test (3.11)",
      "test (3.12)",
      "test (3.13)",
      "audit"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

echo "==> Verifying"
gh api "repos/${REPO}" --jq '{visibility, security_and_analysis}'
gh api "repos/${REPO}/branches/main/protection" --jq '{required_status_checks, allow_force_pushes, allow_deletions}'
echo "Done."
