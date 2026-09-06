"""Offline evidence and planar-copy arithmetic, not a decoder/pixel-content test."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / 'configs/candidates/a16-dev-p3a-compat1b-r1.json'


def test_exact_vendor_copy_disassembly_if_present():
    binary = ROOT / 'out/candidates/a16-dev-p3a-compat1b-r1/preserved-omx_r1'
    tool = Path('/work/src/ubox10-a16-ceiling/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump')
    if not binary.exists() or not tool.exists():
        pytest.skip('exact external candidate/toolchain unavailable')
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == '5fe74a28eb9e083959fdac9cfde870faa2af4447dadb7776c1e7f4cfc6d1ee8b'
    def disasm(start, end):
        return subprocess.check_output([str(tool), '-d', '--triple=thumbv7-linux-gnueabi',
                                        f'--start-address={start}', f'--stop-address={end}',
                                        str(binary)], text=True)
    prepare = disasm('0xd054', '0xd070')
    assert re.search(r'd05e:.*movs\s+r6, #0x1', prepare)
    assert re.search(r'd068:.*str.w\s+r6, \[r5, #0xc0\]', prepare)
    copy = disasm('0xe798', '0xe8ac')
    for address in ('e828', 'e884', 'e89c'):
        assert re.search(rf'{address}:.*blx\s+0x13538', copy)
    assert len(re.findall(r'\bblx\s+0x13538', copy)) == 3
    assert re.search(r'e7da:.*ldr\s+r5, \[r0, #0x50\]', copy)
    # No compressed-to-linear conversion call: only logging and these memcpy call sites.
    assert set(re.findall(r'\bblx\s+(0x[0-9a-f]+)', copy)) == {'0x13538', '0x138a0'}


def test_padded_yv12_to_compact_i420_model():
    # Reconstruct the three memcpy loops, with deliberately different U/V and padding.
    width, src_height, height = 3840, 2176, 2160
    y_size = width * src_height
    source = bytearray([0xee]) * (y_size * 3 // 2)
    plane_specs = ((0, width, height, 0x31),
                   (y_size, width // 2, height // 2, 0x95),  # V
                   (y_size * 5 // 4, width // 2, height // 2, 0x52))  # U
    for base, stride, rows, value in plane_specs:
        for row in range(rows):
            source[base + row * stride:base + (row + 1) * stride] = bytes([value]) * stride
    destination = bytearray()
    for base, stride, rows in ((0, width, height),
                              (y_size * 5 // 4, width // 2, height // 2),
                              (y_size, width // 2, height // 2)):
        for row in range(rows):
            destination.extend(source[base + row * stride:base + (row + 1) * stride])
    assert len(destination) == 12441600
    assert destination[:8294400] == bytes([0x31]) * 8294400
    assert destination[8294400:10368000] == bytes([0x52]) * 2073600
    assert destination[10368000:] == bytes([0x95]) * 2073600
    assert y_size == 8355840 and y_size * 5 // 4 == 10444800
    assert y_size - 8294400 == 61440
    assert y_size * 5 // 4 - 10368000 == 76800
    # All relevant exact 4K arithmetic is far below signed ARM32 overflow.
    assert y_size * 5 < 2**31


def test_new_physical_scope_and_no_repair_claim():
    cfg = json.loads(CFG.read_text())
    gov = cfg['governance']
    assert gov['rc_b'] == 'COMPAT1B_PHYSICAL_PASS_BOUNDED_MAIN8_SDR_4K30_SURFACE'
    assert gov['rc_a2'] == 'PHYSICAL_PASS_CLOSED'
    assert gov['audio_p1'] == 'CLOSED' and gov['p2'] == 'COMPLETE'
    assert gov['p3b_main10'] == 'NOT_AUTHORIZED'
    assert not gov['r8_authorized'] and not gov['r8_built'] and not gov['release']
    assert cfg['thumbnail_forensics']['status'] == 'PHYSICAL_FAIL_HIGH_CONFIDENCE_STORAGE_CONTRACT_MISMATCH'
    assert cfg['thumbnail_forensics']['runtime_fix_applied'] is False
    report = (ROOT / 'docs/m8/device-tests/20260905-a16-p3a-compat1b-r1-build/README.md').read_text()
    for marker in ('0x13', 'I420', 'AFBC', '2176', 'NEEDS_MORE_EVIDENCE',
                   'no decompression', 'not a proven U/V swap'):
        assert marker in report


def test_external_core_evidence_if_present():
    evidence = json.loads(CFG.read_text())['thumbnail_forensics']['evidence']
    archive = Path(evidence['archive'])
    if not archive.exists():
        pytest.skip('raw physical evidence intentionally external')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == evidence['sha256']
    with zipfile.ZipFile(archive) as z:
        names = {str(Path(name)): name for name in z.namelist()}
        manifest = z.read(names['SHA256SUMS.txt']).decode('utf-8-sig')
        entries = [line.split(maxsplit=1) for line in manifest.splitlines() if line.strip()]
        assert len(entries) == 9
        for expected, filename in entries:
            assert hashlib.sha256(z.read(names[filename.lstrip('* ').replace('\\', '/')])).hexdigest() == expected.lower()
        read = lambda name: z.read(names[name]).decode('utf-8-sig')
        pre, post = read('pre-4k-critical.txt'), read('post-4k-critical.txt')
        uuid = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        pattern = rf'^(?:BOOT_ID={uuid}|\s*\d+\s+\d+\s+\S+)\s*$'
        before = re.findall(pattern, pre, re.M)
        assert len(before) == 9  # labelled boot + eight recorded process rows
        assert before == re.findall(pattern, post, re.M)
        playback = read('4k-compat1b-key-signatures.txt')
        ids = re.findall(r'UBOX_P3_COMPAT1B eligible=1 buffer_id=(\d+)', playback)
        assert len(set(ids)) == 14
        for bid in ids:
            for pattern in (rf'translated=1 buffer_id={bid} .*src_offset=23544 dst_offset=128 bytes=56',
                            rf'egl_import_result=1 buffer_id={bid} view=sdr_shadow',
                            rf'stage=BACKEND_TEXTURE buffer_id={bid} valid=1'):
                assert re.search(pattern, playback)
        thumbnail = read('vlc-swthumb2-key.txt')
        assert 'using color format 0x13 in place of 0x7f420888' in thumbnail
        assert 'nSrcBufWidth & H = 3840, 2176,nDstBufWidth & H = 3840, 2160' in thumbnail
        assert '03:06:37.221' in read('vlc-1080-thumb-control-key.txt')
