"""Safety and governance locks for the one-shot Android 16 P2 collector."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts/collect-a16-p2-audit.ps1"


def _source() -> str:
    return COLLECTOR.read_text(encoding="utf-8")


def _device_spec_block() -> str:
    source = _source()
    return source[source.index("$T0Specs = @("):source.index("$AllDeviceSpecs =")]


def _spec_lines(name: str) -> list[str]:
    return [line for line in _device_spec_block().splitlines() if f"name='{name}'" in line]


def _powershell_pattern(variable: str) -> str:
    match = re.search(rf"^\${variable} = '([^']+)'$", _source(), flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


def _comparable(lines: list[str]) -> list[str]:
    boot_id = re.compile(_powershell_pattern("BootIdPattern"))
    process = re.compile(_powershell_pattern("CriticalProcessPattern"))
    return sorted(line for line in lines if boot_id.fullmatch(line) or process.fullmatch(line))


def test_collector_interface_and_host_evidence_contract() -> None:
    source = _source()
    assert "[string]$Endpoint" in source
    assert "^[A-Za-z0-9._-]+:7896$" in source
    assert "C:\\platform-tools\\adb.exe" in source
    assert "192.168.1." not in source
    assert "UBOX10-A16-P2-AUDIT-$RunId" in source
    assert "GetFolderPath('UserProfile')" in source
    assert "'Downloads'" in source
    assert "[int]$SteadyStateWaitSeconds = 180" in source
    assert "[int]$CommandTimeoutSeconds = 60" in source
    assert "Invoke-External" in source
    assert "TimedOut" in source
    assert "COMMAND-STATUS.json" in source
    assert "PERMISSION_DENIED" in source
    assert "NOT_AVAILABLE" in source
    assert "COMMAND_FAILED" in source
    assert "SHA256SUMS.txt" in source
    assert "Get-FileHash -Algorithm SHA256" in source


def test_two_timepoints_and_no_automatic_judgment() -> None:
    source = _source()
    assert "$T0Specs = @(" in source
    assert "$T1Specs = @(" in source
    assert "10-BootSnapshot-T0" in source
    assert "A0-SteadyState-T1" in source
    assert "Start-Sleep -Seconds $SteadyStateWaitSeconds" in source
    assert "critical-pid-diff.txt" in source
    assert "Compare-Object" in source
    assert "no_automated_pass_fail=true" in source
    assert "COLLECTION_COMPLETE_ANALYSIS_PENDING" in source


def test_critical_identity_excludes_elapsed_but_full_census_retains_it() -> None:
    critical = _spec_lines("critical-state")
    assert len(critical) == 2
    for line in critical:
        assert "ps -A -o PID,PPID,NAME" in line
        assert "ELAPSED" not in line
        assert 'printf "BOOT_ID="; cat /proc/sys/kernel/random/boot_id' in line
    census = _spec_lines("process-census")
    assert len(census) == 2
    assert all("ELAPSED" in line for line in census)
    assert "T0/T1 boot-id and critical-process textual diff" in _source()


def test_critical_comparison_canonical_boot_id_and_property_exclusion() -> None:
    actual = "BOOT_ID=90882ee3-4884-445c-ae9c-cada3a1a6449"
    assert _comparable([actual]) == [actual]
    assert _comparable(["zygote64_32"]) == []
    assert "ro.zygote" in _spec_lines("critical-state")[0]
    assert "ro.zygote" not in _spec_lines("critical-state")[1]


def test_critical_comparison_detects_boot_or_pid_change() -> None:
    boot_a = "BOOT_ID=90882ee3-4884-445c-ae9c-cada3a1a6449"
    boot_b = "BOOT_ID=11111111-2222-3333-4444-555555555555"
    stable = [" 492 1 zygote64", " 534 1 audioserver", " 787 492 system_server"]
    assert _comparable([boot_a, *stable]) == _comparable([boot_a, *stable])
    assert _comparable([boot_a, *stable]) != _comparable([boot_b, *stable])
    changed_pid = [" 492 1 zygote64", " 999 1 audioserver", " 787 492 system_server"]
    assert _comparable([boot_a, *stable]) != _comparable([boot_a, *changed_pid])


def test_expected_zero_match_is_narrow_and_real_failures_remain_failures() -> None:
    source = _source()
    selinux_filters = _spec_lines("selinux-logcat-avc")
    assert len(selinux_filters) == 2
    assert all("expectedEmptyExitCodes=@(1)" in line for line in selinux_filters)
    assert source.count("expectedEmptyExitCodes=@(1)") == 2
    classifier = source[source.index("function Get-ResultClass"):
                        source.index("function Invoke-CapturedCommand")]
    expected = classifier.index("$Result.ExitCode -in $ExpectedEmptyExitCodes")
    generic_failure = classifier.index("$Result.ExitCode -ne 0")
    assert expected < generic_failure
    assert "[string]::IsNullOrWhiteSpace($Result.Stderr)" in classifier
    assert "return 'EMPTY_SUCCESS'" in classifier
    assert "return 'COMMAND_FAILED'" in classifier
    assert "expected_empty_exit_codes = @($ExpectedEmptyExitCodes)" in source


def test_executable_device_specs_are_observation_only() -> None:
    commands = _device_spec_block()
    forbidden = (
        r"\breboot\b", r"\broot\b", r"\bunroot\b", r"\bremount\b",
        r"\b(?:disable|enable)-verity\b", r"\bsu\b", r"\bsetprop\b",
        r"\bsettings\s+(?:put|delete)\b", r"\bsvc\s+(?:wifi|data|power)\b",
        r"\bcmd\s+(?:wifi|connectivity|power|package)\b",
        r"\bpm\s+(?:install|uninstall|disable|enable|clear|grant|revoke)\b",
        r"\bam\s+(?:force-stop|kill|start)\b",
        r"\binput\s+(?:keyevent|tap|swipe|text)\b",
        r"(?:^|[;\s])(?:rm|mv|cp|mkdir|touch|chmod|chown|umount)(?:\s|$)",
        r"\blogcat\b[^;\r\n]*\s-c(?:\s|$)",
        r"\b(?:monkey|screenrecord|bugreport)\b",
        r"\b(?:killall|pkill)\b", r"\b(?:stop|start)\b", r">|>>|\btee\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, commands, flags=re.IGNORECASE) is None, pattern

    assert "pm list packages" in commands
    assert "wm size; wm density" in commands
    assert "dumpsys power" in commands
    assert "dumpsys media.audio_flinger" in commands
    assert "dumpsys wifi" in commands
    assert "logcat', '-b', 'all', '-d'" in commands


def test_uart_is_passive_and_finalize_mode_has_no_device_access() -> None:
    source = _source()
    assert "uart_control=NONE_EXTERNAL_PASSIVE_CAPTURE_ONLY" in source
    assert "capture=PASSIVE_EXTERNAL" in source
    assert "commands_entered=false" in source
    finalize = source[source.index("if ($FinalizeOnly) {"):source.index(
        "if ([string]::IsNullOrWhiteSpace($Endpoint))")]
    assert "Invoke-CapturedCommand" not in finalize
    assert "Invoke-DeviceSpec" not in finalize
    assert "Copy-Item -LiteralPath $UartLogPath" in finalize
    assert "Refusing to overwrite UART-passive.log with different content." in finalize
    assert "$ExistingHash -ne $UartHash" in finalize
    assert finalize.count("Copy-Item -LiteralPath $UartLogPath") == 1


def test_powershell_parser_and_embedded_safety_check_when_available() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable; static safety tests remain authoritative")
    parsed = subprocess.run(
        [pwsh, "-NoProfile", "-Command",
         f"$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile('{COLLECTOR}',[ref]$t,[ref]$e)|Out-Null;if($e.Count){{$e|Out-String|Write-Error;exit 1}}"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert parsed.returncode == 0, parsed.stderr
    checked = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(COLLECTOR), "-SelfTest"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert checked.returncode == 0, checked.stderr
    assert "P2 collector executable command safety: PASS" in checked.stdout


def test_governance_keeps_audio_p1_closed_and_records_p2_analysis() -> None:
    device = (ROOT / "docs/DEVICE_TEST.md").read_text(encoding="utf-8")
    status = (ROOT / "docs/m8/STATUS.md").read_text(encoding="utf-8")
    todo = (ROOT / "docs/m8/TODO.md").read_text(encoding="utf-8")
    for text in (device, status, todo):
        assert "P2" in text
        assert "PHYSICAL CAPTURE ANALYZED" in text
    assert "P1 ARM32 AUDIO STARTUP CRASH CLOSED" in status
    assert "P1 CLOSED — legacy HIDL audio boot crash" in todo
    assert "r8 remains unauthorized and unbuilt" in status
    assert "does not start P3" in status
