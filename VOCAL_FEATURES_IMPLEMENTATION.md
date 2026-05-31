# RAIN Vocal Production Features — Implementation Guide

**Status:** SPECIFICATION & ARCHITECTURAL DESIGN  
**Version:** 1.0  
**Date:** 2026-05-31  
**Author:** Phil Weyers Bölke / ARCOVEL Technologies International

---

## Executive Summary

This document specifies the complete integration of **two production-tier audio features** into RAIN:

### 1. Vocal Pitch Correction (Creator+)
- CREPE deep learning pitch detector + WORLD vocoder
- Three correction modes: snap, smooth, transparent
- Optional formant preservation (Artist+)
- Quota: 20/mo Creator, 50/mo Artist, 100/mo Studio Pro, Unlimited Enterprise

### 2. Instrument Synthesis (Artist+)
- Suno v3 API for text-to-music generation
- Automatic key/tempo alignment
- Blending with original mix at user-specified ratio
- Variation selection (1–3 options per tier)
- Quota: 10/mo Artist, 30/mo Studio Pro, Unlimited Enterprise

Both features integrate seamlessly into the existing **12-stem separation** → **mastering** → **distribution** pipeline.

---

## Key Files & References

### Documentation
- **[Vocal-Production-Features.md](docs/wiki/Vocal-Production-Features.md)** — Complete specification (database, API, error codes, roadmap)
- **[Architecture.md](docs/wiki/Architecture.md)** — Updated system topology including both features
- **[Tiers-and-Pricing.md](docs/wiki/Tiers-and-Pricing.md)** — Tier gating matrix (see update below)

### New Service Modules (to implement)
- `backend/app/services/pitch_correction_service.py`
- `backend/app/services/instrument_synthesis_service.py`

### New API Routes (to implement)
- `backend/app/api/routes/pitch_correction.py`
- `backend/app/api/routes/instrument_synthesis.py`

### Database Migrations
- `backend/migrations/versions/0006_vocal_instruments.py` (generated, not yet committed)

---

## Tier Gating Updates

### Vocal Pitch Correction

| Tier | Enabled | Quota/mo | Max Duration | Formant Preservation |
|---|---|---|---|---|
| Free | ❌ | — | — | ❌ |
| Spark | ❌ | — | — | ❌ |
| Creator | ✅ | 20 | 5 min | ❌ |
| Artist | ✅ | 50 | 10 min | ✅ |
| Studio Pro | ✅ | 100 | 30 min | ✅ |
| Enterprise | ✅ | Unlimited | Unlimited | ✅ |

### Instrument Synthesis

| Tier | Enabled | Quota/mo | Variations |
|---|---|---|---|
| Free | ❌ | — | — |
| Spark | ❌ | — | — |
| Creator | ❌ | — | — |
| Artist | ✅ | 10 | 1 |
| Studio Pro | ✅ | 30 | 3 |
| Enterprise | ✅ | Unlimited | 3 |

---

## Implementation Checklist

### Phase 1: Infrastructure Setup (Week 1–2)

- [ ] Database migrations written + tested locally
- [ ] New service modules stubbed out
- [ ] API routes scaffolded (happy path only)
- [ ] Tier gating implemented in `feature_gates.py`
- [ ] Quota tracking implemented in `quota.py`

### Phase 2: Vocal Pitch Correction Core (Week 3–5)

**Dependencies:**
```bash
pip install crepe pyworld librosa pyloudnorm
```

**Implementation:**
- [ ] `PitchCorrectionService.correct_vocal()` — full 7-stage pipeline
- [ ] CREPE F0 extraction (with librosa PYIN fallback)
- [ ] Key detection from F0 contour
- [ ] Vibrato parameter extraction
- [ ] Correction curve generation (3 modes)
- [ ] WORLD pitch shift + formant preservation
- [ ] Output quality validation
- [ ] Post-render metrics computation

**Testing:**
- [ ] Unit tests: CREPE accuracy (±2% F0 error tolerance)
- [ ] Unit tests: Key detection (>85% accuracy on commercial recordings)
- [ ] Unit tests: Vibrato preservation (spectral comparison)
- [ ] Unit tests: Formant shift (separate formant from pitch, verify no phase artifacts)
- [ ] Integration tests: End-to-end correctness
- [ ] Load tests: 5-min audio processing latency <30 seconds

### Phase 3: Instrument Synthesis Core (Week 6–10)

**Dependencies:**
```bash
pip install suno  # Suno API client library (if available; otherwise HTTP client)
```

**Implementation:**
- [ ] Suno API integration (sandbox mode testing)
- [ ] Composition prompt generation from user intent
- [ ] Key/tempo detection on original mix (librosa + MERT embeddings)
- [ ] Key/tempo alignment (time-stretch + pitch-shift) via librosa
- [ ] Loudness matching (pyloudnorm) for blending
- [ ] Blending algorithm (mix original + synthesized at user ratio)
- [ ] Variation selection UI
- [ ] Fallback error handling (API timeout, rate limits, generation failure)

**Testing:**
- [ ] Unit tests: Key detection (±1 semitone tolerance)
- [ ] Unit tests: Tempo detection (±1 BPM tolerance)
- [ ] Unit tests: Time-stretch accuracy (spectral comparison)
- [ ] Unit tests: Loudness matching (±0.5 LU target)
- [ ] Integration tests: Suno API (sandbox mode)
- [ ] End-to-end tests: Full synthesis pipeline

### Phase 4: Compliance & Provenance (Week 11–12)

- [ ] C2PA AI assertion injection
- [ ] AudioSeal watermark integration
- [ ] DDEX AI disclosure field population
- [ ] AI declaration logging

### Phase 5: UI & UX (Week 13–14, parallel with Phase 4)

**Frontend components (React):**
- [ ] Pitch correction panel (mode selector, key picker, before/after preview)
- [ ] Instrument synthesis panel (prompt input, style selector, variation gallery)
- [ ] Real-time progress indicators (WebSocket)
- [ ] Error messaging (user-friendly RAIN-E* codes)

### Phase 6: Testing & QA (Week 15–16)

- [ ] Full test suite passing (unit + integration + E2E)
- [ ] Load testing (concurrent jobs, quota enforcement)
- [ ] Compliance verification (C2PA, DDEX, AudioSeal)
- [ ] Manual QA (artist workflow validation)
- [ ] Documentation updates

---

## Error Code Registry

### Pitch Correction Errors

| Code | HTTP | Meaning | Recovery |
|---|---|---|---|
| RAIN-E710 | 400 | Vocal stem not found | Re-upload track, ensure vocals isolated |
| RAIN-E711 | 503 | CREPE model unavailable | Retry later or contact support |
| RAIN-E712 | 400 | Pitch confidence too low (unvoiced) | User feedback: try different recording |
| RAIN-E713 | 400 | Key detection failed | Manual key input required |
| RAIN-E714 | 500 | WORLD vocoder synthesis error | System error, retry or report |
| RAIN-E715 | 400 | Output validation failed (artifacts) | Reduce correction intensity (smooth mode) |

### Instrument Synthesis Errors

| Code | HTTP | Meaning | Recovery |
|---|---|---|---|
| RAIN-E720 | 503 | Suno API unavailable | Retry after 5 minutes |
| RAIN-E721 | 504 | Generation timeout (>5 min) | Simplify prompt, try again |
| RAIN-E722 | 400 | Mix analysis failed | Try different mix or manual params |
| RAIN-E723 | 500 | Alignment failed (stretch/shift) | System error, retry |
| RAIN-E724 | 500 | Blending failed (loudness) | System error, contact support |
| RAIN-E725 | 500 | S3 export failed | System error, retry |

---

## External API Dependencies

### Suno v3 API

- **Endpoint**: `api.suno.ai` (REST)
- **Rate limit**: 10 req/min (tier-dependent)
- **Cost**: $0.50–1.50 per generation
- **SLA**: 99.5% uptime (publicly available, but unshielded)
- **Fallback**: None — graceful degradation with user messaging

**Sandbox environment:**
```python
SUNO_API_KEY = os.getenv("SUNO_SANDBOX_KEY")
SUNO_API_BASE = "https://api-sandbox.suno.ai"  # Testing
```

---

## Database Schema & Migrations

See `backend/migrations/versions/0006_vocal_instruments.py` in **Vocal-Production-Features.md** for complete schema.

**Key indexes:**
- `idx_pitch_correction_parent` (parent session lookup)
- `idx_pitch_correction_user` (user isolation verification)
- `idx_instrument_synthesis_parent` (parent session lookup)
- `idx_instrument_synthesis_user` (user isolation verification)

---

## API Endpoint Reference

### Vocal Pitch Correction

```
POST /api/v1/pitch-correction/correct
GET  /api/v1/pitch-correction/{correction_id}/status
```

Full spec: See **Vocal-Production-Features.md**

### Instrument Synthesis

```
POST /api/v1/instruments/add
GET  /api/v1/instruments/jobs/{job_id}
GET  /api/v1/instruments/jobs/{job_id}/variations
POST /api/v1/instruments/jobs/{job_id}/select-variation
```

Full spec: See **Vocal-Production-Features.md**

---

## Compliance & Certification

### C2PA v2.2

All pitch-corrected and synthesized outputs must include AI disclosure:

```json
{
  "ai_assertions": [
    {
      "component": "pitch_correction",
      "model": "crepe-v0.0.13",
      "description": "Vocal pitch detection and correction"
    },
    {
      "component": "instrument_synthesis",
      "model": "suno-v3",
      "description": "AI-generated orchestration"
    }
  ]
}
```

### DDEX ERN 4.3

Per-track AI involvement must be populated:

```xml
<ai_involvement>
  <ai_involvement_type>processing</ai_involvement_type>
  <components>
    <component_type>pitch_correction</component_type>
    <model_name>CREPE + WORLD</model_name>
  </components>
</ai_involvement>
```

### EU AI Act Article 50

Hard deadline: **2 August 2026**. Both features automatically populate provenance fields required for compliance.

---

## Performance Targets

### Vocal Pitch Correction

- **Latency**: ~5–15 sec per minute of audio (CPU-bound, single-threaded)
- **Memory**: ~500 MB peak (CREPE model + audio buffer)
- **Throughput**: Can process 4–6 mins of audio per minute on single CPU
- **Cost per correction**: <$0.01 (local computation)

### Instrument Synthesis

- **Latency**: ~45–120 sec per generation (Suno API call + blending)
- **Memory**: ~2 GB (loaded models + mix buffer)
- **Cost per generation**: $0.50–1.50 (Suno API)
- **Queue depth**: Expected 50–100 jobs during peak hours

---

## Rollout Strategy

### Soft Launch (Week 16–17)
- Deploy to **Artist** tier only (instrument synthesis)
- Creator tier gets **pitch correction** only (limited beta)
- Monitor error rates, latency, cost overruns

### General Availability (Week 18)
- Enable all tiers according to tier matrix
- Enable quota enforcement
- Announce feature in release notes

### Post-Launch Monitoring
- Track RAIN-E71x error rate (target: <0.5% of jobs)
- Monitor Suno API cost per user (alert if >$100/user/month)
- Collect user feedback (ratings, reviews)
- Performance regression tests (weekly)

---

## Testing Command Reference

```bash
# Full test suite
pytest backend/tests/ -v -k "pitch_correction or instrument_synthesis"

# Specific test classes
pytest backend/tests/test_pitch_correction.py -v
pytest backend/tests/test_instrument_synthesis.py -v

# Integration test (requires running stack)
docker-compose up
python rain-tests/integration_tests/test_vocal_features.py

# Load test (concurrent jobs)
k6 run rain-tests/performance/vocal_load_test.js
```

---

## Documentation Updates Required

- [ ] Wiki: Vocal-Production-Features.md (NEW, complete)
- [ ] Wiki: Architecture.md (UPDATED with feature additions)
- [ ] Wiki: Tiers-and-Pricing.md (UPDATED with tier matrix)
- [ ] Wiki: Backend-API.md (ADD service descriptions)
- [ ] Wiki: Error-Codes.md (ADD RAIN-E71x / RAIN-E72x codes)
- [ ] README.md (UPDATED with feature highlights)
- [ ] Changelog: CHANGELOG.md (NEW v6.1 release notes)

---

## Sign-Off & Handoff

**Specification Owner**: Phil Weyers Bölke / ARCOVEL  
**Implementation Lead**: [TBD — assign from team]  
**QA Lead**: [TBD — assign from QA team]  
**Deployment Lead**: [TBD — assign from DevOps]

**Sign-off required before Phase 2 start:**
- [ ] Specification reviewed and approved
- [ ] Database schema reviewed (correctness + RLS)
- [ ] API contract approved (compatibility with frontend)
- [ ] External API integrations (Suno) contracted

---

*This specification is complete and ready for implementation. See linked wiki pages for full technical details.*
