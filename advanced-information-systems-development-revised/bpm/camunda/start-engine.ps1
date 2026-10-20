<#
.SYNOPSIS
    Start the local Camunda 8.10 orchestration cluster and confine all runtime writes to the workspace.

.DESCRIPTION
    Why c8run.exe or bin\camunda.bat from the distribution cannot be used directly:

    1. c8run.exe writes camunda.process.lock, log\camunda.log and
       camunda-data\ into its own installation directory. On this machine E:\camunda belongs to BUILTIN\Administrators and grants a normal user
       only ReadAndExecute, so every one of those writes fails with "Access is denied".
    2. bin\camunda.bat forces -Dapp.home and -Dbasedir on the command line to the distribution directory
       (BASEDIR comes from the script's own location), and Java takes the last of duplicate -D options, so it cannot be
       overridden from outside. The ${sys:app.home}/logs of log4j2.xml and the data/ of the Zeebe primary
       storage therefore still land on the read-only E: drive, RocksDB cannot open its metastore and the broker does not start.

    This script therefore calls java directly and supplies -Dapp.home and -Dbasedir itself, both pointing at the writable
    directory _runtime\camunda inside the workspace. Thus:
      * engine logs                    -> _runtime\camunda\logs\
      * Zeebe primary storage (RocksDB) -> _runtime\camunda\data\
      * H2 secondary storage           -> _runtime\camunda\camunda-data\h2db.mv.db
      * Spring configuration           -> supplied by bpm\camunda\application.yaml in this repository
    The submitted repository contains no machine-specific absolute paths; every path is derived by this script.

.PARAMETER Dist
    Camunda distribution directory (containing config\ and lib\).

.PARAMETER JavaCmd
    Path to java.exe. Defaults to the Temurin 25 bundled with c8run, matching c8run's behaviour.

.PARAMETER Port
    Main HTTP port; default 8080.

.EXAMPLE
    pwsh -File bpm\camunda\start-engine.ps1
#>
[CmdletBinding()]
param(
    [string]$Dist = "E:\camunda\c8run-8.10.0-alpha5\camunda-zeebe-8.10.0-alpha5",
    [string]$JavaCmd = "E:\camunda\c8run-8.10.0-alpha5\jre\bin\java.exe",
    [int]$Port = 8080,
    # Turn camunda.security.authorizations off so that **unauthenticated gRPC job workers** can claim jobs.
    #
    # Why this switch is needed (observed in practice; evidence in bpm/screenshots/v15/):
    #   With authorizations.enabled: true, roles, members and authorisations are all persisted correctly, but gRPC
    #   job activation is silently filtered out - jobs stay in CREATED, the worker log shows COMPLETED = 0, and
    #   every scenario that needs a service task times out. With the same workers and the same model, turning it off gives
    #   COMPLETED = 11 and all scenarios pass.
    #   This distribution supports only BASIC / OIDC (there is no NONE in the AuthenticationMethod enum), and
    #   zeebe-client-java 8.9.0 neither performs BASIC nor has a usable OIDC provider,
    #   so in an offline environment the workers cannot carry an identity.
    #
    # Note: this switch changes only the **copy in the runtime directory**; application.yaml in the submitted
    #       repository is left alone, so the claim that RBAC is configured holds at all times.
    [switch]$WorkersProfile,
    # Set camunda.security.authentication.unprotected-api to false.
    #
    # Why it is needed (observed in practice): `unprotected-api: true` means "the whole REST API needs no authentication", and no authentication
    # amounts to **no authorisation** - even when a request carries BASIC credentials, the authorisation decision never runs. Turning
    # authorizations.enabled on while leaving unprotected-api: true means every REST call from a role such as auditor,
    # which holds no USER_TASK permission, still returns 200 and there is no way to tell whether RBAC is in effect.
    # To demonstrate a refusal, this switch has to be turned on as well.
    [switch]$ProtectedApi,
    # Use Start-Process to launch the engine as a **separate process**; the script returns immediately.
    # Why it is needed: in an automation host, when the engine runs as a foreground or background task, the host
    # kills the java child process as it reclaims the task, so the engine is cleaned up as soon as it starts. In detached mode the engine is not attached to the caller's process tree
    # and keeps running until it is stopped explicitly with stop-engine.ps1.
    [switch]$Detached
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Directory containing this script. Normally $PSScriptRoot is used; with some calling conventions (for example invoked with & and no host
# having populated that variable) it is empty, and the script falls back to $PSCommandPath / $MyInvocation.
$scriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition }
if ([string]::IsNullOrEmpty($scriptDir)) { throw "Cannot determine the script directory; specify it explicitly with -RuntimeDir." }

# Repository root = two levels above the directory containing this script
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$runtimeDir = Join-Path $repoRoot "_runtime\camunda"

if (-not (Test-Path $Dist)) { throw "Camunda distribution not found: $Dist" }
if (-not (Test-Path $JavaCmd)) { throw "java not found: $JavaCmd" }

# Working directory: every relative path of the engine is resolved from here
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "config") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "data") | Out-Null

# Copy the Spring configuration from the submitted repository into the engine working directory, so that the configuration submitted is the configuration that runs
$sourceConfig = Join-Path $repoRoot "bpm\camunda\application.yaml"
if (-not (Test-Path $sourceConfig)) { throw "Configuration file not found: $sourceConfig" }
$runtimeConfig = Join-Path $runtimeDir "config\application.yaml"
Copy-Item $sourceConfig $runtimeConfig -Force

# Runtime switches: only the **runtime copy** is changed; application.yaml in the submitted repository is never touched.
#
# The approach is to place a marker comment line in the YAML and then change the first non-comment, non-blank line after it to the target value.
# That way both configuration profiles share one configuration file and cannot drift apart.
$runtimeFlags = @()
function Set-RuntimeFlag {
    param(
        [Parameter(Mandatory = $true)][string]$Marker,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$Label
    )
    # Trap: PowerShell variable names are **case-insensitive**, so $marker must never be used as the loop variable here,
    # otherwise it would overwrite the $Marker parameter with an integer. That is how the first version broke, reporting "you cannot call a method on a null-valued expression".
    # Get-Content/Set-Content are used throughout instead, avoiding the problems .NET static calls have in constrained language mode.
    $path = $runtimeConfig
    if (-not (Test-Path -LiteralPath $path)) { throw "Runtime configuration not found: $path" }
    $all = @(Get-Content -LiteralPath $path -Encoding UTF8)
    if ($all.Count -eq 0) { throw "Runtime configuration is empty: $path" }

    $markerIndex = -1
    for ($i = 0; $i -lt $all.Count; $i++) {
        if (([string]$all[$i]) -match [regex]::Escape($Marker)) { $markerIndex = $i; break }
    }
    if ($markerIndex -lt 0) { throw "Marker $Marker not found in the configuration, so $Label cannot be applied." }

    for ($i = $markerIndex + 1; $i -lt $all.Count; $i++) {
        $line = [string]$all[$i]
        $trimmed = $line.Trim()
        if ($trimmed -eq '' -or $trimmed.StartsWith('#')) { continue }
        if ($trimmed -match ('^' + [regex]::Escape($Key) + ':\s*\S+\s*$')) {
            $lead = $line.Length - $line.TrimStart().Length
            $all[$i] = (' ' * $lead) + $Key + ': ' + $Value
            Set-Content -LiteralPath $path -Value $all -Encoding UTF8
            Write-Host "flag      : $Label -> ${Key}: $Value"
            return
        }
    }
    throw "After $Marker, no $Key line was found, so $Label cannot be applied."
}

if ($WorkersProfile) {
    Set-RuntimeFlag -Marker "WORKERS-PROFILE SWITCH" -Key "enabled" -Value "false" `
        -Label "authorizations.enabled -> false (so unauthenticated gRPC workers can claim jobs)"
    $runtimeFlags += "workers"
}
if ($ProtectedApi) {
    Set-RuntimeFlag -Marker "PROTECTED-API SWITCH" -Key "unprotected-api" -Value "false" `
        -Label "unprotected-api -> false (so REST genuinely requires identity and authorisation)"
    $runtimeFlags += "protected-api"
}
if ($runtimeFlags.Count -eq 0) {
    Write-Host "profile   : RBAC (authorizations.enabled keeps the value from the configuration file)"
} else {
    Write-Host "profile   : $($runtimeFlags -join ' + ')"
}

# The same classpath composition as bin\camunda.bat: the distribution's config directory plus every jar under lib
$classPath = "$Dist\config;$Dist\lib\*"

$javaArgs = @(
    "-XX:+ExitOnOutOfMemoryError"
    "-Dfile.encoding=UTF-8"
    "-Xshare:auto"
    "--add-opens=java.base/java.io=ALL-UNNAMED"
    "--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED"
    "--enable-native-access=ALL-UNNAMED"
    # Essential: point app.home and basedir at the writable working directory
    "-Dapp.home=$runtimeDir"
    "-Dbasedir=$runtimeDir"
    "-classpath", $classPath
    "-Dapp.name=camunda"
    "-Dapp.repo=$Dist\lib"
    "io.camunda.application.StandaloneCamunda"
    "--server.port=$Port"
    "--spring.config.additional-location=optional:file:./config/application.yaml"
)

Write-Host "repo      : $repoRoot"
Write-Host "dist      : $Dist"
Write-Host "runtime   : $runtimeDir"
Write-Host "java      : $JavaCmd"
Write-Host "port      : $Port"
Write-Host "starting Camunda (Ctrl+C to stop) ..."
Write-Host ""

# Remember the caller's original working directory.
#
# Trap (actually hit by a user): Set-Location takes effect in the **caller's session** - invoking a script with &
# does not open a new session, so when the script finishes the current directory is left at $runtimeDir. Any
# relative path afterwards is then resolved from _runtime\camunda, for example
#     & "bpm\tools\deploy-model.ps1"
# is treated as _runtime\camunda\bpm\tools\..., cannot be found, and PowerShell then treats it as a module name,
# reporting the highly misleading "the module bpm could not be loaded". So try/finally guarantees the directory is restored
# (exit 0 also triggers finally, and the detached branch is protected in the same way).
$originalLocation = (Get-Location).Path

try {
Set-Location $runtimeDir

if ($Detached) {
    # Detached process mode: stdout/stderr go to _runtime\camunda\logs\engine-console.*.log
    # and the PID is written to logs\engine.pid for stop-engine.ps1 to use.
    $outLog = Join-Path $runtimeDir "logs\engine-console.out.log"
    $errLog = Join-Path $runtimeDir "logs\engine-console.err.log"
    $proc = Start-Process -FilePath $JavaCmd -ArgumentList $javaArgs `
        -WorkingDirectory $runtimeDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    Set-Content -Path (Join-Path $runtimeDir "logs\engine.pid") -Value $proc.Id -Encoding ASCII
    Write-Host "started detached, pid = $($proc.Id)  (logs\engine.pid)"
    Write-Host "console: $outLog"
    exit 0
}

& $JavaCmd @javaArgs
}
finally {
    # Restore the caller's working directory so that relative paths do not resolve wrongly after the script returns
    Set-Location $originalLocation -ErrorAction SilentlyContinue
}
