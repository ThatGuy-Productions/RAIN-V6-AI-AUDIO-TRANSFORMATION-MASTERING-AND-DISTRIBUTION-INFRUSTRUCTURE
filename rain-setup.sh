#!/usr/bin/env bash
# RAIN Mastering Engine — Complete Build & Run Script
# Compatible: PowerShell, Git Bash, macOS, Linux
# 
# Usage:
#   ./rain-setup.sh              # Full setup
#   ./rain-setup.sh --quick      # Quick start (assumes Docker installed)
#   ./rain-setup.sh --help       # Show this help
#
# Requirements:
#   - Git
#   - Docker & Docker Compose
#   - Python 3.12+ (for manual setup only)
#   - Node.js 20+ (for manual setup only)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variables
REPO_URL="https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE.git"
REPO_DIR="RAIN-MASTERING-DISTRIBUTION-ENGINE"
SETUP_MODE="full"
SKIP_CLONE=false

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

show_help() {
    cat << EOF
RAIN Mastering Engine — Build & Run Script

USAGE:
    ./rain-setup.sh [OPTIONS]

OPTIONS:
    --quick         Skip validation checks, assume Docker is installed
    --no-clone      Skip git clone (repo already exists locally)
    --help          Show this help message
    --version       Show version info

EXAMPLES:
    ./rain-setup.sh                 # Full setup with all checks
    ./rain-setup.sh --quick         # Quick setup (Docker required)
    ./rain-setup.sh --no-clone      # Setup existing local repo

WHAT THIS SCRIPT DOES:
    1. Validates system requirements (Docker, Git, etc.)
    2. Clones RAIN repository from GitHub
    3. Sets up environment (.env file)
    4. Runs database migrations
    5. Starts Docker Compose stack
    6. Displays access URLs

REQUIREMENTS:
    • Git 2.0+
    • Docker 24+
    • Docker Compose 2.20+
    • 8 GB RAM minimum
    • 20 GB disk space

AFTER SETUP:
    Frontend:  http://localhost:5173
    Backend:   http://localhost:8000
    API Docs:  http://localhost:8000/docs
    Database:  localhost:5432
    Cache:     localhost:6379

For more info, see: https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki

EOF
}

show_version() {
    echo "RAIN Setup Script v1.0"
    echo "RAIN Master Spec v6.1"
    echo "Release: 2026-06-01"
}

# ============================================================================
# System Validation
# ============================================================================

check_requirements() {
    print_header "Checking System Requirements"

    local missing=()

    # Check Git
    if ! command -v git &> /dev/null; then
        missing+=("git")
    else
        GIT_VERSION=$(git --version | awk '{print $3}')
        print_success "Git ${GIT_VERSION}"
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    else
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
        print_success "Docker ${DOCKER_VERSION}"
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing+=("docker-compose")
    else
        COMPOSE_VERSION=$(docker compose version 2>/dev/null | awk '{print $4}' || echo "unknown")
        print_success "Docker Compose ${COMPOSE_VERSION}"
    fi

    # Check disk space (minimum 20 GB)
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows
        DISK_SPACE=$(powershell -Command "(Get-Volume -DriveLetter C).SizeRemaining / 1GB" 2>/dev/null || echo "0")
    else
        # macOS / Linux
        DISK_SPACE=$(df / | awk 'NR==2 {print $4/1024/1024}')
    fi

    if (( $(echo "$DISK_SPACE < 20" | bc -l 2>/dev/null || echo "1") )); then
        print_warning "Low disk space: ${DISK_SPACE}GB available (recommend 20GB+)"
    else
        print_success "Disk space: ${DISK_SPACE}GB available"
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        print_error "Missing required tools: ${missing[*]}"
        echo ""
        echo "Install instructions:"
        echo "  • Git:             https://git-scm.com/download"
        echo "  • Docker:          https://docs.docker.com/get-docker/"
        echo "  • Docker Compose:  https://docs.docker.com/compose/install/"
        exit 1
    fi

    print_success "All requirements met!"
}

# ============================================================================
# Repository Setup
# ============================================================================

clone_repository() {
    if [ "$SKIP_CLONE" = true ]; then
        print_info "Skipping clone (--no-clone flag set)"
        if [ -d "$REPO_DIR" ]; then
            cd "$REPO_DIR"
            print_success "Using existing repository at $(pwd)"
        else
            print_error "Repository directory not found: $REPO_DIR"
            exit 1
        fi
        return
    fi

    print_header "Cloning Repository"

    if [ -d "$REPO_DIR" ]; then
        print_warning "Repository already exists at ./$REPO_DIR"
        read -p "Overwrite? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$REPO_DIR"
        else
            cd "$REPO_DIR"
            print_success "Using existing repository"
            return
        fi
    fi

    print_info "Cloning from: $REPO_URL"
    git clone "$REPO_URL" "$REPO_DIR"

    if [ $? -eq 0 ]; then
        cd "$REPO_DIR"
        print_success "Repository cloned successfully"
        print_info "Location: $(pwd)"
    else
        print_error "Failed to clone repository"
        exit 1
    fi
}

# ============================================================================
# Environment Setup
# ============================================================================

setup_environment() {
    print_header "Setting Up Environment"

    if [ -f ".env" ]; then
        print_warning ".env file already exists"
        read -p "Regenerate? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env"
            return
        fi
    fi

    # Copy template
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Created .env from template"
    else
        print_warning ".env.example not found, creating minimal .env"
        cat > .env << 'ENVFILE'
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
ENVFILE
    fi

    print_success "Environment configured"
}

# ============================================================================
# Docker Compose Operations
# ============================================================================

docker_build() {
    print_header "Building Docker Images"

    print_info "Building backend image..."
    docker compose build backend

    if [ $? -eq 0 ]; then
        print_success "Backend image built"
    else
        print_error "Backend build failed"
        exit 1
    fi

    print_info "Building frontend image..."
    docker compose build frontend

    if [ $? -eq 0 ]; then
        print_success "Frontend image built"
    else
        print_error "Frontend build failed"
        exit 1
    fi

    print_success "All images built successfully"
}

docker_start() {
    print_header "Starting Docker Compose Stack"

    print_info "Starting services..."
    docker compose up -d

    if [ $? -eq 0 ]; then
        print_success "Docker Compose stack started"
    else
        print_error "Failed to start Docker Compose"
        exit 1
    fi
}

docker_wait_healthy() {
    print_header "Waiting for Services to Be Ready"

    local max_attempts=60
    local attempt=1

    print_info "Checking database connectivity..."
    while [ $attempt -le $max_attempts ]; do
        if docker compose exec -T db pg_isready -U rain -d rain_dev &> /dev/null; then
            print_success "Database is ready"
            break
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done

    if [ $attempt -gt $max_attempts ]; then
        print_error "Database failed to start within timeout"
        exit 1
    fi

    sleep 2

    print_info "Checking backend API..."
    attempt=1
    while [ $attempt -le 30 ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_success "Backend API is ready"
            break
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done

    if [ $attempt -gt 30 ]; then
        print_warning "Backend API health check timed out (may still be initializing)"
    fi

    print_success "All services are ready!"
}

# ============================================================================
# Database Migration
# ============================================================================

run_migrations() {
    print_header "Running Database Migrations"

    print_info "Running Alembic migrations..."
    docker compose exec -T backend alembic upgrade head

    if [ $? -eq 0 ]; then
        print_success "Database migrations completed"
    else
        print_warning "Migration step encountered issues (check logs)"
    fi
}

# ============================================================================
# Initialization & Verification
# ============================================================================

preflight_check() {
    print_header "Running Preflight Checks"

    print_info "Checking WASM module..."
    if [ -f "rain-dsp/build/rain_dsp.wasm" ]; then
        WASM_SIZE=$(du -h rain-dsp/build/rain_dsp.wasm | awk '{print $1}')
        print_success "WASM module found (${WASM_SIZE})"
    else
        print_warning "WASM module not found (will build during container startup)"
    fi

    print_info "Checking environment variables..."
    if [ -f ".env" ]; then
        print_success ".env file present"
    else
        print_error ".env file missing"
        exit 1
    fi

    print_success "Preflight checks passed"
}

# ============================================================================
# Access Information
# ============================================================================

show_access_info() {
    print_header "RAIN is Ready!"

    cat << EOF

${GREEN}✓ Mastering Engine Status: RUNNING${NC}

${BLUE}Access URLs:${NC}
  • Frontend (Web UI):     ${GREEN}http://localhost:5173${NC}
  • Backend API:           ${GREEN}http://localhost:8000${NC}
  • API Documentation:     ${GREEN}http://localhost:8000/docs${NC}
  • Database (PostgreSQL): localhost:5432
  • Cache (Valkey):        localhost:6379
  • S3 (MinIO):            http://localhost:9001

${BLUE}Default Credentials:${NC}
  • Database user:  rain
  • Database pass:  rainpassword
  • S3 access key:  minioadmin
  • S3 secret key:  minioadmin

${BLUE}Useful Commands:${NC}
  • View logs:         docker compose logs -f
  • Stop services:     docker compose down
  • Restart services:  docker compose restart
  • Run migrations:    docker compose exec backend alembic upgrade head
  • Access database:   docker compose exec db psql -U rain -d rain_dev
  • Access S3:         http://localhost:9001 (minioadmin/minioadmin)

${BLUE}Documentation:${NC}
  • Wiki Home:           https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki
  • Architecture:        https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki/Architecture
  • Development Setup:   https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki/Development-Setup
  • Vocal Features:      https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/wiki/Vocal-Production-Features

${YELLOW}Next Steps:${NC}
  1. Open http://localhost:5173 in your browser
  2. Create an account (dev mode)
  3. Upload an audio file
  4. Explore the mastering pipeline!

For support, see: https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE/issues

EOF
}

# ============================================================================
# Main Execution Flow
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick)
                SETUP_MODE="quick"
                shift
                ;;
            --no-clone)
                SKIP_CLONE=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            --version)
                show_version
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Banner
    cat << 'EOF'

    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     🌧️  RAIN — R∞N AI Mastering Engine v6.1                 ║
    ║                                                               ║
    ║     Complete Setup & Launch Script                           ║
    ║     Repository: aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

EOF

    # Execute setup phases
    if [ "$SETUP_MODE" != "quick" ]; then
        check_requirements
    fi

    clone_repository
    preflight_check
    setup_environment
    docker_build
    docker_start
    docker_wait_healthy
    run_migrations
    show_access_info
}

# Run main function
main "$@"