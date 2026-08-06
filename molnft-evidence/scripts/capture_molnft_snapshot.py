#!/usr/bin/env python3
"""Capture a pinned, reproducible MOLNFT evidence snapshot.

The snapshot separates three claims:

1. exact ERC-721 collection counts at one GenesisL1 block;
2. exact deployed-code hashes at that block; and
3. direct reconstruction of a predeclared sample of MOLNFT PDB v2 records from
   contract state into BinaryCIF bytes, including coordinate-column checks.

It does *not* infer that every record in the collection was reconstructed. The
sample result and the collection count are reported independently.
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import re
import shutil
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable

import msgpack
import requests
from eth_abi import decode, encode
from eth_utils import keccak, to_checksum_address

CHAIN_ID_DECIMAL = 29
DEFAULT_BLOCK = 13_412_747
DEFAULT_BLOCK_HASH = "0x19F42CD995E384E09D5CD4FB2751668E613D762DD1F22301D065EC84950F0F9A"

RPC_PROVIDERS = [
    ("GenesisL1 public", "https://rpc.genesisl1.org"),
    ("GenesisL1 direct", "https://rpca.genesisl1.org"),
    ("ANODE.TEAM", "https://genesisl1.rpc.m.anode.team"),
    ("UTSA", "https://m-l1.rpc.utsa.tech"),
]

GLAST_URL = "https://api.molnft.org/api/nft_by_idcode"
USER_AGENT = "GenesisL1-MOLNFT-Evidence/1.0 (+https://genesisl1.com/)"

CONTRACTS = {
    "pdb_v2": {
        "name": "MOLNFT PDB v2 — full on-chain BinaryCIF payloads",
        "address": "0xd58B01f6C18086e5202cdC5D7Ad3E41790360102",
        "storage_generation": "v2_full_payload",
    },
    "pdb_v1": {
        "name": "MOLNFT PDB v1 — legacy ERC-721 collection",
        "address": "0xDE3723766Bc32dcACD03C17BaA400A7B36837Eba",
        "storage_generation": "v1_legacy_ipfs_asset",
    },
    "af_v1": {
        "name": "MOLNFT AlphaFold/Swiss-Prot v1 — legacy ERC-721 collection",
        "address": "0xBf7491af3407816DFa88a5EA4c82e8A2B1D721eD",
        "storage_generation": "v1_legacy_ipfs_asset",
    },
}

# Declared before the capture. This is a size-stratified set already used by the
# public MOLNFT benchmark, not a post-hoc selection based on capture success.
SAMPLE_IDCODES = ["100D", "101D", "1CRN", "102M", "1AKE", "4HHB", "1AON", "1FNT"]


@dataclass
class RpcResult:
    method: str
    params: list[Any]
    request_id: int
    raw: bytes
    payload: dict[str, Any]
    url: str


class RpcError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_bytes(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: pathlib.Path, value: Any) -> None:
    write_bytes(path, canonical_json_bytes(value))


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "item"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def function_selector(signature: str) -> bytes:
    return keccak(text=signature)[:4]


def call_data(signature: str, arg_types: list[str] | None = None, args: list[Any] | None = None) -> str:
    payload = function_selector(signature)
    if arg_types:
        payload += encode(arg_types, args or [])
    return "0x" + payload.hex()


def rpc_post(session: requests.Session, url: str, method: str, params: list[Any], request_id: int, timeout: float, retries: int) -> RpcResult:
    body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.post(url, json=body, timeout=timeout)
            raw = response.content
            response.raise_for_status()
            payload = response.json()
            if payload.get("error") is not None:
                raise RpcError(f"{method}: {payload['error']}")
            if "result" not in payload:
                raise RpcError(f"{method}: response has no result")
            return RpcResult(method, params, request_id, raw, payload, url)
        except (requests.RequestException, ValueError, RpcError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
    assert last is not None
    raise last


def save_rpc(raw_dir: pathlib.Path, name: str, result: RpcResult) -> None:
    write_bytes(raw_dir / f"{safe_name(name)}.response.json", result.raw)
    write_json(raw_dir / f"{safe_name(name)}.request.json", {"url": result.url, "jsonrpc": "2.0", "id": result.request_id, "method": result.method, "params": result.params})


def eth_call(session: requests.Session, rpc_url: str, to: str, data: str, block_hex: str, request_id: int, timeout: float, retries: int) -> RpcResult:
    return rpc_post(session, rpc_url, "eth_call", [{"to": to_checksum_address(to), "data": data}, block_hex], request_id, timeout, retries)


def decode_uint(result_hex: str) -> int:
    return int(decode(["uint256"], bytes.fromhex(result_hex.removeprefix("0x")))[0])


def decode_string(result_hex: str) -> str:
    return str(decode(["string"], bytes.fromhex(result_hex.removeprefix("0x")))[0])


def decode_metadata(result_hex: str) -> tuple[str, ...]:
    return tuple(str(x) for x in decode(["string"] * 11, bytes.fromhex(result_hex.removeprefix("0x"))))


def rpc_counter(session: requests.Session, rpc_url: str, address: str, signatures: Iterable[str], block_hex: str, raw_dir: pathlib.Path, prefix: str, id_counter: list[int], timeout: float, retries: int) -> tuple[str, int]:
    errors: list[str] = []
    for signature in signatures:
        id_counter[0] += 1
        try:
            result = eth_call(session, rpc_url, address, call_data(signature), block_hex, id_counter[0], timeout, retries)
            save_rpc(raw_dir, f"{prefix}-{signature[:-2]}", result)
            return signature, decode_uint(str(result.payload["result"]))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{signature}: {type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(errors))


def resolve_token(session: requests.Session, idcode: str, raw_dir: pathlib.Path, timeout: float, retries: int) -> int:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(GLAST_URL, params={"code": idcode}, timeout=timeout)
            write_bytes(raw_dir / f"glast-{safe_name(idcode)}.response.json", response.content)
            write_json(raw_dir / f"glast-{safe_name(idcode)}.request.json", {"url": response.url, "method": "GET"})
            response.raise_for_status()
            payload = response.json()
            token = payload.get("NFTID")
            if payload.get("status") != "success" or token is None:
                raise RuntimeError(f"GLAST response did not resolve {idcode}: {payload}")
            return int(token)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
    assert last is not None
    raise last


def inspect_binary_cif(data: bytes) -> dict[str, Any]:
    root = msgpack.unpackb(data, raw=False, strict_map_key=False)
    if not isinstance(root, dict):
        raise ValueError("BinaryCIF root is not a map")
    blocks = root.get("dataBlocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("BinaryCIF has no dataBlocks")

    categories_seen: list[str] = []
    atom_site_rows = 0
    atom_site_columns: list[str] = []
    block_headers: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_headers.append(str(block.get("header") or ""))
        for category in block.get("categories") or []:
            if not isinstance(category, dict):
                continue
            name = str(category.get("name") or "")
            categories_seen.append(name)
            if name.lstrip("_").lower() == "atom_site":
                atom_site_rows += int(category.get("rowCount") or 0)
                atom_site_columns.extend(str(c.get("name") or "") for c in category.get("columns") or [] if isinstance(c, dict))

    required = {"Cartn_x", "Cartn_y", "Cartn_z"}
    present = set(atom_site_columns)
    return {
        "binarycif_decoded": True,
        "data_block_count": len(blocks),
        "data_block_headers": block_headers,
        "category_count": len(categories_seen),
        "has_atom_site": atom_site_rows > 0,
        "atom_site_row_count": atom_site_rows,
        "atom_site_column_count": len(present),
        "coordinate_columns_present": sorted(required & present),
        "has_cartesian_xyz": required.issubset(present),
        "sample_category_names": sorted(set(categories_seen))[:25],
    }


def build_checksums(directory: pathlib.Path) -> None:
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.name not in {"SHA256SUMS.txt", "MANIFEST.json"})
    rows: list[str] = []
    manifest: list[dict[str, Any]] = []
    for path in files:
        rel = path.relative_to(directory).as_posix()
        digest = sha256_file(path)
        rows.append(f"{digest}  {rel}")
        manifest.append({"path": rel, "bytes": path.stat().st_size, "sha256": digest})
    (directory / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    write_json(directory / "MANIFEST.json", {"algorithm": "SHA-256", "files": manifest})


def write_collections_csv(path: pathlib.Path, collections: list[dict[str, Any]]) -> None:
    fields = ["collection_key", "name", "contract", "storage_generation", "total_supply", "parent_record_count", "child_chunk_count", "code_sha256"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in collections:
            writer.writerow({k: item.get(k, "") for k in fields})


def write_samples_csv(path: pathlib.Path, samples: list[dict[str, Any]]) -> None:
    fields = ["idcode", "token_id", "onchain_idcode", "compressed_bytes", "binarycif_bytes", "binarycif_sha256", "atom_site_row_count", "has_cartesian_xyz", "category_count", "sequence_length", "combined_base64_characters"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in samples:
            writer.writerow({k: item.get(k, "") for k in fields})


def write_report(path: pathlib.Path, snapshot: dict[str, Any], samples: list[dict[str, Any]]) -> None:
    meta = snapshot["metadata"]
    counts = snapshot["collection_counts"]
    lines = [
        "# MOLNFT evidence snapshot", "",
        f"**Pinned GenesisL1 block:** `{meta['block_number']}`  ",
        f"**Block hash:** `{meta['block_hash']}`  ",
        f"**Block time:** `{meta['block_time_utc']}`  ",
        f"**Captured:** `{meta['captured_at_utc']}`  ",
        f"**RPC provider:** `{meta['rpc_provider_name']}`", "",
        "## Exact collection observations", "", "| Observation | Result |", "|---|---:|",
        f"| PDB v2 parent records | **{counts['pdb_v2_parent_records']:,}** |",
        f"| PDB v2 total ERC-721 tokens, including child chunks | **{counts['pdb_v2_total_tokens']:,}** |",
        f"| PDB v2 child chunks | **{counts['pdb_v2_child_chunks']:,}** |",
        f"| Legacy PDB v1 tokens | **{counts['pdb_v1_tokens']:,}** |",
        f"| Legacy AlphaFold/Swiss-Prot v1 tokens | **{counts['af_v1_tokens']:,}** |",
        f"| Legacy v1 subtotal | **{counts['legacy_v1_subtotal']:,}** |", "",
        "The PDB v2 parent count and the legacy-v1 subtotal describe different storage generations and potentially overlapping scientific records. They are **not added together**. The legacy subtotal is the sum of two ERC-721 supplies; it is not a claim that those assets store complete coordinate payloads in contract state.", "",
        "## Direct reconstruction audit", "",
        "The following set was declared before capture and reconstructed with `getCombinedData(tokenId)` at the pinned block. The returned base64 was decoded, gunzipped when applicable, parsed as BinaryCIF MessagePack, and checked for `_atom_site.Cartn_x`, `_atom_site.Cartn_y` and `_atom_site.Cartn_z` columns.", "",
        "| PDB ID | Token | BinaryCIF bytes | Atom rows | Coordinates | SHA-256 |", "|---|---:|---:|---:|---|---|",
    ]
    for sample in samples:
        status = "yes" if sample["has_cartesian_xyz"] else "no"
        lines.append(f"| {sample['idcode']} | {sample['token_id']:,} | {sample['binarycif_bytes']:,} | {sample['atom_site_row_count']:,} | {status} | `{sample['binarycif_sha256'][:16]}…` |")
    lines += [
        "", "## Scope", "",
        f"This snapshot proves two things at block {meta['block_number']:,}: the contract counters and ERC-721 supplies shown above, and successful full-byte reconstruction for **{len(samples)} predeclared sample records**. It does not claim that all PDB v2 parent records were exhaustively downloaded and decoded in this run.", "",
        "For each sample, the repository publishes the exact JSON-RPC request and response, the reconstructed `.bcif` bytes, parsed structural checks, CSV results and SHA-256 checksums. Anyone can rerun the capture against an archive-capable GenesisL1 RPC endpoint.", "",
        "## Verify", "", "```bash", "sha256sum -c SHA256SUMS.txt", "python ../scripts/capture_molnft_snapshot.py --block 13412747 --expected-block-hash 19F42CD995E384E09D5CD4FB2751668E613D762DD1F22301D065EC84950F0F9A", "```", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def capture(args: argparse.Namespace) -> tuple[pathlib.Path, dict[str, Any]]:
    block_number = args.block
    block_hex = hex(block_number)
    expected_hash = "0x" + args.expected_block_hash.lower().removeprefix("0x")
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    root = pathlib.Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".capture-{int(time.time())}"
    if staging.exists():
        shutil.rmtree(staging)
    raw_dir = staging / "raw"
    objects_dir = staging / "objects"
    raw_dir.mkdir(parents=True)
    objects_dir.mkdir(parents=True)

    provider_name = ""
    rpc_url = ""
    chain_result: RpcResult | None = None
    block_result: RpcResult | None = None
    failures: list[str] = []
    for name, url in RPC_PROVIDERS:
        try:
            chain = rpc_post(session, url, "eth_chainId", [], 1, args.timeout, args.retries)
            chain_id = int(str(chain.payload["result"]), 16)
            if chain_id != CHAIN_ID_DECIMAL:
                raise RuntimeError(f"wrong chain id {chain_id}")
            block = rpc_post(session, url, "eth_getBlockByNumber", [block_hex, False], 2, args.timeout, args.retries)
            block_payload = block.payload.get("result")
            if not isinstance(block_payload, dict):
                raise RuntimeError("block unavailable")
            observed_hash = str(block_payload.get("hash") or "").lower()
            if observed_hash != expected_hash:
                raise RuntimeError(f"block hash mismatch: {observed_hash} != {expected_hash}")
            provider_name, rpc_url = name, url
            chain_result, block_result = chain, block
            break
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    if not rpc_url or chain_result is None or block_result is None:
        raise RuntimeError("No provider supplied the expected block: " + "; ".join(failures))

    save_rpc(raw_dir, "rpc-chain-id", chain_result)
    save_rpc(raw_dir, "rpc-block", block_result)
    block_payload = block_result.payload["result"]
    block_hash = str(block_payload["hash"])
    block_time = dt.datetime.fromtimestamp(int(block_payload["timestamp"], 16), tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")

    request_id = [10]
    collection_rows: list[dict[str, Any]] = []
    raw_counts: dict[str, int] = {}
    code_hashes: dict[str, str] = {}
    for key, spec in CONTRACTS.items():
        address = to_checksum_address(spec["address"])
        request_id[0] += 1
        code_result = rpc_post(session, rpc_url, "eth_getCode", [address, block_hex], request_id[0], args.timeout, args.retries)
        save_rpc(raw_dir, f"rpc-code-{key}", code_result)
        code_bytes = bytes.fromhex(str(code_result.payload["result"]).removeprefix("0x"))
        if not code_bytes:
            raise RuntimeError(f"No code at {address} for {key}")
        code_hashes[key] = sha256_bytes(code_bytes)

        request_id[0] += 1
        supply_result = eth_call(session, rpc_url, address, call_data("totalSupply()"), block_hex, request_id[0], args.timeout, args.retries)
        save_rpc(raw_dir, f"rpc-total-supply-{key}", supply_result)
        total_supply = decode_uint(str(supply_result.payload["result"]))
        raw_counts[f"{key}_total_supply"] = total_supply
        collection_rows.append({"collection_key": key, "name": spec["name"], "contract": address, "storage_generation": spec["storage_generation"], "total_supply": total_supply, "parent_record_count": "", "child_chunk_count": "", "code_sha256": code_hashes[key]})

    v2_address = CONTRACTS["pdb_v2"]["address"]
    parent_counter_signature, parent_counter = rpc_counter(session, rpc_url, v2_address, ["nextParentId()", "nextNFTId()"], block_hex, raw_dir, "rpc-pdb-v2", request_id, args.timeout, args.retries)
    child_counter_signature, child_counter = rpc_counter(session, rpc_url, v2_address, ["nextChildId()"], block_hex, raw_dir, "rpc-pdb-v2", request_id, args.timeout, args.retries)
    parent_records = max(parent_counter - 1, 0)
    child_chunks = max(child_counter - 100_000_000, 0)
    for row in collection_rows:
        if row["collection_key"] == "pdb_v2":
            row["parent_record_count"] = parent_records
            row["child_chunk_count"] = child_chunks

    samples: list[dict[str, Any]] = []
    for idcode in SAMPLE_IDCODES:
        token_id = resolve_token(session, idcode, raw_dir, args.timeout, args.retries)
        request_id[0] += 1
        metadata_result = eth_call(session, rpc_url, v2_address, call_data("getMetadata(uint256)", ["uint256"], [token_id]), block_hex, request_id[0], args.timeout, args.retries)
        save_rpc(raw_dir, f"rpc-metadata-{idcode}-token-{token_id}", metadata_result)
        metadata = decode_metadata(str(metadata_result.payload["result"]))
        onchain_idcode = metadata[0].strip().upper()
        if onchain_idcode != idcode.upper():
            raise RuntimeError(f"Token {token_id} metadata IDCODE {onchain_idcode!r} != expected {idcode!r}")

        request_id[0] += 1
        combined_result = eth_call(session, rpc_url, v2_address, call_data("getCombinedData(uint256)", ["uint256"], [token_id]), block_hex, request_id[0], args.timeout, args.retries)
        save_rpc(raw_dir, f"rpc-combined-{idcode}-token-{token_id}", combined_result)
        combined_b64 = decode_string(str(combined_result.payload["result"]))
        compressed = base64.b64decode(combined_b64, validate=True)
        binary_cif = gzip.decompress(compressed) if compressed[:2] == b"\x1f\x8b" else compressed
        inspection = inspect_binary_cif(binary_cif)
        if not inspection["has_cartesian_xyz"] or inspection["atom_site_row_count"] <= 0:
            raise RuntimeError(f"{idcode} did not contain verifiable Cartesian atom-site coordinates")

        object_name = f"{idcode.lower()}-token-{token_id}.bcif"
        write_bytes(objects_dir / object_name, binary_cif)
        samples.append({"idcode": idcode, "token_id": token_id, "onchain_idcode": onchain_idcode, "combined_base64_characters": len(combined_b64), "compressed_bytes": len(compressed), "compressed_sha256": sha256_bytes(compressed), "binarycif_bytes": len(binary_cif), "binarycif_sha256": sha256_bytes(binary_cif), "sequence_length": len(metadata[8]), "object_path": f"objects/{object_name}", **inspection})

    counts = {
        "pdb_v2_parent_records": parent_records,
        "pdb_v2_total_tokens": raw_counts["pdb_v2_total_supply"],
        "pdb_v2_child_chunks": child_chunks,
        "pdb_v1_tokens": raw_counts["pdb_v1_total_supply"],
        "af_v1_tokens": raw_counts["af_v1_total_supply"],
        "legacy_v1_subtotal": raw_counts["pdb_v1_total_supply"] + raw_counts["af_v1_total_supply"],
    }
    snapshot = {
        "metadata": {"schema": "org.genesisl1.molnft_evidence.v1", "chain_id": "genesis_29-2", "evm_chain_id": CHAIN_ID_DECIMAL, "block_number": block_number, "block_hash": block_hash, "block_time_utc": block_time, "captured_at_utc": utc_now(), "rpc_provider_name": provider_name, "rpc_url": rpc_url, "sample_selection": {"declared_idcodes": SAMPLE_IDCODES, "basis": "size-stratified public MOLNFT benchmark set, declared before capture", "sample_count": len(SAMPLE_IDCODES)}, "parent_counter_function": parent_counter_signature, "child_counter_function": child_counter_signature},
        "contracts": {key: {**spec, "address": to_checksum_address(spec["address"]), "runtime_code_sha256": code_hashes[key]} for key, spec in CONTRACTS.items()},
        "collection_counts": counts,
        "reconstruction_summary": {"attempted": len(SAMPLE_IDCODES), "successful": len(samples), "all_samples_binarycif_decoded": all(s["binarycif_decoded"] for s in samples), "all_samples_have_atom_site": all(s["has_atom_site"] for s in samples), "all_samples_have_cartesian_xyz": all(s["has_cartesian_xyz"] for s in samples), "total_reconstructed_binarycif_bytes": sum(s["binarycif_bytes"] for s in samples), "scope": "predeclared sample; not an exhaustive reconstruction of every parent record"},
        "samples": samples,
    }

    write_json(staging / "snapshot.json", snapshot)
    write_collections_csv(staging / "collections.csv", collection_rows)
    write_samples_csv(staging / "samples.csv", samples)
    write_report(staging / "README.md", snapshot, samples)
    build_checksums(staging)

    stamp = block_time.replace("-", "").replace(":", "").replace(".", "").replace("Z", "Z")
    final_dir = root / f"block-{block_number}-{stamp}"
    if final_dir.exists():
        shutil.rmtree(final_dir)
    staging.rename(final_dir)
    pointer = {"block_number": block_number, "block_hash": block_hash, "snapshot_directory": final_dir.name, "captured_at_utc": snapshot["metadata"]["captured_at_utc"], "snapshot_sha256": sha256_file(final_dir / "snapshot.json"), "readme_sha256": sha256_file(final_dir / "README.md")}
    write_json(root.parent / "latest.json", pointer)
    return final_dir, snapshot


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--block", type=int, default=DEFAULT_BLOCK)
    parser.add_argument("--expected-block-hash", default=DEFAULT_BLOCK_HASH)
    parser.add_argument("--output-root", default="molnft-evidence/snapshots")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--retries", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        final_dir, snapshot = capture(args)
    except Exception as exc:  # noqa: BLE001
        print(f"capture failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"\nSnapshot: {final_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
