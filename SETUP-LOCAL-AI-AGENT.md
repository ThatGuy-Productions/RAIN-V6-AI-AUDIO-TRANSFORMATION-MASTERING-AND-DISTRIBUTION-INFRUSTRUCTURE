# RAIN Setup Guide for Local AI Coding Agents

This guide enables a local AI model (via Continue.dev, Cursor, GitHub Copilot, or similar) to autonomously clone, build, install, and run the RAIN repository in a development environment.

---

## Prerequisites Verification

Before starting, the AI agent should verify these are installed:

```bash
# Check Git
git --version
# Expected: git version 2.x+

# Check Docker
docker --version
# Expected: Docker version 20.x+ (or compatible)

# Check Docker Compose
docker compose version
# Expected: Docker Compose version v2.x+

# Check Node.js (for frontend development)
node --version npm --version
# Expected: Node.js 20.x+, npm 10.x+

# Check Python
python3 --version
# Expected: Python 3.12+

# Check Rust/Cargo (for Tauri desktop builds — optional)
rustc --version cargo --version
# Expected: If building rain-desktop (optional)
```

---

## One-Command Setup & Run

For AI agents, here's a single consolidated script that handles everything:

### **Linux/macOS**

```bash
#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== RAIN Setup for AI Agents ===${NC}"

# 1. Clone repository
echo -e "${YELLOW}[1/7] Cloning RAIN repository...${NC}"
if [ -d "RAIN-MASTERING-DISTRIBUTION-ENGINE" ]; then
    echo -e "${YELLOW}Repository already exists, pulling latest...${NC}"
    cd RAIN-MASTERING-DISTRIBUTION-ENGINE
    git pull origin main
    cd ..
else
    git clone https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE.git
    cd RAIN-MASTERING-DISTRIBUTION-ENGINE
fi

cd RAIN-MASTERING-DISTRIBUTION-ENGINE

# 2. Verify prerequisites
echo -e "${YELLOW}[2/7] Verifying prerequisites...${NC}"
for cmd in git docker python3 node npm; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}ERROR: $cmd not found. Please install it first.${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ All prerequisites installed${NC}"

# 3. Setup environment
echo -e "${YELLOW}[3/7] Setting up environment files...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env from .env.example${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# 4. Build and start Docker stack
echo -e "${YELLOW}[4/7] Building Docker stack (this may take 2-5 minutes)...${NC}"
docker compose up --build -d
echo -e "${GREEN}✓ Docker services started${NC}"

# 5. Wait for services to be ready
echo -e "${YELLOW}[5/7] Waiting for services to be healthy (max 60s)...${NC}"
timeout=0
while [ $timeout -lt 60 ]; do
    if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend API is ready${NC}"
        break
    fi
    echo -n "."
    sleep 2
    timeout=$((timeout + 2))
done

if [ $timeout -ge 60 ]; then
    echo -e "${YELLOW}⚠ Backend not ready after 60s, but services may still be initializing${NC}"
fi

# 6. Download ML models (optional, for production use)
echo -e "${YELLOW}[6/7] ML Models info...${NC}"
echo -e "${BLUE}Models are auto-downloaded on first use.${NC}"
echo -e "${BLUE}To pre-download: python3 scripts/download_models.py${NC}"

# 7. Display access URLs
echo ""
echo -e "${GREEN}=== RAIN is running! ===${NC}"
echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo -e "  Frontend:        ${GREEN}http://localhost:5173${NC}"
echo -e "  Backend API:     ${GREEN}http://localhost:8000${NC}"
echo -e "  API Docs:        ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  MinIO Console:   ${GREEN}http://localhost:9001${NC}"
echo -e "  Grafana:         ${GREEN}http://localhost:3000${NC}"
echo ""
echo -e "${BLUE}Default credentials:${NC}"
echo -e "  Grafana: admin / rain_grafana"
echo -e "  MinIO: minioadmin / minioadmin"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  • Visit http://localhost:5173 in your browser"
echo -e "  • Read backend/app/main.py to understand the API structure"
echo -e "  • Frontend code: frontend/src/ (React 19 + TypeScript)"
echo -e "  • Backend code: backend/app/ (FastAPI)"
echo ""
echo -e "${YELLOW}To stop services:${NC}"
echo -e "  ${BLUE}docker compose down${NC}"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo -e "  ${BLUE}docker compose logs -f backend${NC}"
echo -e "  ${BLUE}docker compose logs -f frontend${NC}"
```

### **Windows (PowerShell)**

```powershell
# RAIN Setup for AI Agents on Windows

$ErrorActionPreference = "Stop"

# Colors
function Write-Header { Write-Host $args -ForegroundColor Cyan }
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

Write-Header "=== RAIN Setup for AI Agents (Windows) ==="

# 1. Clone repository
Write-Warning "[1/7] Cloning RAIN repository..."
if (Test-Path "RAIN-MASTERING-DISTRIBUTION-ENGINE") {
    Write-Warning "Repository already exists, pulling latest..."
    cd RAIN-MASTERING-DISTRIBUTION-ENGINE
    git pull origin main
    cd ..
} else {
    git clone https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE.git
    cd RAIN-MASTERING-DISTRIBUTION-ENGINE
}

# 2. Verify prerequisites
Write-Warning "[2/7] Verifying prerequisites..."
$required = @("git", "docker", "python", "node", "npm")
foreach ($cmd in $required) {
    try {
        & $cmd --version > $null
        Write-Success "✓ $cmd found"
    } catch {
        Write-Error "ERROR: $cmd not found. Please install it first."
        exit 1
    }
}

# 3. Setup environment
Write-Warning "[3/7] Setting up environment files..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Success "✓ Created .env from .env.example"
} else {
    Write-Success "✓ .env already exists"
}

# 4. Build and start Docker stack
Write-Warning "[4/7] Building Docker stack (this may take 2-5 minutes)..."
docker compose up --build -d
Write-Success "✓ Docker services started"

# 5. Wait for services
Write-Warning "[5/7] Waiting for services to be healthy (max 60s)..."
$timeout = 0
while ($timeout -lt 60) {
    try {
        $response = Invoke-WebRequest http://localhost:8000/docs -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "✓ Backend API is ready"
            break
        }
    } catch {
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 2
        $timeout += 2
    }
}

# 6. Display access URLs
Write-Host ""
Write-Success "=== RAIN is running! ==="
Write-Host ""
Write-Header "Access URLs:"
Write-Host "  Frontend:        http://localhost:5173"
Write-Host "  Backend API:     http://localhost:8000"
Write-Host "  API Docs:        http://localhost:8000/docs"
Write-Host "  MinIO Console:   http://localhost:9001"
Write-Host "  Grafana:         http://localhost:3000"
Write-Host ""
Write-Header "Default credentials:"
Write-Host "  Grafana: admin / rain_grafana"
Write-Host "  MinIO: minioadmin / minioadmin"
Write-Host ""
Write-Header "Next steps:"
Write-Host "  • Visit http://localhost:5173 in your browser"
Write-Host "  • Read backend/app/main.py to understand the API structure"
Write-Host "  • Frontend code: frontend/src/ (React 19 + TypeScript)"
Write-Host "  • Backend code: backend/app/ (FastAPI)"
Write-Host ""
Write-Warning "To stop services:"
Write-Host "  docker compose down"
Write-Host ""
Write-Warning "To view logs:"
Write-Host "  docker compose logs -f backend"
Write-Host "  docker compose logs -f frontend"
```

---

## Step-by-Step Manual Setup (for AI agents that prefer explicit steps)

### Step 1: Clone the Repository

```bash
git clone https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE.git
cd RAIN-MASTERING-DISTRIBUTION-ENGINE
git checkout main
```

**What the AI should know:**
- Default branch: `main`
- Repo size: ~95 MB
- Large files: C++ compiled binaries, ONNX model weights

### Step 2: Verify Environment

```bash
# Check Docker
docker version
docker compose version

# Check Node.js
node --version  # Should be 20+
npm --version   # Should be 10+

# Check Python
python3 --version  # Should be 3.12+
```

### Step 3: Configure Environment Variables

```bash
# Copy example environment
cp .env.example .env

# Edit .env if needed (defaults work for local dev)
# KEY VARIABLES:
#   RAIN_ENV=development
#   DATABASE_URL=postgresql+asyncpg://rain_app:rain_dev@localhost:5432/rain
#   REDIS_URL=redis://localhost:6379/0
#   JWT_SECRET_KEY=dev (auto-generated if empty)
```

### Step 4: Start the Full Stack

```bash
# Build and start all services (PostgreSQL 18, Valkey 9.0, backend, frontend)
docker compose up --build -d

# Wait for services to initialize (~30-60 seconds)
sleep 30

# Check status
docker compose ps
```

### Step 5: Verify Services Are Running

```bash
# Backend health check
curl http://localhost:8000/docs

# Frontend health check
curl http://localhost:5173

# Expected responses: 200 OK
```

### Step 6: Access the Application

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:5173 | Web UI (React 19) |
| Backend API | http://localhost:8000 | REST API |
| API Docs (Swagger) | http://localhost:8000/docs | Interactive API documentation |
| MinIO Console | http://localhost:9001 | Object storage UI |
| Grafana | http://localhost:3000 | Monitoring dashboard |

---

## For AI Agents: Code Structure Navigation

Once running, here's where to find key components:

### Frontend (React 19 + TypeScript)

```
frontend/src/
├── components/          UI components (buttons, sliders, waveforms)
├── stores/              Zustand state management
│   ├── authStore.ts
│   ├── sessionStore.ts  (audio processing state)
│   └── uiStore.ts
├── utils/
│   ├── api.ts           (FastAPI client)
│   ├── analytics.ts     (PostHog integration)
│   └── heuristic-params.ts  (DSP parameter mapping)
├── views/               Page-level components
│   ├── AppLayout.tsx
│   ├── LandingPage.tsx
│   └── MasteringView.tsx
└── main.tsx             Entry point
```

**Key file to understand first:** `frontend/src/views/MasteringView.tsx` — orchestrates the entire mastering flow.

### Backend (FastAPI + Python 3.12)

```
backend/app/
├── main.py              Entry point (FastAPI app definition)
├── api/routes/          13 API routers
│   ├── auth.py          JWT + OAuth
│   ├── master.py        Mastering endpoints
│   ├── separate.py      Stem separation
│   ├── qc.py            Quality control
│   ├── distribution.py  DDEX release
│   └── billing.py       Stripe integration
├── services/            Business logic
│   ├── dsp_engine.py    Calls RainDSP WASM
│   ├── feature_extraction.py    43-dim features
│   ├── ml_inference.py  ONNX Runtime
│   ├── qc_engine.py     18-check validation
│   ├── provenance.py    Ed25519 signing
│   └── intent_engine.py Claude integration
├── models/              SQLAlchemy ORM
│   ├── user.py
│   ├── session.py       Mastering session
│   └── master_job.py
├── schemas/             Pydantic request/response
│   └── master_schemas.py
├── core/
│   ├── config.py        Settings from .env
│   ├── database.py      PostgreSQL connection
│   ├── security.py      JWT + RLS
│   └── observability.py Prometheus/Grafana
├── tasks/               Celery async tasks
│   ├── render.py        RainDSP processing
│   ├── separation.py    BS-RoFormer
│   └── certification.py RAIN-CERT signing
└── worker.py            Celery configuration
```

**Key file to understand first:** `backend/app/main.py` — defines all routes and middleware.

### C++ DSP Engine (RainDSP)

```
rain-dsp/
├── src/
│   ├── main.cpp         WASM entry point
│   ├── fft.cpp          Fast Fourier Transform
│   ├── linear_phase_eq.cpp  8-band parametric EQ
│   ├── multiband.cpp    3-band compressor
│   ├── ms_processing.cpp    Mid-Side stereo
│   ├── saturation.cpp   Analog emulation
│   └── sail.cpp         Stem-Aware Intelligent Limiter
├── include/
│   ├── rain_dsp.h       Header with ProcessingParams struct
│   └── fft.h
├── emscripten.cmake     WASM build config
└── README.md
```

**Key struct:** `ProcessingParams` in `rain_dsp.h` — 46 parameters controlling the entire DSP chain.

### ML Training (Optional for AI Agents)

```
ml/rainnet/
├── model.py             RainNetV2 (46-output PyTorch model)
├── dataset.py           Training data loader
├── export.py            ONNX export
├── train.py             Training loop
└── loss.py              Custom loss functions
```

---

## Common AI Agent Tasks & Commands

### Task: Add a New API Endpoint

1. **Create schema** in `backend/app/schemas/`:
```python
# Example: new endpoint for custom mastering
class CustomMasterRequest(BaseModel):
    audio_id: str
    custom_param: float
```

2. **Add route** in `backend/app/api/routes/master.py`:
```python
@router.post("/master/{id}/custom")
async def custom_master(id: str, req: CustomMasterRequest, user: CurrentUser = Depends(get_current_user)):
    # Implementation
    return {"status": "ok"}
```

3. **Restart backend**: `docker compose restart backend`

4. **Test**: Visit `http://localhost:8000/docs` → try it out

### Task: Modify DSP Parameters

1. **Edit** `rain-dsp/src/` (C++ files)
2. **Rebuild WASM**: `cd rain-dsp && cargo build --target wasm32-unknown-emscripten --release`
3. **Copy to frontend**: `cp rain-dsp/target/wasm32-unknown-emscripten/release/rain_dsp_wasm.* frontend/public/wasm/`
4. **Restart frontend**: `docker compose restart frontend`

### Task: Run Tests

```bash
# Backend tests
docker compose exec backend pytest tests/ -v

# Frontend tests (if configured)
docker compose exec frontend npm test
```

### Task: View Logs

```bash
# Follow all logs
docker compose logs -f

# Backend only
docker compose logs -f backend

# Frontend only
docker compose logs -f frontend

# Database logs
docker compose logs -f postgres
```

### Task: Access Database

```bash
# PostgreSQL CLI
docker compose exec postgres psql -U rain_app -d rain

# Example queries
SELECT COUNT(*) FROM users;
SELECT id, user_id, status FROM master_jobs LIMIT 5;
```

---

## Troubleshooting for AI Agents

### Problem: Port Already in Use

```bash
# Find process using port 5173
lsof -i :5173  # macOS/Linux
netstat -ano | findstr :5173  # Windows

# Kill process or change port in docker-compose.yml
```

### Problem: Docker Build Fails

```bash
# Clean rebuild
docker compose down -v  # Remove all volumes
docker compose up --build -d

# Check Docker disk space
docker system df
docker system prune -a
```

### Problem: Backend Won't Start

```bash
# Check logs
docker compose logs backend

# Verify PostgreSQL is ready
docker compose logs postgres | grep "ready to accept"

# Restart only backend
docker compose restart backend
```

### Problem: API Returns 500 Error

```bash
# Check detailed logs
docker compose logs backend | grep ERROR

# Try accessing /docs to see if API is alive
curl http://localhost:8000/docs

# Restart all services
docker compose down
docker compose up -d
```

---

## For AI Coding Assistants: Architecture Constraints

**When writing code, ALWAYS remember:**

1. **No S3 on free tier** — Free renders must stay in WASM memory
2. **Dual paths are separate** — Preview (Web Audio) ≠ Render (RainDSP)
3. **Multi-tenant isolation** — Every DB query: `WHERE user_id = $user_id`
4. **WASM is deterministic** — Same input + params = same hash, always
5. **ML gate is critical** — `RAIN_NORMALIZATION_VALIDATED` must be checked
6. **Biquad sign convention** — `a1` is stored negative: `y = ... − a1·y₁ − a2·y₂`

See `CLAUDE.md` for the complete immutable specification.

---

## Next Steps for AI Agents

1. **Read `CLAUDE.md`** for architecture immutables
2. **Read `plan.md`** for the implementation roadmap
3. **Explore `backend/app/main.py`** to understand the API structure
4. **Explore `frontend/src/views/MasteringView.tsx`** to understand the UI flow
5. **Check `rain-dsp/include/rain_dsp.h`** to see the ProcessingParams struct
6. **Run `docker compose logs -f`** to watch real-time processing

---

## Support Resources

- **Repository Issues:** https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/issues
- **API Docs:** http://localhost:8000/docs (when running)
- **Architecture:** See `CLAUDE.md` in the root directory
- **Contact:** engineering@arcovel.com (ARCOVEL Technologies)
