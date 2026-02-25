param(
    [string]$SourceDir = "",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" }
function Write-Ok($msg)   { Write-Host "[OK]   $msg" }
function Write-Err($msg)  { Write-Host "[ERR]  $msg" }

try {
    if (-not $SourceDir) {
        $root = Split-Path -Parent $PSScriptRoot
        $SourceDir = Join-Path $root "dist\\__main__.dist"
    }

    if (-not (Test-Path $SourceDir)) {
        Write-Err "Build folder not found: $SourceDir"
        Write-Host "Build with: python -m nuitka --standalone --follow-imports --output-dir=dist django_manager\\__main__.py"
        exit 1
    }

    if (-not $InstallDir) {
        $InstallDir = Join-Path $env:LOCALAPPDATA "DjangoManager"
    }

    Write-Info "Installing from: $SourceDir"
    Write-Info "Installing to:   $InstallDir"

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    }

    Copy-Item -Path (Join-Path $SourceDir "*") -Destination $InstallDir -Recurse -Force

    $exe = Join-Path $InstallDir "__main__.exe"
    $targetExe = Join-Path $InstallDir "django-manager.exe"
    if (Test-Path $exe) {
        Move-Item -Force $exe $targetExe
    } elseif (-not (Test-Path $targetExe)) {
        Write-Err "Executable not found in install directory."
        exit 1
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -and $userPath.Split(";") -contains $InstallDir) {
        Write-Info "PATH already contains install dir."
    } else {
        $newPath = if ($userPath) { "$userPath;$InstallDir" } else { $InstallDir }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Ok "Added install directory to user PATH."
        Write-Info "Restart your terminal to use: django-manager"
    }

    Write-Ok "Install complete."
    Write-Host "Run: django-manager"
    exit 0
}
catch {
    Write-Err $_.Exception.Message
    exit 1
}
