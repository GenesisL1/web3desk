# GenesisL1 Web3Desk (Stateless HTML dApp)

GenesisL1 Web3Desk is a fully static, client-side dashboard that lets any browser interact with the GenesisL1 / L1coin network without a custom backend. Each HTML page talks directly to public RPC/LCD endpoints (plus optional Osmosis market data) and works with both Cosmos (Keplr) and EVM wallets where applicable.

## What the dApp does today

- **GenesisL1 chain stats** (`index.html`): Live circulating supply, staking totals, community pool balance, Osmosis-driven spot price and market cap estimates, plus a responsive supply composition chart. Everything refreshes on a short timer and resizes fluidly for embeds.
- **Staking & wallets** (`staking.html`): Dual EVM + Cosmos wallet panel (MetaMask/Rabby + Keplr) with bech32/hex address mapping, balance checks, quick send from EVM to Keplr, and staking flows (delegate, redelegate, undelegate, claim rewards) using `evmosjs` + `ethers` over LCD/RPC—no server needed.
- **Governance** (`gov.html`): Proposal list and detail views with on-page vote/deposit actions through Keplr, including per-option tallies and minimal signatures for verification. Uses the same stateless wallet discovery stack as staking.
- **IBC transfers** (`ibc.html`): Guided ICS-20 transfers between GenesisL1 and Osmosis with channel defaults (`channel-1` / `channel-253`), Keplr signing, timeout helpers, and status toasts to keep users informed through broadcast/relay steps.
- **Block explorer** (`explorer.html`): Lightweight, iframe-friendly explorer that pulls recent blocks, unified Cosmos+EVM transactions, validator snapshots, and address/tx lookups directly from RPC/LCD. Responsive cards and hash-shortening make it usable on mobile or embedded tabs.

## Things still to build

- Refactor `evmosjs` into a `genesisl1js` bundle that ships every required message type in a modern, CDN-friendly package.
- Enable IBC flows through EVM wallets like MetaMask (not just Keplr), including signing and fee handling.
- Allow governance deposits and proposals to be created from MetaMask/EVM wallets alongside existing Keplr support.

## Running it locally

Because the app is static, you only need a simple file server (or open the HTML files directly). For friendlier CORS behavior, serve the folder and open `index.html`:

```bash
cd web3desk
python -m http.server 8080
# then visit http://localhost:8080/index.html
```

If you prefer cached supply/community-pool data, the optional `gl1_api.py` helper exposes `/api.json` with LCD-derived metrics:

```bash
python gl1_api.py  # listens on 0.0.0.0:8787
