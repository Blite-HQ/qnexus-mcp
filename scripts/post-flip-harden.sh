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

echo "==> Branch protection on main (repository ruleset)"
# A ruleset, not the classic branches/protection API -- the modern, stackable
# replacement (same choice already made for Chimera). CI must pass, no
# force-push, no deletion. No pull_request rule, so this doesn't force every
# change through a PR -- add one once there are other contributors.
gh api -X POST "repos/${REPO}/rulesets" --input - <<'JSON'
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          {"context": "test (3.10)"},
          {"context": "test (3.11)"},
          {"context": "test (3.12)"},
          {"context": "test (3.13)"},
          {"context": "audit"}
        ]
      }
    }
  ]
}
JSON

echo "==> Verifying"
gh api "repos/${REPO}" --jq '{visibility, security_and_analysis}'
gh api "repos/${REPO}/rulesets" --jq '.[] | {id, name, enforcement}'
echo "Done."
