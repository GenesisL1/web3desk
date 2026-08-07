# GenesisL1 Web3Desk — Stateless HTML dApp

GenesisL1 Web3Desk is a fully static, client-side dashboard for interacting with the GenesisL1 / L1 coin network without a custom application backend. Each page communicates directly with public GenesisL1 RPC and REST endpoints, with optional external market-data sources, and supports Cosmos and EVM wallets where applicable.

## Included applications

- **Network dashboard** (`index.html`) — live supply, staking, community-pool and market indicators with responsive charts.
- **Staking and wallets** (`staking.html`) — EVM and Cosmos wallet discovery, address mapping, balances, delegation, redelegation, undelegation and reward claims.
- **Governance** (`gov.html`) — proposal discovery, proposal details, voting and governance deposits through compatible wallets.
- **IBC transfers** (`ibc.html`) — guided ICS-20 transfers between GenesisL1 and connected networks.
- **Explorer** (`explorer.html`) — lightweight blocks, transactions, validators, address and NFT views using public network interfaces.
- **Optional metrics helper** (`gl1_api.py`) — a small local service for cached network indicators when desired.

## Architecture

The browser-facing application is intentionally static. It can be hosted as ordinary files and does not require a project-controlled server for wallet signing or chain interaction. Users should verify transaction details in their wallet before signing and may replace the configured public endpoints with trusted alternatives.

## Run locally

```bash
git clone https://github.com/GenesisL1/web3desk.git
cd web3desk
python -m http.server 8080
```

Open `http://localhost:8080/`.

The optional metrics helper can be started separately:

```bash
python gl1_api.py
```

## Related repositories

Long-form GenesisL1 publications, source graphics and reproducible evidence packages are maintained separately in [GenesisL1/insights](https://github.com/GenesisL1/insights).

## Development priorities

- consolidate the transaction stack into a GenesisL1-focused JavaScript package;
- extend EVM-wallet support for IBC and governance operations;
- preserve the static, independently hostable deployment model;
- improve automated browser and transaction-path testing.

## License

See the license notices embedded in the source files and any repository-level licensing materials.
