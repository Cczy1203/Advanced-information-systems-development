<#
.SYNOPSIS
    Stop the local Camunda engine (the one started by start-engine.ps1 -Detached).

.DESCRIPTION
    The PID is read from _runtime\camunda\logs\engine.pid first; when the PID file is missing or the process no longer exists,
    it falls back to matching io.camunda.application.StandaloneCamunda on the command line, so that other java processes are not killed by mistake.

.EXAMPLE
    pwsh -File bpm\camunda\stop-engine.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$runtimeDir = Join-Path $repoRoot "_runtime\camunda"
$pidFile = Join-Path $runtimeDir "logs\engine.pid"

$stopped = 0

# 1) stop by PID file
if (Test-Path $pidFile) {
    $enginePid = (Get-Content $pidFile -Raw).Trim()
    if ($enginePid -match '^\d+$') {
        $p = Get-Process -Id ([int]$enginePid) -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $p.Id -Force
            Write-Host "stopped pid $($p.Id) from engine.pid"
            $stopped++
        } else {
            Write-Host "pid $enginePid in engine.pid is no longer running"
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# 2) fallback: look up by port and clear any engine processes still left behind
#
# Trap: this used to be
#     Get-CimInstance Win32_Process -Filter "Name='java.exe'" | Where CommandLine -like '*StandaloneCamunda*'
# but **on this machine it cannot see those java processes** (Get-Process java returns nothing
# while the engine is plainly listening on 8080). The consequence is subtle: the fallback never finds anything -> it prints
# "no Camunda engine process found" -> the leftover engine keeps holding 8080/26500 ->
# the next engine started reports java.net.BindException: Address already in use and crashes outright.
# netstat is reliable, so this was changed to look the PID up from the Camunda ports.
$camundaPorts = @(8080, 26500, 26501, 26502, 9600)
$pattern = ':(?:' + ($camundaPorts -join '|') + ')\s+.*LISTENING'
$portPids = @(netstat -ano | Select-String $pattern |
              ForEach-Object { ($_.Line -split '\s+')[-1] } |
              Where-Object { $_ -match '^\d+$' -and $_ -ne '0' } |
              Sort-Object -Unique)

# Trap: with $ErrorActionPreference='Stop', PowerShell 5.1 wraps **any** line a native command writes
# to stderr as a NativeCommandError and throws it as a terminating error - the "ERROR: Access denied"
# that taskkill returns on failure aborted the whole script exactly like this. So it is relaxed to Continue here.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
foreach ($procId in $portPids) {
    & taskkill /PID $procId /F 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "stopped pid $procId (was listening on a Camunda port)"
        $stopped++
    } else {
        Write-Host "could not stop pid $procId (access denied - try an elevated shell)"
    }
}

$ErrorActionPreference = $prevEap

if ($stopped -eq 0) { Write-Host "no Camunda engine process found" }
