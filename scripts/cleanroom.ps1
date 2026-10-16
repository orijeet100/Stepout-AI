<#
.SYNOPSIS
  Installs a built Stepout wheel the way a brand-new user would, in a throwaway folder, and walks the first minutes.

.DESCRIPTION
  The tool environment, the command and Stepout's data folder all live under -Root, and API keys are removed from the environment (uv's own
  download cache is shared, and it needs the network: the first run's made-up key is checked with Anthropic's API, which refuses it). It then:
    1. installs the wheel (`uv tool install`)          2. runs `stepout --help`
    3. runs `stepout status` (must report things to fix)   4. types through the first run in a real console (scripts\first_run_console.py)
  scripts\smoke_install.py (what CI runs) covers start, status, a second start and stop; this covers the interactive first run.

.PARAMETER Wheel  A wheel file or URL. Default: the newest dist\*.whl (build one with `uv build --wheel` after `npm run build` in web).
.PARAMETER Root   The throwaway folder, deleted first. Default: %TEMP%\stepout-cleanroom.
.PARAMETER Port   The chat's port. Default 8792 (not the usual 8765, so a Stepout you use is left alone).
.PARAMETER Phone  Also run `stepout remote` against the REAL Tailscale on this computer. That re-points the one Serve handler on HTTPS port 443
                  at this copy for as long as it runs; to give it back afterwards:
                    tailscale serve --bg --https=443 http://127.0.0.1:<the port your own Stepout uses, usually 8765>
                  Press Ctrl+C to end the chat (that ends the script too, so the line above is printed before it starts).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\cleanroom.ps1
#>
param(
    [string]$Wheel = "",
    [string]$Root = (Join-Path $env:TEMP "stepout-cleanroom"),
    [int]$Port = 8792,
    [switch]$Phone
)

$repo = Split-Path -Parent $PSScriptRoot
if (-not $Wheel) {
    $newest = Get-ChildItem (Join-Path $repo "dist\*.whl") -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $newest) { Write-Host "No wheel: build one (npm --prefix web run build, then uv build --wheel) or pass -Wheel." -ForegroundColor Red; exit 2 }
    $Wheel = $newest.FullName
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Write-Host "uv is not installed: winget install astral-sh.uv" -ForegroundColor Red; exit 2 }

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Fail($text) { Write-Host "cleanroom: FAILED: $text" -ForegroundColor Red; exit 1 }

if (Test-Path $Root) { Remove-Item -Recurse -Force $Root }
New-Item -ItemType Directory -Force $Root | Out-Null
$env:UV_TOOL_DIR = Join-Path $Root "tools"
$env:UV_TOOL_BIN_DIR = Join-Path $Root "bin"
$env:STEPOUT_HOME = Join-Path $Root "home"
$env:STEPOUT_PORT = "$Port"
$env:PATH = "$($env:UV_TOOL_BIN_DIR);$($env:PATH)"
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue

Step "1. install, the way the README says"
uv tool install --python 3.12 $Wheel
if ($LASTEXITCODE -ne 0) { Fail "uv tool install" }

Step "2. stepout --help"
$help = stepout --help | Out-String
Write-Host $help
if ($help -notmatch "stepout remote") { Fail "--help does not list the commands" }

Step "3. stepout status on a machine that is not set up"
stepout status
if ($LASTEXITCODE -ne 1) { Fail "status should exit 1 (nothing is set up yet), it exited $LASTEXITCODE" }

Step "4. the first run, typed through a real console"
uv run --no-project --with pywinpty python (Join-Path $PSScriptRoot "first_run_console.py") $Root $Port
if ($LASTEXITCODE -ne 0) { Fail "the first run" }

if ($Phone) {
    Step "5. stepout remote, with the real Tailscale (Ctrl+C ends it)"
    # Said before, not after: Ctrl+C also ends this script, so nothing printed later would be seen.
    Write-Host "While this runs the phone link points at THIS copy. To give it back to your own Stepout afterwards:" -ForegroundColor Yellow
    Write-Host "  tailscale serve --bg --https=443 http://127.0.0.1:8765" -ForegroundColor Yellow
    $env:ANTHROPIC_API_KEY = "sk-ant-made-up-key-not-real"  # the first run skipped the key; a made-up one keeps `stepout remote` from asking
    stepout remote
}

Write-Host "`ncleanroom: ok. Everything is under $Root ; remove it with:  Remove-Item -Recurse -Force '$Root'" -ForegroundColor Green
