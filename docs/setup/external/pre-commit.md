# pre-commit (Repo-Local Git Discipline)

> Scope: install and use `pre-commit` inside this repository only.
> Goal: enforce commit message + branch naming policy without requiring global Codex App skills.

## 1) Pin source

Source of truth:
- `tools/deps/pins.json` -> `dependencies.pre_commit.pin.version`
- `pyproject.toml` + `uv.lock`

Current pinned version:
- `4.5.1`

## 2) Install (repo-local)

At repo root:

```bash
uv sync --locked
bash scripts/install_repo_git_hooks.sh
```

What this does:
- uses `.venv` pre-commit binary,
- installs local hooks in `.git/hooks`:
  - `pre-commit`
  - `commit-msg`
  - `pre-push`

## 3) Verify

```bash
./.venv/bin/pre-commit --version
bash scripts/install_repo_git_hooks.sh --check
```

Optional dry-run:

```bash
./.venv/bin/pre-commit run --all-files
```

Expected result:
- version command returns pinned series,
- `--check` returns `[git-hooks][PASS]`.

## 4) Recovery

If hooks are missing or stale:

```bash
bash scripts/install_repo_git_hooks.sh
```

If `.venv` is missing:

```bash
uv sync --locked
bash scripts/install_repo_git_hooks.sh
```
