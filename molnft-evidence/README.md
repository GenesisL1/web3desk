# GenesisL1 MOLNFT evidence

This directory is the reproducible evidence layer for collection-size and full-payload reconstruction claims used in the GenesisL1 Insights article **“GenesisL1 and the Next Verifiable Renaissance.”**

The evidence is deliberately narrower than the marketing shorthand it replaces:

- contract counts are pinned to an exact block;
- PDB v2 parent records are distinguished from child chunk tokens;
- legacy PDB and AlphaFold collections are reported as a separate v1 subtotal;
- complete BinaryCIF reconstruction is demonstrated on a predeclared sample rather than asserted for the entire collection without an exhaustive audit;
- all raw JSON-RPC responses, reconstructed files and derived tables are SHA-256 checksummed.

## Files

- [`METHODOLOGY.md`](METHODOLOGY.md) — definitions, storage-generation distinctions and scope.
- [`scripts/capture_molnft_snapshot.py`](scripts/capture_molnft_snapshot.py) — reproducible capture tool.
- [`latest.json`](latest.json) — small pointer to the newest immutable snapshot.
- [`snapshots/`](snapshots/) — immutable evidence packages.
- [GitHub Actions workflow](../.github/workflows/capture-molnft-evidence.yml) — automated pinned capture.

## Reproduce

```bash
python -m pip install requests eth-abi eth-utils msgpack
python molnft-evidence/scripts/capture_molnft_snapshot.py
```

Then verify the generated package:

```bash
cd molnft-evidence/snapshots/block-13412747-*
sha256sum -c SHA256SUMS.txt
```

The report states exactly what was observed and exactly what was not tested.
