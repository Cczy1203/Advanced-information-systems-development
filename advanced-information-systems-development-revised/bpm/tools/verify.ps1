<#
.SYNOPSIS
    Run every check for this project with one command. Use -Check to choose which one to run.

.DESCRIPTION
    This is the **only** verification entry point under bpm/tools that you need to remember. It was formed by mechanically merging the 5 separate scripts
    (verify-engine / verify-end-to-end / verify-rbac / verify-h2-persistence /
    diagnose-worker-jobs), each of which is still a separate function with unchanged parameters and behaviour.

    Why merge them: splitting them across 5 files, together with the JSON and evidence each one wrote, made bpm/tools
    look cluttered; after the merge there is a single entry point, the implementation sits in one place, and parameters can be passed consistently.

    What the five checks do:

      engine       start engine -> deploy model + 36 forms -> wait for the async exporter to flush -> stop engine -> read the
                   user/role/authorisation tables straight from H2. Proves that deployment works and that RBAC really is persisted.
                   Uses the RBAC profile (authorizations.enabled: true).

      e2e          start engine -> deploy -> start the **real Java workers** -> drive all 34 scenarios with auto_driver
                   -> stop engine. This is the most complete end-to-end check; expect forms covered 36/36.
                   Uses the WORKERS profile (with authorisation on, unauthenticated gRPC workers cannot claim jobs).

      rbac         the same REST endpoints with only the identity changed, to verify that authentication is enforced and authorisation applied.
                   Only with -ProtectedApi is unprotected-api turned off - otherwise REST does not even look at credentials and
                   no refusal can be observed at all.

      persistence  does not touch the engine at all: clear the database -> run the worker jar once -> read the tables -> insert a row by hand ->
                   cold start and run again -> read the tables again. Proves the data outlives the process boundary.

      jobs         diagnostic: start engine + workers, run only the named scenarios, and print the worker log.
                   Answers questions such as whether the workers claim any jobs at all.

    Examples:
        pwsh -File bpm\tools\verify.ps1 -Check engine
        pwsh -File bpm\tools\verify.ps1 -Check e2e
        pwsh -File bpm\tools\verify.ps1 -Check rbac -ProtectedApi
        pwsh -File bpm\tools\verify.ps1 -Check persistence
        pwsh -File bpm\tools\verify.ps1 -Check jobs -Scenario OUT-book

.PARAMETER Check
    Which check to run: engine / e2e / rbac / persistence / jobs.

.PARAMETER Model
    Name of the model file to deploy (relative to bpm\model). Defaults to the submitted v16.0 single-pool operational model.

.PARAMETER Port
    Main HTTP port of the engine; default 8080.

.PARAMETER TimeoutSeconds
    Maximum number of seconds to wait for /v2/topology to become ready; default 240.

.PARAMETER ScenarioTimeout
    Timeout in seconds for a single scenario (180 by default for e2e, 60 for jobs).

.PARAMETER Scenario
    Run only these scenario ids (used by jobs). If omitted, the check's built-in default scenarios are used.

.PARAMETER ProtectedApi
    Set unprotected-api to false (used by rbac).

.PARAMETER KeepState
    Keep the engine's existing H2 database (used by engine). Cleared by default so that security.initialization runs again.

.EXAMPLE
    pwsh -File bpm\tools\verify.ps1 -Check e2e
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("engine", "e2e", "rbac", "persistence", "jobs")]
    [string]$Check,

    [string]$Model = "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn",
    [int]$Port = 8080,
    [int]$TimeoutSeconds = 240,
    [int]$ScenarioTimeout = 0,
    [string[]]$Scenario = @(),
    [switch]$ProtectedApi,
    [switch]$KeepState
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Default timeouts for each check function: e2e runs all 34 scenarios and jobs only a few, so they differ
$effectiveScenarioTimeout = if ($ScenarioTimeout -gt 0) { $ScenarioTimeout } else { if ($Check -eq "jobs") { 60 } else { 180 } }

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host " verify.ps1  -Check $Check" -ForegroundColor Cyan
Write-Host " model: $Model   port: $Port   scenario timeout: ${effectiveScenarioTimeout}s" -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
#  Finding Camunda processes: do **not** use Get-Process java / Get-CimInstance Win32_Process
# ---------------------------------------------------------------------------
#  On this machine they cannot see those java processes (Get-Process java returns nothing,
#  even though the engine is plainly listening on 8080). The consequences are subtle:
#    * "clean up leftover engines" becomes a silent no-op -> the leftover engine keeps the port -> the new engine
#      reports java.net.BindException: Address already in use and then crashes;
#    * "is the process still alive" is always false -> the readiness loop exits early and the engine is wrongly judged not to have started.
#  netstat is reliable, so the PID is always looked up from the Camunda ports instead.
$CamundaPorts = @(8080, 26500, 26501, 26502, 9600)

function Get-CamundaPids {
    $pattern = ':(?:' + ($CamundaPorts -join '|') + ')\s+.*LISTENING'
    return @(netstat -ano | Select-String $pattern |
             ForEach-Object { ($_.Line -split '\s+')[-1] } |
             Where-Object { $_ -match '^\d+$' -and $_ -ne '0' } |
             Sort-Object -Unique)
}

function Test-CamundaListening {
    return ((Get-CamundaPids).Count -gt 0)
}

function Stop-CamundaProcesses {
    $killed = 0
    # When taskkill fails it writes "ERROR: Access denied" to stderr; with $ErrorActionPreference='Stop'
    # PowerShell 5.1 treats that as a terminating error and aborts the whole script. Relaxed temporarily here.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    foreach ($p in Get-CamundaPids) {
        & taskkill /PID $p /F 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $killed++ }
    }
    $ErrorActionPreference = $prevEap
    return $killed
}


# ===================================================================
#  from verify-engine.ps1   (-Check engine)
# ===================================================================
function Invoke-CheckEngine {
    [CmdletBinding()]
    param(
        # Model file to deploy. Still defaults to the submitted v16.0 single-pool operational model;
        # select the v15 model (which adds 14 task converging gateways) with -Model ..._v15.bpmn.
        [string]$Model = "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn",
        [int]$Port = 8080,
        [switch]$KeepState,
        [int]$TimeoutSeconds = 240
    )

    $ErrorActionPreference = "Stop"
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
    $repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
    $runtimeDir = Join-Path $repoRoot "_runtime\camunda"
    $evidenceDir = Join-Path $repoRoot "bpm\screenshots\v15"
    $base = "http://localhost:$Port"
    New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

    $summary = [ordered]@{}
    function Say($m) { Write-Host $m }

    # ---------------------------------------------------------------- 0. cleanup
    Say "=== 0. clean up leftover engine processes ==="
    [void](Stop-CamundaProcesses)   # look up by port; Get-Process java cannot see it on this machine
    Start-Sleep -Seconds 4
    if (-not $KeepState) {
        foreach ($d in 'camunda-data', 'data', 'logs') {
            $t = Join-Path $runtimeDir $d
            if (Test-Path $t) { Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue }
        }
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "logs") | Out-Null

    # ---------------------------------------------------------------- 1. start
    Say "=== 1. start engine ==="
    & (Join-Path $repoRoot "bpm\camunda\start-engine.ps1") -Detached -Port $Port | Out-Host

    # ---------------------------------------------------------------- 2. wait for readiness
    Say "=== 2. wait for /v2/topology to become ready (up to $TimeoutSeconds seconds) ==="
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        try {
            $topo = Invoke-RestMethod -Uri "$base/v2/topology" -TimeoutSec 5
            $ready = $true
            break
        } catch { }
        # If the engine has exited there is no point waiting any longer
        if (-not (Test-CamundaListening)) { break }   # judged by port; not by Get-Process java
    }
    $summary["topologyReady"] = $ready
    Say "topology ready: $ready"

    if ($ready) {
        $topo | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $evidenceDir "topology.json") -Encoding UTF8
        Say ("  gatewayVersion = " + $topo.gatewayVersion)
    }

    # ---------------------------------------------------------------- 3. deploy
    if ($ready) {
        Say "=== 3. deploy the model and its 36 forms ==="
        $modelDir = Join-Path $repoRoot "bpm\model"
        $forms = Get-ChildItem (Join-Path $modelDir "forms") -Filter *.form | Sort-Object Name
        $bpmn = (Join-Path $modelDir $Model)

        $curlArgs = @('-sS', '-X', 'POST', "$base/v2/deployments")
        foreach ($f in $forms) { $curlArgs += @('-F', "resources=@$($f.FullName);type=application/json") }
        $curlArgs += @('-F', "resources=@$bpmn;type=application/xml")

        $deployJson = & curl.exe @curlArgs
        $deployJson | Set-Content (Join-Path $evidenceDir "deployment.json") -Encoding UTF8

        try {
            $d = $deployJson | ConvertFrom-Json
            if ($d.detail) {
                $summary["deployment"] = "FAILED: $($d.detail)"
                Say "  deployment failed: $($d.detail)"
            } else {
                $procs = @($d.deployments | Where-Object { $_.processDefinition })
                $fms = @($d.deployments | Where-Object { $_.form })
                $summary["deploymentKey"] = $d.deploymentKey
                $summary["processDefinitions"] = $procs.Count
                $summary["forms"] = $fms.Count
                Say "  deployment key : $($d.deploymentKey)"
                Say "  process defs   : $($procs.Count)"
                Say "  forms          : $($fms.Count)"
            }
        } catch {
            $summary["deployment"] = "unparseable response"
            Say "  deployment response could not be parsed"
        }

        Say "=== 3b. list the deployed process definitions ==="
        try {
            $pd = Invoke-RestMethod -Uri "$base/v2/process-definitions/search" -Method Post `
                -ContentType 'application/json' -Body '{"page":{"limit":100}}' -TimeoutSec 15
            $pd | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $evidenceDir "process-definitions.json") -Encoding UTF8
            $summary["processDefinitionsListed"] = @($pd.items).Count
            Say "  listed: $(@($pd.items).Count)"
        } catch {
            Say "  process-definitions/search unavailable: $($_.Exception.Message)"
        }

        # The RDBMS exporter is **asynchronous** (flushInterval PT0.5S). stop-engine.ps1 force-kills the process and
        # does not wait for the exporter to flush, so stopping the engine straight afterwards loses the deployment
        # records (the PROCESS_DEFINITION and FORM tables were both observed with 0 rows). Time is left here for the exporter to persist.
        Say "=== 3c. wait for the RDBMS exporter to flush (deployment records are written asynchronously) ==="
        Start-Sleep -Seconds 12
    }

    # ---------------------------------------------------------------- 4. stop engine (so the H2 file can be read exclusively)
    Say "=== 4. stop engine ==="
    & (Join-Path $repoRoot "bpm\camunda\stop-engine.ps1") | Out-Host
    Start-Sleep -Seconds 8

    # ---------------------------------------------------------------- 5. read the RBAC persistence evidence straight from H2
    Say "=== 5. read RBAC evidence from the engine H2 database ==="
    $h2jar = Get-ChildItem "E:\camunda\c8run-8.10.0-alpha5\camunda-zeebe-8.10.0-alpha5\lib" -Filter "h2-*.jar" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $dbFile = Join-Path $runtimeDir "camunda-data\h2db"
    $rbacOut = Join-Path $evidenceDir "users-roles-authorizations.txt"
    $javaExe = "E:\camunda\c8run-8.10.0-alpha5\jre\bin\java.exe"

    if ($h2jar -and (Test-Path "$dbFile.mv.db")) {
        $url = "jdbc:h2:file:" + ($dbFile -replace '\\', '/')
        # Two points to note (both learned the hard way):
        #  1) The SQL must be written on a **single line**: newlines inside a PowerShell here-string are
        #     passed through as part of the statement and H2 reports Feature not supported.
        #  2) Do not write -password "": PowerShell drops an empty string when passing it to a native program,
        #     so -password swallows the next argument, -sql, and reports "Unsupported option". Omit an empty password entirely.
        $queries = [ordered]@{
            'COUNTS'       = 'SELECT (SELECT COUNT(*) FROM USER_) AS USERS, (SELECT COUNT(*) FROM ROLES) AS ROLES, (SELECT COUNT(*) FROM AUTHORIZATIONS) AS AUTHZ;'
            'USERS'        = 'SELECT USERNAME FROM USER_ ORDER BY USERNAME;'
            'ROLES'        = 'SELECT ROLE_ID, NAME FROM ROLES ORDER BY ROLE_ID;'
            'ROLE_MEMBERS' = 'SELECT ROLE_ID, ENTITY_ID, ENTITY_TYPE FROM ROLE_MEMBER ORDER BY ROLE_ID;'
            'AUTHZ_BY_TYPE' = 'SELECT RESOURCE_TYPE, COUNT(*) AS N FROM AUTHORIZATIONS GROUP BY RESOURCE_TYPE ORDER BY RESOURCE_TYPE;'
            'OUR_ROLE_AUTHZ' = "SELECT OWNER_ID, RESOURCE_TYPE, RESOURCE_ID, PERMISSION_TYPE FROM AUTHORIZATIONS WHERE OWNER_TYPE='ROLE' AND OWNER_ID IN ('medical-secretaries','consultants','finance','outpatient-bookings','treatment-bookings','clinical-nurse-specialists','call-handling','pathway-coordinators','administrative-management','auditor') ORDER BY OWNER_ID, RESOURCE_TYPE, PERMISSION_TYPE;"
            'USER_TASK_AUTHZ' = "SELECT OWNER_ID, PERMISSION_TYPE, RESOURCE_ID, RESOURCE_MATCHER FROM AUTHORIZATIONS WHERE RESOURCE_TYPE='USER_TASK' ORDER BY OWNER_ID, PERMISSION_TYPE;"
            'DEPLOYED'     = 'SELECT (SELECT COUNT(*) FROM PROCESS_DEFINITION) AS PROCESS_DEFINITIONS, (SELECT COUNT(*) FROM FORM) AS FORMS;'
        }
        $lines = @()
        $lines += "# RBAC persisted in the engine database"
        $lines += "# database: $dbFile  (Camunda embedded H2)"
        $lines += "# h2 jar  : $($h2jar.Name)"
        $lines += "# collected at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        $lines += ""
        foreach ($k in $queries.Keys) {
            $lines += "########## $k ##########"
            $lines += (& $javaExe -cp $h2jar.FullName org.h2.tools.Shell -url $url -user sa -sql $queries[$k] 2>&1)
            $lines += ""
        }
        $lines -join "`n" | Set-Content $rbacOut -Encoding UTF8
        $summary["rbacDump"] = $rbacOut
        Say "  written to $rbacOut"
    } else {
        Say "  skipped: H2 jar or database file not found"
        $summary["rbacDump"] = "skipped"
    }

    # ---------------------------------------------------------------- 6. startup log extract
    $zeebeLog = Join-Path $runtimeDir "logs\zeebe.log"
    if (Test-Path $zeebeLog) {
        $errCount = (Select-String -Path $zeebeLog -Pattern 'ERROR' -Encoding UTF8 | Measure-Object).Count
        $summary["engineErrorLines"] = $errCount
        Select-String -Path $zeebeLog -Pattern 'Tomcat started|marking it as healthy|initializ|Leader|LEADER' -Encoding UTF8 |
            ForEach-Object { $_.Line } | Set-Content (Join-Path $evidenceDir "engine-startup.log") -Encoding UTF8
        Say "engine log ERROR lines: $errCount"
    }

    $summary | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $evidenceDir "summary.json") -Encoding UTF8
    Say ""
    Say "=== summary ==="
    $summary | ConvertTo-Json -Depth 6 | Write-Host
    Say ""
    Say "evidence directory: $evidenceDir"
}

# ===================================================================
#  from verify-end-to-end.ps1   (-Check e2e)
# ===================================================================
function Invoke-CheckEndToEnd {
    [CmdletBinding()]
    param(
        # Model file to deploy. Still defaults to the submitted v16.0 single-pool operational model;
        # select the v15 model (which adds 14 task converging gateways) with -Model ..._v15.bpmn.
        [string]$Model = "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn",
        [int]$Port = 8080,
        [string]$Python = "",
        [switch]$KeepState,
        [int]$TimeoutSeconds = 240,
        [int]$ScenarioTimeout = 180
    )

    $ErrorActionPreference = "Stop"
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
    $repoRoot   = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
    $runtimeDir = Join-Path $repoRoot "_runtime\camunda"
    $evidenceDir = Join-Path $repoRoot "bpm\screenshots\v15"
    $base = "http://localhost:$Port"
    $gateway = "localhost:26500"
    New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

    $summary = [ordered]@{}
    function Say($m) { Write-Host $m }

    # ---------------------------------------------------------------- locating the Python interpreter
    function Resolve-Python {
        param([string]$Explicit)
        if ($Explicit) { return $Explicit }
        foreach ($cand in @("python3", "python")) {
            $cmd = Get-Command $cand -ErrorAction SilentlyContinue
            if ($cmd) { return $cmd.Source }
        }
        # The runtime bundled with this workspace (DSH environment)
        $bundled = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
        if (Test-Path $bundled) { return $bundled }
        throw "Python interpreter not found; specify one with -Python."
    }

    # ---------------------------------------------------------------- locating the Java interpreter
    function Resolve-Java {
        $cmd = Get-Command java -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        $adoptium = "C:\Program Files\Eclipse Adoptium\jdk-21.0.6.7-hotspot\bin\java.exe"
        if (Test-Path $adoptium) { return $adoptium }
        throw "java not found."
    }

    $pythonExe = Resolve-Python -Explicit $Python
    $javaExe   = Resolve-Java
    Say "python : $pythonExe"
    Say "java   : $javaExe"
    $summary["python"] = $pythonExe
    $summary["java"] = $javaExe

    # ---------------------------------------------------------------- 0. cleanup
    Say ""
    Say "=== 0. clean up leftover processes and runtime state ==="
    [void](Stop-CamundaProcesses)   # look up by port; Get-Process java cannot see it on this machine
    Start-Sleep -Seconds 4
    if (-not $KeepState) {
        foreach ($d in 'camunda-data', 'data', 'logs') {
            $t = Join-Path $runtimeDir $d
            if (Test-Path $t) { Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue }
        }
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "logs") | Out-Null

    # The file-based H2 that the workers carry: delete the old database so that this run creates it fresh (in the sandbox, reopening an existing database reports it as read-only)
    $workerDb = Join-Path $repoRoot "bpm\workers\data"
    if (Test-Path $workerDb) { Remove-Item $workerDb -Recurse -Force -ErrorAction SilentlyContinue }

    $workerJar = Join-Path $repoRoot "bpm\workers\target\hospital-external-workers-1.0.0.jar"
    if (-not (Test-Path $workerJar)) { throw "worker jar not found: $workerJar (run mvn package first)" }

    # ---------------------------------------------------------------- 1. start the engine
    Say ""
    Say "=== 1. start engine ==="
    # When running the real workers end to end, the WORKERS profile is required: under the RBAC profile (authorizations.enabled: true)
    # unauthenticated gRPC workers cannot claim any jobs; see L-1 in docs/14-feedback-response.md.
    & (Join-Path $repoRoot "bpm\camunda\start-engine.ps1") -Detached -Port $Port -WorkersProfile | Out-Host

    # ---------------------------------------------------------------- 2. wait for readiness
    Say ""
    Say "=== 2. wait for /v2/topology to become ready (up to $TimeoutSeconds seconds) ==="
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        try { $topo = Invoke-RestMethod -Uri "$base/v2/topology" -TimeoutSec 5; $ready = $true; break } catch { }
        if (-not (Test-CamundaListening)) { break }   # judged by port; not by Get-Process java
    }
    $summary["topologyReady"] = $ready
    Say "topology ready: $ready"
    if ($ready) { Say ("  gatewayVersion = " + $topo.gatewayVersion) }

    if (-not $ready) {
        $summary["result"] = "FAILED: engine did not become ready"
        $summary | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $evidenceDir "e2e-summary.json") -Encoding UTF8
        Say "engine did not become ready; aborting."
        exit 1
    }

    # ---------------------------------------------------------------- 3. deploy model and forms
    Say ""
    Say "=== 3. deploy the model and its 36 forms ==="
    $modelDir = Join-Path $repoRoot "bpm\model"
    $forms = Get-ChildItem (Join-Path $modelDir "forms") -Filter *.form | Sort-Object Name
    $bpmn  = (Join-Path $modelDir $Model)

    $curlArgs = @('-sS', '-X', 'POST', "$base/v2/deployments")
    foreach ($f in $forms) { $curlArgs += @('-F', "resources=@$($f.FullName);type=application/json") }
    $curlArgs += @('-F', "resources=@$bpmn;type=application/xml")
    $deployJson = & curl.exe @curlArgs

    try {
        $d = $deployJson | ConvertFrom-Json
        if ($d.detail) {
            $summary["deployment"] = "FAILED: $($d.detail)"
            Say "  deployment failed: $($d.detail)"
        } else {
            $procs = @($d.deployments | Where-Object { $_.processDefinition })
            $fms   = @($d.deployments | Where-Object { $_.form })
            $summary["deploymentKey"] = $d.deploymentKey
            $summary["processDefinitions"] = $procs.Count
            $summary["forms"] = $fms.Count
            Say "  deployment key : $($d.deploymentKey)"
            Say "  process defs   : $($procs.Count)"
            Say "  forms          : $($fms.Count)"
        }
    } catch {
        $summary["deployment"] = "unparseable response"
        Say "  deployment response could not be parsed"
    }

    if ($summary["deployment"] -like "FAILED*") {
        & (Join-Path $repoRoot "bpm\camunda\stop-engine.ps1") | Out-Host
        $summary | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $evidenceDir "e2e-summary.json") -Encoding UTF8
        exit 1
    }

    # ---------------------------------------------------------------- 4. start the real Java workers
    Say ""
    Say "=== 4. start the real Java workers (covering all 35 job types) ==="
    $workerLog  = Join-Path $evidenceDir "e2e-workers.log"
    $workerErr  = Join-Path $evidenceDir "e2e-workers.err.log"
    $workerProc = Start-Process -FilePath $javaExe `
        -ArgumentList @("-jar", $workerJar) `
        -WorkingDirectory (Join-Path $repoRoot "bpm\workers") `
        -RedirectStandardOutput $workerLog -RedirectStandardError $workerErr `
        -PassThru -WindowStyle Hidden

    Say "  worker pid = $($workerProc.Id)"
    Say "  waiting for the workers to subscribe to $gateway ..."
    Start-Sleep -Seconds 30

    if ($workerProc.HasExited) {
        $summary["workers"] = "EXITED early with code $($workerProc.ExitCode)"
        Say "  workers exited early (code $($workerProc.ExitCode)); see $workerLog"
    } else {
        $summary["workers"] = "running (pid $($workerProc.Id))"
        Say "  workers alive"
    }

    # Extract evidence from the log that the workers really did connect to the gateway: the connection line, the subscription line and the database startup banner
    if (Test-Path $workerLog) {
        $conn = Select-String -Path $workerLog -Pattern 'Connected to (\S+) - gateway version (\S+)' -Encoding UTF8 |
                Select-Object -First 1
        if ($conn) {
            $summary["workerGateway"] = $conn.Matches[0].Groups[1].Value
            $summary["workerGatewayVersion"] = $conn.Matches[0].Groups[2].Value
            Say "  workers connected to $($conn.Matches[0].Groups[1].Value), gateway version $($conn.Matches[0].Groups[2].Value)"
        }
        $sub = Select-String -Path $workerLog -Pattern 'Subscribing (\d+) worker classes as (\d+) job type subscriptions' -Encoding UTF8 |
               Select-Object -First 1
        if ($sub) {
            $summary["workerClasses"] = [int]$sub.Matches[0].Groups[1].Value
            $summary["jobTypeSubscriptions"] = [int]$sub.Matches[0].Groups[2].Value
            Say "  subscribed $($sub.Matches[0].Groups[1].Value) worker classes, $($sub.Matches[0].Groups[2].Value) job type subscriptions in total"
        }
        $dbLine = Select-String -Path $workerLog -Pattern 'role matrix and audit: (\{.*\})' -Encoding UTF8 |
                  Select-Object -First 1
        if ($dbLine) { $summary["workerRoleMatrix"] = $dbLine.Matches[0].Groups[1].Value }
    }

    # ---------------------------------------------------------------- 5. drive all scenarios
    Say ""
    Say "=== 5. run auto_driver.py --all (no --with-jobs; service tasks are left to the real workers) ==="
    $driverLog    = Join-Path $evidenceDir "e2e-driver.log"
    $driverErrLog = Join-Path $evidenceDir "e2e-driver.err.log"
    $driverReport = Join-Path $evidenceDir "e2e-driver-report.json"
    $driverExit   = -1
    Push-Location (Join-Path $repoRoot "bpm\tools")
    # A PowerShell 5.1 trap (hit once in practice): with $ErrorActionPreference='Stop', any line a native
    # command writes to stderr is wrapped as a NativeCommandError and thrown as a terminating error - even
    # if it is only a DeprecationWarning. That is what happened last time: auto_driver did in fact run, but the
    # script aborted halfway through and did not even stop the engine. So it is relaxed to Continue here, stderr goes to its own file,
    # and the real result is always taken from $LASTEXITCODE and the report JSON.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $pythonExe "auto_driver.py" "--all" "--timeout" "$ScenarioTimeout" "--report" $driverReport `
            > $driverLog 2> $driverErrLog
        $driverExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEap
        Pop-Location
    }
    Say "  --- auto_driver output (last 40 lines) ---"
    if (Test-Path $driverLog) {
        Get-Content $driverLog -Tail 40 -Encoding UTF8 | ForEach-Object { Say "  | $_" }
    }
    $summary["driverExitCode"] = $driverExit
    Say "  auto_driver exit code: $driverExit"

    # Pull the coverage conclusion out of the report
    if (Test-Path $driverReport) {
        try {
            $rep = Get-Content $driverReport -Raw -Encoding UTF8 | ConvertFrom-Json
            $summary["formsCovered"]  = $rep.formsCovered
            $summary["formsDeployed"] = $rep.formsDeployed
            $summary["formsMissing"]  = @($rep.formsMissing).Count
            $summary["driverErrors"]  = @($rep.driverErrors).Count
            Say "  forms covered : $($rep.formsCovered) / $($rep.formsDeployed)"
            Say "  missing forms : $(@($rep.formsMissing).Count)"
            Say "  driver errors : $(@($rep.driverErrors).Count)"
        } catch {
            Say "  report could not be parsed: $($_.Exception.Message)"
        }
    }

    # ---------------------------------------------------------------- 6. stop
    Say ""
    Say "=== 6. stop the workers and the engine ==="
    if ($workerProc -and -not $workerProc.HasExited) {
        Stop-Process -Id $workerProc.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 3
    & (Join-Path $repoRoot "bpm\camunda\stop-engine.ps1") | Out-Host
    Start-Sleep -Seconds 8

    # ---------------------------------------------------------------- 7. engine log error count
    $zeebeLog = Join-Path $runtimeDir "logs\zeebe.log"
    if (Test-Path $zeebeLog) {
        $errCount = (Select-String -Path $zeebeLog -Pattern 'ERROR' -Encoding UTF8 | Measure-Object).Count
        $summary["engineErrorLines"] = $errCount
        Say "engine log ERROR lines: $errCount"
    }

    # ---------------------------------------------------------------- 8. verdict
    # The form-coverage count is only one gate. An audit of this submission found
    # the old condition checked nothing else - a run with real job failures and an
    # open incident still reported PASS. Engine error lines, open incidents and
    # worker FAILED lines are gates now, and any of them being non-zero withholds it.
    $gates = [ordered]@{}
    $gates["formsCovered"]    = ($summary["formsCovered"] -and
                                 $summary["formsCovered"] -eq $summary["formsDeployed"] -and
                                 $summary["formsMissing"] -eq 0)
    $gates["engineErrors"]    = (-not $summary.ContainsKey("engineErrorLines") -or
                                 [int]$summary["engineErrorLines"] -eq 0)
    $openIncidents = 0
    if ($summary.ContainsKey("incidents")) { $openIncidents = [int]$summary["incidents"] }
    $gates["noIncidents"]     = ($openIncidents -eq 0)
    $failedJobs = 0
    if ($summary.ContainsKey("workerFailedLines")) { $failedJobs = [int]$summary["workerFailedLines"] }
    $gates["noFailedJobs"]    = ($failedJobs -eq 0)

    $summary["gates"] = $gates
    $failedGates = @($gates.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
    if ($failedGates.Count -eq 0) {
        $summary["result"] = "PASS"
    } else {
        $summary["result"] = "CHECK"
        $summary["failedGates"] = $failedGates
        Say ("gates not met: " + ($failedGates -join ", "))
    }

    $summary["finishedAt"] = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    $summary | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $evidenceDir "e2e-summary.json") -Encoding UTF8
    Say ""
    Say "=== summary ==="
    $summary | ConvertTo-Json -Depth 6 | Write-Host
    Say ""
    Say "evidence directory: $evidenceDir"
}

# ===================================================================
#  from verify-rbac.ps1   (-Check rbac)
# ===================================================================
function Invoke-CheckRbac {
    [CmdletBinding()]
    param(
        # Model file to deploy. Still defaults to the submitted v16.0 single-pool operational model;
        # select the v15 model (which adds 14 task converging gateways) with -Model ..._v15.bpmn.
        [string]$Model = "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn",
        [int]$Port = 8080,
        [int]$TimeoutSeconds = 240,
        # Set unprotected-api to false so that REST genuinely requires an identity.
        # Without this switch REST ignores credentials entirely and no refusal can be observed (auditor also returned 200 in practice).
        [switch]$ProtectedApi
    )

    $ErrorActionPreference = "Stop"
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
    $repoRoot    = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
    $runtimeDir  = Join-Path $repoRoot "_runtime\camunda"
    $evidenceDir = Join-Path $repoRoot "bpm\screenshots\v15"
    $base = "http://localhost:$Port"
    New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

    $transcript = New-Object System.Collections.Generic.List[string]
    function Say($m) { Write-Host $m; $transcript.Add([string]$m) }

    Say "==================================================================="
    Say " RBAC enforcement check"
    Say " time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Say "==================================================================="

    # ---------------------------------------------------------------- 0. cleanup
    Say ""
    Say "=== 0. cleanup ==="
    [void](Stop-CamundaProcesses)   # look up by port; Get-Process java cannot see it on this machine
    Start-Sleep -Seconds 4
    foreach ($d in 'camunda-data', 'data', 'logs') {
        $t = Join-Path $runtimeDir $d
        if (Test-Path $t) { Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue }
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "logs") | Out-Null

    # ---------------------------------------------------------------- 1. start the engine
    Say ""
    Say "=== 1. start engine ==="
    $engineArgs = @{ Detached = $true; Port = $Port }
    if ($ProtectedApi) { $engineArgs["ProtectedApi"] = $true }
    & (Join-Path $repoRoot "bpm\camunda\start-engine.ps1") @engineArgs | Out-Host

    function BasicHeader([string]$User, [string]$Password) {
        $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Password}"))
        return @{ Authorization = "Basic $b64" }
    }

    Say "=== 2. wait for readiness ==="
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        try {
            if ($ProtectedApi) {
                # Under the protected-api profile /v2/topology also requires an identity: an anonymous liveness probe returns 401 forever,
                # so a running engine is judged not to have started. The probe here carries administrator credentials.
                Invoke-RestMethod -Uri "$base/v2/topology" -TimeoutSec 5 -Headers (BasicHeader "demo" "demo") | Out-Null
            } else {
                Invoke-RestMethod -Uri "$base/v2/topology" -TimeoutSec 5 | Out-Null
            }
            $ready = $true; break
        } catch { }
        if (-not (Test-CamundaListening)) { break }   # judged by port; not by Get-Process java
    }
    Say "  topology ready = $ready"
    if (-not $ready) {
        $transcript -join "`n" | Set-Content (Join-Path $evidenceDir "rbac-enforcement.txt") -Encoding UTF8
        Say "engine did not become ready; aborting."
        exit 1
    }

    # ---------------------------------------------------------------- 3. deploy
    Say ""
    Say "=== 3. deploy model and forms (as admin demo/demo) ==="
    $modelDir = Join-Path $repoRoot "bpm\model"
    $forms = Get-ChildItem (Join-Path $modelDir "forms") -Filter *.form | Sort-Object Name
    $bpmn  = (Join-Path $modelDir $Model)
    $curlArgs = @('-sS', '-X', 'POST', "$base/v2/deployments")
    if ($ProtectedApi) { $curlArgs += @('-u', 'demo:demo') }
    foreach ($f in $forms) { $curlArgs += @('-F', "resources=@$($f.FullName);type=application/json") }
    $curlArgs += @('-F', "resources=@$bpmn;type=application/xml")
    $deployJson = & curl.exe @curlArgs
    try {
        $d = $deployJson | ConvertFrom-Json
        $pd = @($d.deployments | Where-Object { $_.processDefinition }).Count
        $fm = @($d.deployments | Where-Object { $_.form }).Count
        Say "  admin deploy -> deploymentKey=$($d.deploymentKey) processDefs=$pd forms=$fm"
    } catch { Say "  deploy response unparseable" }

    # ---------------------------------------------------------------- 3b. record the real REST paths
    Say ""
    Say "=== 3b. record the real REST paths ==="
    try {
        if ($ProtectedApi) { $docsRaw = & curl.exe -sS -u demo:demo "$base/v3/api-docs" }
        else { $docsRaw = & curl.exe -sS "$base/v3/api-docs" }
        $docsObj = $docsRaw | ConvertFrom-Json
        $allPaths = @($docsObj.paths.PSObject.Properties.Name | Sort-Object)
        $allPaths | Set-Content (Join-Path $evidenceDir "openapi-paths.txt") -Encoding UTF8
        Say "  /v3/api-docs lists $($allPaths.Count) paths"
    } catch { Say "  api-docs unavailable: $($_.Exception.Message)" }

    # ---------------------------------------------------------------- 4-6. same endpoints, different identities
    # Trap: PowerShell 5.1 swallows double quotes in arguments passed to native programs, which makes the JSON invalid ->
    #     the engine replies 400 "Failed to read request", which looks like a refusal but never reached the authorisation decision.
    #     So request bodies are always written to a file first and passed with -d "@file".
    function Invoke-Api {
        param(
            [string]$Label, [string]$Method, [string]$Path, [string]$Body,
            [string]$User, [string]$Password
        )
        $respFile = Join-Path $env:TEMP ("rbac-resp-" + [guid]::NewGuid().ToString("N") + ".json")
        $curl = @('-sS', '-o', $respFile, '-w', '%{http_code}', '-X', $Method)
        if ($User) { $curl += @('-u', "${User}:${Password}") }
        if ($Body) {
            $reqFile = Join-Path $env:TEMP ("rbac-req-" + [guid]::NewGuid().ToString("N") + ".json")
            [IO.File]::WriteAllText($reqFile, $Body, [Text.UTF8Encoding]::new($false))
            $curl += @('-H', 'Content-Type: application/json', '-d', "@$reqFile")
        }
        $curl += "$base$Path"
        $code = (& curl.exe @curl)
        $text = ""
        if (Test-Path $respFile) {
            $text = (Get-Content $respFile -Raw -Encoding UTF8)
            Remove-Item $respFile -Force -ErrorAction SilentlyContinue
        }
        $short = if ($text) { $text -replace '\s+', ' ' } else { '' }
        if ($short.Length -gt 140) { $short = $short.Substring(0, 140) + "..." }
        Say ("  {0,-52} HTTP {1}  {2}" -f $Label, $code, $short)
        return [int]$code
    }

    $page = '{"page":{"limit":5}}'

    Say ""
    Say "=== 4. authentication: anonymous must be refused ==="
    $cAnon = Invoke-Api -Label "anonymous -> /v2/user-tasks/search" -Method POST -Path "/v2/user-tasks/search" -Body $page

    Say ""
    Say "=== 5. authorisation (A): AUTHORIZATION resource - none of our 10 roles holds it ==="
    $cAuthzSec   = Invoke-Api -Label "sec.demo (medical-secretaries)" -Method POST -Path "/v2/authorizations/search" -Body $page -User "sec.demo"   -Password "sec.demo"
    $cAuthzAudit = Invoke-Api -Label "audit.demo (auditor)"           -Method POST -Path "/v2/authorizations/search" -Body $page -User "audit.demo" -Password "audit.demo"
    $cAuthzFin   = Invoke-Api -Label "fin.demo (finance)"             -Method POST -Path "/v2/authorizations/search" -Body $page -User "fin.demo"   -Password "fin.demo"
    $cAuthzAdm   = Invoke-Api -Label "demo (built-in admin)"          -Method POST -Path "/v2/authorizations/search" -Body $page -User "demo"       -Password "demo"

    Say ""
    Say "=== 6. authorisation (B): the same identities, on resources they DO hold ==="
    $cPiSec   = Invoke-Api -Label "sec.demo -> /v2/process-instances/search"   -Method POST -Path "/v2/process-instances/search" -Body $page -User "sec.demo"   -Password "sec.demo"
    $cPiAudit = Invoke-Api -Label "audit.demo -> /v2/process-instances/search" -Method POST -Path "/v2/process-instances/search" -Body $page -User "audit.demo" -Password "audit.demo"
    $cAlAudit = Invoke-Api -Label "audit.demo -> /v2/audit-logs/search"        -Method POST -Path "/v2/audit-logs/search"        -Body $page -User "audit.demo" -Password "audit.demo"
    $cUtSec   = Invoke-Api -Label "sec.demo -> /v2/user-tasks/search"          -Method POST -Path "/v2/user-tasks/search"        -Body $page -User "sec.demo"   -Password "sec.demo"

    # ---------------------------------------------------------------- 7. persistence evidence
    Say ""
    Say "=== 7. read the persisted grant matrix back from the engine H2 database ==="
    & (Join-Path $repoRoot "bpm\camunda\stop-engine.ps1") | Out-Host
    Start-Sleep -Seconds 8

    $h2jar = Get-ChildItem "E:\camunda\c8run-8.10.0-alpha5\camunda-zeebe-8.10.0-alpha5\lib" -Filter "h2-*.jar" -ErrorAction SilentlyContinue | Select-Object -First 1
    $dbFile = Join-Path $runtimeDir "camunda-data\h2db"
    $javaExe = "E:\camunda\c8run-8.10.0-alpha5\jre\bin\java.exe"
    if ($h2jar -and (Test-Path "$dbFile.mv.db")) {
        $url = "jdbc:h2:file:" + ($dbFile -replace '\\', '/')
        $q = [ordered]@{
            'COUNTS'            = 'SELECT (SELECT COUNT(*) FROM USER_) AS USERS, (SELECT COUNT(*) FROM ROLES) AS ROLES, (SELECT COUNT(*) FROM AUTHORIZATIONS) AS AUTHZ, (SELECT COUNT(*) FROM ROLE_MEMBER) AS MEMBERS;'
            'AUDITOR_ROWS'      = "SELECT OWNER_ID, RESOURCE_TYPE, RESOURCE_ID, PERMISSION_TYPE FROM AUTHORIZATIONS WHERE OWNER_ID='auditor' ORDER BY RESOURCE_TYPE;"
            'SEC_ROWS'          = "SELECT OWNER_ID, RESOURCE_TYPE, RESOURCE_ID, PERMISSION_TYPE FROM AUTHORIZATIONS WHERE OWNER_ID='medical-secretaries' ORDER BY RESOURCE_TYPE;"
            'AUTHORIZATION_RES' = "SELECT OWNER_ID, COUNT(*) AS N FROM AUTHORIZATIONS WHERE RESOURCE_TYPE='AUTHORIZATION' GROUP BY OWNER_ID;"
        }
        foreach ($k in $q.Keys) {
            Say ""
            Say "########## $k ##########"
            (& $javaExe -cp $h2jar.FullName org.h2.tools.Shell -url $url -user sa -sql $q[$k] 2>&1) | ForEach-Object { Say $_ }
        }
    } else { Say "  H2 jar or database file not found; skipping." }

    # ---------------------------------------------------------------- 8. verdict
    Say ""
    Say "=== 8. verdict ==="
    $anonExpect = if ($ProtectedApi) { 401 } else { 200 }
    $verdicts = @(
        [pscustomobject]@{ Check = "anonymous -> user-tasks/search";                             Expect = $anonExpect; Actual = $cAnon;       Pass = ($cAnon -eq $anonExpect) },
        [pscustomobject]@{ Check = "sec.demo -> authorizations/search (no grant, must refuse)";   Expect = 403;         Actual = $cAuthzSec;   Pass = ($cAuthzSec -eq 403) },
        [pscustomobject]@{ Check = "audit.demo -> authorizations/search (no grant, must refuse)"; Expect = 403;         Actual = $cAuthzAudit; Pass = ($cAuthzAudit -eq 403) },
        [pscustomobject]@{ Check = "fin.demo -> authorizations/search (no grant, must refuse)";   Expect = 403;         Actual = $cAuthzFin;   Pass = ($cAuthzFin -eq 403) },
        [pscustomobject]@{ Check = "demo/admin -> authorizations/search (has grant)";            Expect = 200;         Actual = $cAuthzAdm;   Pass = ($cAuthzAdm -eq 200) },
        [pscustomobject]@{ Check = "sec.demo -> process-instances/search (has grant)";           Expect = 200;         Actual = $cPiSec;      Pass = ($cPiSec -eq 200) },
        [pscustomobject]@{ Check = "audit.demo -> process-instances/search (has grant)";         Expect = 200;         Actual = $cPiAudit;    Pass = ($cPiAudit -eq 200) },
        [pscustomobject]@{ Check = "audit.demo -> audit-logs/search (has grant)";                Expect = 200;         Actual = $cAlAudit;    Pass = ($cAlAudit -eq 200) },
        [pscustomobject]@{ Check = "sec.demo -> user-tasks/search (has grant)";                  Expect = 200;         Actual = $cUtSec;      Pass = ($cUtSec -eq 200) }
    )
    Say ""
    Say ("  {0,-56} {1,-8} {2,-8} {3}" -f "check", "expect", "actual", "verdict")
    foreach ($v in $verdicts) {
        Say ("  {0,-56} {1,-8} {2,-8} {3}" -f $v.Check, $v.Expect, $v.Actual, $(if ($v.Pass) { "PASS" } else { "FAIL" }))
    }
    $passed = ($verdicts | Where-Object { $_.Pass }).Count
    $refused = ($verdicts | Where-Object { $_.Actual -eq 403 }).Count
    $allowed = ($verdicts | Where-Object { $_.Actual -eq 200 }).Count
    Say ""
    Say "  passed $passed / $($verdicts.Count)   refused $refused   allowed $allowed"

    $transcript -join "`n" | Set-Content (Join-Path $evidenceDir "rbac-enforcement.txt") -Encoding UTF8
    Say ""
    Say "evidence: $(Join-Path $evidenceDir 'rbac-enforcement.txt')"
}

# ===================================================================
#  from verify-h2-persistence.ps1   (-Check persistence)
# ===================================================================
function Invoke-CheckPersistence {
    [CmdletBinding()]
    param(
        [int]$RunSeconds = 22,
        [string]$DatabaseUrl = "jdbc:h2:file:./data/hospital"
    )

    $ErrorActionPreference = "Stop"
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
    $repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
    $workerDir = Join-Path $repoRoot "bpm\workers"
    $evidenceDir = Join-Path $repoRoot "bpm\screenshots\v15"
    New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

    $jar = Join-Path $workerDir "target\hospital-external-workers-1.0.0.jar"
    $java = "C:\Program Files\Eclipse Adoptium\jdk-21.0.6.7-hotspot\bin\java.exe"
    $h2jar = (Get-ChildItem "E:\camunda\c8run-8.10.0-alpha5\camunda-zeebe-8.10.0-alpha5\lib" -Filter "h2-*.jar" |
        Select-Object -First 1).FullName
    $dataDir = Join-Path $workerDir "data"
    $dbPath = Join-Path $dataDir "hospital"
    $shellUrl = "jdbc:h2:file:" + $dbPath.Replace('\', '/')
    $log = @()

    function Say($message) {
        Write-Host $message
        $script:log += $message
    }

    function Invoke-Sql($sql) {
        # An empty password must be **omitted** from -password: PowerShell drops an empty string passed to a native program,
        # so -password swallows the next argument. The SQL must be on one line; a newline makes H2 report Feature not supported.
        & $java -cp $h2jar org.h2.tools.Shell -url $shellUrl -user sa -sql $sql 2>&1
    }

    function Run-Workers($label) {
        Say ""
        Say "################ $label ################"
        $outFile = Join-Path $evidenceDir "workers-$label.out.log"
        $proc = Start-Process -FilePath $java `
            -ArgumentList @("-jar", $jar) `
            -WorkingDirectory $workerDir -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $outFile -RedirectStandardError "$outFile.err"
        Start-Sleep -Seconds $RunSeconds
        if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 3

        # The startup banner already contains the database counts, so they are lifted straight out as evidence.
        Get-Content $outFile -Encoding UTF8 -ErrorAction SilentlyContinue |
            Where-Object { $_ -match 'H2 persistence enabled|business table rows|reference data|role matrix|database ready|schema applied' } |
            ForEach-Object { Say ("  " + $_.Trim()) }
    }

    # ------------------------------------------------------------------ start from a clean database
    Say "=== 0. remove the database files from the previous run ==="
    [void](Stop-CamundaProcesses)   # look up by port; Get-Process java cannot see it on this machine
    Start-Sleep -Seconds 3
    if (Test-Path $dataDir) { Remove-Item $dataDir -Recurse -Force }
    Say "  removed $dataDir"

    # ------------------------------------------------------------------ first run
    Run-Workers "run1"
    Say ""
    Say "--- table counts after the first run ---"
    Invoke-Sql 'SELECT (SELECT COUNT(*) FROM patient) AS PATIENTS, (SELECT COUNT(*) FROM gp_practice) AS PRACTICES, (SELECT COUNT(*) FROM role_permission) AS PERMISSIONS, (SELECT COUNT(*) FROM appointment) AS APPOINTMENTS;' | ForEach-Object { Say ("  " + $_) }

    # Insert one row of business data by hand to simulate something created during the first run that must still be there afterwards
    Say ""
    Say "--- write one row of business data (an appointment) ---"
    Invoke-Sql "MERGE INTO appointment (store_key, reference, appointment_date_time, location) KEY (store_key) VALUES ('DEMO-KEY-1', 'APPT-PERSIST-1', '2026-11-02T09:30:00', 'Oncology Day Unit');" | ForEach-Object { Say ("  " + $_) }

    Start-Sleep -Seconds 2

    # ------------------------------------------------------------------ second run (cold start on the same database)
    Run-Workers "run2"
    Say ""
    Say "--- table counts after the second run (must match the first, with the business data still present) ---"
    Invoke-Sql 'SELECT (SELECT COUNT(*) FROM patient) AS PATIENTS, (SELECT COUNT(*) FROM gp_practice) AS PRACTICES, (SELECT COUNT(*) FROM role_permission) AS PERMISSIONS, (SELECT COUNT(*) FROM appointment) AS APPOINTMENTS;' | ForEach-Object { Say ("  " + $_) }
    Invoke-Sql 'SELECT store_key, reference, location FROM appointment;' | ForEach-Object { Say ("  " + $_) }

    Say ""
    Say "evidence files: $evidenceDir\workers-run1.out.log / workers-run2.out.log"

    $log -join "`n" | Set-Content (Join-Path $evidenceDir "h2-persistence.txt") -Encoding UTF8
    Say "summary written to: $evidenceDir\h2-persistence.txt"
}

# ===================================================================
#  from diagnose-worker-jobs.ps1   (-Check jobs)
# ===================================================================
function Invoke-CheckJobs {
    [CmdletBinding()]
    param(
        [int]$Port = 8080,
        [string]$Python = "",
        [string[]]$Scenario = @("OUT-book", "OUT-no-slot", "OUT-follow-up", "FIN-manual-charge", "TRT-declined-payment"),
        [int]$TimeoutSeconds = 240,
        [int]$ScenarioTimeout = 60
    )

    $ErrorActionPreference = "Stop"
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
    $repoRoot    = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
    $runtimeDir  = Join-Path $repoRoot "_runtime\camunda"
    $evidenceDir = Join-Path $repoRoot "bpm\screenshots\v15"
    $base = "http://localhost:$Port"
    New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

    function Say($m) { Write-Host $m }

    function Resolve-Python {
        param([string]$Explicit)
        if ($Explicit) { return $Explicit }
        foreach ($c in @("python3", "python")) {
            $cmd = Get-Command $c -ErrorAction SilentlyContinue
            if ($cmd) { return $cmd.Source }
        }
        $bundled = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
        if (Test-Path $bundled) { return $bundled }
        throw "Python interpreter not found."
    }

    $pythonExe = Resolve-Python -Explicit $Python
    $javaExe = (Get-Command java -ErrorAction SilentlyContinue).Source
    if (-not $javaExe) { $javaExe = "C:\Program Files\Eclipse Adoptium\jdk-21.0.6.7-hotspot\bin\java.exe" }
    Say "python : $pythonExe"
    Say "java   : $javaExe"

    # The current authorizations switch - the most suspicious variable in this run
    $camYaml = Join-Path $repoRoot "bpm\camunda\application.yaml"
    $authzLines = Select-String -Path $camYaml -Pattern 'authorizations:|enabled:|unprotected-api:' -Encoding UTF8
    Say ""
    Say "=== current Camunda security configuration (relevant lines) ==="
    $authzLines | ForEach-Object { Say ("  {0,4}: {1}" -f $_.LineNumber, $_.Line.Trim()) }

    # ---------------------------------------------------------------- 0. cleanup
    Say ""
    Say "=== 0. cleanup ==="
    [void](Stop-CamundaProcesses)   # look up by port; Get-Process java cannot see it on this machine
    Start-Sleep -Seconds 4
    foreach ($d in 'camunda-data', 'data', 'logs') {
        $t = Join-Path $runtimeDir $d
        if (Test-Path $t) { Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue }
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "logs") | Out-Null
    $workerDb = Join-Path $repoRoot "bpm\workers\data"
    if (Test-Path $workerDb) { Remove-Item $workerDb -Recurse -Force -ErrorAction SilentlyContinue }

    $workerJar = Join-Path $repoRoot "bpm\workers\target\hospital-external-workers-1.0.0.jar"
    if (-not (Test-Path $workerJar)) { throw "worker jar not found: $workerJar" }

    # ---------------------------------------------------------------- 1. start the engine and deploy
    Say ""
    Say "=== 1. start the engine ==="
    # When running the real workers end to end, the WORKERS profile is required: under the RBAC profile (authorizations.enabled: true)
    # unauthenticated gRPC workers cannot claim any jobs; see L-1 in docs/14-feedback-response.md.
    & (Join-Path $repoRoot "bpm\camunda\start-engine.ps1") -Detached -Port $Port -WorkersProfile | Out-Host

    Say "=== 2. wait for readiness ==="
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        try { Invoke-RestMethod -Uri "$base/v2/topology" -TimeoutSec 5 | Out-Null; $ready = $true; break } catch { }
        if (-not (Test-CamundaListening)) { break }   # judged by port; not by Get-Process java
    }
    Say "  ready = $ready"
    if (-not $ready) { Say "engine did not start; exiting."; exit 1 }

    Say "=== 3. deploy ==="
    $modelDir = Join-Path $repoRoot "bpm\model"
    $forms = Get-ChildItem (Join-Path $modelDir "forms") -Filter *.form | Sort-Object Name
    $bpmn  = Join-Path $modelDir "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn"
    $curlArgs = @('-sS', '-X', 'POST', "$base/v2/deployments")
    foreach ($f in $forms) { $curlArgs += @('-F', "resources=@$($f.FullName);type=application/json") }
    $curlArgs += @('-F', "resources=@$bpmn;type=application/xml")
    & curl.exe @curlArgs | Out-Null
    Say "  deployment submitted"

    # ---------------------------------------------------------------- 4. start the workers
    Say ""
    Say "=== 4. start the real workers ==="
    $workerLog = Join-Path $evidenceDir "diagnose-workers.log"
    $workerErr = Join-Path $evidenceDir "diagnose-workers.err.log"
    $workerProc = Start-Process -FilePath $javaExe `
        -ArgumentList @("-jar", $workerJar) `
        -WorkingDirectory (Join-Path $repoRoot "bpm\workers") `
        -RedirectStandardOutput $workerLog -RedirectStandardError $workerErr `
        -PassThru -WindowStyle Hidden
    Say "  worker pid = $($workerProc.Id)"
    Start-Sleep -Seconds 30
    Say "  worker alive = $(-not $workerProc.HasExited)"

    function Show-WorkerLog([string]$label) {
        Say ""
        Say "=== worker log: $label ==="
        if (-not (Test-Path $workerLog)) { Say "  (no log file)"; return }
        $all = Get-Content $workerLog -Encoding UTF8
        Say "  lines = $($all.Count)"
        foreach ($pat in @('COMPLETED', 'FAILED', 'BPMN ERROR', 'Waiting for jobs', 'Subscribing')) {
            $n = ($all | Select-String -Pattern $pat).Count
            Say ("  {0,-18} {1}" -f $pat, $n)
        }
        Say "  --- last 25 lines ---"
        $all | Select-Object -Last 25 | ForEach-Object { Say ("  | " + $_.Substring(0, [Math]::Min(180, $_.Length))) }
    }

    Show-WorkerLog "after start-up, before the scenarios"

    # ---------------------------------------------------------------- 5. run only the named scenarios
    Say ""
    Say "=== 5. running only these $($Scenario.Count) scenarios ==="
    $args5 = @("auto_driver.py", "--timeout", "$ScenarioTimeout")
    foreach ($s in $Scenario) { $args5 += @("--scenario", $s) }
    Push-Location (Join-Path $repoRoot "bpm\tools")
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $pythonExe @args5 2>&1 | ForEach-Object { Say ("  | " + $_) }
    } finally {
        $ErrorActionPreference = $prevEap
        Pop-Location
    }

    Show-WorkerLog "after the scenarios have run"

    # ---------------------------------------------------------------- 6. wrap up
    Say ""
    Say "=== 6. stop ==="
    if ($workerProc -and -not $workerProc.HasExited) { Stop-Process -Id $workerProc.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
    & (Join-Path $repoRoot "bpm\camunda\stop-engine.ps1") | Out-Host
    Say "evidence: $workerLog"
}


# ===================================================================
#  dispatcher: call the matching check function for -Check
# ===================================================================
switch ($Check) {
    "engine" {
        Invoke-CheckEngine -Model $Model -Port $Port -TimeoutSeconds $TimeoutSeconds -KeepState:$KeepState
    }
    "e2e" {
        Invoke-CheckEndToEnd -Model $Model -Port $Port -TimeoutSeconds $TimeoutSeconds -ScenarioTimeout $effectiveScenarioTimeout
    }
    "rbac" {
        Invoke-CheckRbac -Model $Model -Port $Port -TimeoutSeconds $TimeoutSeconds -ProtectedApi:$ProtectedApi
    }
    "persistence" {
        Invoke-CheckPersistence
    }
    "jobs" {
        if ($Scenario.Count -gt 0) {
            Invoke-CheckJobs -Port $Port -TimeoutSeconds $TimeoutSeconds -ScenarioTimeout $effectiveScenarioTimeout -Scenario $Scenario
        } else {
            Invoke-CheckJobs -Port $Port -TimeoutSeconds $TimeoutSeconds -ScenarioTimeout $effectiveScenarioTimeout
        }
    }
}
