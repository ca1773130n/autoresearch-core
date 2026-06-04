# Releasing & ownership

This document resolves the cross-repo ownership questions for
`autoresearch-core`: who versions it, how releases happen, how consumers
pin it, and how parity with the GRD reference implementation is kept.

## Ownership

- **Maintainer / release authority:** Cameleon X (the
  [GRD](https://github.com/ca1773130n/GetResearchDone) maintainer). One
  maintainer, one release path — no shared publish rights.
- **Reference implementation:** GRD's TypeScript modules
  (`lib/research/verdict.ts`, `gates.ts`, `runner.ts`) define the behavior.
  This package follows the reference; it does not lead it. Deliberate
  deviations (fail-fast `check_gate`, non-finite metric hardening,
  human-readable `detail` strings) are documented in
  [`parity/vectors.json`](parity/vectors.json) `_meta.excluded_deviations`
  and in the [tutorial](TUTORIAL.md).

## Versioning (SemVer, 0.x phase)

- **Patch (`0.1.z`)** — docs, fixes that don't change any verdict/gate/parse
  outcome for valid inputs. Always safe for consumers.
- **Minor (`0.y.0`)** — anything that changes public API shape or an
  outcome for some input, including hardening. In the 0.x phase a minor IS
  the breaking boundary.
- Consumers therefore pin **`>=0.1.x,<0.2`** (Agented) or an exact `==`
  (HypePaper). Both upgrade *explicitly* — never via an unpinned range. A
  `0.2.0` requires a deliberate bump + changelog read in each consumer.
- `1.0.0` when the API survives a full GRD milestone without shape changes.

## Release procedure

1. Bump the version in **both** `pyproject.toml` and
   `autoresearch_core/__init__.py` (they must match).
2. Add a `CHANGELOG.md` section (Keep a Changelog format).
3. Commit, then tag and push:
   ```bash
   git tag v0.y.z && git push origin main v0.y.z
   ```
4. The tag triggers `.github/workflows/publish.yml` → build → **PyPI
   Trusted Publishing** (OIDC, environment `pypi`, no stored token).
5. Create the GitHub Release from the CHANGELOG section:
   ```bash
   gh release create v0.y.z --title v0.y.z --notes-file <(awk ...)
   ```
6. Verify: `pip install autoresearch-core==0.y.z` in a clean venv, import,
   one `measure()` smoke call.

There is no release coupling with consumers: HypePaper (Railway) and
Agented deploy on their own cadence and only see a new version when they
bump their pin in their own PR.

## Parity vectors — the drift contract

Behavioral parity between GRD (TS) and this kernel (Python) is enforced by
**one shared fixture file run by both test suites**:

| Repo | Path | Runner |
|---|---|---|
| autoresearch-core (canonical) | `parity/vectors.json` | `tests/test_vectors.py` (CI on every push) |
| GRD (vendored) | `tests/fixtures/autoresearch-parity-vectors.json` | `tests/unit/research/parity-vectors.test.ts` (`npm test`) |

Rules:

1. The two copies must stay **byte-identical** (`shasum -a 256` both).
2. A behavior change in GRD's `verdict.ts`/`gates.ts`/`runner.ts` fails its
   own vector test → whoever makes that change must update the vectors in
   **both** repos and ship a kernel release in the same effort.
3. A kernel-only behavior change is a parity break by definition — don't,
   unless it's a documented deviation added to `_meta.excluded_deviations`.
4. New shared behavior ⇒ new vectors, added to both copies.

## Consumer upgrade checklist

1. Read the CHANGELOG entries between the pinned and target version.
2. Bump the pin (`requirements.txt` / `pyproject.toml`), regenerate the
   lock (`uv lock` for Agented), PR it.
3. Let the consumer's own deploy pipeline validate (Railway build for
   HypePaper; Docker build for Agented).
