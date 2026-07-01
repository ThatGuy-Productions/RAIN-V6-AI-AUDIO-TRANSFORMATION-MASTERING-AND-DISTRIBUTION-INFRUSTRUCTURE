# RAIN v6 — Arena Integration Status

Date: 2026-07-01

## Applied patches

### 1. Normalization gate closed by default

Changed:

- `backend/app/core/config.py`

```python
RAIN_NORMALIZATION_VALIDATED: bool = False
```

Added regression coverage:

- `backend/tests/test_spec_compliance.py::test_normalization_gate_closed_by_default`

Purpose: enforce the architecture rule that RainNet inference is disabled unless explicitly opened after validation/sign-off by Phil Bölke.

### 2. Prototype mastering route RAIN-CERT verification gate

Changed:

- `backend/app/api/routes/master.py`

The prototype in-memory `/master/{id}/process` path now verifies that the generated RAIN-CERT is signed and immediately validates before setting:

```python
session["status"] = "complete"
```

Failures raise `RAIN-E306`-style runtime errors.

Note: the DB/S3 Celery render path in `backend/app/tasks/render.py` already has the stricter synchronous provenance gate using `provenance_pipeline.create_rain_cert()` and `sign_and_verify()` before updating the session row to `complete`.

### 3. README consistency patch

Changed:

- `README.md`

Updates:

- Claude model wording changed from hard-coded `Claude Sonnet 4.6` / `claude-sonnet-4-6` to configurable Claude Sonnet with default `claude-sonnet-4-20250514`.
- CBOR reference updated from RFC 7049 to RFC 8949.
- Duplicate waitlist API route row removed.
- API route count corrected to 18 mounted routers.
- Casual tier clarified as preview-only with no file export.

### 4. Integration plan added

Added:

- `docs/ARENA_WAVE1-3_DIFF_AND_INTEGRATION_PLAN.md`

Purpose: records why the GitHub repo remains source of truth and how generated Wave 1–3 code should be selectively integrated.

## Validation performed

Python compilation passed:

```bash
python -m compileall -q backend/app backend/tests/test_spec_compliance.py
```

Attempted targeted pytest:

```bash
PYTHONPATH=backend pytest -q backend/tests/test_spec_compliance.py -q
```

Blocked by missing local dependency in this sandbox:

```text
ModuleNotFoundError: No module named 'pytest_asyncio'
```

The dependency is already declared in `backend/requirements.txt` and `backend/requirements.lock`; install backend test dependencies before running the full test suite.

## Current modified files

```text
M  README.md
M  backend/app/api/routes/master.py
M  backend/app/core/config.py
M  backend/tests/test_spec_compliance.py
?? docs/ARENA_WAVE1-3_DIFF_AND_INTEGRATION_PLAN.md
?? docs/ARENA_INTEGRATION_STATUS.md
```

## Recommended next patch

1. Install backend test dependencies or run tests in the project Docker backend image.
2. Run:

```bash
PYTHONPATH=backend pytest -q backend/tests/test_spec_compliance.py
PYTHONPATH=backend pytest -q backend/tests/test_master_engine.py backend/tests/test_wasm_bridge_fallback.py backend/tests/test_rls.py
```

3. If tests are green, commit the current integration patch.
4. Next development patch should modularize Stage 15 output packaging only if it can reuse existing storage/provenance APIs without duplicating the already-working render task provenance gate.

## Virtual environment test run

Created a local virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

Installed the backend test/runtime dependency subset needed for the integration checks, plus:

```bash
python -m pip install imageio-ffmpeg
```

`imageio-ffmpeg` was added because this sandbox does not have a system `ffmpeg` binary, while `master_engine.export_mp3()` requires ffmpeg through pydub.

### Additional patch from venv run

Changed:

- `backend/app/services/master_engine.py`
- `backend/requirements.txt`

`export_mp3()` now prefers system ffmpeg, but falls back to the `imageio-ffmpeg` wheel-provided executable in virtualenv/test environments.

This keeps production behavior intact while making MP3 packaging testable in clean Python environments.

### Passing targeted tests

```bash
source .venv/bin/activate
PYTHONPATH=.:backend pytest -q backend/tests/test_spec_compliance.py -q
```

Result:

```text
13 passed
```

```bash
PYTHONPATH=.:backend pytest -q \
  backend/tests/test_master_engine.py \
  backend/tests/test_wasm_bridge_fallback.py \
  backend/tests/test_rls.py -q
```

Result:

```text
11 passed, 1 skipped
```

### Full backend test attempt

```bash
PYTHONPATH=.:backend pytest -q backend/tests -q
```

Result summary:

```text
many tests passed, 4 skipped, but full suite still has failures unrelated to the current integration patch
```

Observed existing issues:

1. `backend/tests/test_rls.py` uses emails under `@rls.test`; current `email-validator` rejects `.test` as a reserved/special-use domain.
2. Some upload/auth route tests hit a `slowapi` dynamic limit callable signature issue:
   `TypeError: _dynamic_limit() missing 1 required positional argument: 'request'`.
3. Separation model-loading tests require additional separation/GPU dependencies such as torch and the RoFormer inference packages.

The focused integration tests are green in the virtualenv. The remaining full-suite failures should be handled as a separate test-environment compatibility patch.

## Band-split fallback decision

Confirmed: spectral band splitting is now treated as the official CPU-safe fallback for Pass 3 drum sub-separation.

Changed:

- `backend/app/services/separation_engine.py`

Updates:

- Removed import-time `torch` dependency so the separation module can be imported and tested without GPU/torch packages installed.
- Kept `torch` imports lazy inside model-loading/inference functions.
- Clarified Pass 3 comments: band split is the intended fallback when LarsNet/DrumSep is unavailable.

Validation:

```bash
source .venv/bin/activate
PYTHONPATH=.:backend pytest -q backend/tests/test_separation_model_loading.py -q
```

Result:

```text
4 passed
```
