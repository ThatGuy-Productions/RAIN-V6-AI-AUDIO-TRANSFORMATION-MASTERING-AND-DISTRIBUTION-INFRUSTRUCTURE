# RAIN v6 — Technical Stack Specification Sheet

**Document Version:** 6.0  
**Last Updated:** 2026-07-08  
**Repository:** ThatGuy-Productions/RAIN-V6-AI-AUDIO-TRANSFORMATION-MASTERING-AND-DISTRIBUTION-INFRUSTRUCTURE  
**Language Composition:** Python (49.6%) · TypeScript (32.7%) · C++ (6%) · PowerShell (4.1%) · CSS (2.8%) · Shell (2.2%) · Other (2.6%)

---

## 📋 Executive Summary

RAIN v6 is a **full-stack, local-first AI audio mastering and distribution platform** built on a carefully orchestrated collection of modern technologies:

- **Frontend:** React 19 (TypeScript) + Vite 7 + Tailwind CSS 4 + ONNX Runtime Web (WASM inference)
- **Backend:** FastAPI 0.109+ (Python 3.12) + Celery + Structlog
- **DSP Render Engine:** RainDSP (C++20 → WebAssembly via Emscripten)
- **Database:** PostgreSQL 18 with Row-Level Security
- **Cache/Queue:** Valkey 9.0 (BSD-3-Clause Redis fork)
- **AI Inference:** ONNX Runtime, PyTorch 2.0+, Claude Sonnet API
- **Source Separation:** BS-RoFormer + MelBand RoFormer (music-source-separation-training)
- **Audio DSP:** librosa, scipy, soundfile, pyloudnorm, pydub
- **Desktop:** Tauri 2.0
- **DAW Integration:** JUCE 8 (VST3 / AU / AAX)
- **Provenance:** Ed25519 signing, C2PA v2.2, AudioSeal, Chromaprint, CBOR encoding
- **Distribution:** DDEX ERN 4.3.2, LabelGrid API
- **Billing:** Stripe API
- **AI Integration:** Anthropic Claude Sonnet API

---

## 🎨 Frontend Stack

### Dependencies (package.json)

```json
{
  "name": "rain-frontend",
  "version": "6.0.0",
  "type": "module",
  "runtime": "Node.js 20+",
  "devDependencies": {
    "vite": "^7.3.1",
    "typescript": "^5.5.3",
    "@vitejs/plugin-react": "^5.2.0",
    "tailwindcss": "^4.2.2",
    "@tailwindcss/vite": "^4.2.2"
  },
  "dependencies": {
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "react-router-dom": "^6.26.2",
    "@tanstack/react-query": "^5.56.2",
    "zustand": "^5.0.0",
    "framer-motion": "^11.18.2",
    "recharts": "^2.12.7",
    "@radix-ui/react-*": "^latest",
    "lucide-react": "^0.447.0",
    "onnxruntime-web": "^1.24.3",
    "wavefile": "^11.0.0",
    "posthog-js": "^1.364.7"
  }
}
```

### Core Libraries Explained

| Library | Version | Purpose |
|---------|---------|---------|
| **React** | 19.2.4 | UI framework with concurrent rendering |
| **Vite** | 7.3.1 | Lightning-fast ESM build tool, <100ms hot reload |
| **TypeScript** | 5.5.3 | Full type safety, strict mode enabled |
| **Tailwind CSS** | 4.2.2 | Utility-first CSS, v4 includes new Engine (JIT on steroids) |
| **React Router** | 6.26.2 | Client-side routing, SPA navigation |
| **TanStack Query** | 5.56.2 | Server state management, caching, sync |
| **Zustand** | 5.0.0 | Lightweight global state (session, presets, UI mode) |
| **Framer Motion** | 11.18.2 | Gesture-driven animations, waveform scrubbing |
| **Recharts** | 2.12.7 | React-based charting for analytics dashboard |
| **Radix UI** | ^1.x | Unstyled, accessible component primitives |
| **Lucide React** | 0.447.0 | 450+ SVG icons, tree-shakeable |
| **ONNX Runtime Web** | 1.24.3 | **CRITICAL**: WebAssembly + WebGPU inference engine |
| **wavefile** | 11.0.0 | WAV file encoding/decoding in browser |
| **PostHog** | 1.364.7 | Product analytics, feature flags, A/B testing |

### Frontend Architecture

```
Frontend (React 19 + TypeScript 5.5)
├── UI Layer (Radix + Tailwind)
│   ├── Session Dashboard
│   ├── Preset Editor (7 macros)
│   ├── Waveform Viewer (Recharts-based)
│   └── Distribution Interface
│
├── State Management (Zustand + TanStack Query)
│   ├── Session store (active session, parameters)
│   ├── Server cache (rendered files, history)
│   └── UI mode (theme, sidebar, layout)
│
├── Real-Time Processing
│   ├── Web Audio API (Preview engine, 32-bit float)
│   ├── ONNX Runtime Web (RainNet v2 inference)
│   └── Framer Motion (Waveform scrubbing, feedback)
│
└── Network & Auth
    ├── TanStack Query (API calls, caching)
    ├── REST + WebSocket (FastAPI backend)
    └── JWT token management
```

### Build Pipeline

```bash
# Development
npm run dev
# → Vite dev server on http://localhost:5173
# → Hot Module Replacement (HMR) <100ms
# → Debug source maps

# Type Checking
npm run typecheck
# → tsc --noEmit (strict mode)

# Production Build
npm run build
# → tsc -b && vite build
# → Output: dist/ (optimized bundles, tree-shaken)
# → Automatic code splitting per route
# → WASM binary bundled via import

# Preview
npm run preview
# → Test production build locally
```

---

## ⚙️ Backend Stack

### Core Dependencies (requirements.txt)

```txt
# FastAPI & Async Runtime
fastapi>=0.109.2
uvicorn[standard]>=0.27.1

# Database & Async ORM
sqlalchemy>=2.0.27
asyncpg>=0.29.0              # Async PostgreSQL driver
alembic>=1.13.1              # DB migrations

# Cache & Task Queue
redis>=5.0.1                 # Client library (connects to Valkey)
celery>=5.3.6                # Async task broker
valkey>=1.0.0                # (Or: redis client for Valkey compatibility)

# Cloud Storage
aioboto3>=13.0.0             # Async S3 client
boto3>=1.34.34               # S3 operations

# Authentication & Security
pydantic[email]>=2.6.1
email-validator>=2.1.0
pydantic-settings>=2.1.0     # Environment config
PyJWT[crypto]>=2.8.0         # JWT encoding/decoding
passlib[bcrypt]>=1.7.4       # Password hashing
cryptography>=42.0.2         # Encryption utilities

# HTTP & API
python-multipart>=0.0.9      # Form data parsing
httpx>=0.26.0                # Async HTTP client
slowapi>=0.1.9               # Rate limiting

# Audio DSP & Processing
numpy>=1.26.4
scipy>=1.12.0
librosa>=0.10.1              # Audio feature extraction
soundfile>=0.12.1            # WAV/FLAC I/O
pyloudnorm>=0.1.0            # ITU-R BS.1770-4 loudness metering
pydub>=0.25.1                # Audio codec operations
mutagen>=1.47.0              # Metadata reading
resampy>=0.4.3               # High-quality resampling
imageio-ffmpeg>=0.6.0        # FFmpeg bindings
pyacoustid>=1.3.0            # Chromaprint fingerprinting
audioseal>=0.2.1             # Meta AudioSeal watermarking
bs-roformer-infer>=0.1.1     # BS-RoFormer source separation
melband-roformer-infer>=0.1.0 # MelBand RoFormer

# ML & Model Loading
torch>=2.0.0                 # PyTorch (CPU or GPU)
torchaudio>=2.0.0            # Audio utilities
onnxruntime>=1.17.0          # ONNX Runtime (CPU/GPU/WebNN)

# Provenance & Standards
c2pa-python>=0.6.0           # C2PA manifest creation
cbor2>=5.6.0                 # CBOR encoding (RFC 8949)

# Monitoring & Observability
prometheus-fastapi-instrumentator>=6.1.0
structlog>=24.1.0            # Structured logging (JSON)
sentry-sdk[fastapi]>=1.40.6  # Error tracking

# Billing
stripe>=8.3.0

# AI Integration
anthropic>=0.18.1            # Claude API (native async)

# Testing
pytest>=8.0.2
pytest-asyncio>=0.23.5       # Async test runner
pytest-httpx>=0.28.0         # HTTP mocking
```

### FastAPI Application Structure

```python
# app/main.py (simplified)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from app.api.routes import (
    auth, upload, master, separate, download, distribution,
    billing, aie, sessions, qc, provenance_routes, waitlist,
    assist, lora, suno_import, whitelabel, workspaces, score
)

app = FastAPI(
    title="RAIN v6 API",
    version="6.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.rain.local", "rain.local"])
app.add_middleware(CORSMiddleware, allow_origins=["https://rain.local"], allow_credentials=True)

# Mount routers (18 total)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(master.router, prefix="/api/v1/master", tags=["Mastering"])
app.include_router(separate.router, prefix="/api/v1/separate", tags=["Source Separation"])
# ... 14 more routers

# Health checks
@app.get("/health")
async def health():
    return {"status": "ok", "version": "6.0.0"}

@app.get("/ready")
async def readiness():
    # Check DB, cache, S3, etc.
    return {"ready": True}
```

### 18 API Routers (v1)

| Router | Prefix | Auth Level | Responsibility |
|--------|--------|-----------|-----------------|
| **auth.py** | `/auth` | Public / JWT | Login, registration, password reset, OAuth |
| **upload.py** | `/upload` | JWT | S3 pre-signed URLs, file validation, metadata extraction |
| **master.py** | `/master` | JWT | Mastering pipeline, session creation, parameter tuning |
| **separate.py** | `/separate` | JWT · Creator+ | Source separation, stem job management |
| **download.py** | `/download` | JWT | Signed URLs, render/stem downloads |
| **distribution.py** | `/distribution` | JWT · Producer+ | DDEX ERN 4.3.2, LabelGrid, ISRC/UPC generation |
| **billing.py** | `/billing` | JWT | Stripe checkout, subscription, webhooks |
| **aie.py** | `/aie` | JWT · Artist+ | Artist Identity Engine (64-dim voice vectors) |
| **sessions.py** | `/sessions` | JWT | Session history, metadata, RAIN Score retrieval |
| **qc.py** | `/qc` | JWT | QC re-run, 18-point check reports |
| **provenance_routes.py** | `/provenance` | JWT | RAIN-CERT retrieval, C2PA verification |
| **waitlist.py** | `/waitlist` | Public | Beta signup |
| **assist.py** | `/assist` | JWT | Claude AI co-master (natural language macros) |
| **lora.py** | `/lora` | JWT · Enterprise | Custom LoRA training & inference |
| **suno_import.py** | `/suno` | JWT | Import Suno AI tracks for mastering |
| **whitelabel.py** | `/whitelabel` | JWT · Enterprise | White-label API provisioning |
| **workspaces.py** | `/workspaces` | JWT · Studio+ | Multi-artist collaboration |
| **score.py** | `/score` | Public (rate-limited) | RAIN Score (0-100 quality metric) |

### Backend Services

```python
# app/services/
├── master_engine.py          # 16-stage mastering pipeline
├── qc_engine.py              # 18-point quality checks + auto-fix
├── rain_score_v2.py          # Composite quality metric
├── separation_service.py     # BS-RoFormer integration
├── feature_extraction.py     # 43-dimensional audio feature vector
├── heuristic_loudness.py     # Fallback when NORMALIZATION_VALIDATED=false
├── ai_assist_service.py      # Claude Sonnet intent mapping
├── aie.py                    # Artist Identity Engine (64-dim EMA)
├── distribution_service.py   # DDEX ERN 4.3.2 XML generation
├── provenance_service.py     # Ed25519 signing, C2PA manifests
├── stripe_service.py         # Billing integration
└── observability.py          # Structlog, Prometheus, Sentry
```

---

## 🗄️ Database Layer

### PostgreSQL 18 + Row-Level Security

```sql
-- Connection: asyncpg (high-performance async driver)
-- Features: RLS on ALL user-facing tables, UUID PKs, JSONB columns

CREATE TABLE accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  tier VARCHAR(20) DEFAULT 'casual',
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;

CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES accounts(id),
  name TEXT DEFAULT 'Untitled',
  input_file_hash TEXT,
  input_metadata JSONB,       -- { sr: 48000, channels: 2, duration: 180.5 }
  render_settings JSONB,      -- { preset: {...}, target_lufs: -14 }
  rain_dsp_wasm_hash TEXT,    -- SHA-256 binary integrity
  status VARCHAR(20),         -- draft | inferring | rendered | archived
  created_at TIMESTAMP DEFAULT now()
);
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY session_isolation ON sessions USING (user_id = current_user_id());

CREATE TABLE renders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id),
  user_id UUID NOT NULL REFERENCES accounts(id),
  output_file_hash TEXT NOT NULL,
  s3_key TEXT NOT NULL,       -- s3://rain-audio/{user_id}/{session_id}/{hash}.wav
  format VARCHAR(10),         -- wav | mp3 | flac | opus
  loudness_lufs DECIMAL(5,2),
  true_peak_dbfs DECIMAL(5,2),
  render_time_ms INT,
  created_at TIMESTAMP DEFAULT now()
);
ALTER TABLE renders ENABLE ROW LEVEL SECURITY;
CREATE POLICY render_isolation ON renders USING (user_id = current_user_id());

-- Indexing strategy (optimized for queries)
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_renders_user_created ON renders(user_id, created_at DESC);
CREATE INDEX idx_inference_jobs_status ON inference_jobs(status);
```

### Valkey (Redis) Usage

**Valkey 9.0** (BSD-3-Clause Redis fork maintained by Linux Foundation)

```python
# Cache patterns
CACHE_KEYS = {
    "session_metadata": f"session:{session_id}:metadata",        # 1 hour TTL
    "inference_result": f"infer:{session_id}:result",            # 24h TTL
    "user_tier": f"user:{user_id}:tier",                         # 7d TTL
    "usage_stats": f"usage:{user_id}:{year}:{month}",            # 30m TTL
    "ratelimit": f"ratelimit:{user_id}:{action}",                # 24h TTL
}

# Celery broker/backend
CELERY_BROKER_URL = "valkey://localhost:6379/0"
CELERY_RESULT_BACKEND = "valkey://localhost:6379/1"
CELERY_TASK_ROUTES = {
    "tasks.separation.separate_stems": {"queue": "gpu"},
    "tasks.master.render": {"queue": "cpu"},
}
```

---

## 🎵 Audio DSP Stack

### Core Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| **NumPy** | 1.26.4+ | Vectorized audio arrays, 64-bit float64 operations |
| **SciPy** | 1.12.0+ | Signal processing (FFT, filtering, IIR design) |
| **librosa** | 0.10.1+ | Mel spectrograms, chroma features, tempogram |
| **soundfile** | 0.12.1+ | WAV / FLAC I/O with metadata |
| **pydub** | 0.25.1+ | Audio codec operations (MP3, AAC, Opus) |
| **pyloudnorm** | 0.1.0+ | ITU-R BS.1770-4 loudness metering & normalization |
| **resampy** | 0.4.3+ | High-quality Sinc resampling |
| **mutagen** | 1.47.0+ | ID3/Vorbis metadata |
| **pyacoustid** | 1.3.0+ | Chromaprint fingerprinting (AcoustID) |
| **audioseal** | 0.2.1+ | Meta AudioSeal watermarks (16-bit, imperceptible) |

### RainDSP — C++20 WASM Render Engine

**Language:** C++20  
**Compilation:** Emscripten 3.1.50+  
**Output:** WebAssembly binary + JavaScript glue  
**Precision:** 64-bit IEEE 754 float (double)  
**Determinism:** Bit-exact reproducible across browsers/OS

```cpp
// rain_dsp/src/engine.hpp (conceptual)
#include <cmath>
#include <vector>
#include <cstring>

struct ProcessingParams {
    float loudness_target;      // LUFS
    float eq_brightness;        // 0-10 (BRIGHTEN macro)
    float dynamics_glue;        // 0-10 (GLUE macro)
    float width;                // 0-10 (WIDTH macro)
    float transient_punch;      // 0-10 (PUNCH macro)
    float warmth;               // 0-10 (WARMTH macro)
    float stereo_space;         // 0-10 (SPACE macro)
    float spectral_repair;      // 0-10 (REPAIR macro)
};

class RainDSPEngine {
public:
    void process(
        const double* input,
        double* output,
        size_t frames,
        uint32_t sample_rate,
        const ProcessingParams& params
    );
    
private:
    // 16-stage pipeline
    void stage_01_format_normalization(double* buf, size_t frames);
    void stage_04_ai_inference(const ProcessingParams& p);
    void stage_10_master_bus(double* buf, size_t frames);
    void stage_13_qc_validation(double* buf, size_t frames);
};
```

**Key Characteristic:** K-Weighting biquad filter uses **ITU-R BS.1770-4 sign convention**

```cpp
// CORRECT K-weight implementation
float64_t y = b[0]*x + b[1]*x1 + b[2]*x2
            - a[1]*y1 - a[2]*y2;   // a[1] SUBTRACTED (stored negative)
```

---

## 🤖 Machine Learning & Inference Stack

### ONNX Runtime Web (Frontend Inference)

**ONNX Runtime Web 1.24.3** — Runs inside the browser

```typescript
// frontend/src/hooks/useONNXInference.ts
import * as ort from 'onnxruntime-web';

export async function inferRainNet(
  audioFeatures: Float32Array,    // 43-dim feature vector
  model: 'base' | 'tiny' | 'nano'
): Promise<ProcessingParams> {
  // Load WASM-backed ONNX model
  const session = await ort.InferenceSession.create(
    `/models/rainnet_${model}_v6.onnx`,
    { executionProviders: ['wasm', 'webgpu'] }
  );
  
  const input = new ort.Tensor('float32', audioFeatures, [1, 43]);
  const results = await session.run({ input });
  
  // Output: 46-dim processing params + 7 macro outputs
  const output = results.output.data as Float32Array;
  
  return {
    loudness_target: output[0],
    eq_brightness: Math.min(10, output[39] * 10),  // Macro: BRIGHTEN
    dynamics_glue: Math.min(10, output[40] * 10),  // Macro: GLUE
    // ... 5 more macros
  };
}
```

### PyTorch 2.0+ (Backend Training & GPU Inference)

```python
# backend/ml/model.py
import torch
import torchaudio
from transformers import AutoModel

class RainNetV2(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = torch.nn.ModuleList([
            torch.nn.Linear(43, 256),
            torch.nn.LayerNorm(256),
            torch.nn.ReLU(),
            torch.nn.Linear(256, 128),
            torch.nn.LayerNorm(128),
            torch.nn.ReLU(),
            torch.nn.Linear(128, 46)
        ])
    
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        for layer in self.encoder:
            features = layer(features)
        return torch.sigmoid(features) * 10.0  # Clamp to [0, 10]

# Training loop with Celery (GPU worker)
@celery_app.task
def train_rainnet_epoch(model_id: str, epoch: int):
    model = load_model(model_id)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    
    for batch in training_dataloader:
        output = model(batch['features'])
        loss = compute_loss(output, batch['targets'])
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    
    # Save checkpoint
    torch.save(model.state_dict(), f"checkpoints/{model_id}_epoch_{epoch}.pt")
```

### Source Separation: BS-RoFormer

**Installed via pip:** `bs-roformer-infer>=0.1.1`  
**Model Card:** Facebook Research Music Source Separation

```python
# backend/services/separation_service.py
from bs_roformer_infer import BSRoformer
import torch

async def separate_stems(audio_path: str, session_id: str) -> Dict[str, str]:
    """
    4-pass cascade:
    Pass 1: BS-RoFormer → (vocals, drums, bass, guitar, piano, other)
    Pass 2: MelBand RoFormer → (lead vocals, backing vocals)
    Pass 3: Spectral band-split → (kick, snare, hats, percussion)
    Pass 4: Dereverb → (room ambience + dry FX)
    """
    
    model = BSRoformer.from_pretrained("bs-roformer-musdb18", device="cuda")
    
    # Load audio
    waveform, sr = torchaudio.load(audio_path)
    
    # Inference
    stems = model.separate(waveform, sr)  # Returns dict of stem waveforms
    
    # Save 12 stems to S3
    stem_paths = {}
    for stem_name, stem_waveform in stems.items():
        s3_key = f"s3://rain-audio/{session_id}/stems/{stem_name}.wav"
        await upload_to_s3(stem_waveform, s3_key)
        stem_paths[stem_name] = s3_key
    
    return stem_paths
```

---

## 💾 Object Storage & Provenance

### S3-Compatible Storage (MinIO / AWS S3)

```
Bucket Structure:
s3://rain-audio/
├── {user_id}/
│   ├── {session_id}/
│   │   ├── input__{hash}.wav              (original upload)
│   │   ├── render__{hash}.wav             (final output)
│   │   ├── stems/
│   │   │   ├── vocals__{hash}.wav
│   │   │   ├── drums__{hash}.wav
│   │   │   └── ...
│   │   └── manifest__{hash}.json          (RAIN-CERT + C2PA)
```

### Cryptographic Signing & Provenance

**Ed25519 Signing** (256-bit elliptic curve)

```python
# backend/services/provenance_service.py
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import json

class ProvenanceService:
    def __init__(self, private_key_path: str):
        with open(private_key_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(f, password=None)
    
    def sign_render(self, render_data: Dict) -> str:
        """Generate RAIN-CERT (Ed25519-signed manifest)."""
        manifest = {
            "render_id": render_data['id'],
            "session_id": render_data['session_id'],
            "user_id": render_data['user_id'],
            "output_hash": render_data['output_hash'],
            "timestamp": datetime.now().isoformat(),
            "wasm_hash": render_data['wasm_hash'],
            "processing_params": render_data['params']
        }
        
        # Sign manifest
        message = json.dumps(manifest, sort_keys=True).encode()
        signature = self.private_key.sign(message)
        
        manifest['signature'] = signature.hex()
        return json.dumps(manifest)
    
    def verify_render(self, manifest_json: str) -> bool:
        """Verify RAIN-CERT signature."""
        manifest = json.loads(manifest_json)
        signature_hex = manifest.pop('signature')
        signature = bytes.fromhex(signature_hex)
        
        message = json.dumps(manifest, sort_keys=True).encode()
        try:
            self.public_key.verify(signature, message)
            return True
        except Exception:
            return False
```

### C2PA v2.2 Manifests (CBOR Encoding)

**CBOR** (Concise Binary Object Representation) per RFC 8949

```python
# backend/services/c2pa_service.py
import cbor2
from c2pa import (
    C2PAManifest,
    AssertionStore,
    ManifestStore
)

class C2PAService:
    def generate_manifest(self, render: Render) -> bytes:
        """Create C2PA v2.2 manifest with AI disclosure."""
        
        manifest = C2PAManifest(
            version="2.2",
            claim_generator="RAIN v6 by ThatGuy Productions",
            assertions={
                "c2pa.ai_generative_process": {
                    "c2pa_version": "2.2",
                    "process": [
                        {
                            "name": "RainNet v2 AI Inference",
                            "description": "Neural network loudness/EQ/dynamics mapping",
                            "tool": {
                                "name": "RainNet v2",
                                "version": "6.0.0"
                            },
                            "execution_time": render.inference_time_ms
                        },
                        {
                            "name": "RainDSP Mastering Engine",
                            "description": "Deterministic 16-stage DSP processing",
                            "tool": {
                                "name": "RainDSP",
                                "version": "6.0.0"
                            }
                        }
                    ]
                },
                "c2pa.actions": {
                    "actions": [
                        {
                            "action": "c2pa.created",
                            "changed": ["audio/*"],
                            "parameters": render.processing_params
                        }
                    ]
                }
            }
        )
        
        # Encode to CBOR
        return cbor2.dumps(manifest)
```

---

## 🔌 Desktop & DAW Integration

### Tauri 2.0 (Lightweight Desktop Wrapper)

**File:** `rain-desktop/package.json`

```json
{
  "name": "rain-desktop",
  "version": "6.0.0",
  "devDependencies": {
    "@tauri-apps/cli": "^2.0.0"
  }
}
```

**Build Command:**
```bash
npm run build
# Generates native apps for macOS, Windows, Linux
# Uses embedded Chromium; <50MB overhead
```

### JUCE 8 (DAW Plugin Framework)

**File:** `rain-plugin/README.md`

```
Run: git clone https://github.com/juce-framework/JUCE vendor/JUCE
```

**Plugin Types:**
- VST3 (Windows, macOS, Linux)
- AU (Audio Units, macOS)
- AAX (ProTools, Windows, macOS)

**JUCE Architecture:**
```cpp
// rain-plugin/src/PluginProcessor.h
#include <juce_audio_processors/juce_audio_processors.h>

class RAINAudioProcessor : public juce::AudioProcessor {
public:
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    
private:
    RainDSPEngine dsp;  // C++ → WASM binding
    ProcessingParams params;
};
```

---

## 💰 Billing & Payment Integration

### Stripe API (v8.3.0+)

```python
# backend/services/stripe_service.py
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class StripeService:
    PRODUCTS = {
        "casual": None,          # Free tier
        "creator": "prod_creator",
        "artist": "prod_artist",
        "producer": "prod_producer",
        "studio": "prod_studio",
        "label": "prod_label",
        "enterprise": None       # Custom
    }
    
    async def create_checkout_session(
        self,
        user_id: str,
        tier: str,
        is_annual: bool = False
    ) -> str:
        """Generate Stripe Checkout link."""
        
        price_id = self.PRODUCTS[tier]
        if is_annual:
            price_id = price_id.replace("monthly", "annual")
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1
                }
            ],
            mode="subscription",
            success_url="https://rain.local/success",
            cancel_url="https://rain.local/billing"
        )
        
        return session.url
    
    async def handle_webhook(self, event: Dict) -> None:
        """Process Stripe webhooks (subscription updates, failures)."""
        
        if event['type'] == 'customer.subscription.updated':
            customer_id = event['data']['object']['customer']
            # Update user tier in DB
        elif event['type'] == 'customer.subscription.deleted':
            # Downgrade user to free tier
            pass
```

---

## 🤖 Claude Sonnet AI Integration

### Anthropic SDK (anthropic>=0.40.0)

```python
# backend/services/ai_assist_service.py
from anthropic import AsyncAnthropic

class AIAssistService:
    def __init__(self):
        self.client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-20250514"
    
    async def suggest_macros(self, user_input: str) -> Dict:
        """
        Natural language intent → 7 macro suggestions + confidence.
        E.g. "make it brighter and punchier" → {BRIGHTEN: 7, PUNCH: 6}
        """
        
        prompt = f"""
You are a mastering engineer AI assistant for RAIN v6.
User request: "{user_input}"

Map this request to the 7 macro controls (each 0-10):
- BRIGHTEN: High-frequency presence, air
- GLUE: Multiband cohesion, bus compression
- WIDTH: Stereo width, M/S balance
- PUNCH: Transient shaping, vocal clarity
- WARMTH: Low-end presence, saturation
- SPACE: Stereo depth, decorrelation
- REPAIR: Spectral cleanup, de-essing

Return JSON: {{"macros": {{"BRIGHTEN": 5, ...}}, "confidence": 0.85}}
        """
        
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse and validate response
        response_text = message.content[0].text
        result = json.loads(response_text)
        
        # Clamp macros to [0, 10]
        for macro in result['macros']:
            result['macros'][macro] = max(0, min(10, result['macros'][macro]))
        
        return result
    
    async def generate_mastering_report(
        self,
        before_metrics: Dict,
        after_metrics: Dict
    ) -> str:
        """Generate human-readable mastering report."""
        
        prompt = f"""
Before mastering: {before_metrics}
After mastering: {after_metrics}

Generate a 3-4 sentence professional mastering report for the artist.
        """
        
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
```

---

## 📊 Monitoring & Observability

### Structlog (JSON Structured Logging)

```python
# backend/core/observability.py
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info(
    "render_completed",
    session_id=session_id,
    loudness_lufs=loudness,
    render_time_ms=render_time,
    user_tier=tier
)
# Output: {"event": "render_completed", "session_id": "...", ...}
```

### Prometheus Metrics

```python
# backend/core/metrics.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)

# Pre-defined metrics auto-tracked:
# - http_requests_total
# - http_request_duration_seconds (histogram)
# - http_requests_in_progress
```

### Sentry Error Tracking

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1
)
```

---

## 🚀 Deployment & Docker

### Docker Compose (Full Stack)

```yaml
version: '3.9'

services:
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://rain:password@postgres:5432/rain
      - VALKEY_URL=valkey://valkey:6379
      - S3_BUCKET=rain-audio
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - STRIPE_API_KEY=${STRIPE_API_KEY}
      - RAIN_NORMALIZATION_VALIDATED=true
    depends_on:
      - postgres
      - valkey

  frontend:
    build:
      context: ./frontend
      dockerfile: ../docker/Dockerfile.frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000

  postgres:
    image: postgres:18-alpine
    environment:
      - POSTGRES_USER=rain
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=rain
    volumes:
      - postgres_data:/var/lib/postgresql/data

  valkey:
    image: valkey:9.0-alpine
    ports:
      - "6379:6379"
    volumes:
      - valkey_data:/data

  worker:  # Celery GPU worker (source separation)
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    environment:
      - CELERY_BROKER_URL=valkey://valkey:6379/0
      - CUDA_VISIBLE_DEVICES=0
    depends_on:
      - valkey
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  postgres_data:
  valkey_data:
```

---

## 🧪 Testing Stack

### Frontend Testing

```json
// rain-tests/frontend/package.json
{
  "devDependencies": {
    "vitest": "^1.2.0",
    "@testing-library/react": "^14.2.0",
    "@testing-library/jest-dom": "^6.4.0",
    "jsdom": "^24.0.0"
  }
}
```

### Backend Testing

```python
# pytest async fixtures
# requirements.txt includes: pytest>=8.0.2, pytest-asyncio>=0.23.5

@pytest.mark.asyncio
async def test_render_pipeline(client, session_id):
    # Test full mastering pipeline
    response = await client.post(
        f"/api/v1/master/{session_id}/render",
        json={"target_lufs": -14}
    )
    assert response.status_code == 200
    assert "render_id" in response.json()
```

---

## 📦 Dependency Tree Summary

```
RAIN v6 Stack
├── Frontend (React 19)
│   ├── Build: Vite 7 + TypeScript 5.5
│   ├── Styling: Tailwind CSS 4
│   ├── State: Zustand 5 + TanStack Query 5
│   ├── Components: Radix UI + Framer Motion
│   └── ML: ONNX Runtime Web 1.24.3 (WASM)
│
├── Backend (FastAPI)
│   ├── API Server: FastAPI 0.109+ + uvicorn
│   ├── Database: PostgreSQL 18 + SQLAlchemy 2.0
│   ├── Cache: Valkey 9.0 (Redis fork)
│   ├── Tasks: Celery 5.3 (GPU worker)
│   ├── Audio DSP: scipy, librosa, soundfile, pyloudnorm
│   ├── Source Sep: BS-RoFormer + MelBand RoFormer
│   ├── ML: PyTorch 2.0, ONNX Runtime 1.17
│   ├── Provenance: Ed25519, C2PA v2.2, CBOR2
│   ├── AI: Anthropic Claude Sonnet
│   ├── Billing: Stripe API
│   ├── Logging: Structlog + Sentry
│   └── Metrics: Prometheus + Instrumentator
│
├── DSP Engine
│   ├── RainDSP: C++20 → Emscripten WASM
│   └── Precision: 64-bit IEEE 754 double
│
├── Desktop / DAW
│   ├── Desktop: Tauri 2.0
│   └── Plugins: JUCE 8 (VST3 / AU / AAX)
│
└── Infrastructure
    ├── Storage: S3-compatible (MinIO / AWS)
    ├── CI/CD: GitHub Actions
    └── Container: Docker + Compose
```

---

## 🔑 Environment Variables (Required)

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/rain_prod

# Cache/Queue
VALKEY_URL=valkey://localhost:6379
CELERY_BROKER_URL=valkey://localhost:6379/0
CELERY_RESULT_BACKEND=valkey://localhost:6379/1

# Object Storage
S3_BUCKET=rain-audio
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Authentication & Security
JWT_SECRET=your-secret-key
RAIN_NORMALIZATION_VALIDATED=true
RAIN_EXPECTED_WASM_HASH=sha256:a1b2c3d4...

# Billing
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# AI Integration
ANTHROPIC_API_KEY=sk-ant-...

# Distribution
LABELGRID_API_KEY=...
DDEX_ERN_VERSION=4.3.2

# Observability
SENTRY_DSN=https://...@sentry.io/...
PROMETHEUS_PUSHGATEWAY=http://localhost:9091

# GPU (Optional)
CUDA_VISIBLE_DEVICES=0
SEPARATION_ENABLED=true
```

---

## 📈 Performance Targets (v6.0)

| Operation | Latency | Target |
|-----------|---------|--------|
| Preview render (Web Audio) | <50ms | Real-time |
| RainNet inference (WASM) | <2s | 3-min track |
| RainDSP render (C++) | <5s | 3-min track, 48kHz 24-bit |
| API response (cached) | <50ms | Session metadata |
| S3 upload (100MB) | <30s | 100 Mbps network |
| Source separation | <30s | 3-min stereo (GPU) |

---

## 🎓 Quick Start

```bash
# Clone
git clone https://github.com/ThatGuy-Productions/RAIN-V6-...git
cd RAIN-V6-...

# Environment
cp .env.example .env
# Edit .env — add API keys

# Full stack
docker compose up --build

# Backend only (dev)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# Frontend only (dev)
cd frontend && npm install && npm run dev
```

---

**© 2026 ThatGuy Productions · ARCOVEL Technologies International**  
*RAIN v6.0 · Local-first AI mastering and distribution infrastructure*
