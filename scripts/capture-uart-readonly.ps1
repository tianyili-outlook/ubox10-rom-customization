[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(?i:COM)[0-9]+$')]
    [string]$PortName,

    [ValidateRange(300, 3000000)]
    [int]$BaudRate = 115200,

    [ValidateRange(10, 6000)]
    [int]$DurationSeconds = 90,

    [string]$OutputRoot,

    [string]$AdapterDescription = 'FTDI FT232RL',

    [string]$DeviceState = 'UBOX10 UART receive-only capture',

    [switch]$GenerateChecksums,

    [switch]$ReceiveOnlyWiringConfirmed
)

# U3 receive-only UART collector.
# The script never calls SerialPort.Write and disables DTR/RTS. Physical safety
# still depends on leaving adapter TXD and every VCC pin disconnected.
$ErrorActionPreference = 'Stop'

if (-not $ReceiveOnlyWiringConfirmed) {
    throw 'Refusing to open the port. Confirm target GND -> adapter GND and target TX -> adapter RXD only, then add -ReceiveOnlyWiringConfirmed.'
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot 'logs\device'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repositoryRoot $OutputRoot
}

$normalizedPort = $PortName.ToUpperInvariant()
$availablePorts = @([System.IO.Ports.SerialPort]::GetPortNames())
if ($normalizedPort -notin $availablePorts) {
    throw "Serial port $normalizedPort is not currently present. Available ports: $($availablePorts -join ', ')"
}

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputDir = Join-Path $OutputRoot $runId
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$rawPath = Join-Path $outputDir "uart-$($normalizedPort.ToLowerInvariant())-$BaudRate.raw.bin"
$textPath = Join-Path $outputDir "uart-$($normalizedPort.ToLowerInvariant())-$BaudRate.txt"
$metadataPath = Join-Path $outputDir 'uart-capture.json'
$hashPath = Join-Path $outputDir 'SHA256SUMS.txt'

$serialPort = [System.IO.Ports.SerialPort]::new(
    $normalizedPort,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serialPort.Handshake = [System.IO.Ports.Handshake]::None
$serialPort.DtrEnable = $false
$serialPort.RtsEnable = $false
$serialPort.ReadTimeout = 250
$serialPort.WriteTimeout = 250
$serialPort.ReadBufferSize = 65536

$startedAt = Get-Date
$endedAt = $null
$bytesReceived = [int64]0
$captureError = $null
$rawStream = $null
$stopwatch = $null
$terminationReason = 'DurationElapsed'
$manualStopAvailable = $false
$manualStopSetupError = $null
$originalTreatControlCAsInput = $null
$buffer = New-Object byte[] 4096
$displayEncoding = [System.Text.Encoding]::ASCII

try {
    $rawStream = [System.IO.File]::Open(
        $rawPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::Read
    )
    $serialPort.Open()

    try {
        $originalTreatControlCAsInput = [Console]::TreatControlCAsInput
        [Console]::TreatControlCAsInput = $true
        $manualStopAvailable = $true
    }
    catch {
        $manualStopSetupError = $_.Exception.Message
    }

    Write-Output "UART receive-only capture armed on $normalizedPort at $BaudRate 8N1."
    Write-Output 'Power on UBOX10 now.'
    if ($manualStopAvailable) {
        Write-Output 'Press Ctrl+C or Q to stop safely; received data and metadata will still be saved.'
    }
    else {
        Write-Warning "Manual stop keys are unavailable in this host: $manualStopSetupError"
    }
    Write-Output 'Keyboard input is consumed locally and is never sent to the serial port.'

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($stopwatch.Elapsed.TotalSeconds -lt $DurationSeconds) {
        if ($manualStopAvailable -and [Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            $isCtrlC = (
                $key.Key -eq [ConsoleKey]::C -and
                ($key.Modifiers -band [ConsoleModifiers]::Control)
            )
            if ($isCtrlC) {
                $terminationReason = 'ManualCtrlC'
                break
            }
            if ($key.Key -eq [ConsoleKey]::Q) {
                $terminationReason = 'ManualQ'
                break
            }
        }

        $available = $serialPort.BytesToRead
        if ($available -le 0) {
            Start-Sleep -Milliseconds 20
            continue
        }

        $requested = [Math]::Min($available, $buffer.Length)
        $read = $serialPort.Read($buffer, 0, $requested)
        if ($read -gt 0) {
            $rawStream.Write($buffer, 0, $read)
            $rawStream.Flush()
            $bytesReceived += $read
            [Console]::Write($displayEncoding.GetString($buffer, 0, $read))
        }
    }
}
catch {
    $captureError = $_.Exception.Message
    $terminationReason = 'CaptureError'
}
finally {
    $endedAt = Get-Date
    if ($null -ne $stopwatch) {
        $stopwatch.Stop()
    }
    if ($serialPort.IsOpen) {
        $serialPort.Close()
    }
    $serialPort.Dispose()
    if ($null -ne $rawStream) {
        $rawStream.Dispose()
    }
    if ($manualStopAvailable) {
        [Console]::TreatControlCAsInput = $originalTreatControlCAsInput
    }
}

if (Test-Path -LiteralPath $rawPath -PathType Leaf) {
    $rawBytes = [System.IO.File]::ReadAllBytes($rawPath)
    $latin1 = [System.Text.Encoding]::GetEncoding(28591)
    [System.IO.File]::WriteAllText(
        $textPath,
        $latin1.GetString($rawBytes),
        [System.Text.UTF8Encoding]::new($false)
    )
}

$metadata = [ordered]@{
    SchemaVersion = 2
    StartedAt = $startedAt.ToString('o')
    EndedAt = $endedAt.ToString('o')
    DurationRequestedSeconds = $DurationSeconds
    DurationActualSeconds = [Math]::Round(($endedAt - $startedAt).TotalSeconds, 3)
    TerminationReason = $terminationReason
    ManualStopAvailable = $manualStopAvailable
    ManualStopKeys = @('Ctrl+C', 'Q')
    ManualStopSetupError = $manualStopSetupError
    PortName = $normalizedPort
    BaudRate = $BaudRate
    DataBits = 8
    Parity = 'None'
    StopBits = 1
    FlowControl = 'None'
    DtrEnabled = $false
    RtsEnabled = $false
    AdapterDescription = $AdapterDescription
    DeviceState = $DeviceState
    OutputDirectory = $outputDir
    Wiring = @(
        'UBOX10 J21 GND -> FT232RL GND',
        'UBOX10 J21 TX -> FT232RL RXD',
        'UBOX10 J21 RX disconnected',
        'FT232RL TXD disconnected',
        'All VCC/5V/3V3 pins disconnected'
    )
    BytesReceived = $bytesReceived
    RawFile = if (Test-Path -LiteralPath $rawPath) { $rawPath } else { $null }
    TextFile = if (Test-Path -LiteralPath $textPath) { $textPath } else { $null }
    ChecksumsGenerated = [bool]$GenerateChecksums
    CaptureError = $captureError
}
$metadata | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $metadataPath -Encoding UTF8

if ($GenerateChecksums) {
    $hashLines = Get-ChildItem -LiteralPath $outputDir -File |
        Where-Object { $_.Name -ne 'SHA256SUMS.txt' } |
        ForEach-Object {
            $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            "{0}  {1}" -f $hash.Hash, $hash.Path
        }
    $hashLines | Set-Content -LiteralPath $hashPath -Encoding UTF8
}

Write-Output ''
Write-Output "UART evidence written to: $outputDir"
Write-Output "Bytes received: $bytesReceived"
Write-Output "Termination reason: $terminationReason"
if ($GenerateChecksums) {
    Write-Output "Checksums written to: $hashPath"
}
if ($captureError) {
    throw "UART capture failed after preserving available evidence: $captureError"
}
