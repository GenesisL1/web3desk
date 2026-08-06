# GenesisL1 decentralization snapshot methodology

This directory publishes reproducible, height-pinned observations of the GenesisL1 (`genesis_29-2`) active consensus set.

## What is measured

The primary distribution is calculated from the `voting_power` values returned by the CometBFT `/validators` RPC at one exact block height. Bonded staking records are fetched at the same height through the Cosmos REST API and matched to consensus validators by Ed25519 consensus public key so the report can attach monikers, operator addresses and commission metadata.

The CometBFT validator set is the authoritative basis for the headline consensus metrics. Staking `tokens` are retained as supporting data, not substituted for consensus voting power.

## Height pinning

1. The script reads the RPC tip.
2. Unless an explicit historical height is supplied, it selects a finalized height two blocks behind the observed tip.
3. It fetches the block and validator set from CometBFT at that exact height.
4. It sends `x-cosmos-block-height: <height>` to each REST query.
5. Any returned height header that disagrees with the requested height causes the provider attempt to fail.
6. If a paired REST endpoint trails its RPC endpoint, the script can retry at a slightly older height, up to the configured limit. The exact lag is recorded.

## Published raw evidence

Each snapshot contains the unmodified response bytes from:

- RPC `/status`;
- RPC `/block?height=...`;
- every RPC `/validators` page;
- every height-pinned REST bonded-validator page;
- the height-pinned REST staking-parameters query.

The snapshot also contains:

- `snapshot.json` — metadata and computed metrics;
- `validators.csv` — ranked consensus set;
- `README.md` — human-readable report;
- `SHA256SUMS.txt` — SHA-256 digest for every evidence and result file;
- `MANIFEST.json` — file size and digest manifest.

## Metric definitions

Let validator voting-power shares sorted from largest to smallest be `p1 ... pn`.

- **Top-k share:** `sum(p1 ... pk)`.
- **One-third coefficient (≥ 1/3):** smallest `k` whose cumulative share is at least one-third. A cohort at exactly one-third leaves at most two-thirds outside it, which is insufficient for CometBFT's strictly-greater-than-two-thirds commit rule.
- **One-third coefficient (> 1/3):** also published to remove any ambiguity at the boundary.
- **Two-thirds coefficient (> 2/3):** smallest `k` whose cumulative share strictly exceeds two-thirds and can therefore supply the voting-power threshold used for commit.
- **HHI:** sum of squared shares; published as both a 0–1 fraction and a 0–10,000 index.
- **Effective validator count:** reciprocal of HHI.
- **Gini coefficient:** inequality of voting power across active validators.
- **Normalized entropy:** Shannon entropy divided by `ln(n)`, ranging from 0 to 1.

## What the snapshot does not prove

On-chain validator records do not prove that differently named validators have independent beneficial owners, signing-key custody, hosting providers, jurisdictions or upgrade control. The report therefore describes **observable consensus distribution**, not a complete social-independence audit.

## Verification

From the repository root:

```bash
python decentralization/scripts/capture_validator_snapshot.py
cd decentralization/latest
sha256sum -c SHA256SUMS.txt
```

The script uses only the Python standard library.
