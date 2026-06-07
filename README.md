RAIN AI Mastering & Distribution Engine

**Professional AI-powered mastering and distribution engine by ThatGuy Productions**

> "Rain doesn't live in the cloud." The render engine runs on your machine. Audio never leaves your device during processing.

### What is RAIN?
RAIN (R∞N) is a full-stack, local-first AI mastering and distribution engine that brings studio-grade audio mastering to independent artists and labels. It combines a deterministic C++/WASM DSP render engine with cloud-based AI inference, cryptographic provenance certificates, and direct streaming platform distribution — all in one product.

**Beyond LANDR. Beyond iZotope. Beyond anything that came before.**

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│  Browser (React 19 + Vite 6)                                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Web Audio   │  │ ONNX Runtime │  │  RainDSP (C++/WASM)    │  │
│  │ API (route) │  │ Web (infer.) │  │  64-bit, deterministic │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST / WebSocket (FastAPI)
┌────────────────────────────▼────────────────────────────────────┐
│  Backend (Python 3.12 + FastAPI)                                │
│  ┌──────────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Master       │  │ QC Engine │  │ RAIN-CERT│  │ DDEX ERN │    │
│  │ Engine (DSP) │  │ 18 checks │  │ Ed25519  │  │ 4.3.2    │    │
│  └──────────────┘  └───────────┘  └──────────┘  └──────────┘    │
│  ┌──────────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Feature Ext. │  │ Heuristic │  │ LabelGrid│  │ Stripe   │    │
│  │ 43-dim vector│  │ Params    │  │ Distrib. │  │ Billing  │    │
│  └──────────────┘  └───────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
    PostgreSQL 18         Valkey 9.0           MinIO / S3
Dual-Path DesignPathEnginePrecisionPurposePreviewWeb Audio API32-bit floatReal-time monitoring, < 50 ms latencyRenderRainDSP WASM64-bit doubleDeterministic, authoritative outputSame input + same params + same WASM binary = bit-identical output, every time.FeaturesCore Mastering16-stage DSP chain: format normalization → provenance record → feature extraction → AI inference → reference matching → spectral repair → source separation → per-stem repair → per-stem processing → master bus → loudness targeting → spatial rendering → QC validation → forensics watermark → output packaging → distribution.43-dimensional feature extraction across 6 groups: Loudness (5), Dynamics (6), Spectral (16), Stereo (7), Transient (5), Tonal (4).18 automated QC checks with auto-remediation for critical issues.27 platform loudness targets: Spotify −14 LUFS, Apple Music −16, Dolby Atmos −18, CD −9, vinyl, broadcast, podcast, and more.46-parameter ProcessingParams schema — heuristic fallback when ML gate is closed.7 Macro ControlsBRIGHTEN / GLUE / WIDTH / PUNCH / WARMTH / SPACE / REPAIREmotionally-resonant, non-technical controls mapping to bounded subsets of the 46 DSP parameters.RainNet v2 outputs all 7 macros at indices 39–45 via sigmoid × 10 → [0.0, 10.0].Tension-pair warnings (e.g., BRIGHTEN + WARMTH conflict detection).12-Stem Source SeparationProtect your authentic human vocal recordings. Upload your AI-reworked structures, separate the stems, and cleanly replace the vocals with your original takes.PassModelOutput1BS-RoFormer SWvocals, drums, bass, guitar, piano, other2MVSep Karaokelead vocals + backing vocals3Spectral band-splitkick, snare, hats, percussion (LarsNet pending)4anvuew dereverb MelBandroom/ambience + dry FXPer-stem gain faders, solo/mute, 12-stem waveform display.SAIL v2 (Stem-Aware Intelligent Limiting) — sail_stem_gains[12], 5 limiter modes, dedicated vocal protection.Provenance & ComplianceRAIN-CERT: Ed25519-signed provenance certificates with strict Pydantic validation (input hash, output hash, WASM binary hash, processing params).Synchronous enforcement gate: Output hash verified before session marked complete (RAIN-E305 on mismatch, RAIN-E306 on unsigned cert).C2PA v2.2: CBOR-encoded Content Provenance manifests with AI disclosure assertions.AudioSeal: 16-bit invisible watermarks (Meta, MIT licence) — survives compression and re-encoding.Chromaprint: Audio fingerprints stored in PostgreSQL for content identification.DDEX ERN 4.3: Full AI involvement disclosure (September 2025 standard, 5 granular areas).EU AI Act Article 50: Machine-readable AI marking; stamp_output auto-triggered after every render.Distribution & IntegrationDirect-to-DSP delivery via LabelGrid API.ISRC generation (ISO 3901), UPC/EAN-13 with check digit.Per-platform loudness targeting and codec-aware mastering.4-step distribution wizard: Platforms → Metadata → Review → Status.AI Co-Master Engineer & Artist Identity Engine (AIE)Claude Sonnet 4.6 integration: Natural language Intent Engine mapping to bounded ProcessingParams deltas.Voice control: Web Speech API for hands-free mastering commands.64-dimensional voice vector: EQ / dynamics / stereo / coloring / genre / meta decomposition.Adaptive EMA: α = 0.90 stable, 0.60 cold-start (personalizes after 5 sessions). Exportable as HMAC-SHA256 signed JSON.Tech StackLayerTechnologyFrontendReact 19.2 · Vite 6 · TypeScript 5.5 · Tailwind 4 · Framer Motion 11StateZustand 5 · TanStack Query 5Render EngineRainDSP (C++20 / WASM via Emscripten)ML InferenceONNX Runtime Web 1.24 (WebGPU → WASM fallback)Backend APIFastAPI 0.109+ · Python 3.12DatabasePostgreSQL 18 with RLSCache / QueueValkey 9.0 (BSD-3-Clause Redis fork)Object StorageS3-compatible (MinIO in dev)ProvenanceEd25519 · C2PA v2.2 · AudioSeal · Chromaprint · CBOR (RFC 7049)SeparationBS-RoFormer SW · MelBand RoFormer (auto-download via pip)DistributionDDEX ERN 4.3 · LabelGrid APIPricingTierPriceRendersKey FeaturesCasual$00 (listen only)WASM mastering, real-time preview, RAIN ScoreCreator$9 / mo50 downloadsFull-resolution export, WAV / FLAC / MP3, Simple ModeIndependent Artist$29 / mo10 rendersStem separation, Claude AI (10/mo), Artist Identity EngineProducer$59 / mo25 rendersDAW plugin, Distribution Intelligence, RAIN-CERTStudio$149 / mo75 rendersDolby Atmos, DDEX / DDP, vinyl mastering, collaborationLabel / Distributor$349 / mo300 rendersMulti-artist roster, batch processing, LabelGrid directEnterpriseCustomUnlimitedCustom RainNet LoRA, white-label API, dedicated supportAnnual discount: ~20%. Contact engineering@thatguy-productions.com for enterprise licensing.Getting StartedPrerequisitesDocker Desktop 4.x+Node.js 20+Python 3.12+Quickstart (Docker)Bashgit clone [https://github.com/thatguyproductions/RAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE.git](https://github.com/thatguyproductions/RAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE.git)
cd RAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE

# Copy and configure environment
cp .env.example .env

# Start the full stack (PostgreSQL 18 + Valkey 9.0 + backend + frontend)
docker compose up --build -d
Local DevelopmentBash# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
Non-Negotiable Architecture RulesThese constraints are immutable. See CLAUDE.md for the full specification.Local-First Processing — RainDSP WASM is the sole render engine. Audio never reaches S3 on the free path.Dual-Path Architecture — Preview (Web Audio API, 32-bit) and Render (RainDSP, 64-bit) are always separate codepaths. Never merge them.Multi-Tenant Isolation — Every DB query includes WHERE user_id = $user_id. Row-Level Security enabled on all tables.K-Weighting Sign Convention — y = b0·x + b1·x₁ + b2·x₂ − a1·y₁ − a2·y₂. a1 stored negative, subtracted. Never change this.NORMALIZATION_VALIDATED Gate — RAIN_NORMALIZATION_VALIDATED=true; gate OPEN. RainNet inference active.WASM Binary Integrity — rain_dsp_wasm_hash verified at session start. Mismatch = RAIN-E304, render blocked.Free Tier = No S3 — Free renders live in WASM memory and are discarded on session close. Never written to disk or S3.Project StructurePlaintextRAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE/
├── backend/                   FastAPI application
│   ├── app/
│   │   ├── api/routes/        13 API routers (auth, master, qc, billing, …)
│   │   ├── core/              Config, database, security, observability
│   │   ├── models/            SQLAlchemy ORM models
│   │   ├── schemas/           Pydantic request / response schemas
│   │   └── services/          Business logic (DSP, QC, provenance, DDEX, …)
│   └── tests/                 pytest test suite
├── frontend/                  React SPA
│   └── src/
├── rain-dsp/                  C++20 DSP engine (WASM build via Emscripten)
├── rain-desktop/              Tauri 2.0 desktop wrapper
├── rain-plugin/               JUCE 8 VST3 / AU / AAX plugin
├── ml/                        PyTorch training, ONNX export
├── docker/                    Dockerfiles (backend, frontend, worker)
├── CLAUDE.md                  Immutable architecture specification
└── plan.md                    Implementation plan — all 6 batches complete
ComplianceStandardStatusNotesEU AI Act Article 50✅C2PA v2.2 + DDEX AI disclosure in every exportDDEX ERN 4.3.2✅Full AI involvement fields per Sep 2025 standardC2PA v2.2✅CBOR-encoded manifests, Ed25519 signedISO 3901 (ISRC)✅Generated per standardAES17 True Peak✅4× oversampling limiterLicense: Proprietary — © 2026 ThatGuy Productions. All rights reserved.Contact engineering@thatguy-productions.com for licensing enquiries.
