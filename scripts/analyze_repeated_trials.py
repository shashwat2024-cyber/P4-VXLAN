#!/usr/bin/env python3
"""Summarize actual per-trial CSV observations.

Example:
  python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv

No results are generated unless raw records exist. Conditions differing in
tenant, configuration, transport, MSS, payload, duration, MTU or offload are
kept in separate groups.
"""
import argparse
import csv
import math
import statistics
from pathlib import Path

T95 = {1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,8:2.306,
       9:2.262,10:2.228,11:2.201,12:2.179,13:2.160,14:2.145,15:2.131,
       16:2.120,17:2.110,18:2.101,19:2.093,20:2.086,21:2.080,22:2.074,
       23:2.069,24:2.064,25:2.060,26:2.056,27:2.052,28:2.048,29:2.045,30:2.042}

def stats(values):
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, None, None, None
    sd = statistics.stdev(values)
    critical = T95.get(len(values) - 1, 1.96)
    half = critical * sd / math.sqrt(len(values))
    return mean, sd, mean - half, mean + half

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", nargs="?", default="results/repeated_trials.csv")
    args = parser.parse_args()
    source = Path(args.csv_file)
    if not source.exists():
        parser.error(f"Input not found: {source}")
    with source.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    group_columns = ("experiment_id","configuration","tenant","transport","mss_bytes",
                     "payload_bytes","duration_seconds","mtu","offload")
    groups = {}
    invalid = 0
    for row in rows:
        if row.get("status") != "success" or not row.get("receiver_mbps"):
            continue
        try:
            value = float(row["receiver_mbps"])
            if not math.isfinite(value) or value < 0:
                raise ValueError("receiver throughput must be finite and nonnegative")
        except (ValueError, TypeError):
            invalid += 1
            continue
        key = tuple(row.get(column, "") for column in group_columns)
        groups.setdefault(key, []).append(row)

    output = source.with_name("repeated_summary.csv")
    columns = list(group_columns) + ["n","mean_receiver_mbps","sd_receiver_mbps",
        "ci95_low_mbps","ci95_high_mbps","mean_latency_ms",
        "mean_packet_loss_percent","mean_retransmissions"]
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for key, items in sorted(groups.items()):
            values = [float(row["receiver_mbps"]) for row in items]
            mean, sd, low, high = stats(values)
            latencies = [float(row["latency_ms"]) for row in items if row.get("latency_ms")]
            losses = [float(row["packet_loss_percent"]) for row in items if row.get("packet_loss_percent")]
            retransmits = [float(row["retransmissions"]) for row in items if row.get("retransmissions")]
            record = dict(zip(group_columns, key))
            record.update(
                n=len(values), mean_receiver_mbps=f"{mean:.4f}",
                sd_receiver_mbps="" if sd is None else f"{sd:.4f}",
                ci95_low_mbps="" if low is None else f"{low:.4f}",
                ci95_high_mbps="" if high is None else f"{high:.4f}",
                mean_latency_ms=f"{statistics.mean(latencies):.4f}" if latencies else "",
                mean_packet_loss_percent=f"{statistics.mean(losses):.4f}" if losses else "",
                mean_retransmissions=f"{statistics.mean(retransmits):.2f}" if retransmits else "")
            writer.writerow(record)

    successes = sum(len(values) for values in groups.values())
    print(f"Raw rows: {len(rows)}; successful throughput observations analysed: {successes}; malformed numeric rows skipped: {invalid}.")
    print(f"Summary written to {output}")
    for key, items in sorted(groups.items()):
        values = [float(row["receiver_mbps"]) for row in items]
        mean, sd, low, high = stats(values)
        label = " / ".join(value for value in key[:7] if value)
        if sd is None:
            print(f"{label}: n=1; SD and 95% CI unavailable.")
        else:
            print(f"{label}: n={len(values)}, mean={mean:.3f} Mbps, SD={sd:.3f}, "
                  f"95% CI [{low:.3f}, {high:.3f}] Mbps")

if __name__ == "__main__":
    main()
