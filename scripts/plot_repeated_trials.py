#!/usr/bin/env python3
"""Generate a transparent summary and plot from repeated_vxlan_trials.csv.

Only successful raw trial rows are used for numeric summaries. No synthetic data are
added. Use the output in a report only after the raw trials have been collected.
"""
import argparse
import csv
import os
import statistics

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv")
    ap.add_argument("--out-dir", default="results/analysis")
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(args.out_dir, exist_ok=True)
    values = {}
    failures = {}
    with open(args.input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"configuration", "tenant", "mss_bytes", "receiver_mbps", "status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            ap.error("Missing columns: " + ", ".join(sorted(missing)))
        for row in reader:
            key = (row["configuration"], row["tenant"], row["mss_bytes"])
            if row["status"] == "ok":
                try:
                    values.setdefault(key, []).append(float(row["receiver_mbps"]))
                except (ValueError, TypeError):
                    failures[key] = failures.get(key, 0) + 1
            else:
                failures[key] = failures.get(key, 0) + 1

    summary_path = os.path.join(args.out_dir, "summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "configuration", "tenant", "mss_bytes", "valid_runs", "failed_runs",
            "mean_receiver_mbps", "sample_sd_mbps", "median_receiver_mbps"
        ])
        for key in sorted(set(values) | set(failures)):
            rows = values.get(key, [])
            writer.writerow([
                *key, len(rows), failures.get(key, 0),
                "" if not rows else round(statistics.mean(rows), 6),
                "" if len(rows) < 2 else round(statistics.stdev(rows), 6),
                "" if not rows else round(statistics.median(rows), 6)
            ])

    groups = sorted(values.items())
    if not groups:
        print("No successful receiver throughput rows; summary contains failure counts only.")
        print(summary_path)
        return
    labels, means, errors = [], [], []
    for (config, tenant, mss), rows in groups:
        labels.append("%s/%s\nMSS %s\nn=%d" % (config, tenant, mss, len(rows)))
        means.append(statistics.mean(rows))
        errors.append(statistics.stdev(rows) if len(rows) > 1 else 0)
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.35), 5))
    ax.bar(range(len(labels)), means, yerr=errors, capsize=4)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=0, fontsize=8)
    ax.set_ylabel("Receiver throughput (Mbit/s)")
    ax.set_title("Repeated VXLAN trial throughput (mean ± sample SD)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    plot_path = os.path.join(args.out_dir, "receiver-throughput.png")
    fig.savefig(plot_path, dpi=160)
    print("Wrote %s" % summary_path)
    print("Wrote %s" % plot_path)
    print("Error bars show sample SD, not confidence intervals; use summarise_trials.py for run-level 95% CI.")

if __name__ == "__main__":
    main()
