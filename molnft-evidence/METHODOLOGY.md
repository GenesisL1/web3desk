# MOLNFT evidence methodology

This directory publishes a height-pinned evidence package for claims about MOLNFT collection size and full on-chain molecular reconstruction on GenesisL1.

## Questions answered

The capture separates three questions that should not be conflated:

1. **How many ERC-721 tokens did each deployed collection report at one exact block?**
2. **How many PDB v2 parent records did the full-payload contract counter report?**
3. **Can complete molecular coordinate files be reconstructed from PDB v2 contract state at that block?**

The first two are collection-wide counter observations. The third is tested on a predeclared, size-stratified sample and is not extrapolated into an exhaustive audit of every parent record.

## Pinned state

The Article 02 evidence run uses GenesisL1 block `13,412,747`, whose expected block hash is:

```text
19F42CD995E384E09D5CD4FB2751668E613D762DD1F22301D065EC84950F0F9A
```

The script rejects any provider that returns a different chain ID, cannot serve the historical block, or returns a different block hash. Every `eth_call` and `eth_getCode` query uses that exact block tag.

## Contracts observed

| Collection | Contract | Evidence purpose |
|---|---|---|
| MOLNFT PDB v2 | `0xd58B01f6C18086e5202cdC5D7Ad3E41790360102` | Parent counter, total supply, child counter, full payload reconstruction |
| MOLNFT PDB v1 | `0xDE3723766Bc32dcACD03C17BaA400A7B36837Eba` | Legacy ERC-721 supply |
| MOLNFT AlphaFold/Swiss-Prot v1 | `0xBf7491af3407816DFa88a5EA4c82e8A2B1D721eD` | Legacy ERC-721 supply |

Runtime bytecode is retrieved at the pinned height and SHA-256 hashed. This identifies the exact deployed code observed by the capture without claiming source-code verification.

## PDB v2 count

The script reads `nextParentId()` or, for compatible deployments, `nextNFTId()`. Because the counter begins at 1 and is incremented when a parent is minted, the parent-record count is `counter - 1`. It also publishes `totalSupply()` and the child counter separately. Child chunks are ERC-721 tokens used to extend large payloads; they are not independent molecular records.

## Reconstruction sample

The sample is declared in the script before capture:

```text
100D, 101D, 1CRN, 102M, 1AKE, 4HHB, 1AON, 1FNT
```

It is the same size-stratified set used by the public MOLNFT retrieval benchmark. GLAST is used only to resolve PDB IDs to token IDs; each mapping is then checked against the PDB ID stored in the contract at the pinned height.

For each token, the capture:

1. calls `getMetadata(tokenId)` at the pinned block and checks the on-chain `IDCODE`;
2. calls `getCombinedData(tokenId)` at the same block;
3. ABI-decodes the returned string;
4. base64-decodes it;
5. gunzips it when the gzip magic bytes are present;
6. writes the reconstructed `.bcif` bytes;
7. parses the BinaryCIF MessagePack container;
8. requires a nonzero `_atom_site` row count; and
9. requires `_atom_site.Cartn_x`, `_atom_site.Cartn_y`, and `_atom_site.Cartn_z` columns.

The package publishes the exact JSON-RPC request and response bytes, reconstructed objects, parsed measurements and SHA-256 digests.

## Legacy v1 subtotal

The legacy subtotal is the arithmetic sum of the two v1 `totalSupply()` observations. It is reported as a token count for an earlier storage generation documented as using IPFS assets. It is not added to the PDB v2 parent count because the generations can overlap scientifically and do not make the same storage claim.

## Limits of the evidence

A successful sample reconstruction proves that those sampled records were complete coordinate-bearing BinaryCIF objects recoverable from contract state at the pinned block. It does **not** prove that all parent records were exhaustively downloaded and decoded in this run.

Collection counters prove the values returned by the deployed contracts at the pinned height. They do not independently establish scientific uniqueness, absence of duplicate biological records, correctness of source annotations, or downstream scientific validity.

## Reproduction

```bash
python -m pip install requests eth-abi eth-utils msgpack
python molnft-evidence/scripts/capture_molnft_snapshot.py \
  --block 13412747 \
  --expected-block-hash 19F42CD995E384E09D5CD4FB2751668E613D762DD1F22301D065EC84950F0F9A

cd molnft-evidence/snapshots/block-13412747-*
sha256sum -c SHA256SUMS.txt
```

The capture is intentionally immutable for Article 02: any later block belongs in a new snapshot rather than silently replacing the evidence cited by the article. The committed snapshot is therefore both a research artifact and a versioned citation target.
