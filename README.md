# R∞N — RAIN v6
### AI Audio Transformation, Mastering & Distribution Infrastructure
**ThatGuy Productions · ARCOVEL Technologies International**

> "Rain doesn't live in the cloud." — The render engine runs on your machine. Audio never leaves your device during processing.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-blue?style=flat-square)
![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?style=flat-square&logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-Proprietary-red?style=flat-square)
![EU AI Act](https://img.shields.io/badge/EU_AI_Act_Art.50-Compliant-green?style=flat-square)
![DDEX](https://img.shields.io/badge/DDEX_ERN-4.3.2-orange?style=flat-square)

RAIN is a full-stack, local-first AI mastering and distribution engine that brings studio-grade audio processing to independent artists and labels. It combines a deterministic C++/WASM DSP render engine with cloud-based AI inference, cryptographic provenance certificates, and direct streaming platform distribution — all in one product.

Beyond LANDR. Beyond iZotope. Beyond anything that came before.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser  (React 19 + Vite 7 + TypeScript 5.5 + Tailwind 4)        │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │ Web Audio API    │  │ ONNX Runtime Web│  │ RainDSP  C++/WASM  │ │
│  │ 32-bit preview   │  │ WebGPU → WASM   │  │ 64-bit · deterministic│ │
│  └──────────────────┘  └─────────────────┘  └─────────────────────┘ │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ REST / WebSocket  (FastAPI)
┌────────────────────────────────▼────────────────────────────────────┐
│  Backend  (Python 3.12 · FastAPI · Celery · Structlog)              │
│  ┌──────────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐  │
│  │ Master Engine│ │ QC Engine  │ │ RAIN-CERT   │ │ DDEX ERN 4.3 │  │
│  │ 16-stage DSP │ │ 18 checks  │ │ Ed25519     │ │ AI disclosure │  │
│  └──────────────┘ └────────────┘ └─────────────┘ └──────────────┘  │
│  ┌──────────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐  │
│  │ Feature Ext. │ │ Heuristic  │ │ LabelGrid   │ │ Stripe       │  │
│  │ 43-dim vector│ │ 46 params  │ │ Distribution│ │ Billing      │  │
│  └──────────────┘ └────────────┘ └─────────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                      │                     │
   PostgreSQL 18          Valkey 9.0            MinIO / S3
   (RLS enabled)          (BSD-3 Redis fork)    (paid tiers only)
```

### Dual-Path Design

| Path | Engine | Precision | Purpose |
|------|--------|-----------|---------|
| Preview | Web Audio API | 32-bit float | Real-time monitoring, < 50 ms latency |
| Render | RainDSP WASM | 64-bit double | Deterministic, authoritative output |

**Determinism guarantee:** Same input + same params + same WASM binary = bit-identical output, every time.

---

## 16-Stage Mastering Pipeline

| Stage | Name | Description |
|-------|------|-------------|
| 01 | Format Normalization | Resample to 48 kHz, 64-bit float stereo |
| 02 | Provenance Record | Ed25519 input hash, C2PA manifest init, AudioSeal seed |
| 03 | Feature Extraction | 43-dim vector — Loudness (5), Dynamics (6), Spectral (16), Stereo (7), Transient (5), Tonal (4) |
| 04 | AI Inference | RainNet v2 → 46 ProcessingParams via sigmoid × 10 macro mapping |
| 05 | Reference Matching | Genre-aware spectral target matching |
| 06 | Spectral Repair | HPF, sibilance reduction, rumble removal, spectral smoothing |
| 07 | Source Separation | BS-RoFormer 4-pass cascade → 12 stems |
| 08 | Per-Stem Repair | Individual stem QC and spectral correction |
| 09 | Per-Stem Processing | SAIL v2 stem-aware limiting, vocal protection, gain faders |
| 10 | Master Bus | EQ → Multiband compression → Stereo widening → Groove → Life injection |
| 11 | Loudness Targeting | 27 platform targets — Spotify −14, Apple −16, Atmos −18, CD −9, vinyl… |
| 12 | Spatial Rendering | Dolby Atmos HRTF binaural, M/S stereo enhancement |
| 13 | QC Validation | 18 automated checks with auto-remediation |
| 14 | Forensic Watermark | 16-bit AudioSeal, Chromaprint fingerprint |
| 15 | Output Packaging | 24-bit WAV @ 48 kHz + 320 kbps MP3 with TPDF dither; RAIN-CERT signed |
| 16 | Distribution | DDEX ERN 4.3.2, LabelGrid API delivery, ISRC/UPC generation |

---

## 7 Macro Controls

Emotionally-resonant, non-technical controls mapping to bounded subsets of the 46 DSP parameters. RainNet v2 outputs all 7 macros at indices 39–45 via sigmoid × 10 → [0.0, 10.0].

| Macro | DSP Mapping |
|-------|-------------|
| **BRIGHTEN** | High-shelf at 8 kHz + air peak at 16 kHz · 0 → +4 dB |
| **GLUE** | Multiband compression ratios/thresholds · 0 = transparent, 10 = bus glue 4:1 |
| **WIDTH** | M/S side-channel gain · bass mono below 200 Hz enforced regardless |
| **PUNCH** | Mid-band transient shaping via attack/release · snare, kick, vocal presence |
| **WARMTH** | Low-shelf at 200 Hz + analog saturation · 0 = clean, 10 = +3 dB + tube sat |
| **SPACE** | Stereo decorrelation and M/S balance for depth · interacts with WIDTH |
| **REPAIR** | Spectral repair intensity, HPF, de-essing, noise floor |

---

## 12-Stem Source Separation

Protect your authentic human vocal recordings. Upload AI-reworked structures, separate the stems, and cleanly replace AI vocals with your original takes.

| Pass | Model | Output |
|------|-------|--------|
| 1 | BS-RoFormer SW | vocals · drums · bass · guitar · piano · other |
| 2 | MVSep Karaoke MelBand RoFormer | lead vocals + backing vocals |
| 3 | Spectral band-split *(LarsNet pending)* | kick · snare · hats · percussion |
| 4 | anvuew dereverb MelBand RoFormer | room/ambience + dry FX |

Per-stem gain faders, solo/mute, 12-stem waveform display. **SAIL v2** (Stem-Aware Intelligent Limiting) with dedicated vocal protection.

---

## Provenance & Compliance

| Standard | Status | Notes |
|----------|--------|-------|
| EU AI Act Article 50 | ✅ Active | C2PA v2.2 + DDEX AI disclosure · deadline 2026-08-02 |
| DDEX ERN 4.3.2 | ✅ Active | Full AI involvement fields per September 2025 standard |
| C2PA v2.2 | ✅ Active | CBOR-encoded manifests, Ed25519 signed |
| RAIN-CERT | ✅ Active | Ed25519 provenance certificates on every render |
| AudioSeal | ✅ Active | 16-bit invisible watermarks (Meta, MIT licence) |
| Chromaprint | ✅ Active | Audio fingerprints in PostgreSQL |
| ISO 3901 (ISRC) | ✅ Active | Generated per standard with registrant code |
| AES17 True Peak | ✅ Active | 4× oversampling limiter · −1.0 dBTP ceiling |

---

## AI Co-Master Engineer

**Claude Sonnet 4.6** integration via `claude_service.py`:
- Natural language Intent Engine maps requests to bounded `ProcessingParams` deltas
- 7 macro suggestions with confidence scores (JSON-validated, clamped 0–10)
- Before/after mastering reports in plain language
- Tension-pair conflict detection (e.g. BRIGHTEN + WARMTH)
- Voice control via Web Speech API for hands-free mastering

**Artist Identity Engine (AIE):** 64-dimensional voice vector. Adaptive EMA (α = 0.90 stable, 0.60 cold-start). Personalizes after 5 sessions. Exportable as HMAC-SHA256 signed JSON.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19 · Vite 7 · TypeScript 5.5 · Tailwind 4 · Framer Motion 11 |
| State | Zustand 5 · TanStack Query 5 |
| Render Engine | RainDSP (C++20 / WASM via Emscripten) · 64-bit · deterministic |
| ML Inference | ONNX Runtime Web 1.24 (WebGPU → WASM fallback) · RainNet v2 |
| Backend API | FastAPI 0.109+ · Python 3.12 · Celery · Structlog · SlowAPI |
| Database | PostgreSQL 18 with Row-Level Security on all tables |
| Cache / Queue | Valkey 9.0 (BSD-3-Clause Redis fork) |
| Object Storage | S3-compatible (MinIO in dev) · free tier = WASM-only, no S3 |
| Provenance | Ed25519 · C2PA v2.2 · AudioSeal · Chromaprint · CBOR (RFC 7049) |
| Separation | BS-RoFormer SW · MelBand RoFormer · auto-download via pip |
| Distribution | DDEX ERN 4.3 · LabelGrid API · ISRC / UPC-EAN-13 |
| Desktop / Plugin | Tauri 2.0 · JUCE 8 (VST3 / AU / AAX) |

---

## Getting Started

### Prerequisites
- Docker Desktop 4.x+
- Node.js 20+
- Python 3.12+

### Docker (recommended)

```bash
# Clone
git clone https://github.com/ThatGuy-Productions/RAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE.git
cd RAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE

# Configure environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, STRIPE_SECRET_KEY, LABELGRID_API_KEY, etc.

# Start full stack (PostgreSQL 18 + Valkey 9.0 + backend + frontend)
docker compose up --build -d

# Verify
curl http://localhost:8000/health
```

### Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### GPU worker (stem separation)

```bash
# Requires CUDA 12+ and SEPARATION_ENABLED=true in .env
docker compose -f docker-compose.gpu.yml up -d worker
```

---

## API Routes

The backend exposes 19 API routers under `/api/v1/`.

| Router | Prefix | Auth | Description |
|--------|--------|------|-------------|
| `auth.py` | `/auth` | Public / JWT | Registration, login, JWT refresh, password reset |
| `upload.py` | `/upload` | JWT | Audio file upload, S3 pre-signed URLs, file validation |
| `master.py` | `/master` | JWT | Session creation, mastering pipeline trigger, status polling, parameter overrides |
| `separate.py` | `/separate` | JWT · Creator+ | BS-RoFormer 12-stem separation jobs, stem download |
| `download.py` | `/download` | JWT | Signed download URLs for rendered masters and stems |
| `distribution.py` | `/distribution` | JWT · Producer+ | DDEX ERN 4.3.2 package generation, LabelGrid delivery, ISRC/UPC issuance |
| `billing.py` | `/billing` | JWT | Stripe checkout sessions, subscription management, webhook receiver |
| `aie.py` | `/aie` | JWT · Artist+ | Artist Identity Engine — vector query, export, reset |
| `sessions.py` | `/sessions` | JWT | Session history, status, output metadata, RAIN Score retrieval |
| `qc.py` | `/qc` | JWT | Manual QC re-run, 18-point check report |
| `provenance_routes.py` | `/provenance` | JWT | RAIN-CERT retrieval, C2PA manifest query, Ed25519 verification |
| `waitlist.py` | `/waitlist` | Public | Beta waitlist registration |
| `assist.py` | `/assist` | JWT | Claude AI assistant — intent parsing, macro suggestions, mastering advice, voice command processing |
| `lora.py` | `/lora` | JWT · Enterprise | Custom LoRA adapter training jobs, model version management, inference switching |
| `suno_import.py` | `/suno` | JWT | Suno AI track import — fetch by song ID or URL, normalize, queue for mastering |
| `whitelabel.py` | `/whitelabel` | JWT · Enterprise | White-label API key provisioning, partner branding config, usage metering |
| `workspaces.py` | `/workspaces` | JWT · Studio+ | Multi-artist workspace management, collaborator roles, shared session access |
| `score.py` | `/score` | Public (10 req/hr/IP) | Public RAIN Score endpoint — no auth required, returns 0-100 composite quality metric |
| `waitlist.py` | `/waitlist` | Public | Beta waitlist registration |

> **Auth tiers:** `Public` = no token required · `JWT` = any authenticated user · tier suffixes (Creator+, Artist+, etc.) = minimum subscription required.

---

## Pricing

| Tier | Price | Renders / mo | Key Features |
|------|-------|-------------|--------------|
| Casual | Free | Listen only | WASM mastering, real-time preview, RAIN Score |
| Creator | $9 | 50 downloads | Full-res export, WAV / FLAC / MP3, Simple Mode |
| **Independent Artist** | **$29** | **10 renders** | **Stem separation, Claude AI (10/mo), Artist Identity Engine** |
| Producer | $59 | 25 renders | DAW plugin, Distribution Intelligence, RAIN-CERT |
| Studio | $149 | 75 renders | Dolby Atmos, DDEX / DDP, vinyl mastering, collaboration |
| Label / Distributor | $349 | 300 renders | Multi-artist roster, batch processing, LabelGrid direct |
| Enterprise | Custom | Unlimited | Custom RainNet LoRA, white-label API, dedicated support |

Annual billing: ~20% discount. Contact [engineering@thatguy-productions.com](mailto:engineering@thatguy-productions.com) for enterprise licensing.

---

## Architecture Rules

These constraints are immutable. See `CLAUDE.md` for the full specification.

1. **Local-First Processing** — RainDSP WASM is the sole render engine. Audio never reaches S3 on the free path. Free renders live in WASM memory and are discarded on session close.

2. **Dual-Path Architecture** — Preview (Web Audio API, 32-bit) and Render (RainDSP, 64-bit) are always separate codepaths. Never merge them.

3. **Multi-Tenant Isolation** — Every DB query includes `WHERE user_id = $user_id`. Row-Level Security enabled on all tables. No exceptions.

4. **K-Weighting Sign Convention** — `y = b0·x + b1·x₁ + b2·x₂ − a1·y₁ − a2·y₂`. a1 stored negative, subtracted. ITU-R BS.1770-4 convention — never change this.

5. **NORMALIZATION_VALIDATED Gate** — `RAIN_NORMALIZATION_VALIDATED=true` → gate OPEN → RainNet inference active. Closed by default. Sign-off authority: Phil Bölke.

6. **WASM Binary Integrity** — `rain_dsp_wasm_hash` verified at session start via SHA-256. Mismatch = `RAIN-E304`, render blocked. Set `RAIN_EXPECTED_WASM_HASH` in production.

7. **Provenance Before Output** — Output hash verified against RAIN-CERT before session marked complete. `RAIN-E305` on mismatch. `RAIN-E306` on unsigned cert. No exceptions in production.

---

## Project Structure

```
RAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE/
├── backend/                   FastAPI application
│   ├── app/
│   │   ├── api/routes/        19 routers — see API Routes table above
│   │   ├── core/              config, database, security, observability, audio_io
│   │   ├── models/            SQLAlchemy ORM models (PostgreSQL 18 + RLS)
│   │   ├── schemas/           Pydantic request / response schemas
│   │   └── services/          master_engine, qc_engine, rain_score_v2, separation…
│   └── tests/                 pytest async test suite
├── frontend/                  React 19 SPA (Vite 7 · TypeScript · Tailwind 4)
├── rain-dsp/                  C++20 DSP engine — Emscripten WASM build
├── rain-desktop/              Tauri 2.0 desktop wrapper
├── rain-plugin/               JUCE 8 VST3 / AU / AAX plugin
├── ml/                        PyTorch training, ONNX export, RainNet v2
├── docker/                    Dockerfiles (backend, frontend, gpu-worker)
├── monitoring/                Prometheus + Grafana dashboards
├── docs/                      Architecture docs, pipeline specs
├── CLAUDE.md                  Immutable architecture specification
├── RAIN-BLUEPRINT.md          Full technical blueprint
└── .env.example               All required environment variables documented
```

---

## Error Code Reference

| Code | Meaning | Action |
|------|---------|--------|
| `RAIN-E100` | JWT authentication failure | Re-authenticate; check token expiry |
| `RAIN-E304` | WASM binary hash mismatch | Set `RAIN_EXPECTED_WASM_HASH` to deployed hash |
| `RAIN-E305` | Output hash mismatch in RAIN-CERT | Re-render; check CERT signing key |
| `RAIN-E306` | Session completed without signed cert | Check C2PA key paths in config |
| `RAIN-E503` | Public score rate limit exceeded | 10 requests/hour per IP — wait or authenticate |
| `RAIN-E620` | Separation disabled | Set `SEPARATION_ENABLED=true` and provision model checkpoints |
| `RAIN-E621` | `demix()` not available | Install `music-source-separation-training` on GPU worker |
| `RAIN-E900` | Claude API auth failure | Check `ANTHROPIC_API_KEY` in env |
| `RAIN-E901` | Claude API timeout / exhausted retries | 3 retries with exponential backoff — check network |
| `RAIN-E902` | Claude response parse failure | Invalid JSON from model — check logs for raw response |

---

## License

Proprietary — © 2026 ThatGuy Productions. All rights reserved.

Contact [engineering@thatguy-productions.com](mailto:engineering@thatguy-productions.com) for licensing enquiries.

---

*RAIN v6 · Engine stamp: `RAIN v6 — BS-RoFormer 12-stem` · LLM advisory layer: `claude-sonnet-4-6` · Publisher: ThatGuy Productions*


<img width="1652" height="830" alt="image" src="https://github.com/user-attachments/assets/49a5af79-dad5-4f27-83e5-0a1dca0d4f50" />
