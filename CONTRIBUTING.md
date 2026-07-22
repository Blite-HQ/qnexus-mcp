# Contributing to qnexus-mcp

Thanks for your interest! This is a community project (not affiliated with Quantinuum). Contributions are
welcome under Apache-2.0.

## Developer Certificate of Origin (DCO)

We use the [DCO](https://developercertificate.org/) instead of a CLA. Every commit must be signed off,
certifying you have the right to submit it under the project's license:

```bash
git commit -s -m "feat: ..."
```

This adds a `Signed-off-by: Your Name <you@example.com>` line. No copyright is assigned to anyone; every
contribution stays under Apache-2.0 with clean provenance.

## Development setup

Requires [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                       # install deps into .venv
uv run pytest                 # run the test suite
uv run ruff check .           # lint
uv run ruff format --check .  # format check
uv run mypy src               # type check
```

Optional live tests (need a Nexus account; run `qnx login` first):

```bash
QNEXUS_MCP_LIVE=1 uv run pytest tests/smoke/
```

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`,
`chore:`, `refactor:`, …) and Semantic Versioning. PR titles are checked for the same format.

## Design & tests

- Read [`docs/DESIGN.md`](docs/DESIGN.md) before proposing new tools, especially §6 (permissions) and §7
  (security). Every spend/destructive action is enforced **server-side**.
- New tools need unit tests (mock the Nexus client; see `tests/conftest.py`). Never add a tool that can
  spend credits or mutate state without a guard and a test proving the guard blocks by default.
