# Publishing `qnexus-mcp`

Distribution has three parts: **PyPI** (the installable package), the **MCP Registry** (discovery
metadata), and the **public GitHub repo**. Publishing to PyPI makes the code downloadable — treat it as
part of "going public" (the M5 flip), not before.

The [`Publish` workflow](../.github/workflows/publish.yml) automates PyPI + registry on a GitHub Release.
It uses **Trusted Publishing (OIDC)** — no API tokens are stored anywhere.

## One-time setup (a maintainer, once)

### PyPI Trusted Publishing

1. Sign in to PyPI (a personal or a shared Blite account).
2. At <https://pypi.org/manage/account/publishing/>, add a **pending publisher**:
   - **PyPI project name:** `qnexus-mcp`
   - **Owner:** `Blite-HQ` · **Repository:** `qnexus-mcp`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. In GitHub → the repo → **Settings → Environments → New environment** → name it `pypi`.

No token is created: PyPI verifies the GitHub Actions OIDC identity at publish time.

### MCP Registry namespace

The `io.github.Blite-HQ` namespace is granted automatically to a Blite-HQ member via GitHub OAuth when
the workflow runs (or via `mcp-publisher login github` for a manual publish). No pre-setup needed; the
`name` in [`server.json`](../server.json) must stay `io.github.Blite-HQ/qnexus-mcp`.

## Cut the FIRST release (v0.1.0)

`cz bump` needs an existing tag to work from (with none it would compute v0.2.0 from the feat commits).
The first release is therefore manual — and the version files already say `0.1.0`:

1. In `CHANGELOG.md`, rename `## [Unreleased]` to `## [0.1.0] - YYYY-MM-DD` (today's date) and add a
   fresh empty `## [Unreleased]` above it. Commit.
2. Tag and push:
   ```bash
   git tag v0.1.0
   git push --follow-tags
   ```
3. Create a **GitHub Release** for `v0.1.0`. That triggers `publish.yml`:
   - builds the wheel/sdist and publishes to **PyPI** (OIDC, no token);
   - publishes the `server.json` entry to the **MCP Registry**.
4. Verify: `uvx qnexus-mcp` runs from PyPI; the server appears at
   `https://registry.modelcontextprotocol.io/v0.1/servers?search=qnexus-mcp`.

## Cut subsequent releases

1. Bump the version (Commitizen reads the Conventional-Commit history since the last tag):
   ```bash
   uv run cz bump           # updates version in pyproject + __init__ + .cz.toml, updates CHANGELOG, tags vX.Y.Z
   git push --follow-tags
   ```
2. Update `server.json` `version` fields to match, commit, then create the **GitHub Release** for the
   new tag (same automation as above).

## The public flip (M5)

1. Confirm CI is green, the README renders, and there are no secrets.
2. Make the repo public:
   ```bash
   gh repo edit Blite-HQ/qnexus-mcp --visibility public --accept-visibility-change-consequences
   ```
3. Cut the first release (above) → PyPI + registry.
4. Announce to Quantathon participants: `uvx qnexus-mcp` plus the `mcpServers` snippet from the README.

## Manual publish (fallback)

- **PyPI:** `uv build && uv publish` (needs a token or a configured trusted publisher).
- **Registry:** install `mcp-publisher`, then `mcp-publisher login github` → `mcp-publisher publish`.
