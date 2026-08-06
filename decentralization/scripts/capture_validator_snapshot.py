#!/usr/bin/env python3
"""Capture a cryptographically reproducible GenesisL1 consensus snapshot.

The capture is pinned to one finalized block height. It preserves the exact raw
JSON bytes returned by the selected RPC and REST endpoints, calculates metrics
from CometBFT voting power, emits a ranked CSV and Markdown report, and writes
SHA-256 checksums for every published file.

Only the Python standard library is required.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Any, Iterable

getcontext().prec = 80

CHAIN_ID = "genesis_29-2"
USER_AGENT = "GenesisL1-Decentralization-Snapshot/2.0 (+https://genesisl1.com/)"
PROVIDERS = [
    {
        "name": "ANODE.TEAM",
        "rpc": "https://genesisl1.rpc.m.anode.team",
        "rest": "https://genesisl1.api.m.anode.team",
    },
    {
        "name": "GenesisL1 public",
        "rpc": "https://26657.genesisl1.org",
        "rest": "https://1317.genesisl1.org",
    },
    {
        "name": "UTSA",
        "rpc": "https://m-l1.rpc.utsa.tech",
        "rest": "https://m-l1.api.utsa.tech",
    },
]


@dataclass(frozen=True)
class HttpResult:
    url: str
    raw: bytes
    payload: Any
    headers: dict[str, str]
    status: int


@dataclass(frozen=True)
class ConsensusRow:
    rank: int
    moniker: str
    operator_address: str
    consensus_address: str
    consensus_pubkey_b64: str
    voting_power: int
    share: Decimal
    cumulative_share: Decimal
    tokens_atomic: int | None
    commission_rate: str
    website: str


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def request(url: str, *, headers: dict[str, str] | None = None, timeout: float = 25.0, retries: int = 3) -> HttpResult:
    req_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                return HttpResult(
                    url=url,
                    raw=raw,
                    payload=json.loads(raw.decode("utf-8")),
                    headers={k.lower(): v for k, v in response.headers.items()},
                    status=int(response.status),
                )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
    assert last is not None
    raise last


def canonical_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_bytes(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: pathlib.Path, payload: Any) -> None:
    write_bytes(path, canonical_json_bytes(payload))


def parse_rpc_status(result: HttpResult) -> tuple[int, str, str, str]:
    body = result.payload.get("result", {})
    sync = body.get("sync_info", {})
    node = body.get("node_info", {})
    height = int(sync["latest_block_height"])
    return height, str(sync.get("latest_block_time", "")), str(node.get("network", "")), str(node.get("version", ""))


def parse_block(result: HttpResult) -> tuple[int, str, str, str]:
    body = result.payload.get("result", {})
    block = body.get("block", {})
    header = block.get("header", {})
    height = int(header["height"])
    return height, str(header.get("time", "")), str((body.get("block_id") or {}).get("hash", "")), str(header.get("app_hash", ""))


def fetch_rpc_validators(rpc: str, height: int, raw_dir: pathlib.Path, timeout: float, retries: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validators: list[dict[str, Any]] = []
    page_meta: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{rpc.rstrip('/')}/validators?" + urllib.parse.urlencode({"height": height, "page": page, "per_page": 100})
        result = request(url, timeout=timeout, retries=retries)
        write_bytes(raw_dir / f"rpc-validators-page-{page}.json", result.raw)
        body = result.payload.get("result", {})
        page_rows = body.get("validators") or []
        validators.extend(page_rows)
        total = int(body.get("total") or len(validators))
        page_meta.append({"page": page, "url": url, "count": len(page_rows), "total": total})
        if len(validators) >= total or not page_rows:
            break
        page += 1
        if page > 100:
            raise RuntimeError("RPC validator pagination exceeded 100 pages")
    return validators, page_meta


def fetch_rest_pages(rest: str, height: int, raw_dir: pathlib.Path, timeout: float, retries: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validators: list[dict[str, Any]] = []
    page_meta: list[dict[str, Any]] = []
    next_key = ""
    page = 1
    while True:
        params: dict[str, str] = {
            "status": "BOND_STATUS_BONDED",
            "pagination.limit": "200",
            "pagination.count_total": "true",
        }
        if next_key:
            params["pagination.key"] = next_key
        url = f"{rest.rstrip('/')}/cosmos/staking/v1beta1/validators?{urllib.parse.urlencode(params)}"
        result = request(url, headers={"x-cosmos-block-height": str(height)}, timeout=timeout, retries=retries)
        observed = result.headers.get("x-cosmos-block-height")
        if observed is not None and int(observed) != height:
            raise RuntimeError(f"REST height mismatch: requested {height}, response header {observed}")
        write_bytes(raw_dir / f"lcd-staking-validators-page-{page}.json", result.raw)
        page_rows = result.payload.get("validators") or []
        validators.extend(page_rows)
        pagination = result.payload.get("pagination") or {}
        next_key = pagination.get("next_key") or ""
        page_meta.append({
            "page": page,
            "url": url,
            "count": len(page_rows),
            "response_height_header": observed,
            "pagination_total": pagination.get("total"),
        })
        if not next_key:
            break
        page += 1
        if page > 100:
            raise RuntimeError("REST validator pagination exceeded 100 pages")
    return validators, page_meta


def consensus_pubkey_b64(staking_validator: dict[str, Any]) -> str:
    pk = staking_validator.get("consensus_pubkey") or {}
    return str(pk.get("key") or pk.get("value") or pk.get("ed25519") or "")


def rpc_pubkey_b64(consensus_validator: dict[str, Any]) -> str:
    pk = consensus_validator.get("pub_key") or {}
    return str(pk.get("value") or pk.get("key") or "")


def decimal_percent(value: Decimal, places: int = 8) -> str:
    return f"{value * Decimal(100):.{places}f}".rstrip("0").rstrip(".")


def threshold_coefficient(powers: list[int], *, numerator: int, denominator: int, strict: bool) -> int | None:
    total = sum(powers)
    cumulative = 0
    for index, power in enumerate(powers, 1):
        cumulative += power
        left = cumulative * denominator
        right = total * numerator
        if left > right if strict else left >= right:
            return index
    return None


def gini(values: list[int]) -> Decimal:
    if not values or sum(values) == 0:
        return Decimal(0)
    ordered = sorted(values)
    n = len(ordered)
    numerator = sum((2 * i - n - 1) * value for i, value in enumerate(ordered, 1))
    return Decimal(numerator) / Decimal(n * sum(ordered))


def normalized_entropy(shares: Iterable[Decimal]) -> Decimal:
    values = [float(x) for x in shares if x > 0]
    n = len(values)
    if n <= 1:
        return Decimal(0)
    entropy = -sum(p * math.log(p) for p in values)
    return Decimal(str(entropy / math.log(n)))


def build_rows(rpc_validators: list[dict[str, Any]], staking_validators: list[dict[str, Any]]) -> tuple[list[ConsensusRow], dict[str, Any]]:
    staking_by_pubkey = {consensus_pubkey_b64(v): v for v in staking_validators if consensus_pubkey_b64(v)}
    normalized: list[dict[str, Any]] = []
    matched = 0
    for item in rpc_validators:
        power = int(item.get("voting_power") or 0)
        pubkey = rpc_pubkey_b64(item)
        staking = staking_by_pubkey.get(pubkey)
        if staking is not None:
            matched += 1
        description = (staking or {}).get("description") or {}
        commission = (((staking or {}).get("commission") or {}).get("commission_rates") or {}).get("rate") or ""
        tokens = None
        if staking is not None and staking.get("tokens") is not None:
            tokens = int(staking["tokens"])
        normalized.append({
            "moniker": str(description.get("moniker") or "Unmatched consensus validator"),
            "operator_address": str((staking or {}).get("operator_address") or ""),
            "consensus_address": str(item.get("address") or ""),
            "consensus_pubkey_b64": pubkey,
            "voting_power": power,
            "tokens_atomic": tokens,
            "commission_rate": str(commission),
            "website": str(description.get("website") or ""),
        })
    normalized.sort(key=lambda row: (-row["voting_power"], row["consensus_address"]))
    total = sum(row["voting_power"] for row in normalized)
    if total <= 0:
        raise ValueError("Total consensus voting power is zero")
    cumulative = Decimal(0)
    rows: list[ConsensusRow] = []
    for rank, row in enumerate(normalized, 1):
        share = Decimal(row["voting_power"]) / Decimal(total)
        cumulative += share
        rows.append(ConsensusRow(rank=rank, share=share, cumulative_share=cumulative, **row))
    match = {
        "consensus_validator_count": len(rpc_validators),
        "staking_bonded_validator_count": len(staking_validators),
        "matched_by_consensus_pubkey": matched,
        "unmatched_consensus_validators": len(rpc_validators) - matched,
        "unused_staking_records": len(staking_validators) - matched,
    }
    return rows, match


def calculate_metrics(rows: list[ConsensusRow], max_validators: int | None) -> dict[str, Any]:
    powers = [r.voting_power for r in rows]
    total = sum(powers)
    shares = [r.share for r in rows]
    hhi = sum((s * s for s in shares), Decimal(0))

    def top(n: int) -> Decimal:
        return sum(shares[:n], Decimal(0))

    return {
        "basis": "CometBFT validator-set voting_power at the pinned height",
        "active_consensus_validators": len(rows),
        "protocol_max_validators": max_validators,
        "active_set_utilization_percent": decimal_percent(Decimal(len(rows)) / Decimal(max_validators), 4) if max_validators else None,
        "total_consensus_voting_power": str(total),
        "largest_validator_share_percent": decimal_percent(top(1)),
        "top_3_share_percent": decimal_percent(top(3)),
        "top_5_share_percent": decimal_percent(top(5)),
        "top_10_share_percent": decimal_percent(top(10)),
        "coefficient_at_or_above_one_third": threshold_coefficient(powers, numerator=1, denominator=3, strict=False),
        "coefficient_strictly_above_one_third": threshold_coefficient(powers, numerator=1, denominator=3, strict=True),
        "coefficient_at_or_above_two_thirds": threshold_coefficient(powers, numerator=2, denominator=3, strict=False),
        "coefficient_strictly_above_two_thirds": threshold_coefficient(powers, numerator=2, denominator=3, strict=True),
        "hhi_fraction": format(hhi, "f"),
        "hhi_10000": format(hhi * Decimal(10000), "f"),
        "effective_validator_count": format(Decimal(1) / hhi if hhi else Decimal(0), "f"),
        "gini_coefficient": format(gini(powers), "f"),
        "normalized_entropy": format(normalized_entropy(shares), "f"),
    }


def write_csv(path: pathlib.Path, rows: list[ConsensusRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "rank", "moniker", "operator_address", "consensus_address", "consensus_pubkey_b64",
            "voting_power", "share_percent", "cumulative_share_percent", "tokens_atomic",
            "commission_rate", "website",
        ])
        for row in rows:
            writer.writerow([
                row.rank, row.moniker, row.operator_address, row.consensus_address,
                row.consensus_pubkey_b64, row.voting_power, decimal_percent(row.share),
                decimal_percent(row.cumulative_share), row.tokens_atomic if row.tokens_atomic is not None else "",
                row.commission_rate, row.website,
            ])


def format_decimal(value: str, places: int) -> str:
    return f"{Decimal(value):.{places}f}"


def write_summary(path: pathlib.Path, snapshot: dict[str, Any], rows: list[ConsensusRow]) -> None:
    meta = snapshot["metadata"]
    m = snapshot["metrics"]
    lines = [
        "# GenesisL1 decentralization snapshot",
        "",
        f"**Pinned block:** `{meta['pinned_height']}`  ",
        f"**Block time:** `{meta['block_time_utc']}`  ",
        f"**Captured:** `{meta['captured_at_utc']}`  ",
        f"**Block hash:** `{meta['block_hash']}`  ",
        f"**Provider:** `{meta['provider_name']}`",
        "",
        "## Exact results",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Active consensus validators | **{m['active_consensus_validators']}** |",
        f"| Protocol maximum | **{m['protocol_max_validators']}** |",
        f"| Largest validator | **{m['largest_validator_share_percent']}%** |",
        f"| Top 3 | **{m['top_3_share_percent']}%** |",
        f"| Top 5 | **{m['top_5_share_percent']}%** |",
        f"| Top 10 | **{m['top_10_share_percent']}%** |",
        f"| One-third coefficient (≥ 1/3) | **{m['coefficient_at_or_above_one_third']}** |",
        f"| One-third coefficient (> 1/3) | **{m['coefficient_strictly_above_one_third']}** |",
        f"| Two-thirds coefficient (≥ 2/3) | **{m['coefficient_at_or_above_two_thirds']}** |",
        f"| Two-thirds coefficient (> 2/3) | **{m['coefficient_strictly_above_two_thirds']}** |",
        f"| HHI (0–10,000) | **{format_decimal(m['hhi_10000'], 2)}** |",
        f"| Effective validator count | **{format_decimal(m['effective_validator_count'], 2)}** |",
        f"| Gini coefficient | **{format_decimal(m['gini_coefficient'], 4)}** |",
        f"| Normalized entropy | **{format_decimal(m['normalized_entropy'], 4)}** |",
        "",
        "## Ranked validator set",
        "",
        "| Rank | Validator | Voting power | Share | Cumulative |",
        "|---:|---|---:|---:|---:|",
    ]
    for row in rows:
        name = row.moniker.replace("|", "\\|")
        lines.append(f"| {row.rank} | {name} | {row.voting_power:,} | {decimal_percent(row.share)}% | {decimal_percent(row.cumulative_share)}% |")
    lines += [
        "",
        "## Threshold interpretation",
        "",
        "CometBFT commits a block with **more than two-thirds** of voting power. The one-third coefficient is therefore primarily a liveness measure: a coordinated cohort at or above one-third can leave the remainder unable to exceed two-thirds. It cannot, by itself, supply the signatures required to commit arbitrary state. The two-thirds coefficient is the smallest leading cohort whose cumulative voting power is strictly above the commit threshold.",
        "",
        "Validator entries prove on-chain voting-power distribution. They do not, by themselves, prove independent beneficial ownership, signing-key custody, hosting provider, jurisdiction or operational control. Those are separate decentralization dimensions and should remain unknown unless independently evidenced.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "python decentralization/scripts/capture_validator_snapshot.py --output-root decentralization/snapshots",
        "cd decentralization/latest && sha256sum -c SHA256SUMS.txt",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def sha256sum(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(directory: pathlib.Path) -> None:
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.name not in {"SHA256SUMS.txt", "MANIFEST.json"})
    rows = []
    manifest = []
    for path in files:
        rel = path.relative_to(directory).as_posix()
        digest = sha256sum(path)
        rows.append(f"{digest}  {rel}")
        manifest.append({"path": rel, "bytes": path.stat().st_size, "sha256": digest})
    (directory / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    write_json(directory / "MANIFEST.json", {"algorithm": "SHA-256", "files": manifest})


def copy_latest(snapshot_dir: pathlib.Path, latest_dir: pathlib.Path) -> None:
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(snapshot_dir, latest_dir)


def provider_candidates(args: argparse.Namespace) -> list[dict[str, str]]:
    if args.rpc and args.rest:
        return [{"name": args.provider_name or "custom", "rpc": args.rpc, "rest": args.rest}]
    return PROVIDERS


def capture_with_provider(provider: dict[str, str], args: argparse.Namespace, staging: pathlib.Path) -> tuple[pathlib.Path, dict[str, Any]]:
    rpc = provider["rpc"].rstrip("/")
    rest = provider["rest"].rstrip("/")
    raw_dir = staging / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    status = request(f"{rpc}/status", timeout=args.timeout, retries=args.retries)
    write_bytes(raw_dir / "rpc-status.json", status.raw)
    latest_height, latest_time, network, comet_version = parse_rpc_status(status)
    if network != CHAIN_ID:
        raise RuntimeError(f"Unexpected chain ID from RPC: {network!r}")

    requested = args.height
    lag_used = args.lag_blocks
    while True:
        pinned = requested if requested is not None else latest_height - lag_used
        if pinned <= 0:
            raise RuntimeError("Pinned height is not positive")
        try:
            block = request(f"{rpc}/block?height={pinned}", timeout=args.timeout, retries=args.retries)
            write_bytes(raw_dir / "rpc-block.json", block.raw)
            block_height, block_time, block_hash, app_hash = parse_block(block)
            if block_height != pinned:
                raise RuntimeError(f"RPC block mismatch: requested {pinned}, got {block_height}")

            rpc_validators, rpc_pages = fetch_rpc_validators(rpc, pinned, raw_dir, args.timeout, args.retries)
            staking_validators, rest_pages = fetch_rest_pages(rest, pinned, raw_dir, args.timeout, args.retries)

            params_url = f"{rest}/cosmos/staking/v1beta1/params"
            params = request(params_url, headers={"x-cosmos-block-height": str(pinned)}, timeout=args.timeout, retries=args.retries)
            observed = params.headers.get("x-cosmos-block-height")
            if observed is not None and int(observed) != pinned:
                raise RuntimeError(f"Staking params height mismatch: requested {pinned}, response {observed}")
            write_bytes(raw_dir / "lcd-staking-params.json", params.raw)
            break
        except Exception:
            if requested is not None or lag_used >= args.max_lag_blocks:
                raise
            lag_used += 2
            shutil.rmtree(raw_dir)
            raw_dir.mkdir(parents=True, exist_ok=True)
            write_bytes(raw_dir / "rpc-status.json", status.raw)

    rows, matching = build_rows(rpc_validators, staking_validators)
    params_body = params.payload.get("params") or {}
    max_validators_raw = params_body.get("max_validators")
    max_validators = int(max_validators_raw) if max_validators_raw is not None else None
    metrics = calculate_metrics(rows, max_validators)

    metadata = {
        "schema": "org.genesisl1.decentralization_snapshot.v2",
        "network": "GenesisL1",
        "chain_id": CHAIN_ID,
        "provider_name": provider["name"],
        "rpc_endpoint": rpc,
        "rest_endpoint": rest,
        "captured_at_utc": utc_now(),
        "rpc_latest_height_at_start": latest_height,
        "rpc_latest_time_at_start": latest_time,
        "pinned_height": pinned,
        "lag_blocks_from_rpc_tip": latest_height - pinned,
        "block_time_utc": block_time,
        "block_hash": block_hash,
        "app_hash": app_hash,
        "cometbft_version": comet_version,
        "height_verification": {
            "rpc_block_height": block_height,
            "rest_validator_page_headers": [page.get("response_height_header") for page in rest_pages],
            "rest_params_height_header": observed,
        },
        "raw_rpc_validator_pages": rpc_pages,
        "raw_rest_validator_pages": rest_pages,
        "matching": matching,
        "methodology_version": "2.0.0",
    }
    snapshot = {"metadata": metadata, "metrics": metrics}
    write_json(staging / "snapshot.json", snapshot)
    write_csv(staging / "validators.csv", rows)
    write_summary(staging / "README.md", snapshot, rows)
    write_checksums(staging)
    return staging, snapshot


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="decentralization/snapshots", help="Directory in which dated snapshots are created")
    parser.add_argument("--latest-dir", default="decentralization/latest", help="Directory replaced with the newest snapshot")
    parser.add_argument("--height", type=int, help="Explicit historical height; otherwise pin near the current tip")
    parser.add_argument("--lag-blocks", type=int, default=2, help="Initial lag behind RPC tip for a current capture")
    parser.add_argument("--max-lag-blocks", type=int, default=40, help="Maximum automatic lag if REST trails RPC")
    parser.add_argument("--rpc", help="Custom CometBFT RPC base URL; requires --rest")
    parser.add_argument("--rest", help="Custom Cosmos REST base URL; requires --rpc")
    parser.add_argument("--provider-name", help="Label for custom provider")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--no-latest", action="store_true", help="Do not replace the latest directory")
    args = parser.parse_args(argv)
    if bool(args.rpc) != bool(args.rest):
        parser.error("--rpc and --rest must be supplied together")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = pathlib.Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []

    for provider in provider_candidates(args):
        staging = root / f".capture-{os.getpid()}-{int(time.time())}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        try:
            _, snapshot = capture_with_provider(provider, args, staging)
            meta = snapshot["metadata"]
            stamp = str(meta["block_time_utc"]).replace("-", "").replace(":", "").replace(".", "").replace("Z", "Z")
            final_name = f"height-{meta['pinned_height']}-{stamp}"
            final_dir = root / final_name
            if final_dir.exists():
                shutil.rmtree(final_dir)
            staging.rename(final_dir)
            if not args.no_latest:
                copy_latest(final_dir, pathlib.Path(args.latest_dir))
            print(json.dumps(snapshot, indent=2))
            print(f"\nSnapshot: {final_dir}")
            print(f"Latest:   {args.latest_dir if not args.no_latest else '(not updated)'}")
            return 0
        except Exception as exc:
            failures.append({"provider": provider["name"], "type": type(exc).__name__, "message": str(exc)})
            shutil.rmtree(staging, ignore_errors=True)

    print(json.dumps({"captured_at_utc": utc_now(), "failures": failures}, indent=2), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
