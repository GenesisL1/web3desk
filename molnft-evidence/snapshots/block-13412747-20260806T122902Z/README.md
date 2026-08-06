# MOLNFT evidence snapshot

**Pinned GenesisL1 block:** `13412747`  
**Block hash:** `0x19f42cd995e384e09d5cd4fb2751668e613d762dd1f22301d065ec84950f0f9a`  
**Block time:** `2026-08-06T12:29:02Z`  
**Captured:** `2026-08-06T23:24:01Z`  
**RPC provider:** `GenesisL1 public`

## Exact collection observations

| Observation | Result |
|---|---:|
| PDB v2 parent records | **229,271** |
| PDB v2 total ERC-721 tokens, including child chunks | **265,786** |
| PDB v2 child chunks | **36,515** |
| Legacy PDB v1 tokens | **191,600** |
| Legacy AlphaFold/Swiss-Prot v1 tokens | **542,319** |
| Legacy v1 subtotal | **733,919** |

The PDB v2 parent count and the legacy-v1 subtotal describe different storage generations and potentially overlapping scientific records. They are **not added together**. The legacy subtotal is the sum of two ERC-721 supplies; it is not a claim that those assets store complete coordinate payloads in contract state.

## Direct reconstruction audit

The following set was declared before capture and reconstructed with `getCombinedData(tokenId)` at the pinned block. The returned base64 was decoded, gunzipped when applicable, parsed as BinaryCIF MessagePack, and checked for `_atom_site.Cartn_x`, `_atom_site.Cartn_y` and `_atom_site.Cartn_z` columns.

| PDB ID | Token | BinaryCIF bytes | Atom rows | Coordinates | SHA-256 |
|---|---:|---:|---:|---|---|
| 100D | 1 | 167,950 | 489 | yes | `a793f658cfd5a803…` |
| 101D | 2 | 174,860 | 556 | yes | `1515c558fb8cfddc…` |
| 1CRN | 3,429 | 154,573 | 327 | yes | `74e867532f637699…` |
| 102M | 6 | 189,675 | 1,423 | yes | `a99060d2a95131c3…` |
| 1AKE | 886 | 224,201 | 3,816 | yes | `1a7955697a230ec9…` |
| 4HHB | 93,945 | 309,112 | 4,779 | yes | `1afa1f71d13b27be…` |
| 1AON | 1,019 | 977,462 | 58,870 | yes | `c5539898baca2e20…` |
| 1FNT | 6,808 | 1,153,429 | 70,622 | yes | `88334aecb3e3fa58…` |

## Scope

This snapshot proves two things at block 13,412,747: the contract counters and ERC-721 supplies shown above, and successful full-byte reconstruction for **8 predeclared sample records**. It does not claim that all PDB v2 parent records were exhaustively downloaded and decoded in this run.

For each sample, the repository publishes the exact JSON-RPC request and response, the reconstructed `.bcif` bytes, parsed structural checks, CSV results and SHA-256 checksums. Anyone can rerun the capture against an archive-capable GenesisL1 RPC endpoint.

## Verify

```bash
sha256sum -c SHA256SUMS.txt
python ../scripts/capture_molnft_snapshot.py --block 13412747 --expected-block-hash 19F42CD995E384E09D5CD4FB2751668E613D762DD1F22301D065EC84950F0F9A
```
