#!/usr/bin/env python3
"""Validate and summarize repeated P4 VXLAN benchmark observations.

Latency is the mean RTT from pings performed after iperf3 completes, not
latency under load. Ping packet loss is not TCP packet loss.
"""
import argparse
import csv
import math
import statistics
from pathlib import Path

T95 = {
    1:12.706, 2:4.303, 3:3.182, 4:2.776, 5:2.571, 6:2.447,
    7:2.365, 8:2.306, 9:2.262, 10:2.228, 11:2.201, 12:2.179,
    13:2.160, 14:2.145, 15:2.131, 16:2.120, 17:2.110, 18:2.101,
    19:2.093, 20:2.086, 21:2.080, 22:2.074, 23:2.069, 24:2.064,
    25:2.060, 26:2.056, 27:2.052, 28:2.048, 29:2.045, 30:2.042,
}
GROUP_COLUMNS = (
    "campaign_id", "experiment_id", "configuration", "tenant", "transport",
    "mss_bytes", "payload_bytes", "duration_seconds", "mtu", "offload",
)

def number(value, minimum=None, maximum=None):
    if value is None or str(value).strip() == "":
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value):
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value

def stats(values):
    n = len(values)
    if not n:
        return None, None, None, None
    mean = statistics.mean(values)
    if n < 2:
        return mean, None, None, None
    sd = statistics.stdev(values)
    # Student-t through 30 df; normal approximation for larger samples.
    critical = T95.get(n - 1, 1.96)
    half = critical * sd / math.sqrt(n)
    return mean, sd, mean - half, mean + half

def fmt(value, digits=4):
    return "" if value is None else f"{value:.{digits}f}"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv_file", nargs="?", default="results/repeated_trials_v2.csv")
    p.add_argument("--experiment-id", action="append",
                   help="Include only this experiment ID; repeat to include multiple IDs.")
    p.add_argument("--campaign-id", action="append",
                   help="Include only this campaign ID; repeat to include multiple IDs.")
    p.add_argument("--output",
                   help="Summary CSV destination (must not already exist).")
    args = p.parse_args()
    source = Path(args.csv_file)
    if not source.is_file():
        p.error(f"Input not found: {source}")
    with source.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            p.error("CSV has no header")
        rows = list(reader)
    fieldnames = set(reader.fieldnames or [])
    if args.campaign_id:
        if "campaign_id" not in fieldnames:
            p.error("Campaign filtering requires a CSV with a campaign_id column.")
        wanted_campaigns = set(args.campaign_id)
        rows = [r for r in rows if r.get("campaign_id", "") in wanted_campaigns]

    if args.experiment_id:
        wanted_experiments = set(args.experiment_id)
        rows = [r for r in rows
                if r.get("experiment_id", "") in wanted_experiments]

    groups = {}
    non_success = 0
    invalid_rx = 0
    for row in rows:
        if (row.get("status") or "").strip().lower() != "success":
            non_success += 1
            continue
        rx = number(row.get("receiver_mbps"), 0)
        if rx is None:
            invalid_rx += 1
            continue
        key = tuple((row.get(c) or "").strip() for c in GROUP_COLUMNS)
        groups.setdefault(key, []).append(row)

    output = Path(args.output) if args.output else source.with_name(source.stem + "_summary.csv")
    if output.exists():
        p.error(f"Refusing to overwrite existing summary: {output}")
    columns = list(GROUP_COLUMNS) + [
        "n_throughput", "mean_receiver_mbps", "sd_receiver_mbps",
        "ci95_low_mbps", "ci95_high_mbps", "n_sender", "mean_sender_mbps",
        "n_latency", "mean_latency_ms", "latency_definition", "n_ping_loss",
        "mean_ping_loss_percent", "n_retransmissions", "mean_retransmissions",
    ]
    with output.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for key, items in sorted(groups.items()):
            record = dict(zip(GROUP_COLUMNS, key))
            rx = [number(r.get("receiver_mbps"), 0) for r in items]
            rx = [v for v in rx if v is not None]
            mean, sd, low, high = stats(rx)
            record.update(n_throughput=len(rx), mean_receiver_mbps=fmt(mean),
                          sd_receiver_mbps=fmt(sd), ci95_low_mbps=fmt(low),
                          ci95_high_mbps=fmt(high))
            metrics = [
                ("sender_mbps", "n_sender", "mean_sender_mbps", 0, None, 4),
                ("latency_ms", "n_latency", "mean_latency_ms", 0, None, 4),
                ("packet_loss_percent", "n_ping_loss", "mean_ping_loss_percent", 0, 100, 4),
                ("retransmissions", "n_retransmissions", "mean_retransmissions", 0, None, 2),
            ]
            for field, nfield, meanfield, lo, hi, digits in metrics:
                vals = [number(r.get(field), lo, hi) for r in items]
                vals = [v for v in vals if v is not None]
                record[nfield] = len(vals)
                record[meanfield] = fmt(statistics.mean(vals) if vals else None, digits)
            record["latency_definition"] = "10-ping mean RTT after TCP transfer; not under-load latency"
            writer.writerow(record)

    print(f"Rows considered: {len(rows)}")
    print(f"Successful groups with valid receiver throughput: {len(groups)}")
    print(f"Non-success rows excluded: {non_success}")
    print(f"Success rows with missing/invalid receiver throughput excluded: {invalid_rx}")
    print(f"Summary written to: {output}")
    for key, items in sorted(groups.items()):
        vals = [number(r.get("receiver_mbps"), 0) for r in items]
        vals = [v for v in vals if v is not None]
        mean, sd, low, high = stats(vals)
        label = " / ".join(v for v in key[:7] if v) or "(unlabelled)"
        if sd is None:
            print(f"{label}: n={len(vals)}, mean={mean:.3f} Mbps; SD/CI unavailable")
        else:
            print(f"{label}: n={len(vals)}, mean={mean:.3f} Mbps, SD={sd:.3f}, "
                  f"95% t/approx CI [{low:.3f}, {high:.3f}] Mbps")
        for field, label2, lo, hi in (
            ("latency_ms", "post-transfer RTT", 0, None),
            ("packet_loss_percent", "ping loss", 0, 100),
            ("retransmissions", "TCP retransmissions", 0, None),
        ):
            vals2 = [number(r.get(field), lo, hi) for r in items]
            vals2 = [v for v in vals2 if v is not None]
            extra = f", mean={statistics.mean(vals2):.3f}" if vals2 else ", unavailable"
            print(f"  {label2}: valid n={len(vals2)}/{len(items)}{extra}")

if __name__ == "__main__":
    main()
