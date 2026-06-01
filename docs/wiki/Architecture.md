# Architecture

**Document ref:** RAIN-ARCH-PIPELINE-v1.0 · RAIN-MASTER-SPEC-v6.1

---

## System Topology

```
User Browser / Tauri Desktop
       │
       ├─ Web Audio API  ←── Preview Path  (32-bit float, non-deterministic, <50ms latency)
       │
       └─ RainDSP WASM   ←── Render Path   (64-bit double, deterministic, authoritative)
               │
               └─ ONNX Runtime Web ←── RainNet v2 inference (local, WASM)
                       │
                       ▼  (user-initiated upload only)
              FastAPI Backend
                       │
              ┌────────┼────────┬──────────┐
              │        │        │          │
          PostgreSQL  Valkey    S3    GPU Workers
          (RLS on)   9.0      (tiered) (BS-RoFormer)
                       │
        ┌──────────────┼──────────────────┬──────────┐
        │              │                  │          │
   Distribution    Pitch Corr.       Instruments    AI
      (DDEX)     (CREPE/WORLD)      (Suno v3)    (Claude)
```

### The Two Paths — Critical Distinction

| | Preview Path | Render Path |
|---|---|---|
| Engine | Web Audio API | RainDSP WASM |
| Precision | 32-bit float | 64-bit double |
| Determinism | Non-deterministic | Bit-identical across runs |
| Latency | <50 ms | Batch |
| Deliverable? | **No** — monitoring only | **Yes** — the authoritative output |
| Expected divergence | ±0.5 LU LUFS-I, ±0.3 dB true peak | — |

**Never** use the preview path as the source of a deliverable. The UI must display a disclaimer on preview measurements: *"Preview measurement — final render may differ slightly."*

---

## Full Processing Pipeline

```
User Language ("make it warmer and punchier")
           │
           ▼
    ┌─────────────┐
    │ INTENT      │  Keyword classifier → ControlSignals
    │ ENGINE      │  {warmth: +2.5, punch: +2.5, brighten: -0.8}
    └──────┬──────┘
           │ ControlSignals (bounded deltas + confidence + restraints)
           ▼
    ┌─────────────┐
    │ MACRO       │  7 macro knobs → current MacroValues
    │ CONTROLLER  │  {brighten, glue, width, punch, warmth, space, repair}
    └──────┬──────┘
           │ MacroValues (7 × [0.0, 10.0])
           ▼
    ┌─────────────┐
    │ RAINNET v2  │  EfficientNet-B2 + FiLM conditioning
    │ (or heuristic│  Genre- / platform- / artist-identity-aware
    │  fallback)  │  → 46 DSP parameters (ProcessingParams)
    └──────┬──────┘
           │ ProcessingParams (46 canonical fields)
           ▼
    ┌─────────────┐
    │ PARAMETER   │  Range validation, schema conformance, conflict detection
    │ VALIDATION  │
    └──────┬──────┘
           │ Validated ProcessingParams
           ▼
    ┌─────────────┐
    │ RAINDSP     │  C++20/WASM, 64-bit double, deterministic
    │ ENGINE      │  EQ → Multiband → M/S → Saturation → SAIL → Dither
    └──────┬──────┘
           │ Processed audio
           ▼
    ┌─────────────────────────────────────────┐
    │ [OPTIONAL] VOCAL PRODUCTION FEATURES    │
    │ · Pitch Correction (CREPE + WORLD)      │
    │ · Instrument Synthesis (Suno v3)        │
    └──────┬──────────────────────────────────┘
           │ Enhanced mix
           ▼
    ┌─────────────┐
    │ RESTRAINT   │  Post-processing verification:
    │ VALIDATOR   │  LUFS ±0.5 LU, true peak ceiling, crest factor ≥60%,
    │             │  phase correlation. Fail → reduce gain, retry (max 3×)
    └──────┬──────┘
           │ Verified audio
           ▼
    ┌─────────────┐
    │ RAIN SCORE  │  Technical(60) + Dynamic(15) + Translation(10) + Emotional(15)
    │ v2          │  → 0–100 · verdict · per-platform compliance
    └──────┬──────┘
           │ ScoreBreakdown
           ▼
    ┌─────────────┐
    │ OUTPUT      │  WAV 24-bit/48kHz (archive master)
    │             │  MP3 320kbps/44.1kHz (with LUFS correction)
    │             │  RAIN-CERT Ed25519 provenance signature
    │             │  C2PA v2.2 manifest (EU AI Act Article 50)
    └─────────────┘
```

---

## Technology Stack (Authoritative)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 18 + Vite 6 + TypeScript 5 + Tailwind 4 | |
| Preview Engine | Web Audio API + WebGL2 | Local only |
| Render Engine | RainDSP (C++20/WASM via Emscripten 3.1.50+) | Local only |
| ML Inference | ONNX Runtime Web (WASM) | Local for base/tiny/nano variants |
| Backend API | FastAPI 0.109+ (Python 3.12+) | |
| Database | PostgreSQL 18+ with RLS (UUIDv7 primary keys) | |
| Cache / Queue | Valkey 9.0 (Linux Foundation Redis fork, BSD) | |
| Object Storage | S3-compatible (MinIO in dev) | |
| ML Training | PyTorch 2.x | |
| Source Separation | BS-RoFormer SW cascaded 4-pass pipeline (12-stem) | Cloud GPU only |
| Vocal Pitch Correction | CREPE v0.0.13 + WORLD vocoder | Creator+ tier |
| Instrument Synthesis | Suno v3 API | Artist+ tier |
| AI Assistant | Anthropic API (`claude-opus-4-6`) | |
| Billing | Stripe | |
| Desktop App | Tauri 2.0 (Rust + WebView) | Studio Pro+ |
| DAW Plugin | JUCE 8 (VST3/AU/AAX) | Studio Pro+ |
| Containerisation | Docker + Docker Compose | |
| CDN | CloudFront or equivalent | |
| Monitoring | Prometheus + Grafana | |

---

## Multi-Tenant Isolation

Every database query on user data **must** include `WHERE user_id = $user_id`. Row-Level Security (RLS) is enabled on **all** PostgreSQL tables that hold user data. S3 object path: `users/{user_id}/{session_id}/{file_hash}.{ext}` — no exceptions. Cross-tenant data access is a critical incident with zero tolerance.

---

## Execution Domain Split

### Browser-side (zero server cost, free tier)
- RainDSP WASM DSP engine (EQ, compression, limiting, loudness, dither)
- RainNet inference via ONNX Runtime Web (base/tiny/nano models)
- Neural analog models via RTNeural
- Essentia.js emotion/genre classification
- DeepFilterNet WASM (denoising)
- libspatialaudio (spatial audio rendering)
- Loudness measurement (K-weighting, BS.1770-4)

### Server-side (paid tiers, cloud GPU, Celery workers)
- BS-RoFormer cascaded 4-pass 12-stem separation
- SonicMaster unified audio repair
- MERT / Music2Emo feature extraction
- Codec pre-optimisation (SandwichedCompression approach)
- **Vocal pitch correction** (CREPE + WORLD vocoder, Creator+)
- **Instrument synthesis** (Suno v3 API, Artist+)
- C2PA manifest generation and signing
- DDEX ERN 4.3 export and validation
- AI co-mastering via `claude-opus-4-6`

---

## Non-Negotiable Architecture Rules

1. `RainDSP` WASM is the **only** render engine. Never substitute Web Audio API for render output.
2. Biquad sign: `y = b0·x + b1·x1 + b2·x2 − a1·y1 − a2·y2`. `a1` is **subtracted**.
3. `RAIN_NORMALIZATION_VALIDATED=false` until ML lead + Phil Bölke sign off. Gate **blocks** RainNet inference.
4. Every DB query on user data includes `WHERE user_id = $user_id`. RLS on all tables.
5. S3 prefix: `users/{user_id}/{session_id}/{file_hash}.{ext}`. Zero exceptions.
6. Free tier: no S3, no upload, no session persistence, WASM-only, listen only.
7. Error codes: always `RAIN-E*` or `RAIN-B*`. Never raw exception messages to client.
8. WASM binary hash verified at session start. Mismatch → `RAIN-E304`, render blocked.
9. `claude-opus-4-6` for all Anthropic API calls. Never a different model.
10. Vocal pitch correction and instrument synthesis are **optional** post-render stages. Either can be skipped without blocking mastering completion.

---

*See [[RainDSP-Engine]] for the DSP layer detail. See [[Processing-Pipeline]] for the full parameter schema. See [[Vocal-Production-Features]] for pitch correction and instrument synthesis specification.*
