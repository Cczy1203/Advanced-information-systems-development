<#
.SYNOPSIS
    Deploy the BPMN model and all Camunda forms to an engine that is **already running**; starting and stopping the engine is not this script's job.

.DESCRIPTION
    The repository previously had only `bpm/tools/deploy.sh` (a bash script written for macOS), which cannot be used on Windows;
    and although `verify.ps1 -Check engine` also deploys, it **stops** the engine at the end - that is for verification
    and is not suitable for "I want to run the system and then click through it in a browser".

    So this script does one thing only: deploy. You have to start the engine yourself first (`bpm\camunda\start-engine.ps1`).

    Two points to remember:
      1. **The model and its 36 forms must be submitted in the same batch.** Every user task carries
         `zeebe:formDefinition formId`; submitting the model without the forms fails deployment validation
         (observed as a 400 INVALID_ARGUMENT). Submitting the forms alone is fine.
      2. When the engine already holds a process definition of the same name, deploying again is **allowed**: it creates a new version
         (version 2, 3, ...) and reports no error.

.PARAMETER Url
    Base address of the engine; defaults to http://localhost:8080.

.PARAMETER Model
    Name of the model file to deploy (relative to bpm\model); defaults to the v14.0 model reviewed by the tutor.

.EXAMPLE
    pwsh -File bpm\tools\deploy-model.ps1
#>
[CmdletBinding()]
param(
    [string]$Url = "http://localhost:8080",
    [string]$Model = "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$modelDir = Join-Path $repoRoot "bpm\model"
$bpmn = Join-Path $modelDir $Model

if (-not (Test-Path $bpmn)) { throw "Model file not found: $bpmn" }

# Confirm the engine is alive first; otherwise curl throws a pile of unhelpful errors
try {
    Invoke-RestMethod -Uri "$Url/v2/topology" -TimeoutSec 5 | Out-Null
} catch {
    throw "The engine did not respond ($Url). Start it first with bpm\camunda\start-engine.ps1."
}

$forms = Get-ChildItem (Join-Path $modelDir "forms") -Filter *.form | Sort-Object Name
Write-Host "Model      : $Model  ($((Get-Item $bpmn).Length) bytes)"
Write-Host "Form count : $($forms.Count)"
Write-Host "Engine     : $Url"
Write-Host "Submitting ..."

# curl multipart form: the forms first, then the model (the order does not affect the result, but this matches the verify script)
$curlArgs = @('-sS', '-X', 'POST', "$Url/v2/deployments")
foreach ($f in $forms) {
    $curlArgs += @('-F', "resources=@$($f.FullName);type=application/json")
}
$curlArgs += @('-F', "resources=@$bpmn;type=application/xml")

$json = & curl.exe @curlArgs
try {
    $d = $json | ConvertFrom-Json
} catch {
    Write-Host "Deployment response could not be parsed:" -ForegroundColor Red
    Write-Host $json
    exit 1
}

if ($d.detail) {
    Write-Host "Deployment failed:" -ForegroundColor Red
    Write-Host "  $($d.detail)"
    exit 1
}

$procs = @($d.deployments | Where-Object { $_.processDefinition })
$fms = @($d.deployments | Where-Object { $_.form })
Write-Host ""
Write-Host "Deployment succeeded" -ForegroundColor Green
Write-Host "  deployment key : $($d.deploymentKey)"
Write-Host "  Process definitions : $($procs.Count)"
Write-Host "  Forms               : $($fms.Count)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1) Start the workers (in another window): java -jar bpm\workers\target\hospital-external-workers-1.0.0.jar"
Write-Host "  2) Open $Url/tasklist in a browser - check the Processes tab first; it should list the processes above"
Write-Host "  3) Use Start process there to start one, or start it with a message (see the README)"
