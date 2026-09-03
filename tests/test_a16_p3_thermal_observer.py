"""Safety and contract locks for the Android 16 P3 thermal observer."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
OBSERVER = ROOT / "scripts/collect-a16-p3-thermal-observability.ps1"
PLAN = (
    ROOT
    / "docs/m8/device-tests/20260903-a16-p3-thermal-4k30-plan/README.md"
)


def _source() -> str:
    return OBSERVER.read_text(encoding="utf-8")


def _device_command_block() -> str:
    source = _source()
    return source[source.index("$IdentityCommand ="): source.index("$AllDeviceSpecs =")]


def test_interface_is_explicit_bounded_and_host_side() -> None:
    source = _source()
    assert "[Parameter(Mandatory = $true)]" in source
    assert "[string]$Endpoint" in source
    assert "^[A-Za-z0-9._-]+:7896$" in source
    assert "C:\\platform-tools\\adb.exe" in source
    assert "192.168.1." not in source
    assert "[ValidateSet('Discovery', 'Sample')]" in source
    assert "[ValidateRange(1, 5)]" in source
    assert "[int]$SampleIntervalSeconds = 2" in source
    assert "[ValidateRange(5, 120)]" in source
    assert "[int]$DurationSeconds = 60" in source
    assert "UBOX10-A16-P3-THERMAL-$RunId" in source
    assert "GetFolderPath('UserProfile')" in source
    assert "'Downloads'" in source
    assert "Start-Sleep -Seconds $SampleIntervalSeconds" in source


def test_dynamic_observability_and_no_fixed_zone_assumption() -> None:
    commands = _device_command_block()
    assert "/sys/class/thermal/thermal_zone*" in commands
    assert "/sys/class/thermal/cooling_device*" in commands
    assert "/sys/devices/system/cpu/cpufreq/policy*" in commands
    assert "/sys/class/devfreq/*" in commands
    assert "trip_point_*_temp" in commands
    assert "trip_point_*_type" in commands
    assert "scaling_cur_freq" in commands
    assert "cur_state" in commands
    assert "ve_info" in commands
    assert "thermal_zone0" not in commands


def test_device_commands_are_strictly_observational() -> None:
    commands = _device_command_block()
    forbidden = (
        r"\breboot\b", r"\broot\b", r"\bunroot\b", r"\bremount\b",
        r"\b(?:disable|enable)-verity\b", r"(?:^|[;\s])su(?:\s|$)",
        r"\bsetprop\b", r"\bsettings\s+(?:put|delete)\b",
        r"\bdevice_config\s+(?:put|delete)\b",
        r"\bsvc\s+(?:wifi|data|power)\b",
        r"\bcmd\s+(?:wifi|connectivity|power|package)\b",
        r"\bpm\s+(?:install|uninstall|disable|enable|clear|grant|revoke)\b",
        r"\bam\s+(?:force-stop|kill|start)\b",
        r"\binput\s+(?:keyevent|tap|swipe|text)\b",
        r"(?:^|[;\s])(?:rm|mv|cp|mkdir|touch|chmod|chown|mount|umount)(?:\s|$)",
        r"\blogcat\b[^;\r\n]*\s-c(?:\s|$)",
        r"\b(?:kill|killall|pkill|stop|start)\b",
        r"\b(?:monkey|screenrecord|bugreport|stress-ng)\b",
        r"\b(?:scaling_min_freq|scaling_max_freq|scaling_governor)\s*=",
        r">|>>|\btee\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, commands, flags=re.IGNORECASE) is None, pattern

    assert "logcat -b all -d" in commands
    assert "cat /proc/sys/kernel/random/boot_id" in commands
    assert "playback" not in commands.lower()


def test_command_failures_and_expected_empty_are_preserved() -> None:
    source = _source()
    assert "PERMISSION_DENIED" in source
    assert "NOT_AVAILABLE" in source
    assert "COMMAND_FAILED" in source
    assert "TIMEOUT" in source
    assert "expectedEmptyExitCodes=@(1)" in source
    classifier = source[source.index("function Get-ResultClass"):
                        source.index("function Invoke-CapturedCommand")]
    assert classifier.index("$Result.ExitCode -in $ExpectedEmptyExitCodes") < (
        classifier.index("$Result.ExitCode -ne 0")
    )
    assert "[string]::IsNullOrWhiteSpace($Result.Stderr)" in classifier
    assert "expected_empty_exit_codes = @($ExpectedEmptyExitCodes)" in source
    assert "RedirectStandardError = $true" in source
    assert "timed_out = $Result.TimedOut" in source


def test_manifest_and_no_automated_device_action() -> None:
    source = _source()
    assert "SHA256SUMS.txt" in source
    assert "Get-FileHash -Algorithm SHA256" in source
    assert "device_contract=READ_ONLY" in source
    assert "playback_control=NONE_MANUAL_EXTERNAL_ONLY" in source
    assert "automated_abort_or_power_action=NONE" in source
    assert "No device state or media playback was controlled" in source


def test_plan_governance_and_scope() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    assert "PARTIAL OBSERVABILITY — SHORT SMOKE ONLY" in plan
    assert "P3-A" in plan and "PHYSICAL CAPTURE PENDING" in plan
    assert "P3-B" in plan and "NOT AUTHORIZED" in plan
    assert "Main10" in plan and "HDR" in plan
    assert "BITSTREAM / PROFILE REJECTION" in plan
    assert "SKIA / EGL" in plan
    assert "r8" in plan and "NOT AUTHORIZED / NOT BUILT" in plan
    assert "P2" in plan and "COMPLETE" in plan
    assert "audio P1" in plan and "CLOSED" in plan


def test_powershell_parser_and_embedded_self_test_if_available() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("pwsh is unavailable; static source-level safety tests cover this VM")
    parse = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{OBSERVER}', [ref]$null, [ref]$e); if ($e.Count) {{ $e; exit 1 }}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert parse.returncode == 0, parse.stdout + parse.stderr
    self_test = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(OBSERVER), "-Endpoint", "example:7896", "-SelfTest"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert self_test.returncode == 0, self_test.stdout + self_test.stderr
    assert "command safety: PASS" in self_test.stdout
