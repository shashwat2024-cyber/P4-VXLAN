#!/usr/bin/env python3

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/udp_rss_analysis"
OUT.mkdir(parents=True, exist_ok=True)

COMPARISONS = [
    {
        "name": "payload",
        "old": ROOT / "results/scalability/udp_payload_sweep/udp_payload_trials.csv",
        "new": ROOT / "results/scalability/udp_payload_sweep/udp_payload_rss_full_20261101.csv",
        "keys": ["tenant", "datagram_bytes"],
    },
    {
        "name": "scalability",
        "old": ROOT / "results/final_evaluation_20261027/scalability/udp_scalability_30_20261027.csv",
        "new": ROOT / "results/scalability/udp_scalability_rss_full_20261101.csv",
        "keys": ["tenant", "target_mbps"],
    },
]

METRICS = [
    "receiver_mbps",
    "udp_loss_percent",
    "latency_ms",
    "jitter_ms",
    "under_load_rtt_mean_ms",
    "under_load_rtt_max_ms",
    "rss_mean_total_mib",
    "rss_peak_total_mib",
]

def summarize(df, metric):
    if metric not in df.columns:
        return None

    values = pd.to_numeric(df[metric], errors="coerce").dropna()

    if values.empty:
        return None

    return {
        "n": len(values),
        "mean": values.mean(),
        "std": values.std(ddof=1) if len(values) > 1 else np.nan,
    }

all_rows = []

for comparison in COMPARISONS:
    old = pd.read_csv(comparison["old"])
    new = pd.read_csv(comparison["new"])

    old = old[old["status"] == "success"].copy()
    new = new[new["status"] == "success"].copy()

    keys = comparison["keys"]

    for group_key, old_group in old.groupby(keys):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        mask = pd.Series(True, index=new.index)

        for key, value in zip(keys, group_key):
            mask &= new[key] == value

        new_group = new[mask]

        if new_group.empty:
            continue

        for metric in METRICS:
            old_stats = summarize(old_group, metric)
            new_stats = summarize(new_group, metric)

            if old_stats is None or new_stats is None:
                continue

            row = {
                "comparison": comparison["name"],
                **dict(zip(keys, group_key)),
                "metric": metric,
                "old_n": old_stats["n"],
                "new_n": new_stats["n"],
                "old_mean": old_stats["mean"],
                "new_mean": new_stats["mean"],
                "old_std": old_stats["std"],
                "new_std": new_stats["std"],
                "new_minus_old": new_stats["mean"] - old_stats["mean"],
            }

            all_rows.append(row)

result = pd.DataFrame(all_rows)
output = OUT / "original_vs_new_udp_comparison.csv"
result.to_csv(output, index=False)

print("Original versus new UDP comparison")
print("=" * 75)
print("Comparison rows:", len(result))
print("\n")
print(result.to_string(index=False))
print("\nSaved:", output)
