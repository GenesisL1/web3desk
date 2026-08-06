# MOLNFT evidence at GenesisL1 block 13,412,747

This is the permanent public summary for the MOLNFT evidence capture used by the GenesisL1 Insights article **“GenesisL1 and the Next Verifiable Renaissance.”**

**Block:** `13,412,747`  
**Block hash:** `19F42CD995E384E09D5CD4FB2751668E613D762DD1F22301D065EC84950F0F9A`  
**Block time:** `2026-08-06T12:29:02Z`  
**Capture time:** `2026-08-06T23:12:56Z`

## Exact contract observations

| Observation | Result |
|---|---:|
| PDB v2 parent records | **229,271** |
| PDB v2 total ERC-721 tokens, including child chunks | **265,786** |
| PDB v2 child chunks | **36,515** |
| Legacy PDB v1 tokens | **191,600** |
| Legacy AlphaFold/Swiss-Prot v1 tokens | **542,319** |
| Legacy v1 subtotal | **733,919** |

The PDB v2 parent count and the legacy-v1 subtotal describe different storage generations and potentially overlapping scientific records. They are not added into a single corpus total. Child chunks extend large PDB v2 payloads and are not independent molecular records.

## Direct reconstruction audit

A predeclared size-stratified sample—`100D`, `101D`, `1CRN`, `102M`, `1AKE`, `4HHB`, `1AON`, and `1FNT`—was reconstructed with `getCombinedData(tokenId)` at the pinned block.

All **8 of 8** payloads were:

- ABI-decoded and base64-decoded;
- decompressed where required;
- parsed as BinaryCIF MessagePack;
- confirmed to contain nonzero `_atom_site` rows; and
- confirmed to contain `_atom_site.Cartn_x`, `_atom_site.Cartn_y`, and `_atom_site.Cartn_z` coordinate columns.

The reconstructed BinaryCIF objects total **3,351,262 bytes**. This is a direct full-byte result for the declared sample. It is not presented as an exhaustive reconstruction of all 229,271 parent records.

## Evidence package

The complete package contains the exact JSON-RPC requests and responses, runtime-code hashes, reconstructed `.bcif` files, CSV tables, machine-readable snapshot, manifest and SHA-256 checksums.

- [Capture workflow run](https://github.com/GenesisL1/web3desk/actions/runs/31130158735)
- [Machine-readable public summary](pinned-block-13412747.json)
- [Methodology](METHODOLOGY.md)
- [Capture implementation](scripts/capture_molnft_snapshot.py)

Complete artifact ZIP SHA-256:

```text
2ed0c6c190689528f2f98998682a3c3009d163950d8bce8c13ff6ba57c7c673f
```

The workflow capture, internal checksum verification and artifact upload succeeded. The workflow’s final repository-push step encountered a concurrent-branch update; the permanent summary is therefore committed separately, while the complete raw package remains the checksummed workflow artifact and downloadable publication attachment.
