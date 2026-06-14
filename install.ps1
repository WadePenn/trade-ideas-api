# Trade Ideas Panel - One-Click Installer
# https://github.com/WadePenn/trade-ideas-api
# Run via: powershell -ExecutionPolicy Bypass -File install.ps1

$REPO = "https://github.com/WadePenn/trade-ideas-api.git"
$DIR  = "$env:USERPROFILE\trade-ideas-api"

Write-Host ""
Write-Host "+------------------------------------------+" -ForegroundColor Cyan
Write-Host "|  Trade Ideas Panel  -  One-Click Setup   |" -ForegroundColor Cyan
Write-Host "|  github.com/WadePenn/trade-ideas-api     |" -ForegroundColor Cyan
Write-Host "+------------------------------------------+" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python 3.11 ────────────────────────────────────────────────────────────
Write-Host "[1/5] Checking Python 3.11..." -ForegroundColor Yellow
$pyBin = $null
try {
    $v = & py -3.11 -c "import sys;print(sys.version_info.minor)" 2>$null
    if ($v -match "11") { $pyBin = (& py -3.11 -c "import sys;print(sys.executable)").Trim() }
} catch {}
if (-not $pyBin) {
    Write-Host "      Installing Python 3.11 via winget..." -ForegroundColor Yellow
    winget install --id Python.Python.3.11 -e --silent --accept-source-agreements --accept-package-agreements | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $pyBin = (& py -3.11 -c "import sys;print(sys.executable)").Trim()
}
Write-Host "      OK  Python 3.11 ready" -ForegroundColor Green

# ── 2. Git ────────────────────────────────────────────────────────────────────
Write-Host "[2/5] Checking Git..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "      Installing Git via winget..." -ForegroundColor Yellow
    winget install --id Git.Git -e --silent --accept-source-agreements --accept-package-agreements | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Write-Host "      OK  Git ready" -ForegroundColor Green

# ── 3. Clone / update repo ────────────────────────────────────────────────────
Write-Host "[3/5] Getting repository..." -ForegroundColor Yellow
if (Test-Path "$DIR\.git") {
    Write-Host "      Pulling latest changes..." -ForegroundColor Yellow
    git -C $DIR pull | Out-Null
} else {
    Write-Host "      Cloning to $DIR ..." -ForegroundColor Yellow
    git clone $REPO $DIR | Out-Null
}
Write-Host "      OK  Repository ready at $DIR" -ForegroundColor Green

# ── 4. Virtual environment + packages ─────────────────────────────────────────
Write-Host "[4/5] Installing Python packages (1-2 min)..." -ForegroundColor Yellow
if (-not (Test-Path "$DIR\venv\Scripts\python.exe")) {
    & $pyBin -m venv "$DIR\venv"
}
& "$DIR\venv\Scripts\python.exe" -m pip install --upgrade pip -q
& "$DIR\venv\Scripts\pip.exe" install -r "$DIR\requirements.txt" -q
Write-Host "      OK  All packages installed" -ForegroundColor Green

# ── 5. Desktop shortcut ───────────────────────────────────────────────────────
Write-Host "[5/5] Creating Desktop shortcut..." -ForegroundColor Yellow
$sh  = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut("$env:USERPROFILE\Desktop\Trade Ideas Panel.lnk")
$lnk.TargetPath       = "$DIR\StartTradeIdeas.bat"
$lnk.WorkingDirectory = $DIR
$lnk.IconLocation     = "C:\Windows\System32\imageres.dll,3"
$lnk.Description      = "Launch Trade Ideas API + Panel"
$lnk.Save()
Write-Host "      OK  Desktop shortcut created" -ForegroundColor Green

Write-Host ""
Write-Host "+------------------------------------------+" -ForegroundColor Green
Write-Host "|  Installation complete!                  |" -ForegroundColor Green
Write-Host "|  Double-click 'Trade Ideas Panel'        |" -ForegroundColor Green
Write-Host "|  on your Desktop to launch.              |" -ForegroundColor Green
Write-Host "+------------------------------------------+" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
