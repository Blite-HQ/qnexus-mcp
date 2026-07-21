<!-- Thanks for contributing! Please read CONTRIBUTING.md first (DCO sign-off required: `git commit -s`). -->

## What & why

<!-- What does this change do, and why? Link any related issue. -->

## Safety checklist

- [ ] No tool can spend credits or mutate cloud state without a server-side guard, and a test proves the guard blocks by default (see `docs/DESIGN.md` §6–§7).
- [ ] No secret material (tokens, cookies) is read, stored, logged, or returned anywhere.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src` all pass.
- [ ] Commits are signed off (`git commit -s`) and follow Conventional Commits.
