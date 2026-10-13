$ErrorActionPreference = "Continue"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

Set-Location $PSScriptRoot

$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line.Split("=", 2)
        if ($key -and -not [Environment]::GetEnvironmentVariable($key)) {
            [Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), "Process")
        }
    }
}

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$pythonExe = $env:PYTHON_EXE
if (-not $pythonExe) {
    $pythonExe = "python"
}
$appHost = $env:APP_HOST
if (-not $appHost) {
    $appHost = "127.0.0.1"
}
$appPort = $env:APP_PORT
if (-not $appPort) {
    $appPort = "9000"
}
$logFile = Join-Path $logDir "backend.combined.log"

& $pythonExe -m uvicorn src.api.main:app --host $appHost --port $appPort *>> $logFile
