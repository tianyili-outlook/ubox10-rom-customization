# Tests

Run from the repository root:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

The default suite is safe for a clean clone: it uses checked-in fixtures and never flashes or accesses a device. Tests for r2-r6 candidate bytes skip when the large ignored files under `out/candidates/` are absent and activate automatically after the candidate chain is built.

Fixtures are small public parser samples. Original firmware, APKs, device logs, extracted partitions, and candidate images must remain outside Git.
