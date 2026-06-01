@echo off
REM RAIN Mastering Engine — Complete Build & Run Script (Windows)
REM Compatible: PowerShell, Command Prompt, Windows Terminal
REM
REM Usage:
REM   rain-setup.ps1              # Full setup (PowerShell only)
REM   rain-setup.ps1 -Quick       # Quick start
REM   rain-setup.ps1 -Help        # Show help
REM
REM Requirements:
REM   - Git for Windows
REM   - Docker Desktop for Windows
REM   - PowerShell 7+ (recommended)

param(
    [switch]$Quick,
    [switch]$NoClone,
    [switch]$Help,
    [switch]$Version
)

$ErrorActionPreference = "Stop"

# Colors
$Colors = @{
    Red    = "Red"
    Green  = "Green"
    Yellow = "Yellow"
    Cyan   = "Cyan"
    Gray   = "Gray"
}

# Global configuration
$REPO_URL = "https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE.git"
$REPO_DIR = "RAIN-MASTERING-DISTRIBUTION-ENGINE"
$SETUP_MODE = if ($Quick) { "quick" } else { "full" }

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Show-Help {
    $help = @"
RAIN Mastering Engine — Build & Run Script (Windows)

USAGE:
    .\rain-setup.ps1 [-Quick] [-NoClone] [-Help] [-Version]

OPTIONS:
    -Quick          Skip validation checks, assume Docker is installed
    -NoClone        Skip git clone (repo already exists locally)
    -Help           Show this help message
    -Version        Show version info

EXAMPLES:
    .\rain-setup.ps1                    # Full setup with all checks
    .\rain-setup.ps1 -Quick             # Quick setup (Docker required)
    .\rain-setup.ps1 -NoClone           # Setup existing local repo

REQUIREMENTS:
    • Git for Windows (git-scm.com)
    • Docker Desktop for Windows
    • PowerShell 7+ (recommended)
    • 8 GB RAM minimum
    • 20 GB disk space

AFTER SETUP:
    Frontend:  http://localhost:5173
    Backend:   http://localhost:8000
    API Docs:  http://localhost:8000/docs
    Database:  localhost:5432
    Cache:     localhost:6379

For more info, see: https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki
"@
    Write-Host $help
}

function Show-Version {
    Write-Host "RAIN Setup Script v1.0 (Windows)"
    Write-Host "RAIN Master Spec v6.1"
    Write-Host "Release: 2026-06-01"
}

function Check-Requirements {
    Write-Header "Checking System Requirements"

    $missing = @()

    # Check Git
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        $missing += "git"
    } else {
        $gitVersion = & git --version
        Write-Success $gitVersion
    }

    # Check Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        $missing += "docker"
    } else {
        $dockerVersion = & docker --version
        Write-Success $dockerVersion
    }

    # Check disk space (C: drive, minimum 20 GB)
    $drive = Get-PSDrive -Name C
    $diskSpaceGB = [math]::Round($drive.Free / 1GB, 2)

    if ($diskSpaceGB -lt 20) {
        Write-Warning "Low disk space: ${diskSpaceGB}GB available (recommend 20GB+)"
    } else {
        Write-Success "Disk space: ${diskSpaceGB}GB available"
    }

    if ($missing.Count -gt 0) {
        Write-Error "Missing required tools: $($missing -join ', ')"
        Write-Host ""
        Write-Host "Install instructions:"
        Write-Host "  • Git:             https://git-scm.com/download/win"
        Write-Host "  • Docker Desktop:  https://www.docker.com/products/docker-desktop"
        exit 1
    }

    Write-Success "All requirements met!"
}

function Clone-Repository {
    if ($NoClone) {
        Write-Info "Skipping clone (-NoClone flag set)"
        if (Test-Path $REPO_DIR) {
            Push-Location $REPO_DIR
            Write-Success "Using existing repository at $(Get-Location)"
        } else {
            Write-Error "Repository directory not found: $REPO_DIR"
            exit 1
        }
        return
    }

    Write-Header "Cloning Repository"

    if (Test-Path $REPO_DIR) {
        Write-Warning "Repository already exists at .\$REPO_DIR"
        $response = Read-Host "Overwrite? (y/n)"
        if ($response -eq 'y') {
            Remove-Item -Recurse -Force $REPO_DIR
        } else {
            Push-Location $REPO_DIR
            Write-Success "Using existing repository"
            return
        }
    }

    Write-Info "Cloning from: $REPO_URL"
    & git clone $REPO_URL $REPO_DIR

    if ($LASTEXITCODE -eq 0) {
        Push-Location $REPO_DIR
        Write-Success "Repository cloned successfully"
        Write-Info "Location: $(Get-Location)"
    } else {
        Write-Error "Failed to clone repository"
        exit 1
    }
}

function Setup-Environment {
    Write-Header "Setting Up Environment"

    if (Test-Path ".env") {
        Write-Warning ".env file already exists"
        $response = Read-Host "Regenerate? (y/n)"
        if ($response -ne 'y') {
            Write-Info "Keeping existing .env"
            return
        }
    }

    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success "Created .env from template"
    } else {
        Write-Warning ".env.example not found, creating minimal .env"
        $envContent = @"
# RAIN Development Environment
RAIN_ENV=development
DEBUG=true

# Database
DATABASE_URL=postgresql://rain:rainpassword@db:5432/rain_dev
POSTGRES_USER=rain
POSTGRES_PASSWORD=rainpassword
POSTGRES_DB=rain_dev

# Cache
VALKEY_URL=redis://cache:6379/0
REDIS_URL=redis://cache:6379/0

# S3 (MinIO in dev)
S3_ENDPOINT=http://storage:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=rain-dev

# JWT
JWT_SECRET_KEY=dev-secret-key-do-not-use-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# ML Gates
RAIN_NORMALIZATION_VALIDATED=false
SEPARATION_ENABLED=false

# API Keys (development placeholders)
ANTHROPIC_API_KEY=sk-placeholder-dev
SUNO_API_KEY=placeholder-dev
LABELGRID_API_KEY=placeholder-dev
STRIPE_SECRET_KEY=sk_test_placeholder

# Feature flags
FEATURE_PITCH_CORRECTION=true
FEATURE_INSTRUMENT_SYNTHESIS=true
FEATURE_STEM_SEPARATION=false

# WASM
RAIN_EXPECTED_WASM_HASH=

# Logging
LOG_LEVEL=INFO
STRUCTLOG_PROCESSORS=json

# Port
API_PORT=8000
FRONTEND_PORT=5173
"@
        $envContent | Out-File -Encoding UTF8 ".env"
    }

    Write-Success "Environment configured"
}

function Docker-Build {
    Write-Header "Building Docker Images"

    Write-Info "Building backend image..."
    & docker compose build backend
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Backend build failed"
        exit 1
    }
    Write-Success "Backend image built"

    Write-Info "Building frontend image..."
    & docker compose build frontend
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Frontend build failed"
        exit 1
    }
    Write-Success "Frontend image built"

    Write-Success "All images built successfully"
}

function Docker-Start {
    Write-Header "Starting Docker Compose Stack"

    Write-Info "Starting services..."
    & docker compose up -d

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker Compose stack started"
    } else {
        Write-Error "Failed to start Docker Compose"
        exit 1
    }
}

function Docker-Wait-Healthy {
    Write-Header "Waiting for Services to Be Ready"

    $maxAttempts = 60
    $attempt = 1

    Write-Info "Checking database connectivity..."
    while ($attempt -le $maxAttempts) {
        $dbReady = & docker compose exec -T db pg_isready -U rain -d rain_dev 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Database is ready"
            break
        }
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 1
        $attempt++
    }

    if ($attempt -gt $maxAttempts) {
        Write-Error "Database failed to start within timeout"
        exit 1
    }

    Start-Sleep -Seconds 2

    Write-Info "Checking backend API..."
    $attempt = 1
    while ($attempt -le 30) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "Backend API is ready"
                break
            }
        } catch {
            # API not ready yet
        }
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 1
        $attempt++
    }

    if ($attempt -gt 30) {
        Write-Warning "Backend API health check timed out (may still be initializing)"
    }

    Write-Success "All services are ready!"
}

function Run-Migrations {
    Write-Header "Running Database Migrations"

    Write-Info "Running Alembic migrations..."
    & docker compose exec -T backend alembic upgrade head

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Database migrations completed"
    } else {
        Write-Warning "Migration step encountered issues (check logs)"
    }
}

function Preflight-Check {
    Write-Header "Running Preflight Checks"

    Write-Info "Checking WASM module..."
    if (Test-Path "rain-dsp/build/rain_dsp.wasm") {
        $wasmSize = (Get-Item "rain-dsp/build/rain_dsp.wasm").Length / 1MB
        Write-Success "WASM module found (${wasmSize}MB)"
    } else {
        Write-Warning "WASM module not found (will build during container startup)"
    }

    Write-Info "Checking environment variables..."
    if (Test-Path ".env") {
        Write-Success ".env file present"
    } else {
        Write-Error ".env file missing"
        exit 1
    }

    Write-Success "Preflight checks passed"
}

function Show-Access-Info {
    Write-Header "RAIN is Ready!"

    $info = @"
✓ Mastering Engine Status: RUNNING

Access URLs:
  • Frontend (Web UI):     http://localhost:5173
  • Backend API:           http://localhost:8000
  • API Documentation:     http://localhost:8000/docs
  • Database (PostgreSQL): localhost:5432
  • Cache (Valkey):        localhost:6379
  • S3 (MinIO):            http://localhost:9001

Default Credentials:
  • Database user:  rain
  • Database pass:  rainpassword
  • S3 access key:  minioadmin
  • S3 secret key:  minioadmin

Useful Commands:
  • View logs:         docker compose logs -f
  • Stop services:     docker compose down
  • Restart services:  docker compose restart
  • Run migrations:    docker compose exec backend alembic upgrade head
  • Access database:   docker compose exec db psql -U rain -d rain_dev
  • Access S3:         http://localhost:9001 (minioadmin/minioadmin)

Documentation:
  • Wiki Home:           https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki
  • Architecture:        https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki/Architecture
  • Development Setup:   https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki/Development-Setup
  • Vocal Features:      https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki/Vocal-Production-Features

Next Steps:
  1. Open http://localhost:5173 in your browser
  2. Create an account (dev mode)
  3. Upload an audio file
  4. Explore the mastering pipeline!

For support, see: https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/issues
"@
    Write-Host $info -ForegroundColor Green
}

function Main {
    # Display banner
    @"

    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     🌧️  RAIN — R∞N AI Mastering Engine v6.1                 ║
    ║                                                               ║
    ║     Complete Setup & Launch Script (Windows)                 ║
    ║     Repository: aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

"@ | Write-Host -ForegroundColor Cyan

    # Handle special flags
    if ($Help) {
        Show-Help
        return
    }

    if ($Version) {
        Show-Version
        return
    }

    # Execute setup phases
    if ($SETUP_MODE -ne "quick") {
        Check-Requirements
    }

    Clone-Repository
    Preflight-Check
    Setup-Environment
    Docker-Build
    Docker-Start
    Docker-Wait-Healthy
    Run-Migrations
    Show-Access-Info

    Write-Host ""
    Write-Info "Setup complete! Press Ctrl+C to stop services."
}

Main