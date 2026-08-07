# Releases

This project uses **git tags** (`v*`) as the release mechanism. Pushing a tag
triggers a GitHub Actions workflow that generates the changelog and publishes
a GitHub Release.

## Cutting a release

One command bumps the version, commits, tags, and pushes:

```bash
make release KIND=patch   # 2.0.0 -> 2.0.1 (bug fixes)
make release KIND=minor   # 2.0.0 -> 2.1.0 (new features)
make release KIND=major   # 2.0.0 -> 3.0.0 (breaking changes)
```

What `make release` does:

1. Reads the current version from `pyproject.toml`
2. Bumps it per `KIND` (patch/minor/major)
3. Updates `version = "..."` in `pyproject.toml`
4. Commits (`release: vX.Y.Z`) and tags (`vX.Y.Z`)
5. Pushes `main` and the tag

## What CI does on tag push

The `.github/workflows/release.yml` workflow runs when a `v*` tag is pushed:

1. **Verifies the tag matches `pyproject.toml`** — fails if they drifted
2. **Generates `CHANGELOG.md`** via `scripts/gen_changelog.py` — reads commits
   since the previous tag, categorizes by conventional-commit prefix
   (`feat:` → Added, `fix:` → Fixed, `test:`/`docs:`/`chore:` → Changed),
   and prepends a `## [X.Y.Z] - YYYY-MM-DD` section
3. **Commits `CHANGELOG.md` back to `main`** as `github-actions[bot]`
4. **Creates a GitHub Release** with the new changelog section as the body
   (falls back to GitHub's auto-generated notes if the section is empty)

## Version sync

The version lives in **one place**: `pyproject.toml`. The tag must match it.
`make release` keeps them in sync; the workflow enforces it as a safety net.

## CHANGELOG.md

`CHANGELOG.md` is **auto-generated** — do not hand-edit it. It follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

To preview what the next changelog section will look like without tagging:

```bash
python3 scripts/gen_changelog.py v2.1.0 --dry-run
```

## Manual tag push (skip make)

If you prefer to tag manually, ensure `pyproject.toml` version matches first:

```bash
git tag v2.0.1
git push origin v2.0.1
```

## Out of scope

- **PyPI publishing** — the package is installed from source (`pip install -e .`),
  not published to PyPI. A publish workflow can be added later if needed.
- **Pre-releases** — tags like `v2.0.1-rc1` are treated as full releases. Add
  prerelease detection in the workflow if you need RC/alpha/beta tags.
