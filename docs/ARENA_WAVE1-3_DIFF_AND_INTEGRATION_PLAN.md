# RAIN v6 — Arena Wave 1–3 vs GitHub Repository Diff & Integration Plan

Date: 2026-07-01

## Repositories compared

- **Generated Arena build:** `/home/user/RAIN-v6`
- **GitHub source-of-truth clone:** `/home/user/github-rain-v6`
- **GitHub HEAD:** `2a65d89 feat(dsp): wire apply_6band_multiband into Stage 10, replace legacy 3-band`

## Executive decision

Use the **GitHub repository as source of truth**.

The GitHub repository is far more complete than the generated Wave 1–3 scaffold:

- 394 tracked files excluding `.git` internals
- Existing backend implementation with routes, services, models, tasks, tests
- Existing frontend React/Vite implementation
- Existing RainDSP C++/WASM code
- Existing desktop/plugin scaffolds
- Existing ML training/export code and ONNX model artifacts
- Existing docs, ADRs, installers, and test protocols

The generated Wave 1–3 files should **not** be wholesale copied over the GitHub repo. They are useful as a spec-aligned implementation reference and should be cherry-picked only where they close real gaps.

## Raw comparison summary

| Category | Count |
|---|---:|
| Generated files | 92 |
| GitHub files | 394 |
| Overlapping paths | 44 |
| Generated-only paths | 48 |
| GitHub-only paths | 350 |

All GitHub backend Python currently compiles:

```bash
python -m compileall -q backend/app
```

All generated backend Python also compiles.

## Major finding

The GitHub implementation already contains richer, more project-specific versions of most Wave 1–3 files. In many cases, the generated files are cleaner/spec-focused but less integrated with the actual repo's canonical naming, tests, and architecture.

Examples:

- GitHub uses canonical RainNet parameter schema from `ml/rainnet/heuristics.py` and `backend/app/services/heuristic_params.py`.
- GitHub's `backend/app/services/inference.py` already decodes the 46-neuron RainNet v2 output.
- GitHub's `backend/app/services/master_engine.py` already implements a production server-side DSP chain and recently added a 6-band LR8 multiband Stage 10.
- GitHub has provenance modules under `backend/app/services/provenance/` plus `provenance_pipeline.py`.
- GitHub has `separation_engine.py`, `tasks/separation.py`, and tests for model-loading/separation behavior.

## Do-not-overwrite list

These generated files overlap existing GitHub files and should **not** replace them directly:

- `backend/app/api/routes/*.py`
- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/core/security.py`
- `backend/app/models/*.py`
- `backend/app/services/claude_service.py`
- `backend/app/services/feature_extraction.py`
- `backend/app/services/master_engine.py`
- `backend/app/services/qc_engine.py`
- `backend/app/services/rain_score_v2.py`
- `backend/requirements.txt`
- `docker-compose.yml`
- `docker-compose.gpu.yml`

Reason: GitHub versions are integrated with existing tests, naming conventions, task modules, frontend contract, and RainDSP/ML code.

## Candidate integrations from Arena Wave 3

### 1. K-weighting sign-convention documentation/test

**Generated reference:** `RAIN-v6/backend/app/services/feature_extraction.py`

GitHub currently uses `pyloudnorm` for loudness. That is fine. But the architecture rule explicitly calls out the K-weighting IIR sign convention. We should add a small regression test or doc note to GitHub to prevent future sign regressions in RainDSP and any Python fallback.

Recommended integration:

- Add/extend a test around `rain-dsp/tests/test_lufs.cpp` or backend feature extraction tests.
- Document: `a1 is stored negative and subtracted`.

Decision: **Integrate as test/doc, not as replacement code.**

### 2. Output packaging service abstraction

**Generated reference:** `RAIN-v6/backend/app/services/output_packaging.py`

GitHub's `master_engine.py` currently exports WAV/MP3 internally. A separate `output_packaging.py` would make Stage 15 more modular and easier to connect to RAIN-CERT enforcement.

Recommended integration:

- Create/port a GitHub-native `backend/app/services/output_packaging.py` using repo settings names.
- Refactor `master_engine.py` Stage 15 to call it only after tests pass.

Decision: **Integrate after adapting settings/storage names.**

### 3. Provenance-before-output enforcement

**Generated reference:** `RAIN-v6/backend/app/services/provenance_service.py`

GitHub already has `provenance_pipeline.py` with strict RAIN-CERT creation/sign/verify. The generated implementation's useful part is the Stage 15 enforcement shape: package output, compute hash, create cert, verify before complete.

Recommended integration:

- Do not add duplicate `provenance_service.py` unless needed.
- Instead, wire existing `provenance_pipeline.py` synchronously into the actual render completion path.
- Verify `RAIN-E305` and `RAIN-E306` are raised before a session/job is marked complete.

Decision: **Integrate behavior into existing provenance pipeline.**

### 4. QC report shape compatibility

**Generated reference:** `RAIN-v6/backend/app/services/qc_engine.py`

GitHub QC is richer and uses IDs/severity/critical failures. Generated QC has a simpler dict keyed by check name. Existing frontend/API may expect GitHub's richer shape.

Recommended integration:

- Keep GitHub QC engine.
- If needed, add an adapter that exposes keyed check names for API responses without changing internal QC.

Decision: **Keep GitHub QC; optional API adapter only.**

### 5. RainNet gate defaults

Generated Wave 1 defaults the normalization gate closed:

```env
RAIN_NORMALIZATION_VALIDATED=false
```

GitHub config currently defaults:

```python
RAIN_NORMALIZATION_VALIDATED: bool = True
```

The architecture says the gate is **closed by default** and opened only by sign-off authority Phil Bölke.

Recommended integration:

- Change GitHub default to `False`.
- Keep allowing `.env` to open it explicitly.
- Add/adjust tests to assert closed-by-default behavior.

Decision: **Integrate immediately.**

### 6. PostgreSQL version alignment

Generated Wave 1 uses PostgreSQL 17; README mentions PostgreSQL 18. GitHub compose should be checked for PG version.

Recommended integration:

- Use stable PostgreSQL 17 unless intentionally tracking PG 18 beta/RC.
- Update docs if necessary.

Decision: **Audit compose/docs.**

### 7. Valkey version alignment

Generated Wave 1 used Valkey 8.1 despite comments saying Valkey 9.0. GitHub should be source of truth here.

Recommended integration:

- Keep actual available Valkey image pinned to a real tag.
- Update comments/docs to match the image tag.

Decision: **Audit compose/docs.**

## Files generated-only that may be useful

These generated files do not exist under the same path in GitHub and can be considered for adapted integration:

- `backend/app/services/rainnet_inference.py` — but GitHub already has `services/inference.py`; likely unnecessary.
- `backend/app/services/output_packaging.py` — useful abstraction candidate.
- `backend/app/services/dsp_processors.py` — useful only as Python fallback; GitHub already has real DSP functions in `master_engine.py` and RainDSP C++.
- `backend/app/services/provenance_service.py` — behavior useful, name likely duplicative.
- `backend/app/services/distribution_service.py` — GitHub already has `ddex.py` and `labelgrid.py`; use as reference only.
- `backend/scripts/generate_keys.py` — may be useful if GitHub does not already have an equivalent key-generation helper.

## Immediate patch queue

Recommended first integration patch set:

1. **Gate default fix**
   - `backend/app/core/config.py`: set `RAIN_NORMALIZATION_VALIDATED = False`.
   - Add/update test for closed-by-default gate.

2. **Docs consistency patch**
   - README/docs: PG 17 vs PG 18 consistency.
   - CBOR RFC 7049 → RFC 8949.
   - Remove duplicate waitlist route row if still present.
   - Clarify free tier as preview/no export.

3. **Provenance completion gate audit**
   - Find all session/job completion transitions.
   - Assert signed cert exists before complete.
   - Add regression test for RAIN-E305/E306 behavior.

4. **Stage 15 modularization**
   - Add repo-native `output_packaging.py` only after mapping GitHub settings/storage APIs.

5. **K-weighting regression**
   - Add a test or doc assertion around the sign convention in Python and RainDSP.

## Integration principle

Do not introduce parallel duplicate implementations unless there is a clear call path.

Prefer this order:

1. Keep GitHub canonical modules.
2. Add tests that capture architecture rules.
3. Refactor existing modules to satisfy tests.
4. Only add new modules when they reduce duplication or isolate a stage cleanly.

## Status

This report is the completed Option 2 diff pass. No production code has been overwritten.
