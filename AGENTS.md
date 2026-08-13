# UBOX10 operating rules

- Use `.agents/skills/ubox-fast-track/SKILL.md` for M8 planning, documentation, builds, candidate checks, and diagnosis.
- Keep scope, architecture, final diff inspection, and acceptance in the main session. Treat check output as evidence, not proof.
- Prefer one reversible candidate, one focused offline check, and the first reproducible device failure over broad audits or production-grade gates.
- Never modify original firmware or irreplaceable device evidence. Keep stock and Test8r2 rollback assets available.
- Never flash or otherwise mutate the physical UBOX10 without explicit user authorization.
- Preserve stock boot, kernel, vendor, vendor_dlkm, TEE, DRM, graphics, media, wireless, and partition dependencies unless a bounded experiment explicitly changes one.
- Keep active documentation limited to `README.md`, `docs/m8/STATUS.md`, `docs/m8/TODO.md`, `docs/BUILD.md`, `docs/DEVICE_TEST.md`, and the current candidate record.
- Treat the checked-in H616 platform evidence as authoritative; do not promote an H618 sales label to a confirmed hardware fact without new chip-level evidence.
