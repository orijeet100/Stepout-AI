# Releasing

A release is a git tag `v<version>` on `main`. Pushing the tag runs [`.github/workflows/release.yml`](../.github/workflows/release.yml): it builds the page and the wheel, proves the wheel installs and runs on a clean Windows machine, and attaches it to a GitHub Release. The README's install line points at that file, so it works only once the release exists.

```
uv tool install https://github.com/orijeet100/Stepout-AI/releases/download/v0.1.0/stepout-0.1.0-py3-none-any.whl
                                                              └─ the tag ─┘          └─ the version in pyproject.toml ─┘
```

## Cut a release

1. **`main` is what you want to ship**, merged and green. (Every push to a `feat/**` branch already runs the same build and smoke test on a clean Windows runner; a tag runs it again and then publishes.)
2. **Set the version.** `version` in `pyproject.toml` must equal the tag without the `v` (`0.1.1` for `v0.1.1`): the wheel's file name comes from it, and so does the URL. In one PR change both `pyproject.toml` and the install URL in `README.md` (the tag and the file name), and merge it. A release for a version that already has a tag cannot be made again; use the next number.
3. **Tag and push.** The tag is the release: do not also create it on GitHub's Releases page, because the workflow creates the Release itself and `gh release create` fails when one already exists for that tag.

```
git checkout main
```

```
git pull
```

```
git tag v0.1.1
```

```
git push origin v0.1.1
```

4. **Watch it** (about two minutes) with `gh run watch`, or on the repository's Actions tab. In order, the workflow: checks out; builds the page (`npm ci`, `npm run build` in `web/`, which writes `src/stepout/_web/`); builds the wheel (`uv build --wheel`); runs `scripts/smoke_install.py` on it (installs it into an empty tool folder, starts it, checks the page and the API, `status`, a refused second start, `stop`); and only then runs `gh release create` with the wheel attached and the install line as the notes. If the smoke test fails nothing is published.
5. **Check it from outside.** The Release page lists `stepout-<version>-py3-none-any.whl`, and this prints `200`:

```
curl -s -o /dev/null -w "%{http_code}" -L https://github.com/orijeet100/Stepout-AI/releases/download/v0.1.1/stepout-0.1.1-py3-none-any.whl
```

   Then install that URL the way a new user would, in a throwaway folder (it touches nothing outside `%TEMP%`):

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cleanroom.ps1 -Wheel https://github.com/orijeet100/Stepout-AI/releases/download/v0.1.1/stepout-0.1.1-py3-none-any.whl
```

## Trying the workflow without releasing

On GitHub, Actions, "release", "Run workflow" (`workflow_dispatch`) builds and smoke-tests the wheel and keeps it as a workflow artifact named `stepout-wheel`. No Release is created.

## When something goes wrong

- **The smoke test failed.** Nothing was published. Fix it on `main` through a PR, then move the tag: delete it (below) and tag again.
- **A bad release was published.** Delete the Release and the tag, fix, and release again. If anyone may have installed it, use the next version number instead: people who already have the bad one keep it, and a new number reaches them with a normal upgrade (`uv tool install --force <the new URL>`).

```
gh release delete v0.1.1 --yes
```

```
git push origin :refs/tags/v0.1.1
```

```
git tag -d v0.1.1
```

## Know

- **The wheel is the whole release.** There is no PyPI package (`uvx stepout` would need one, and it is a public name claim: [roadmap](roadmap.md)). The built page is inside the wheel, so a user needs no Node.
- **A release does not lock its dependencies.** `pyproject.toml` gives ranges, and `uv tool install` resolves them when the user installs, so two installs of the same wheel on different days can get different library versions (seen: `pydantic-ai-slim` resolved to 2.56.0 on 2026-10-14 and to 2.57.0 on 2026-10-16 from the same range). The offline suite and the smoke test run against whatever was newest at the time.
- **A release holds only what was on `main` at the tag.** `v0.1.0` is the PR 5 merge (`5b6edf9`); commits after it, such as the design fixes, are in the next release.
- **The first release, `v0.1.0`, was published on 2026-10-15.** Its install URL answers 200 and installs into an empty folder.
