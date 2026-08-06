# GenesisL1 decentralization snapshot

**Pinned block:** `13412747`  
**Block time:** `2026-08-06T12:29:02.693197721Z`  
**Captured:** `2026-08-06T12:30:13Z`  
**Block hash:** `19F42CD995E384E09D5CD4FB2751668E613D762DD1F22301D065EC84950F0F9A`  
**Provider:** `ANODE.TEAM`

## Exact results

| Metric | Result |
|---|---:|
| Active consensus validators | **26** |
| Protocol maximum | **50** |
| Largest validator | **9.35831582%** |
| Top 3 | **25.27219345%** |
| Top 5 | **38.74159708%** |
| Top 10 | **67.24438276%** |
| One-third coefficient (≥ 1/3) | **5** |
| One-third coefficient (> 1/3) | **5** |
| Two-thirds coefficient (≥ 2/3) | **10** |
| Two-thirds coefficient (> 2/3) | **10** |
| HHI (0–10,000) | **567.31** |
| Effective validator count | **17.63** |
| Gini coefficient | **0.3919** |
| Normalized entropy | **0.9213** |

## Ranked validator set

| Rank | Validator | Voting power | Share | Cumulative |
|---:|---|---:|---:|---:|
| 1 | anodeofzen | 2,290,264 | 9.35831582% | 9.35831582% |
| 2 | OG Oganesson | 2,058,579 | 8.41162085% | 17.76993668% |
| 3 | ⚡ FirstTensor.com ⚡ 4% Fee | 1,836,030 | 7.50225677% | 25.27219345% |
| 4 | CryptmasGhost | 1,661,203 | 6.78789097% | 32.06008441% |
| 5 | BlueHole-II | 1,635,169 | 6.68151267% | 38.74159708% |
| 6 | Calcium by Faust | 1,554,901 | 6.3535272% | 45.09512428% |
| 7 | Elon_Nodes 🌌 Galactic | 1,541,435 | 6.29850338% | 51.39362766% |
| 8 | LCserve | 1,494,652 | 6.10734197% | 57.50096964% |
| 9 | 𝐥𝐞𝐬𝐧𝐢𝐤 \| 𝐔𝐓𝐒𝐀 | 1,211,590 | 4.95071392% | 62.45168356% |
| 10 | ALL-STARS | 1,172,919 | 4.7926992% | 67.24438276% |
| 11 | ⬢ 𝐅𝐢𝐫𝐬𝐭𝐁𝐥𝐨𝐜𝐤 ⬢ | 1,146,352 | 4.68414299% | 71.92852575% |
| 12 | bgvcvaloper | 1,034,438 | 4.22684787% | 76.15537361% |
| 13 | Aluminium | 975,029 | 3.98409499% | 80.1394686% |
| 14 | ZEUSvF | 856,304 | 3.49896923% | 83.63843783% |
| 15 | vanpe | 674,682 | 2.75683818% | 86.39527601% |
| 16 | ELIO | 587,158 | 2.39920376% | 88.79447977% |
| 17 | Vicky_Pulsican | 519,443 | 2.12251149% | 90.91699126% |
| 18 | LADA | 451,274 | 1.84396411% | 92.76095536% |
| 19 | Aurie | 426,538 | 1.7428896% | 94.50384497% |
| 20 | AlxVoy ⚡ ANODE.TEAM | 334,023 | 1.36486131% | 95.86870628% |
| 21 | StingRay | 212,773 | 0.86941808% | 96.73812436% |
| 22 | 🔥STAVR🔥 REStake ON✅ | 209,823 | 0.857364% | 97.59548836% |
| 23 | StakeUp | 199,544 | 0.81536267% | 98.41085103% |
| 24 | LiveRaveN | 182,435 | 0.74545308% | 99.15630411% |
| 25 | 5ElementsNodes | 110,100 | 0.44988288% | 99.60618699% |
| 26 | BlockPro | 96,378 | 0.39381301% | 100% |

## Threshold interpretation

CometBFT commits a block with **more than two-thirds** of voting power. The one-third coefficient is therefore primarily a liveness measure: a coordinated cohort at or above one-third can leave the remainder unable to exceed two-thirds. It cannot, by itself, supply the signatures required to commit arbitrary state. The two-thirds coefficient is the smallest leading cohort whose cumulative voting power is strictly above the commit threshold.

Validator entries prove on-chain voting-power distribution. They do not, by themselves, prove independent beneficial ownership, signing-key custody, hosting provider, jurisdiction or operational control. Those are separate decentralization dimensions and should remain unknown unless independently evidenced.

## Reproduce

```bash
python decentralization/scripts/capture_validator_snapshot.py --output-root decentralization/snapshots
cd decentralization/latest && sha256sum -c SHA256SUMS.txt
```
