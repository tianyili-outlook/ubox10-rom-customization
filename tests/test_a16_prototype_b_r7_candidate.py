"""Root-cause and preservation locks for the bounded Prototype B r7."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/candidates/a16-prototype-b-r7.json"
CAUSE = ROOT / "docs/m8/candidates/a16-prototype-b-r7-mapper-root-cause-audit.json"
CONTROL = ROOT / "docs/m8/candidates/a16-prototype-b-r7-arm32-arm64-mapper-control.json"
R6_PHYSICAL = ROOT / "docs/m8/candidates/a16-prototype-b-r6-physical-result.json"
R7_PHYSICAL = ROOT / "docs/m8/candidates/a16-prototype-b-r7-physical-result.json"
R7_CANDIDATE = ROOT / "docs/m8/candidates/a16-prototype-b-r7.md"
DEVICE_TEST = ROOT / "docs/DEVICE_TEST.md"
GATE3_CAPTURE = ROOT / "scripts/capture-a16-prototype-b-r7-functional-preservation.ps1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class A16PrototypeBR7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.cause = json.loads(CAUSE.read_text(encoding="utf-8"))
        cls.control = json.loads(CONTROL.read_text(encoding="utf-8"))
        cls.r6_physical = json.loads(R6_PHYSICAL.read_text(encoding="utf-8"))
        cls.r7_physical = json.loads(R7_PHYSICAL.read_text(encoding="utf-8"))

    def test_r6_physical_frontier_and_zygote_correction_are_frozen(self) -> None:
        self.assertEqual("a16-prototype-b-r6", self.r6_physical["candidate"])
        self.assertTrue(self.r6_physical["graphics_failure"]["current_unique_primary_blocker"])
        self.assertEqual("gralloc-mapper is missing", self.r6_physical["graphics_failure"]["abort_message"])
        self.assertEqual(
            "PHYSICAL_REACHED",
            self.r6_physical["zygote_causal_correction"]["primary"]["preload"],
        )
        self.assertFalse(
            self.r6_physical["zygote_causal_correction"]["primary"]["independent_crash_proven"]
        )
        self.assertEqual(
            "SECONDARY_EFFECT",
            self.r6_physical["zygote_causal_correction"]["service_restarting"],
        )

    def test_r7_physical_architecture_gate_is_frozen(self) -> None:
        physical = self.r7_physical
        self.assertEqual("a16-prototype-b-r7", physical["candidate"])
        self.assertEqual(
            "PHYSICAL_ARCHITECTURE_PASS_PENDING_GATE3_FUNCTIONAL_PRESERVATION",
            physical["physical_status"],
        )
        self.assertEqual(
            "ANDROID_16_ARM64_MIXED_ARCHITECTURE_PROVEN_VIABLE",
            physical["architecture_decision"],
        )
        self.assertFalse(physical["evidence_provenance"]["raw_capture_tracked"])
        self.assertIsNone(physical["evidence_provenance"]["raw_capture_sha256"])
        self.assertEqual("PASS", physical["mixed_abi"]["status"])
        self.assertEqual("arm64-v8a", physical["mixed_abi"]["ro.product.cpu.abilist64"])
        self.assertEqual("CLOSED", physical["boringssl_vendor_gate"]["r5_missing_64_bit_executable_gap"])
        processes = physical["runtime_architecture"]["processes"]
        self.assertEqual(processes["zygote64"]["pid"], processes["system_server"]["ppid"])
        self.assertEqual("PASS", physical["graphics"]["status"])
        self.assertEqual("NO_MATCH_OBSERVED", physical["graphics"]["r6_abort_recurrence_in_validated_run"])
        self.assertEqual("Mali-G31", physical["graphics"]["gles_renderer"])
        self.assertEqual(
            [
                "GLOBAL_MIXED_ABI_PROPERTY_CONTRACT",
                "VENDOR_BORINGSSL64_MISSING_EXECUTABLE",
                "ARM64_GRALLOC_MAPPER_IS_MISSING",
            ],
            physical["closed_architecture_blockers"],
        )

    def test_unique_root_cause_authorizes_only_two_existing_arm64_files(self) -> None:
        self.assertEqual(
            "PROVEN_ARM64_MAPPER_AND_GRALLOC_VNDK31_LIBCPP_BACKDEPLOY_FAILURE",
            self.cause["result"],
        )
        self.assertTrue(self.cause["r7_decision"]["authorized"])
        self.assertEqual(
            [
                "/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so",
                "/vendor/lib64/hw/gralloc.apollo.so",
            ],
            self.cause["r7_decision"]["allowed_vendor_tree_delta"],
        )
        self.assertFalse(self.cause["linker_namespace"]["vndk31_exports_libcpp_verbose_abort"])
        self.assertEqual(
            "_ZNSt3__122__libcpp_verbose_abortEPKcz",
            self.cause["r6_provider_failure"]["missing_symbol"],
        )

    def test_arm32_control_has_zero_unmatched_and_arm64_r6_has_one(self) -> None:
        for name in ("mapper", "gralloc"):
            self.assertEqual(0, self.control["control"][name]["unmatched_strong_import_count"])
            self.assertFalse(self.control["control"][name]["libcpp_verbose_abort_import"])
            self.assertEqual(
                ["_ZNSt3__122__libcpp_verbose_abortEPKcz"],
                self.control["failed_arm64"][name]["unmatched_strong_imports"],
            )
            self.assertTrue(self.control["failed_arm64"][name]["libcpp_verbose_abort_import"])
            self.assertEqual(
                0,
                self.control["candidate_r7_prebuild_outputs"][name]["unmatched_strong_import_count"],
            )

    def test_backdeploy_sources_are_exact_and_arm64_only(self) -> None:
        source = self.cfg["source_contract"]
        self.assertEqual("ARM64_ONLY", source["architecture_scope"])
        self.assertEqual(
            "#define _LIBCPP_VERBOSE_ABORT(...) __builtin_abort()",
            source["compatibility_macro"],
        )
        for name in ("gralloc_android_mk", "gralloc_backdeploy_header", "mapper_patch"):
            path = ROOT / source[name]["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(source[name]["sha256"], digest(path))
        header = (ROOT / source["gralloc_backdeploy_header"]["path"]).read_text()
        self.assertIn("defined(__aarch64__)", header)
        self.assertIn("_LIBCPP_VERBOSE_ABORT(...) __builtin_abort()", header)
        makefile = (ROOT / source["gralloc_android_mk"]["path"]).read_text()
        self.assertIn("LOCAL_CPPFLAGS_64 += -include", makefile)

    def test_r7_is_exact_r6_base_and_preserves_non_target_contracts(self) -> None:
        self.assertEqual("a16-prototype-b-r7", self.cfg["id"])
        self.assertEqual("a16-prototype-b-r6", self.cfg["base_candidate"]["id"])
        self.assertEqual(
            "2AAF8E2CA89DDE486A9416FDE7ACFF7BCD6DB80CDCB161598ABF99A7CB2DBD53",
            self.cfg["base_candidate"]["sha256"],
        )
        self.assertEqual(
            ["/vendor/bin/boringssl_self_test64"],
            self.cfg["elf_census_contract"]["approved_additional_vendor64"],
        )
        for name in ("mali", "mapper32", "gralloc32", "boringssl32", "boringssl64", "boringssl_rc"):
            self.assertIn(name, self.cfg["retained_vendor_contract"])
        for forbidden in ("Mali", "ARM32_mapper_or_gralloc", "BoringSSL32_or_BoringSSL64", "kernel_or_vendor_dlkm"):
            self.assertIn(forbidden, self.cfg["forbidden_changes"])
        active = self.cfg["active_product_property_contract"]
        self.assertEqual("/system/product", active["root_object"]["target"])
        self.assertEqual("system/product", active["target_copy_out_product"])
        self.assertEqual("/product", self.cfg["skip_mount_contract"]["required_pattern"])

    def test_builder_and_auditor_fail_closed(self) -> None:
        builder = (ROOT / "scripts/build-a16-prototype-b-r7-candidate.py").read_text()
        auditor = (ROOT / "scripts/audit-a16-prototype-b-r7.py").read_text()
        checker = (ROOT / "scripts/check-a16-prototype-b-r7-graphics.py").read_text()
        self.assertIn("r7 root-cause authorization is not uniquely closed", builder)
        self.assertIn("imports_verbose_abort", builder)
        self.assertIn("r7 vendor semantic delta expanded", auditor)
        self.assertIn("PASS_EXACT_ARM64_MAPPER_GRALLOC_SPHAL_CLOSURE", auditor)
        self.assertIn("NOT_EXPORTED_TO_SPHAL", checker)
        self.assertIn("FAIL_CLOSED_ARM64_MAPPER_GRALLOC_SPHAL_CLOSURE", checker)

    def test_gate3_is_exact_r7_functional_preservation_only(self) -> None:
        gate3 = self.r7_physical["gate3"]
        self.assertEqual("DEFINED_READY_FOR_PHYSICAL_EXECUTION", gate3["status"])
        self.assertTrue(gate3["candidate_must_remain_exact_r7"])
        self.assertFalse(gate3["r8_authorized"])
        self.assertTrue(all(value == "NOT_TESTED_GATE3" for value in gate3["pending"].values()))
        self.assertFalse(self.r7_physical["future_branch"]["created"])

        candidate = R7_CANDIDATE.read_text(encoding="utf-8")
        procedure = DEVICE_TEST.read_text(encoding="utf-8")
        self.assertIn("FROZEN AGAINST ARCHITECTURE CHANGES", candidate)
        self.assertIn("Gate 3 — Android 16 Mixed-Architecture Functional Preservation", procedure)
        for requirement in (
            "H.264 + AAC",
            "HEVC/H.265 + AAC",
            "VP9",
            "DPAD_CENTER",
            "Wi-Fi OFF→ON",
            "NOT TESTED — FIXTURE UNAVAILABLE",
            "PLAYBACK PASS",
            "HARDWARE DECODE PATH PROVEN",
            "exit 65",
        ):
            self.assertIn(requirement, procedure)

    def test_gate3_capture_commands_are_read_only_and_manual_boundaries_are_explicit(self) -> None:
        script = GATE3_CAPTURE.read_text(encoding="utf-8")
        command_pattern = re.compile(
            r"^\s+'[^']+\.txt'\s*=\s*(['\"])(.*?)\1\s*$",
            re.MULTILINE,
        )
        commands = [match.group(2) for match in command_pattern.finditer(script)]
        self.assertGreaterEqual(len(commands), 18)
        forbidden = re.compile(
            r"(?i)(?:setprop|\breboot\b|\bremount\b|settings\s+put|svc\s+wifi|"
            r"pm\s+(?:grant|revoke|install|uninstall)|(?:^|[;&| ]+)(?:mount|umount)(?:[;&| ]|$))"
        )
        for command in commands:
            self.assertIsNone(forbidden.search(command), command)
        self.assertIn("PHYSICAL_TV_UI_ONLY", script)
        self.assertIn("manual-observations.txt", script)
        self.assertIn("Wireless ADB loss is expected", script)
        self.assertNotIn("192.168.", script)
        self.assertEqual(script.count('{'), script.count('}'))
        self.assertEqual(script.count('@"'), script.count('"@'))
        self.assertEqual(script.count("@'"), script.count("'@"))
        adb_invocations = [line.strip() for line in script.splitlines() if "& $AdbPath" in line]
        self.assertEqual(3, len(adb_invocations))
        self.assertTrue(any(" shell " in line for line in adb_invocations))
        self.assertTrue(any(" connect " in line for line in adb_invocations))
        self.assertTrue(any(" get-state" in line for line in adb_invocations))

    def test_offline_result_if_candidate_exists(self) -> None:
        result = ROOT / "docs/m8/candidates/a16-prototype-b-r7-offline-result.json"
        candidate = ROOT / "out/candidates/a16-prototype-b-r7/offline-audit/offline-audit.json"
        if not result.is_file() or not candidate.is_file():
            self.skipTest("r7 offline artifact/result not present yet")
        tracked = json.loads(result.read_text(encoding="utf-8"))
        local = json.loads(candidate.read_text(encoding="utf-8"))
        self.assertEqual("OFFLINE CHECKED / READY FOR PHYSICAL VALIDATION", tracked["decision"])
        self.assertEqual(
            "HISTORICAL_OFFLINE_SNAPSHOT_BEFORE_PHYSICAL_VALIDATION",
            tracked["record_scope"],
        )
        self.assertEqual("NOT_YET_VALIDATED", tracked["physical_status_at_record_time"])
        self.assertEqual(
            "PHYSICAL_ARCHITECTURE_PASS_PENDING_GATE3_FUNCTIONAL_PRESERVATION",
            tracked["current_physical_status"],
        )
        self.assertEqual(
            "docs/m8/candidates/a16-prototype-b-r7-physical-result.json",
            tracked["current_physical_result"],
        )
        self.assertEqual(
            "A1F58668AEFFC9DC83CFFD8A49A309839332B6616C02153DCC00A71136A7AA27",
            tracked["candidate_identity"]["sha256"],
        )
        self.assertEqual(
            self.cfg["providers"]["mapper"]["sha256"],
            tracked["graphics"]["mapper"]["sha256"],
        )
        self.assertEqual(
            self.cfg["providers"]["gralloc"]["sha256"],
            tracked["graphics"]["gralloc"]["sha256"],
        )
        self.assertEqual(0, tracked["graphics"]["mapper"]["strong_unmatched"])
        self.assertEqual(0, tracked["graphics"]["gralloc"]["strong_unmatched"])
        self.assertEqual(65, tracked["offline_gates"]["full_vintf_exit"])
        self.assertIn("NOT_PASS", tracked["offline_gates"]["full_vintf"])
        self.assertEqual(
            "PASS_OFFLINE_ZERO_UNMATCHED_FOR_MAPPER_AND_GRALLOC",
            local["graphics_mapper"]["candidate_closure"],
        )
        self.assertIn("NOT PASS", " ".join(local["limitations"]))


if __name__ == "__main__":
    unittest.main()
