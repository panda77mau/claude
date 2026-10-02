#!/usr/bin/env python3
"""Tim vi tung giu mot so du RACA (BEP20) cu the trong mot khoang thoi gian.

Cach chay (can RPC archive BSC, vi du Ankr/QuickNode/NodeReal, hoac RPC cong khai
neu khoang block ngan):

    python3 tools/find_raca_wallet.py \
        --rpc https://rpc.ankr.com/bsc \
        --from-date 2021-09-20 --to-date 2021-09-25 \
        --target 506325307.46

Script quet toan bo su kien Transfer cua hop dong RACA V2 trong khoang block,
cong don so du tung dia chi, va in ra:
  * cac giao dich don le co gia tri xap xi target
  * cac dia chi ma so du cong don cham target tai bat ky thoi diem nao
"""
import argparse
import datetime as dt
import json
import sys
import urllib.request

RACA_V2 = "0x12BB890508c125661E03b09EC06E404bc9289040"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
DECIMALS = 18


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["result"]


def block_ts(url, n):
    return int(rpc(url, "eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def block_at(url, ts, lo, hi):
    """Binary search: first block with timestamp >= ts."""
    while lo < hi:
        mid = (lo + hi) // 2
        if block_ts(url, mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def scan(url, start, end, step, target, tol):
    balances = {}
    hits_tx, hits_bal = [], set()
    tgt = int(target * 10**DECIMALS)
    tol_wei = int(tol * 10**DECIMALS)
    for b in range(start, end + 1, step):
        e = min(b + step - 1, end)
        logs = rpc(url, "eth_getLogs", [{
            "fromBlock": hex(b), "toBlock": hex(e),
            "address": RACA_V2, "topics": [TRANSFER_TOPIC],
        }])
        for lg in logs:
            frm = "0x" + lg["topics"][1][-40:]
            to = "0x" + lg["topics"][2][-40:]
            val = int(lg["data"], 16)
            if abs(val - tgt) <= tol_wei:
                hits_tx.append((lg["transactionHash"], frm, to, val / 10**DECIMALS))
            balances[frm] = balances.get(frm, 0) - val
            balances[to] = balances.get(to, 0) + val
            if abs(balances[to] - tgt) <= tol_wei:
                hits_bal.add((to, int(lg["blockNumber"], 16)))
        print(f"blocks {b}-{e}: {len(logs)} transfers, {len(hits_tx)} tx hits, {len(hits_bal)} balance hits", file=sys.stderr)
    return hits_tx, sorted(hits_bal, key=lambda x: x[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", required=True)
    ap.add_argument("--from-date", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--to-date", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--target", type=float, default=506325307.46)
    ap.add_argument("--tol", type=float, default=0.01, help="sai so cho phep (RACA)")
    ap.add_argument("--step", type=int, default=2000, help="so block moi lan goi eth_getLogs")
    a = ap.parse_args()

    latest = int(rpc(a.rpc, "eth_blockNumber", []), 16)
    t0 = int(dt.datetime.fromisoformat(a.from_date).replace(tzinfo=dt.timezone.utc).timestamp())
    t1 = int(dt.datetime.fromisoformat(a.to_date).replace(tzinfo=dt.timezone.utc).timestamp()) + 86400
    start = block_at(a.rpc, t0, 1, latest)
    end = block_at(a.rpc, t1, start, latest)
    print(f"quet block {start} -> {end}", file=sys.stderr)

    hits_tx, hits_bal = scan(a.rpc, start, end, a.step, a.target, a.tol)
    print("\n== Giao dich don le ~ target ==")
    for h in hits_tx:
        print(f"tx {h[0]}  {h[1]} -> {h[2]}  {h[3]:,.2f} RACA")
    print("\n== Dia chi co so du cong don ~ target (chi tinh tu dau khoang quet) ==")
    for addr, blk in hits_bal:
        print(f"{addr}  tai block {blk}  https://bscscan.com/token/{RACA_V2}?a={addr}")


if __name__ == "__main__":
    main()
