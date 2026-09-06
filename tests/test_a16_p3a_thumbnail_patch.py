"""Offline patch, ELF mapping and actual Thumb guard execution; no device use."""
import importlib.util
import itertools
from pathlib import Path
import struct

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('thumbnail_patch', ROOT / 'scripts/patch-a16-p3a-thumbnail-r1.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
SOURCE = ROOT / 'out/candidates/a16-dev-p3a-compat1b-r1/preserved-omx_r1'


@pytest.fixture(scope='module')
def patch():
    if not SOURCE.exists() or not P.DEFAULT_TOOLS.exists():
        pytest.skip('external exact ELF/toolchain absent')
    original = SOURCE.read_bytes()
    hook, stub, dis = P.assemble(P.DEFAULT_TOOLS)
    result, proof = P.patch_bytes(original, hook, stub)
    return original, result, hook, stub, dis, proof


def test_exact_patch_and_rejection(patch):
    original, result, hook, stub, dis, proof = patch
    assert len(result) == 89192 and P.sha(result) == P.OUTPUT_SHA256
    assert P.patch_bytes(original, hook, stub)[0] == result
    for bad in (b'', result, original[:-1], bytes(len(original)),
                original[:P.HOOK_OFFSET] + b'\0' + original[P.HOOK_OFFSET+1:]):
        with pytest.raises(ValueError):
            P.patch_bytes(bad, hook, stub)
    with pytest.raises(ValueError):
        P.patch_bytes(original, bytes(4), stub)
    assert '0xd06c' in dis and '0x13f00' in dis
    assert original[0xd130:0xd134] == result[0xd130:0xd134] == bytes.fromhex('4fea0c00')


def test_original_sections_and_load_mapping(patch):
    original, result, hook, _, _, _ = patch
    old, _ = P.sections(original)
    new, _ = P.sections(result)
    # Every existing section, including mini-debug, preserved apart from .text hook
    # and the explicitly extended/repointed non-loaded section-name table.
    for i, a in enumerate(old):
        b = new[i]
        if i == 23:
            continue
        assert a[1:4] == b[1:4] and a[5:] == b[5:]
        expected = bytearray(original[a[4]:a[4]+a[5]])
        if a[4] <= P.HOOK_OFFSET < a[4]+a[5]:
            off = P.HOOK_OFFSET-a[4]
            expected[off:off+4] = hook
        assert result[b[4]:b[4]+b[5]] == expected
    for i in range(10):
        a = struct.unpack_from('<8I', original, 52+i*32)
        b = struct.unpack_from('<8I', result, 52+i*32)
        assert a[0] == b[0] and a[2:4] == b[2:4] and a[6:] == b[6:]
        assert b[1] == a[1] + (4096 if a[1] >= P.INSERT_OFFSET else 0)
        assert b[4:6] == tuple(x+(4096 if i == 2 else 0) for x in a[4:6])
        if b[0] == 1:
            assert b[1] % b[7] == b[2] % b[7]
            assert not (b[6] & 1 and b[6] & 2), 'no RWX'


def test_second_assembler_and_original_byte_guard(patch, monkeypatch):
    original, _, hook, stub, _, _ = patch
    alternate = P.DEFAULT_TOOLS.parent.parent / 'clang-r530567/bin'
    if not alternate.exists():
        pytest.skip('second retained LLVM toolchain absent')
    h2, s2, _ = P.assemble(alternate)
    assert (h2, s2) == (hook, stub)
    bad = original[:P.HOOK_OFFSET] + bytes(4) + original[P.HOOK_OFFSET+4:]
    monkeypatch.setattr(P, 'INPUT_SHA256', P.sha(bad))
    with pytest.raises(ValueError, match='original AFBC instruction'):
        P.patch_bytes(bad, hook, stub)


def test_governance_and_scope():
    import json
    cfg = json.loads((ROOT / 'configs/candidates/a16-dev-p3a-thumbnail-r1.json').read_text())
    assert cfg['runtime_change']['partition_path'] == '/vendor/lib/libOmxVdec.so'
    assert cfg['runtime_change']['candidate']['sha256'].lower() == P.OUTPUT_SHA256
    gov = cfg['governance']
    assert gov['audio_p1'] == 'CLOSED' and gov['p2'] == 'COMPLETE'
    assert gov['rc_a2'] == 'PHYSICAL_PASS_CLOSED'
    assert gov['p3b_main10'] == 'NOT_AUTHORIZED'
    assert not any(gov[k] for k in ('r8_authorized','r8_built','release'))
    assert gov['physical_validation_required']
    assert 'PHYSICAL_PASS' in gov['rc_b']


def test_existing_candidate_audit():
    import json
    path = ROOT / 'out/candidates/a16-dev-p3a-thumbnail-r1/offline-audit/offline-audit.json'
    if not path.exists():
        pytest.skip('external candidate audit absent')
    audit = json.loads(path.read_text())
    assert audit['physical_status'] == 'NOT_YET_VALIDATED'
    assert audit['filesystem']['system_byte_identical_to_compat1b']
    assert audit['filesystem']['vendor_tree_delta'] == {'added': [], 'removed': [], 'changed': ['lib/libOmxVdec.so']}
    assert audit['elf']['canonical_patched_identity'].lower() == P.OUTPUT_SHA256
    assert audit['elf']['namespace_closure']['unmatched_count'] == 0
    assert audit['vintf']['system_exit'] == 0 and audit['vintf']['full_exit'] == 65


def test_actual_thumb_guard(patch):
    # Optional small host emulator. This executes the packaged machine bytes,
    # not a Python reimplementation of the predicate. No vendor decoder runs.
    U = pytest.importorskip('unicorn')
    from unicorn import arm_const as A
    original, result, _, _, _, _ = patch
    regs = [getattr(A, f'UC_ARM_REG_R{i}') for i in range(13)]
    regs += [A.UC_ARM_REG_SP, A.UC_ARM_REG_LR]
    for native, zero, secure, codec, width, height, c1, c2 in itertools.product(
        (0, 1), (0, 1), (0, 1), (0x116, 0x110), (3840, 1920),
        (2160, 1080), (0x13, 0x15), (0x13, 0x15)):
        cpu = U.Uc(U.UC_ARCH_ARM, U.UC_MODE_THUMB)
        cpu.mem_map(0, 0x20000)
        # Loader-equivalent original RX mapping plus the inserted stub page.
        cpu.mem_write(0x76c0, result[0x66c0:0x13f00])
        ctx, port, stack = 0x30000, 0x40000, 0x51000
        cpu.mem_map(ctx, 0x10000); cpu.mem_map(port, 0x10000); cpu.mem_map(stack-0x1000, 0x2000)
        def word(addr, val): cpu.mem_write(addr, struct.pack('<I', val))
        for off, val in ((0xc,width),(0x10,height),(0x58a4,secure),
                         (0x58b0,native),(0x58bc,zero),(0x58cc,port)):
            word(ctx+off, val)
        word(port+0xac,c1); word(port+0xd0,c2)
        vals = [codec, 32, 0x12345678, 0x87654321, ctx, ctx+8, 1,
                7, 0x5894, 9, ctx+0x58bc, 11, 12, stack, 0x1235]
        # CMP codec,0x110 precedes the original hook; preserve its branch flags.
        flags = 0x60000030 if codec == 0x110 else 0x20000030
        cpu.reg_write(A.UC_ARM_REG_CPSR,flags)
        for reg, val in zip(regs, vals): cpu.reg_write(reg,val)
        cpu.emu_start(P.HOOK_VA|1, P.HOOK_VA+4, count=100)
        assert cpu.reg_read(A.UC_ARM_REG_PC) == P.HOOK_VA+4
        assert [cpu.reg_read(r) for r in regs] == vals
        assert cpu.reg_read(A.UC_ARM_REG_CPSR) & 0xf8000000 == flags & 0xf8000000
        selected = not(native or zero or secure) and codec==0x116 and width==3840 and height==2160 and c1==c2==0x13
        assert struct.unpack('<I',cpu.mem_read(ctx+0xc8,4))[0] == (0 if selected else 1)
