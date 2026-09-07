param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & $PythonExe -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12+ required'"
    if ($LASTEXITCODE -ne 0) { throw "Python preflight failed" }
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        & $PythonExe -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
    }
    $venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    & $venvPython -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    & $venvPython -m pip install --no-build-isolation -e .
    if ($LASTEXITCODE -ne 0) { throw "Project installation failed" }
    & $venvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
    & $venvPython -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Lint failed" }
    & $venvPython -m ruff format --check .
    if ($LASTEXITCODE -ne 0) { throw "Format check failed" }
    & $venvPython -m mech_design cases/heated_cantilever.toml
    if ($LASTEXITCODE -ne 0) { throw "Demo failed" }
} finally {
    Pop-Location
}
