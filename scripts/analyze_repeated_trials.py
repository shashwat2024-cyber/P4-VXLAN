#!/usr/bin/env python3
"""Analyze raw repeated benchmark CSVs without fabricating observations.

Usage:
  python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
Produces results/repeated_summary.csv and a summary text report. Rows marked
failed are retained in the raw data but excluded from throughput summaries.
"""
import argparse, csv, math, statistics
from pathlib import Path

T95 = {1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,8:2.306,
       9:2.262,10:2.228,11:2.201,12:2.179,13:2.160,14:2.145,15:2.131,
       16:2.120,17:2.110,18:2.101,19:2.093,20:2.086,21:2.080,22:2.074,
       23:2.069,24:2.064,25:2.060,26:2.056,27:2.052,28:2.048,29:2.045,30:2.042}

def stats(v):
    mean = statistics.mean(v)
    if len(v) < 2:
        return mean, None, None, None
    sd = statistics.stdev(v)
    half = T95.get(len(v)-1, 1.96) * sd / math.sqrt(len(v))
    return mean, sd, mean-half, mean+half

def main():
    p=argparse.ArgumentParser()
    p.add_argument("csv_file", nargs="?", default="results/repeated_trials.csv")
    a=p.parse_args()
    src=Path(a.csv_file)
    if not src.exists(): p.error(f"Input not found: {src}")
    with src.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
    grouped={}
    for row in rows:
        if row.get("status") != "success" or not row.get("receiver_mbps"): continue
        key=tuple(row.get(k,"") for k in ("experiment_id","configuration","tenant","transport","mss_bytes","payload_bytes","duration_seconds","mtu","offload"))
        grouped.setdefault(key,[]).append(row)
    out=src.with_name("repeated_summary.csv")
    cols=["experiment_id","configuration","tenant","transport","mss_bytes","payload_bytes","duration_seconds","mtu","offload","n","mean_receiver_mbps","sd_receiver_mbps","ci95_low_mbps","ci95_high_mbps","mean_latency_ms","mean_packet_loss_percent","mean_retransmissions"]
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for key,items in sorted(grouped.items()):
            vals=[float(r["receiver_mbps"]) for r in items]
            mean,sd,lo,hi=stats(vals)
            lats=[float(r["latency_ms"]) for r in items if r.get("latency_ms")]
            loss=[float(r["packet_loss_percent"]) for r in items if r.get("packet_loss_percent")]
            retrans=[float(r["retransmissions"]) for r in items if r.get("retransmissions")]
            d=dict(zip(cols[:9],key));d.update(n=len(vals),mean_receiver_mbps=f"{mean:.4f}",
              sd_receiver_mbps="" if sd is None else f"{sd:.4f}",
              ci95_low_mbps="" if lo is None else f"{lo:.4f}",
              ci95_high_mbps="" if hi is None else f"{hi:.4f}",
              mean_latency_ms=f"{statistics.mean(lats):.4f}" if lats else "",
              mean_packet_loss_percent=f"{statistics.mean(loss):.4f}" if loss else "",
              mean_retransmissions=f"{statistics.mean(retrans):.2f}" if retrans else "")
            w.writerow(d)
    print(f"Analysed {len(rows)} raw rows; {sum(len(v) for v in grouped.values())} successful throughput observations.")
    print(f"Wrote {out}")
    for key,items in sorted(grouped.items()):
        vals=[float(r["receiver_mbps"]) for r in items]
        mean,sd,lo,hi=stats(vals)
        name=" / ".join(x for x in key[:7] if x)
        if len(vals)<2: print(f"{name}: n=1; CI unavailable")
        else: print(f"{name}: n={len(vals)}, mean={mean:.3f} Mbps, SD={sd:.3f}, 95% CI [{lo:.3f}, {hi:.3f}] Mbps")
if __name__=="__main__": main()
