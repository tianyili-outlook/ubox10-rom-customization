# Storage and reproduction

Immutable stock inputs and rollback assets live under the sibling project root, not as Git artifacts. Candidate evidence is at `out/candidates/m8a-initial-atv-r1/`.

Reproduction requires the locked WSL AOSP images, stock container, extracted AVB payloads, official vendor caches, test key, repository tools, and the candidate builder. Hash/provenance locks are authoritative.

The assembly is intentionally not bit-for-bit reproducible: ext4 e2fsck/resize metadata can change the rebuilt logical, AVB, super, and outer hashes. A valid rebuild must instead pass protected source locks, LP/layout checks, preservation audit, AVB/IMAGEWTY checks, and SHA256SUMS.

No media was prepared and no device was operated during M8A.2b.
