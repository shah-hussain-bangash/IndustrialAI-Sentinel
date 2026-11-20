$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    Write-Host 'Creating the project Python environment...'
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 or create .venv manually.' }
}
& '.venv/Scripts/python.exe' -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 24 LTS, then run: npm install -g pnpm@11.25.0 . Re-run this script after installation.'
}
pnpm install --frozen-lockfile
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
pnpm build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Host 'Open http://127.0.0.1:8127 in your browser. Press Ctrl+C to stop.'
& '.venv/Scripts/python.exe' scripts/run.py
