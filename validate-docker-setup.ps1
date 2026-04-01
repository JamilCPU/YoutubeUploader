# PowerShell script to validate Docker setup for YouTube Uploader
# This script checks prerequisites and configuration before building/running the container

Write-Host "Validating Docker Setup for YouTube Uploader..." -ForegroundColor Cyan
Write-Host ""

$errors = @()
$warnings = @()

# Check if Docker is installed and running
Write-Host "Checking Docker installation..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Docker is installed: $dockerVersion" -ForegroundColor Green
    } else {
        $errors += "Docker is not installed or not in PATH"
    }
}
catch {
    $errors += "Docker is not installed or not accessible"
}

# Check if Docker is running
Write-Host "Checking if Docker is running..." -ForegroundColor Yellow
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Docker daemon is running" -ForegroundColor Green
    } else {
        $errors += "Docker daemon is not running"
    }
}
catch {
    $errors += "Cannot connect to Docker daemon"
}

# Check Windows containers
Write-Host "Checking Windows container support..." -ForegroundColor Yellow
try {
    $info = docker info 2>&1 | Select-String "OSType"
    if ($info -match "windows") {
        Write-Host "  [OK] Windows containers are available" -ForegroundColor Green
    } else {
        $warnings += "Windows containers may not be enabled. Switch to Windows containers in Docker Desktop."
    }
}
catch {
    $warnings += "Could not verify Windows container support"
}

# Check environment variables
Write-Host "Checking environment variables..." -ForegroundColor Yellow
$requiredVars = @("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_PROJECT_ID")
foreach ($var in $requiredVars) {
    $value = [Environment]::GetEnvironmentVariable($var, "Process")
    if ([string]::IsNullOrEmpty($value)) {
        $value = [Environment]::GetEnvironmentVariable($var, "User")
    }
    if ([string]::IsNullOrEmpty($value)) {
        $value = [Environment]::GetEnvironmentVariable($var, "Machine")
    }
    
    if ([string]::IsNullOrEmpty($value)) {
        $errors += "Environment variable $var is not set"
        Write-Host "  [FAIL] $var is not set" -ForegroundColor Red
    } else {
        if ($value.Length -gt 8) {
            $masked = $value.Substring(0, 8) + "..."
        } else {
            $masked = "***"
        }
        Write-Host "  [OK] $var is set ($masked)" -ForegroundColor Green
    }
}

# Check required files
Write-Host "Checking required files..." -ForegroundColor Yellow
$requiredFiles = @("Dockerfile", "docker-compose.yml", "requirements.txt", "main.py")
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  [OK] $file exists" -ForegroundColor Green
    } else {
        $errors += "Required file $file is missing"
        Write-Host "  [FAIL] $file is missing" -ForegroundColor Red
    }
}

# Check data directory
Write-Host "Checking data directory..." -ForegroundColor Yellow
if (Test-Path "data") {
    Write-Host "  [OK] data directory exists" -ForegroundColor Green
} else {
    Write-Host "  [WARN] data directory does not exist (will be created)" -ForegroundColor Yellow
    $warnings += "data directory does not exist. It will be created when you run docker-compose."
}

# Check watched directory (from docker-compose.yml)
Write-Host "Checking watched directory configuration..." -ForegroundColor Yellow
if (Test-Path "docker-compose.yml") {
    $composeContent = Get-Content "docker-compose.yml" -Raw
    if ($composeContent -match "source:\s*(.+)") {
        $watchDir = $matches[1].Trim()
        if (Test-Path $watchDir) {
            Write-Host "  [OK] Watched directory exists: $watchDir" -ForegroundColor Green
        } else {
            $warnings += "Watched directory in docker-compose.yml does not exist: $watchDir"
            Write-Host "  [WARN] Watched directory does not exist: $watchDir" -ForegroundColor Yellow
        }
    }
}

# Summary
Write-Host ""
Write-Host "Validation Summary:" -ForegroundColor Cyan
if ($errors.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host "  [OK] All checks passed! You're ready to build and run the container." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Create data directory: mkdir data" -ForegroundColor White
    Write-Host "  2. Build and run: docker-compose up --build" -ForegroundColor White
    exit 0
} else {
    if ($errors.Count -gt 0) {
        Write-Host "  Errors found:" -ForegroundColor Red
        foreach ($error in $errors) {
            Write-Host "    - $error" -ForegroundColor Red
        }
    }
    if ($warnings.Count -gt 0) {
        Write-Host "  Warnings:" -ForegroundColor Yellow
        foreach ($warning in $warnings) {
            Write-Host "    - $warning" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    Write-Host "Please fix the errors before building the container." -ForegroundColor Red
    exit 1
}
