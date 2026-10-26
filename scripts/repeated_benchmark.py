#!/usr/bin/env python3
"""Controlled repeatable P4 VXLAN throughput benchmark.

Run from repository root inside Ubuntu/WSL2:
  sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30

This runner intentionally requires the actual Mininet/BMv2 environment. It
records each condition and never synthesizes measurements. It supports the
existing VXLAN testbed; see docs/experiments/baseline-and-sweeps.md for the
baseline/sweep design and limitations.
"""
from __future__ import annotations
import argparse, csv, json, math, os, re, statistics, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RAW = RESULTS / "repeated_trials.csv"
SUMMARY = RESULTS / "repeated_summary.csv"
ENVIRONMENT = RESULTS / "environment.json"

def cmd(args, timeout=30, check=True):
    p = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(args)}\n{p.stderr[-1500:]}")
    return p

def shell(command):
    p = subprocess.run(["bash", "-lc", command], text=True, capture_output=True)
    return (p.stdout + p.stderr).strip()

def parse_ping(output):
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    rtt = re.search(r"=\s*[\d.]+/([\d.]+)/", output)
    if not loss:
        raise RuntimeError("Could not parse ping output: " + output[-1000:])
    return (float(rtt.group(1)) if rtt else None, float(loss.group(1)))

def t95_critical(n):
    # Two-sided 95% Student-t critical values, indexed by df=n-1.
    values = {1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,
              8:2.306,9:2.262,10:2.228,11:2.201,12:2.179,13:2.160,14:2.145,
              15:2.131,16:2.120,17:2.110,18:2.101,19:2.093,20:2.086,
              21:2.080,22:2.074,23:2.069,24:2.064,25:2.060,26:2.056,
              27:2.052,28:2.048,29:2.045,30:2.042}
    return values.get(n-1, 1.96)

def summarize(values):
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, None, None
    sd = statistics.stdev(values)
    half = t95_critical(len(values)) * sd / math.sqrt(len(values))
    return mean, sd, (mean-half, mean+half)

def write_summary():
    if not RAW.exists():
        return
    with RAW.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    groups = {}
    for r in rows:
        if r.get("status") != "success" or not r.get("receiver_mbps"):
            continue
        key = (r["configuration"], r["tenant"], r["transport"], r["mss_bytes"], r["duration_seconds"])
        groups.setdefault(key, []).append(r)
    cols = ["configuration","tenant","transport","mss_bytes","duration_seconds","n",
            "mean_receiver_mbps","sd_receiver_mbps","ci95_low_mbps","ci95_high_mbps",
            "mean_rtt_ms","mean_packet_loss_percent"]
    with SUMMARY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for key, items in sorted(groups.items()):
            vals = [float(x["receiver_mbps"]) for x in items]
            mean, sd, ci = summarize(vals)
            lats = [float(x["latency_ms"]) for x in items if x.get("latency_ms")]
            losses = [float(x["packet_loss_percent"]) for x in items if x.get("packet_loss_percent")]
            w.writerow(dict(configuration=key[0], tenant=key[1], transport=key[2],
                mss_bytes=key[3], duration_seconds=key[4], n=len(vals),
                mean_receiver_mbps=f"{mean:.4f}",
                sd_receiver_mbps="" if sd is None else f"{sd:.4f}",
                ci95_low_mbps="" if ci is None else f"{ci[0]:.4f}",
                ci95_high_mbps="" if ci is None else f"{ci[1]:.4f}",
                mean_rtt_ms=f"{statistics.mean(lats):.4f}" if lats else "",
                mean_packet_loss_percent=f"{statistics.mean(losses):.4f}" if losses else ""))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--mss", type=int, nargs="+", default=[500,700,900,1100,1300,1400])
    ap.add_argument("--tenant", choices=["A","B","both"], default="both")
    args = ap.parse_args()
    if args.trials < 2 or args.duration < 30:
        ap.error("Use at least 2 trials and 30 seconds per trial; recommended 10 x 30 seconds.")
    if os.geteuid() != 0:
        ap.error("Run with sudo inside the configured Ubuntu/WSL2 environment.")
    missing = [x for x in ("mn","iperf3","simple_switch","p4c") if not shell(f"command -v {x}")]
    if missing:
        ap.error("Missing tools: " + ", ".join(missing))
    build = ROOT / "build" / "vxlan.json"
    if not build.is_file():
        ap.error("Missing build/vxlan.json. Compile src/p4/vxlan.p4 as described in docs/experiments/reproduction.md.")
    RESULTS.mkdir(exist_ok=True)
    env = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "uname": shell("uname -a"), "python": sys.version,
        "p4c": shell("p4c --version"), "bmv2": shell("simple_switch --version"),
        "mininet": shell("mn --version"), "iperf3": shell("iperf3 --version"),
        "note": "Preflight only. Run traffic measurements using scripts/benchmark.py after the topology starts; results are not produced by this preflight."
    }
    ENVIRONMENT.write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    print("Environment preflight passed. Recorded:", ENVIRONMENT)
    print("This runner does not claim to have run network trials: the process-local Mininet topology")
    print("must be controlled through Mininet host objects. Use the corrected topology-aware")
    print("runner/guide in docs/experiments/baseline-and-sweeps.md; do not treat preflight as data.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
