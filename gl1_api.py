#!/usr/bin/env python3
import json
import time
import ssl
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ====== CONFIG (match your dashboard) ======
COSMOS_LCD = "https://1317.genesisl1.org"
DISPLAY_DENOM = "L1"

DEFAULT_BASE_DENOM = "ul1"
DEFAULT_DECIMALS = 18

HTTP_TIMEOUT = 12
RETRIES = 1
BACKOFF_START = 0.8

CACHE_TTL_SEC = 60
DENOM_TTL_SEC = 6 * 60 * 60  # 6h

OUT_MAX_FRAC = 18  # output precision (trimmed)

HOST = "0.0.0.0"
PORT = 8787

_ssl_ctx = ssl.create_default_context()

# ====== small utils ======
def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _is_denom_base_like(denom: str, base_denom: str) -> bool:
    dn = _norm(denom)
    bd = _norm(base_denom)
    disp = _norm(DISPLAY_DENOM)
    if not dn:
        return False
    if dn == bd:
        return True
    if dn == disp:
        return True
    if dn == ("u" + disp):
        return True
    # keep this in case your chain sometimes uses it
    if dn == "el1":
        return True
    return False

def _sleep(sec: float) -> None:
    time.sleep(sec)

def _fetch_json(url: str, timeout: int = HTTP_TIMEOUT, retries: int = RETRIES, backoff: float = BACKOFF_START):
    last_err = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GenesisL1-api/1.0"})
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            last_err = e
            if i < retries:
                _sleep(backoff)
                backoff *= 1.8
            else:
                raise last_err

def _pow10_big(n: int) -> int:
    if n <= 0:
        return 1
    return 10 ** n

def _parse_dec_to_scaled18(dec_str: str) -> int:
    """
    Parse sdk.Dec-style decimal string into integer scaled by 1e18.
    Example: "12.34" => 12340000000000000000
    """
    s0 = str(dec_str or "0").strip()
    if not s0:
        return 0
    neg = s0.startswith("-")
    if neg:
        s0 = s0[1:]
    whole, dot, frac = s0.partition(".")
    whole = "".join(ch for ch in whole if ch.isdigit()) or "0"
    frac = "".join(ch for ch in frac if ch.isdigit())
    frac18 = (frac + "0" * 18)[:18]
    val = int(whole) * (10 ** 18) + int(frac18 or "0")
    return -val if neg else val

def _format_units(amount_int: int, decimals: int, max_frac: int = OUT_MAX_FRAC) -> str:
    """
    Format integer `amount_int` with `decimals` into a decimal string.
    Trims trailing zeros. Avoids floats.
    """
    neg = amount_int < 0
    a = -amount_int if neg else amount_int
    if decimals <= 0:
        return ("-" if neg else "") + str(a)

    base = _pow10_big(decimals)
    whole = a // base
    frac = a % base

    frac_full = str(frac).rjust(decimals, "0")
    take = max(0, min(decimals, int(max_frac)))
    frac_part = frac_full[:take] if take < decimals else frac_full
    frac_part = frac_part.rstrip("0")

    s = str(whole) + (("." + frac_part) if frac_part else "")
    return ("-" + s) if neg else s

def _clamp_nonneg(x: int) -> int:
    return 0 if x < 0 else x

# ====== denom/decimals detection (cached) ======
_denom_cache = {
    "ts": 0.0,
    "base_denom": DEFAULT_BASE_DENOM,
    "decimals": DEFAULT_DECIMALS,
}

def _detect_base_denom_and_decimals():
    now = time.time()
    if now - _denom_cache["ts"] < DENOM_TTL_SEC:
        return _denom_cache["base_denom"], _denom_cache["decimals"]

    base = _denom_cache["base_denom"] or DEFAULT_BASE_DENOM
    dec = _denom_cache["decimals"] or DEFAULT_DECIMALS

    # staking params -> bond denom
    try:
        sp = _fetch_json(f"{COSMOS_LCD}/cosmos/staking/v1beta1/params")
        bd = sp.get("params", {}).get("bond_denom")
        if bd:
            base = bd
    except Exception:
        pass

    # mint params -> mint denom
    try:
        mp = _fetch_json(f"{COSMOS_LCD}/cosmos/mint/v1beta1/params")
        md = mp.get("params", {}).get("mint_denom")
        if md:
            base = md
    except Exception:
        pass

    # denom metadata -> display exponent for L1 (optional)
    try:
        next_key = ""
        found = None
        for _ in range(30):
            url = f"{COSMOS_LCD}/cosmos/bank/v1beta1/denoms_metadata?pagination.limit=200"
            if next_key:
                url += "&pagination.key=" + urllib.parse.quote(next_key, safe="")
            j = _fetch_json(url)
            metas = j.get("metadatas", []) or []
            found = next((m for m in metas if _norm(m.get("base")) == _norm(base)), None)
            if not found:
                found = next((m for m in metas if _norm(m.get("display")) == _norm(DISPLAY_DENOM)), None)
            if found:
                break
            next_key = (j.get("pagination") or {}).get("next_key") or ""
            if not next_key:
                break

        if found:
            denom_units = found.get("denom_units", []) or []
            disp = _norm(found.get("display") or DISPLAY_DENOM)
            du = next((u for u in denom_units if _norm(u.get("denom")) == disp), None)
            if du and isinstance(du.get("exponent"), int):
                dec = du["exponent"]
    except Exception:
        pass

    _denom_cache.update({"ts": now, "base_denom": base, "decimals": dec})
    return base, dec

# ====== compute API data (cached) ======
_api_cache = {"ts": 0.0, "data": None}

def _get_supply_raw(base_denom: str) -> int:
    # preferred endpoint
    try:
        sup = _fetch_json(f"{COSMOS_LCD}/cosmos/bank/v1beta1/supply/by_denom?denom={urllib.parse.quote(base_denom, safe='')}")
        amt = (sup.get("amount") or {}).get("amount") or sup.get("amount") or "0"
        return int(str(amt))
    except Exception:
        # fallback: scan full supply
        sup_all = _fetch_json(f"{COSMOS_LCD}/cosmos/bank/v1beta1/supply?pagination.limit=100000")
        for c in sup_all.get("supply", []) or []:
            if _is_denom_base_like(c.get("denom"), base_denom):
                return int(str(c.get("amount") or "0"))
        return 0

def _get_community_pool_scaled18(base_denom: str) -> int:
    j = _fetch_json(f"{COSMOS_LCD}/cosmos/distribution/v1beta1/community_pool")
    coins = j.get("community_pool") or j.get("pool") or []
    if not isinstance(coins, list):
        coins = []
    total = 0
    for c in coins:
        if _is_denom_base_like(c.get("denom"), base_denom) and c.get("amount") is not None:
            total += _parse_dec_to_scaled18(c["amount"])
    return total

def _get_total_staked_raw() -> int:
    j = _fetch_json(f"{COSMOS_LCD}/cosmos/staking/v1beta1/pool")
    pool = j.get("pool") or {}
    bonded = int(str(pool.get("bonded_tokens") or "0"))
    not_bonded = int(str(pool.get("not_bonded_tokens") or "0"))
    return bonded + not_bonded

def compute_api_payload():
    base, decimals = _detect_base_denom_and_decimals()

    supply_raw = _get_supply_raw(base)                  # base atomics
    staked_raw = _get_total_staked_raw()                # base atomics
    comm_scaled18 = _get_community_pool_scaled18(base)  # base atomics * 1e18 (sdk.Dec)

    # Do subtraction at a common scale: *1e18
    supply_scaled18 = supply_raw * (10 ** 18)
    staked_scaled18 = staked_raw * (10 ** 18)



    return {
        "circulating_supply": _format_units(supply_raw, decimals, OUT_MAX_FRAC),
        "circulating_supply_raw": str(supply_raw),
        "community_pool": _format_units(comm_scaled18, decimals + 18, OUT_MAX_FRAC),
        "total_staked": _format_units(staked_raw, decimals, OUT_MAX_FRAC),

    }

def get_cached_payload():
    now = time.time()
    if _api_cache["data"] is not None and (now - _api_cache["ts"] < CACHE_TTL_SEC):
        return _api_cache["data"]
    payload = compute_api_payload()
    _api_cache.update({"ts": now, "data": payload})
    return payload

# ====== HTTP handler ======
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] != "/api.json":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found\n")
            return

        try:
            payload = get_cached_payload()
            body = (json.dumps(payload, indent=2) + "\n").encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=30")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err = {"error": str(e)}
            body = (json.dumps(err) + "\n").encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        # quiet logs (comment out if you want access logs)
        return

def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Listening on http://{HOST}:{PORT}/api.json")
    srv.serve_forever()

if __name__ == "__main__":
    main()
