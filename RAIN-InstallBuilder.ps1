<#
.SYNOPSIS
RAIN Hardware-Aware Installer & Builder (Production-Grade)
Detects local machine specs and configures frontend for cloud backend routing

.DESCRIPTION
Enterprise-grade one-click installer for RAIN mastering engine on everyday machines.
- Robust hardware detection (WMI + registry fallback for GPU VRAM)
- Auto-installs Node.js 20 LTS if needed
- Hardware-aware feature gating
- Generates optimized frontend .env
- Builds and launches with full error handling

.PARAMETER CloudBackendUrl
Backend API URL (default: https://api.rain.arcovel.com)

.PARAMETER InstallNodeIfMissing
Auto-install Node.js 20 LTS if not found (default: $true)

.PARAMETER DevMode
Launch in hot-reload dev mode instead of production build

.EXAMPLE
.\RAIN-InstallBuilder.ps1
.\RAIN-InstallBuilder.ps1 -CloudBackendUrl "http://localhost:8000"
.\RAIN-InstallBuilder.ps1 -DevMode
#>

param(
    [string]$CloudBackendUrl = "https://api.rain.arcovel.com",
    [bool]$InstallNodeIfMissing = $true,
    [switch]$DevMode
)

# ============================================================================
# Global State & Configuration
# ============================================================================

$script:ExitCode = 0
$script:HardwareInfo = @{}

# More permissive error handling — we'll handle errors explicitly
$ErrorActionPreference = "Continue"

# Colors
$Colors = @{
    Success = "Green"
    Error   = "Red"
    Warning = "Yellow"
    Info    = "Cyan"
    Header  = "Blue"
}

# ============================================================================
# Logging Functions (Fixed Border Construction)
# ============================================================================

function Write-Title {
    param([string]$Text)
    Write-Host ""
    $border = "╔" + ("═" * 70) + "╗"
    $content = "║ " + $Text.PadRight(68) + " ║"
    $footer = "╚" + ("═" * 70) + "╝"
    
    Write-Host $border -ForegroundColor $Colors.Header
    Write-Host $content -ForegroundColor $Colors.Header
    Write-Host $footer -ForegroundColor $Colors.Header
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "→ $Text" -ForegroundColor $Colors.Info
}

function Write-OK {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor $Colors.Success
}

function Write-Warn {
    param([string]$Text)
    Write-Host "⚠ $Text" -ForegroundColor $Colors.Warning
}

function Write-Fail {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor $Colors.Error
}

function Write-Section {
    param([string]$Text)
    Write-Host ""
    Write-Host "► $Text" -ForegroundColor $Colors.Header
    Write-Host ("─" * ($Text.Length + 2)) -ForegroundColor $Colors.Header
}

# ============================================================================
# Exit Handler (Consistent Exit Path)
# ============================================================================

function Exit-Script {
    param(
        [int]$Code = 0,
        [string]$Message = ""
    )
    
    if ($Message) {
        if ($Code -eq 0) {
            Write-OK $Message
        } else {
            Write-Fail $Message
        }
    }
    
    exit $Code
}

# ============================================================================
# Step 1: Hardware Detection (Fixed WMI + Registry Fallback)
# ============================================================================

function Get-GPUMemory {
    param([object]$GPU)
    
    # First try: WMI AdapterRAM
    $vramBytes = $GPU.AdapterRAM
    
    # Handle 32-bit overflow or zero values
    if ($vramBytes -eq 0 -or $vramBytes -eq [uint32]::MaxValue) {
        Write-Step "WMI AdapterRAM unreliable; querying registry..."
        
        # Fallback 1: Registry (DirectX driver info)
        try {
            $regPaths = @(
                "HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}",
                "HKLM:\SYSTEM\ControlSet002\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            ) | Where-Object { Test-Path $_ }
            
            foreach ($regPath in $regPaths) {
                Get-ChildItem $regPath -ErrorAction SilentlyContinue | ForEach-Object {
                    $props = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
                    if ($props.HardwareInformation) {
                        # NVIDIA stores as binary; extract if possible
                        $vramBytes = [BitConverter]::ToInt64($props.HardwareInformation.psobject.properties['VRAM'].Value, 0) 2>$null
                        if ($vramBytes -gt 0) {
                            return $vramBytes
                        }
                    }
                }
            }
        } catch {
            # Silent — use hardcoded fallback below
        }
        
        # Fallback 2: Hardcoded GPU table
        $gpu.Name -match "GeForce GTX 960M" | Out-Null
        if ($?) {
            $vramBytes = 2GB
        }
        
        if ($vramBytes -le 0) {
            Write-Warn "Could not determine GPU VRAM; assuming integrated graphics"
            $vramBytes = 0
        }
    }
    
    return $vramBytes
}

function Detect-Hardware {
    Write-Title "🔍 Detecting Hardware"
    
    # CPU (with error handling)
    $cpu = Get-WmiObject -Class Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cpu) {
        $cpuName = $cpu.Name
        $cpuCores = $cpu.NumberOfCores
        $cpuThreads = $cpu.ThreadCount
        Write-Step "CPU: $cpuName ($cpuCores cores / $cpuThreads threads)"
    } else {
        Write-Warn "Could not detect CPU"
        $cpuName = "Unknown"
        $cpuCores = 4
        $cpuThreads = 8
    }

    # RAM
    $ram = Get-WmiObject -Class Win32_ComputerSystem -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ram) {
        $ramGB = [math]::Round($ram.TotalPhysicalMemory / 1GB, 1)
        Write-Step "RAM: ${ramGB}GB"
    } else {
        Write-Warn "Could not detect RAM"
        $ramGB = 8
    }

    # GPU & VRAM (with robust fallback)
    $gpu = Get-WmiObject -Class Win32_VideoController -ErrorAction SilentlyContinue | Select-Object -First 1
    
    if ($gpu) {
        $gpuName = $gpu.Name
        $vramBytes = Get-GPUMemory -GPU $gpu
        
        if ($vramBytes -gt 0) {
            $vramGB = [math]::Round($vramBytes / 1GB, 2)
            Write-OK "GPU: $gpuName (${vramGB}GB VRAM)"
            $hasGPU = $true
        } else {
            Write-Warn "GPU: Integrated graphics or not detected"
            $hasGPU = $false
            $vramGB = 0
        }
    } else {
        Write-Warn "Could not detect GPU"
        $hasGPU = $false
        $vramGB = 0
        $gpuName = "Not detected"
    }

    # OS
    $os = (Get-WmiObject -Class Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
    if (-not $os) { $os = "Unknown" }
    Write-Step "OS: $os"

    # Disk
    $disk = Get-PSDrive -Name C -ErrorAction SilentlyContinue
    if ($disk) {
        $diskFreeGB = [math]::Round($disk.Free / 1GB, 1)
        Write-Step "Disk free: ${diskFreeGB}GB"
    } else {
        Write-Warn "Could not determine disk space"
        $diskFreeGB = 0
    }

    # Classify tier
    $tier = Classify-Hardware -RAM $ramGB -GPU $hasGPU -VRAM $vramGB -Cores $cpuCores
    Write-OK "Hardware Tier: $tier"

    $script:HardwareInfo = @{
        CPU       = $cpuName
        Cores     = $cpuCores
        RAM       = $ramGB
        GPU       = $gpuName
        HasGPU    = $hasGPU
        VRAM      = $vramGB
        OS        = $os
        DiskFree  = $diskFreeGB
        Tier      = $tier
    }
    
    return $script:HardwareInfo
}

function Classify-Hardware {
    param(
        [double]$RAM,
        [bool]$GPU,
        [double]$VRAM,
        [int]$Cores
    )

    # Conservative classification
    if ($RAM -lt 8) {
        return "CONSTRAINED"
    } elseif ($GPU -and $VRAM -ge 6) {
        return "GPU_CAPABLE"
    } elseif ($GPU -and $VRAM -ge 2) {
        return "GPU_LOW_VRAM"
    } else {
        return "CPU_ONLY"
    }
}

# ============================================================================
# Step 2: Check Node.js (with Explicit PATH Search)
# ============================================================================

function Check-NodeJS {
    Write-Title "📦 Checking Node.js"

    $nodePath = $null
    
    # Try command resolution first
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCmd) {
        $nodePath = $nodeCmd.Source
    } else {
        # Fallback: check common install paths
        $commonPaths = @(
            "C:\Program Files\nodejs\node.exe",
            "C:\Program Files (x86)\nodejs\node.exe",
            "$env:LOCALAPPDATA\nvm\v20.11.1\node.exe"
        )
        
        foreach ($path in $commonPaths) {
            if (Test-Path $path) {
                $nodePath = $path
                break
            }
        }
    }
    
    if ($nodePath) {
        $version = & $nodePath --version 2>&1
        Write-OK "Node.js found: $version ($nodePath)"
        
        # Ensure this path is in current process PATH for future child processes
        $env:Path = "$(Split-Path $nodePath)" + ";" + $env:Path
        
        return $true
    } else {
        Write-Warn "Node.js not found in PATH or common install locations"
        return $false
    }
}

function Install-NodeJS {
    Write-Title "📥 Installing Node.js 20 LTS"

    Write-Step "Downloading Node.js v20.11.1 installer..."
    $nodeInstallerURL = "https://nodejs.org/dist/v20.11.1/node-v20.11.1-x64.msi"
    $installerPath = "$env:TEMP\nodejs-installer.msi"

    try {
        # Ensure TLS 1.2 for older PowerShell versions
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $progressPreference = 'SilentlyContinue'
        
        Invoke-WebRequest -Uri $nodeInstallerURL -OutFile $installerPath -ErrorAction Stop
        Write-OK "Downloaded to $installerPath"

        Write-Step "Running installer (this may take 2-3 minutes)..."
        $installResult = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$installerPath`" /passive" -Wait -PassThru
        
        if ($installResult.ExitCode -ne 0) {
            Write-Fail "Installer exited with code $($installResult.ExitCode)"
            return $false
        }

        Write-OK "Node.js installed"
        
        # Refresh PATH from system environment
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        
        # Retry loop to find node binary
        $maxRetries = 5
        $retry = 0
        
        while ($retry -lt $maxRetries) {
            $nodeExe = Get-ChildItem "C:\Program Files\nodejs\node.exe" -ErrorAction SilentlyContinue
            if ($nodeExe) {
                $version = & $nodeExe.FullName --version 2>&1
                Write-OK "Verified: $version"
                
                # Ensure in PATH for this process
                $env:Path = "C:\Program Files\nodejs" + ";" + $env:Path
                
                return $true
            }
            
            Start-Sleep -Milliseconds 500
            $retry++
        }
        
        Write-Fail "Could not verify Node.js installation after $maxRetries attempts"
        return $false
    } catch {
        Write-Fail "Failed to install Node.js: $_"
        return $false
    }
}

# ============================================================================
# Step 3: Generate .env for Frontend (Fixed Feature Gating)
# ============================================================================

function Generate-Frontend-Env {
    param(
        [string]$BackendUrl,
        [hashtable]$Hardware
    )

    Write-Title "⚙️  Generating Frontend Configuration"

    # Determine feature flags based on hardware tier
    $canUseGPU = $Hardware.Tier -in @("GPU_CAPABLE", "GPU_LOW_VRAM")
    $stemSeparationEnabled = $Hardware.Tier -eq "GPU_CAPABLE"
    
    # Hardware-specific optimizations
    $pitchCorrectionEnabled = $Hardware.RAM -ge 8 # CREPE needs memory
    $instrumentSynthesisEnabled = $canUseGPU # Cloud-side only
    
    $envPath = "frontend\.env.local"
    $envContent = @"
# RAIN Frontend Environment
# Auto-generated by RAIN-InstallBuilder.ps1
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

# Backend API URL
VITE_API_URL=$BackendUrl
VITE_API_TIMEOUT=30000

# Hardware tier for optimization hints
VITE_HARDWARE_TIER=$($Hardware.Tier)
VITE_HARDWARE_GPU=$($Hardware.HasGPU.ToString().ToLower())
VITE_HARDWARE_VRAM=$($Hardware.VRAM)
VITE_HARDWARE_RAM=$($Hardware.RAM)
VITE_HARDWARE_CORES=$($Hardware.Cores)

# Feature flags (derived from hardware capabilities)
VITE_FEATURE_PITCH_CORRECTION=$($pitchCorrectionEnabled.ToString().ToLower())
VITE_FEATURE_INSTRUMENT_SYNTHESIS=$($instrumentSynthesisEnabled.ToString().ToLower())
VITE_FEATURE_STEM_SEPARATION=$($stemSeparationEnabled.ToString().ToLower())

# Optimization hints
VITE_WASM_ENABLE_SIMD=$($canUseGPU.ToString().ToLower())
VITE_ONNX_EXECUTION_MODE=$(if ($canUseGPU) { "webgpu" } else { "wasm" })

# Analytics (optional)
VITE_POSTHOG_DISABLED=false

# Development
VITE_LOG_LEVEL=info
"@

    if (-not (Test-Path "frontend")) {
        Write-Fail "frontend/ directory not found. Make sure you're in the RAIN repo root."
        return $false
    }

    try {
        Set-Content -Path $envPath -Value $envContent -Encoding UTF8 -ErrorAction Stop
        Write-OK "Created $envPath"

        Write-Step "Backend: $BackendUrl"
        Write-Step "Hardware Tier: $($Hardware.Tier)"
        Write-Step "Features Enabled:"
        Write-Step "  • Pitch Correction: $(if ($pitchCorrectionEnabled) { '✓' } else { '✗' })"
        Write-Step "  • Instrument Synthesis: $(if ($instrumentSynthesisEnabled) { '✓' } else { '✗' })"
        Write-Step "  • Stem Separation: $(if ($stemSeparationEnabled) { '✓' } else { '✗' })"
        
        return $true
    } catch {
        Write-Fail "Failed to generate .env: $_"
        return $false
    }
}

# ============================================================================
# Step 4: Install Dependencies (Fixed Location Management)
# ============================================================================

function Install-Dependencies {
    Write-Title "📚 Installing Frontend Dependencies"

    Write-Step "Running: npm install (this takes 2-3 minutes first time)"

    Push-Location frontend -ErrorAction Stop
    try {
        $npmResult = & npm install --legacy-peer-deps 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "npm install exited with code $LASTEXITCODE"
            Write-Step "Output: $npmResult"
            return $false
        }
        
        Write-OK "Dependencies installed"
        return $true
    } catch {
        Write-Fail "npm install failed: $_"
        return $false
    } finally {
        Pop-Location
    }
}

# ============================================================================
# Step 5: Build Frontend (Fixed Location Management)
# ============================================================================

function Build-Frontend {
    Write-Title "🔨 Building Frontend"

    Push-Location frontend -ErrorAction Stop
    try {
        $buildResult = & npm run build 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Build exited with code $LASTEXITCODE"
            Write-Step "Output: $buildResult"
            return $false
        }
        
        Write-OK "Frontend built successfully"
        
        # Verify dist directory exists
        if (Test-Path "dist") {
            $distSize = (Get-ChildItem dist -Recurse | Measure-Object -Property Length -Sum).Sum
            $distSizeMB = [math]::Round($distSize / 1MB, 2)
            Write-Step "Output size: ${distSizeMB}MB"
        }
        
        return $true
    } catch {
        Write-Fail "Build failed: $_"
        return $false
    } finally {
        Pop-Location
    }
}

# ============================================================================
# Step 6: Launch
# ============================================================================

function Launch-Dev {
    Write-Title "🚀 Launching Dev Server (Hot Reload)"

    Write-Step "Starting Vite dev server on http://localhost:5173"
    Write-Warn "Press Ctrl+C to stop"
    Write-Host ""

    Push-Location frontend -ErrorAction Stop
    try {
        & npm run dev
    } catch {
        Write-Fail "Failed to launch dev server: $_"
        return $false
    } finally {
        Pop-Location
    }
}

function Launch-Production {
    Write-Title "🌐 Frontend Ready"

    Write-OK "Frontend build complete at ./frontend/dist"
    Write-Host ""
    Write-Step "To serve the production build, run:"
    Write-Host "  npx http-server frontend/dist -p 5173 -c-1" -ForegroundColor Yellow
    Write-Host ""
    Write-Step "Then open: http://localhost:5173" -ForegroundColor Green
}

# ============================================================================
# Step 7: Success Banner
# ============================================================================

function Show-Success-Banner {
    Write-Host ""
    $banner = "╔" + ("═" * 70) + "╗"
    $line1 = "║" + "✓ Setup Complete!".PadRight(70) + "║"
    $footer = "╚" + ("═" * 70) + "╝"
    
    Write-Host $banner -ForegroundColor Green
    Write-Host $line1 -ForegroundColor Green
    Write-Host $footer -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Backend: $CloudBackendUrl" -ForegroundColor Cyan
    Write-Host "Hardware Tier: $($script:HardwareInfo.Tier)" -ForegroundColor Cyan
    Write-Host "RAM: $($script:HardwareInfo.RAM)GB | GPU: $($script:HardwareInfo.HasGPU) | VRAM: $($script:HardwareInfo.VRAM)GB" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================================
# Main Execution (Fixed Error Path)
# ============================================================================

function Main {
    Write-Host ""
    $banner = "╔" + ("═" * 70) + "╗"
    $title1 = "║" + "🌧️  RAIN — Hardware-Aware Installer & Builder".PadRight(70) + "║"
    $title2 = "║" + "v1.0 (Production-Grade)".PadRight(70) + "║"
    $footer = "╚" + ("═" * 70) + "╝"
    
    Write-Host $banner -ForegroundColor Blue
    Write-Host $title1 -ForegroundColor Blue
    Write-Host $title2 -ForegroundColor Blue
    Write-Host $footer -ForegroundColor Blue
    Write-Host ""

    # 1. Detect Hardware
    Detect-Hardware | Out-Null

    # 2. Check/Install Node.js
    $hasNode = Check-NodeJS
    if (-not $hasNode) {
        if ($InstallNodeIfMissing) {
            $installed = Install-NodeJS
            if (-not $installed) {
                Exit-Script -Code 1 -Message "Cannot continue without Node.js"
            }
        } else {
            Exit-Script -Code 1 -Message "Node.js required. Install from https://nodejs.org/"
        }
    }

    # 3. Generate .env (with proper exit handling)
    $envOK = Generate-Frontend-Env -BackendUrl $CloudBackendUrl -Hardware $script:HardwareInfo
    if (-not $envOK) {
        Exit-Script -Code 1 -Message "Cannot continue without .env configuration"
    }

    # 4. Install dependencies
    $depsOK = Install-Dependencies
    if (-not $depsOK) {
        Exit-Script -Code 1 -Message "Cannot continue without dependencies"
    }

    # 5. Build or Dev (consistent exit handling)
    Write-Title "🎯 Next Steps"

    if ($DevMode) {
        Write-Step "Launching in DEV mode (hot reload enabled)"
        Launch-Dev
        Exit-Script -Code 0
    } else {
        Write-Step "Building for production..."
        $buildOK = Build-Frontend
        
        if (-not $buildOK) {
            Exit-Script -Code 1 -Message "Build failed — check output above"
        }
        
        Show-Success-Banner
        Launch-Production
        Exit-Script -Code 0 -Message "Ready to go!"
    }
}

Main
