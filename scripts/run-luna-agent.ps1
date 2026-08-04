[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Task,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string[]]$AllowedPath,

    [string]$Id,

    [switch]$Write,

    [string]$Worktree
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$model = "gpt-5.6-luna"
$reasoningEffort = "max"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$jobsRoot = Join-Path $repoRoot "tmp\agent-jobs"
$jobDirectory = $null
$codexExitCode = $null
$effectiveModel = $null
$failureReasons = New-Object System.Collections.Generic.List[string]
$startedUtc = [DateTime]::UtcNow.ToString("o")
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [AllowEmptyString()][string]$Content
    )

    [IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )

    Write-Utf8File -Path $Path -Content (($Value | ConvertTo-Json -Depth 8) + [Environment]::NewLine)
}

function Normalize-RelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $normalized = $Path.Trim().Replace("\", "/")
    while ($normalized.StartsWith("./", [StringComparison]::Ordinal)) {
        $normalized = $normalized.Substring(2)
    }
    $normalized = $normalized.TrimEnd("/")

    if ([string]::IsNullOrWhiteSpace($normalized) -or
        [IO.Path]::IsPathRooted($normalized) -or
        $normalized -match "(^|/)\.\.(/|$)" -or
        $normalized -match "[\*\?\[\]]") {
        throw "Allowed paths must be exact repository-relative paths: $Path"
    }

    return $normalized
}

function Get-GitStatusText {
    param([Parameter(Mandatory = $true)][string]$Root)

    $lines = @(& git -c core.quotePath=false -C $Root status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed for $Root"
    }
    return ($lines -join "`n")
}

function Get-ChangedPaths {
    param([Parameter(Mandatory = $true)][string]$Root)

    $tracked = @(& git -c core.quotePath=false -C $Root diff --name-only HEAD --)
    if ($LASTEXITCODE -ne 0) {
        throw "git diff failed for $Root"
    }
    $untracked = @(& git -c core.quotePath=false -C $Root ls-files --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed for $Root"
    }
    return @($tracked + $untracked | Where-Object { $_ } | Sort-Object -Unique)
}

function Test-AllowedChange {
    param(
        [Parameter(Mandatory = $true)][string]$ChangedPath,
        [Parameter(Mandatory = $true)][string[]]$AllowedPaths
    )

    $candidate = $ChangedPath.Replace("\", "/")
    foreach ($allowed in $AllowedPaths) {
        if ($candidate.Equals($allowed, [StringComparison]::OrdinalIgnoreCase) -or
            $candidate.StartsWith($allowed.TrimEnd("/") + "/", [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Write-FailureResult {
    param([string]$Reason)

    if ($Reason) {
        $failureReasons.Add($Reason)
    }
    if ($jobDirectory -and (Test-Path -LiteralPath $jobDirectory)) {
        if ($null -eq $codexExitCode) {
            $codexExitCode = 1
        }
        foreach ($recordName in @("output.txt", "events.jsonl", "stderr.log")) {
            $recordPath = Join-Path $jobDirectory $recordName
            if (-not (Test-Path -LiteralPath $recordPath)) {
                Write-Utf8File -Path $recordPath -Content ""
            }
        }
        Write-Utf8File -Path (Join-Path $jobDirectory "exit-code.txt") -Content ([string]$codexExitCode)
        Write-Utf8File -Path (Join-Path $jobDirectory "effective-model.txt") -Content $(if ($effectiveModel) { $effectiveModel } else { "UNAVAILABLE" })
        $result = [ordered]@{
            schema_version = 1
            id = $Id
            status = "LUNA_DISPATCH_FAILED"
            requested_model = $model
            reasoning_effort = $reasoningEffort
            effective_model = $effectiveModel
            exit_code = $codexExitCode
            failure_reasons = @($failureReasons)
            completed_utc = [DateTime]::UtcNow.ToString("o")
            output = "output.txt"
            logs = [ordered]@{
                events = "events.jsonl"
                stderr = "stderr.log"
            }
        }
        Write-JsonFile -Path (Join-Path $jobDirectory "result.json") -Value $result
    }
    Write-Output "LUNA_DISPATCH_FAILED"
    exit 1
}

try {
    if ([string]::IsNullOrWhiteSpace($Id)) {
        $Id = "{0}-{1}" -f [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ"), ([Guid]::NewGuid().ToString("N").Substring(0, 8))
    }
    if ($Id -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") {
        throw "Job id must contain only letters, digits, dots, underscores, or hyphens"
    }

    $normalizedAllowedPaths = @($AllowedPath | ForEach-Object { Normalize-RelativePath -Path $_ } | Sort-Object -Unique)
    if ($normalizedAllowedPaths.Count -eq 0) {
        throw "At least one allowed path is required"
    }

    $executionRoot = $repoRoot
    $sandbox = "read-only"
    if ($Write) {
        if ([string]::IsNullOrWhiteSpace($Worktree)) {
            throw "Write mode requires -Worktree pointing to a separate clean Git worktree"
        }
        $executionRoot = (Resolve-Path -LiteralPath $Worktree).Path
        $reportedRoot = (& git -C $executionRoot rev-parse --show-toplevel 2>$null)
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($reportedRoot)) {
            throw "Write root is not a Git worktree"
        }
        $reportedRoot = [IO.Path]::GetFullPath($reportedRoot.Trim())
        if (-not $reportedRoot.Equals([IO.Path]::GetFullPath($executionRoot), [StringComparison]::OrdinalIgnoreCase)) {
            throw "-Worktree must point to the worktree root"
        }
        if ($reportedRoot.Equals([IO.Path]::GetFullPath($repoRoot), [StringComparison]::OrdinalIgnoreCase)) {
            throw "Write mode refuses the primary checkout; provide an isolated worktree"
        }
        if (Get-GitStatusText -Root $executionRoot) {
            throw "Write worktree must be clean before dispatch"
        }
        $sandbox = "workspace-write"
    } elseif (-not [string]::IsNullOrWhiteSpace($Worktree)) {
        throw "-Worktree is accepted only with -Write"
    }

    foreach ($allowed in $normalizedAllowedPaths) {
        $fullPath = [IO.Path]::GetFullPath((Join-Path $executionRoot $allowed.Replace("/", "\")))
        $rootPrefix = [IO.Path]::GetFullPath($executionRoot).TrimEnd("\") + "\"
        if (-not $fullPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Allowed path escapes the execution root: $allowed"
        }
        if (-not $Write -and -not (Test-Path -LiteralPath $fullPath)) {
            throw "Read-only allowed path does not exist: $allowed"
        }
    }

    New-Item -ItemType Directory -Path $jobsRoot -Force | Out-Null
    $jobDirectory = Join-Path $jobsRoot $Id
    if (Test-Path -LiteralPath $jobDirectory) {
        throw "Job already exists: $Id"
    }
    New-Item -ItemType Directory -Path $jobDirectory | Out-Null

    $outputPath = Join-Path $jobDirectory "output.txt"
    $eventsPath = Join-Path $jobDirectory "events.jsonl"
    $stderrPath = Join-Path $jobDirectory "stderr.log"
    $promptPath = Join-Path $jobDirectory "prompt.txt"
    $exitCodePath = Join-Path $jobDirectory "exit-code.txt"
    $effectiveModelPath = Join-Path $jobDirectory "effective-model.txt"

    $codexArguments = @(
        "exec",
        "--ignore-user-config",
        "--strict-config",
        "--ephemeral",
        "--model", $model,
        "--sandbox", $sandbox,
        "--config", "model_reasoning_effort=max",
        "--json",
        "--color", "never",
        "-"
    )

    $contract = [ordered]@{
        schema_version = 1
        id = $Id
        task = $Task
        allowed_paths = $normalizedAllowedPaths
        mode = $(if ($Write) { "write" } else { "read-only" })
        sandbox = $sandbox
        execution_root = $executionRoot
        requested_model = $model
        reasoning_effort = $reasoningEffort
        created_utc = $startedUtc
        command = @("codex") + $codexArguments
    }
    Write-JsonFile -Path (Join-Path $jobDirectory "task.json") -Value $contract

    $allowedList = ($normalizedAllowedPaths | ForEach-Object { "- $_" }) -join "`n"
    $workerPrompt = @"
You are a bounded repository worker running in an independent codex exec process.
Use exactly GPT-5.6 Luna with maximum reasoning. Do not fall back to or substitute another model.
Mode: $($contract.mode)
You may access only these repository-relative paths:
$allowedList

Task:
$Task

Do not expand scope. In read-only mode, do not modify any file. In write mode, modify only the listed paths.
Return a concise result to the orchestrator.
"@
    Write-Utf8File -Path $promptPath -Content $workerPrompt

    $statusBefore = Get-GitStatusText -Root $executionRoot
    $codexPath = (@(Get-Command codex -CommandType Application -ErrorAction Stop)[0]).Source
    $codexProcess = Start-Process -FilePath $codexPath -ArgumentList $codexArguments -WorkingDirectory $executionRoot -RedirectStandardInput $promptPath -RedirectStandardOutput $eventsPath -RedirectStandardError $stderrPath -WindowStyle Hidden -Wait -PassThru
    $codexExitCode = $codexProcess.ExitCode
    Write-Utf8File -Path $exitCodePath -Content ([string]$codexExitCode)

    $agentMessages = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath $eventsPath) {
        foreach ($eventLine in [IO.File]::ReadLines($eventsPath, $utf8NoBom)) {
            try {
                $event = $eventLine | ConvertFrom-Json
                if ($event.type -eq "item.completed" -and $event.item.type -eq "agent_message" -and $event.item.text) {
                    $agentMessages.Add([string]$event.item.text)
                }
            } catch {
                # Preserve unrecognized event lines in events.jsonl; they remain diagnostic evidence.
            }
        }
    }
    if ($agentMessages.Count -gt 0) {
        Write-Utf8File -Path $outputPath -Content $agentMessages[$agentMessages.Count - 1]
    } else {
        Write-Utf8File -Path $outputPath -Content ""
    }

    if ($codexExitCode -eq 0) {
        $effectiveModel = $model
        Write-Utf8File -Path $effectiveModelPath -Content $effectiveModel
    } else {
        Write-Utf8File -Path $effectiveModelPath -Content "UNAVAILABLE"
        $failureReasons.Add("codex exec exited with code $codexExitCode")
    }

    if ($codexExitCode -eq 0 -and $agentMessages.Count -eq 0) {
        $failureReasons.Add("codex exec succeeded without an agent output message")
    }

    if ($Write) {
        $changedPaths = @(Get-ChangedPaths -Root $executionRoot)
        foreach ($changedPath in $changedPaths) {
            if (-not (Test-AllowedChange -ChangedPath $changedPath -AllowedPaths $normalizedAllowedPaths)) {
                $failureReasons.Add("write outside allowed paths: $changedPath")
            }
        }
    } else {
        $statusAfter = Get-GitStatusText -Root $executionRoot
        if ($statusAfter -ne $statusBefore) {
            $failureReasons.Add("read-only job changed repository status")
        }
    }

    if ($failureReasons.Count -gt 0) {
        Write-FailureResult
    }

    $result = [ordered]@{
        schema_version = 1
        id = $Id
        status = "OK"
        requested_model = $model
        reasoning_effort = $reasoningEffort
        effective_model = $effectiveModel
        model_verification = "forced --model argument with user config ignored; no fallback path"
        exit_code = $codexExitCode
        allowed_paths = $normalizedAllowedPaths
        completed_utc = [DateTime]::UtcNow.ToString("o")
        output = "output.txt"
        logs = [ordered]@{
            events = "events.jsonl"
            stderr = "stderr.log"
        }
    }
    Write-JsonFile -Path (Join-Path $jobDirectory "result.json") -Value $result
    Write-Output "LUNA_DISPATCH_OK"
    Write-Output $jobDirectory
    exit 0
} catch {
    Write-FailureResult -Reason $_.Exception.Message
}
