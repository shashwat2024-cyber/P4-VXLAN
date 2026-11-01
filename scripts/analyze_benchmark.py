import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "results" / "combined_240_trials_20261027.csv"
OUT = ROOT / "results" / "analysis_20261027"

if not INPUT.exists():
    raise SystemExit(f"ERROR: Dataset not found: {INPUT}")

OUT.mkdir(parents=True, exist_ok=True)

with INPUT.open(newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

if len(rows) != 240:
    raise SystemExit(
        f"ERROR: Expected 240 data rows, found {len(rows)}. "
        "No analysis was generated."
    )

def number(row, field):
    value = row.get(field, "")
    if value is None or not value.strip():
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None

def mean(values):
    return statistics.mean(values) if values else None

def sd(values):
    return statistics.stdev(values) if len(values) > 1 else None

def fmt(value):
    return "" if value is None else f"{value:.6f}"

# Preserve all observations. Summaries exclude only missing/non-numeric
# values for the specific metric being summarized.
metrics = [
    ("sender_mbps", "Sender throughput (Mbps)", "Throughput"),
    ("receiver_mbps", "Receiver throughput (Mbps)", "Throughput"),
    ("retransmissions", "TCP retransmissions", "Retransmissions"),
    ("latency_ms", "Latency (ms)", "Latency"),
    ("packet_loss_percent", "Packet loss (%)", "Packet loss"),
]

groups = defaultdict(list)
for row in rows:
    key = (
        row.get("configuration", ""),
        row.get("tenant", ""),
        row.get("mss_bytes", ""),
    )
    groups[key].append(row)

# Save per-condition metric summaries.
summary_path = OUT / "metric_summary.csv"
with summary_path.open("w", newline="", encoding="utf-8") as f:
    fields = [
        "configuration", "tenant", "mss_bytes", "trial_rows",
        "successful_rows",
    ]
    for metric, _, _ in metrics:
        fields += [f"{metric}_n", f"{metric}_mean", f"{metric}_sd"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for key in sorted(groups, key=lambda k: (int(k[2]), k[1], k[0])):
        config, tenant, mss = key
        group = groups[key]
        result = {
            "configuration": config,
            "tenant": tenant,
            "mss_bytes": mss,
            "trial_rows": len(group),
            "successful_rows": sum(
                r.get("status", "").lower() == "success" for r in group
            ),
        }
        for metric, _, _ in metrics:
            values = [number(r, metric) for r in group]
            values = [v for v in values if v is not None]
            result[f"{metric}_n"] = len(values)
            result[f"{metric}_mean"] = fmt(mean(values))
            result[f"{metric}_sd"] = fmt(sd(values))
        writer.writerow(result)

# Compare VXLAN to baseline at each MSS and tenant.
configs = sorted({r.get("configuration", "") for r in rows})
baseline_candidates = [c for c in configs if "BASELINE" in c.upper()]
vxlan_candidates = [c for c in configs if "VXLAN" in c.upper()]

comparison_path = OUT / "baseline_vs_vxlan.csv"
with comparison_path.open("w", newline="", encoding="utf-8") as f:
    fields = [
        "tenant", "mss_bytes", "metric",
        "baseline_configuration", "baseline_n", "baseline_mean", "baseline_sd",
        "vxlan_configuration", "vxlan_n", "vxlan_mean", "vxlan_sd",
        "vxlan_change_percent",
    ]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    if len(baseline_candidates) != 1 or len(vxlan_candidates) != 1:
        print("WARNING: Could not uniquely identify baseline and VXLAN configs.")
        print("Configurations found:", configs)
    else:
        baseline, vxlan = baseline_candidates[0], vxlan_candidates[0]
        tenants = sorted({r.get("tenant", "") for r in rows})
        msses = sorted({int(r["mss_bytes"]) for r in rows if r.get("mss_bytes")})

        for tenant in tenants:
            for mss in msses:
                for metric, _, _ in metrics:
                    def collect(config):
                        values = [
                            number(r, metric)
                            for r in rows
                            if r.get("configuration") == config
                            and r.get("tenant") == tenant
                            and number(r, "mss_bytes") == mss
                        ]
                        return [v for v in values if v is not None]

                    bvals, xvals = collect(baseline), collect(vxlan)
                    bm, xm = mean(bvals), mean(xvals)
                    change = (
                        (xm - bm) / bm * 100
                        if bm not in (None, 0) and xm is not None
                        else None
                    )
                    writer.writerow({
                        "tenant": tenant,
                        "mss_bytes": mss,
                        "metric": metric,
                        "baseline_configuration": baseline,
                        "baseline_n": len(bvals),
                        "baseline_mean": fmt(bm),
                        "baseline_sd": fmt(sd(bvals)),
                        "vxlan_configuration": vxlan,
                        "vxlan_n": len(xvals),
                        "vxlan_mean": fmt(xm),
                        "vxlan_sd": fmt(sd(xvals)),
                        "vxlan_change_percent": fmt(change),
                    })

# Plot each metric separately for each tenant.
# Means and standard-deviation error bars are computed from available values.
plot_metrics = [
    ("sender_mbps", "Sender throughput (Mbps)", "throughput_sender"),
    ("receiver_mbps", "Receiver throughput (Mbps)", "throughput_receiver"),
    ("retransmissions", "TCP retransmissions", "retransmissions"),
    ("latency_ms", "Latency (ms)", "latency"),
    ("packet_loss_percent", "Packet loss (%)", "packet_loss"),
]

all_configs = sorted({r.get("configuration", "") for r in rows})
all_tenants = sorted({r.get("tenant", "") for r in rows})
all_msses = sorted({int(r["mss_bytes"]) for r in rows if r.get("mss_bytes")})

for metric, ylabel, filename in plot_metrics:
    for tenant in all_tenants:
        fig, ax = plt.subplots(figsize=(9, 5.5))
        plotted = False

        for config in all_configs:
            xs, ys, errors = [], [], []
            for mss in all_msses:
                values = [
                    number(r, metric)
                    for r in rows
                    if r.get("configuration") == config
                    and r.get("tenant") == tenant
                    and number(r, "mss_bytes") == mss
                ]
                values = [v for v in values if v is not None]
                if not values:
                    continue
                xs.append(mss)
                ys.append(mean(values))
                errors.append(sd(values) or 0)
            if ys:
                ax.errorbar(
                    xs, ys, yerr=errors, marker="o",
                    capsize=3, label=config
                )
                plotted = True

        if plotted:
            ax.set_title(f"{ylabel} vs MSS — Tenant {tenant}")
            ax.set_xlabel("MSS (bytes)")
            ax.set_ylabel(ylabel)
            ax.set_xticks(all_msses)
            ax.grid(True, alpha=0.3)
            ax.legend()
            fig.tight_layout()
            fig.savefig(OUT / f"{filename}_tenant_{tenant}.png", dpi=160)
        plt.close(fig)

# Save a transparent record of packet-loss observations.
loss_rows = [
    r for r in rows
    if number(r, "packet_loss_percent") is not None
    and number(r, "packet_loss_percent") > 0
]
loss_path = OUT / "packet_loss_observations.csv"
with loss_path.open("w", newline="", encoding="utf-8") as f:
    fields = [
        "campaign_id", "trial_number", "configuration", "tenant",
        "mss_bytes", "packet_loss_percent", "retransmissions", "status",
    ]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for r in loss_rows:
        writer.writerow({k: r.get(k, "") for k in fields})

# Dataset-level status summary.
status_counts = defaultdict(int)
for r in rows:
    status_counts[r.get("status", "") or "(blank)"] += 1

with (OUT / "dataset_validation.txt").open("w", encoding="utf-8") as f:
    f.write(f"Input: {INPUT.name}\n")
    f.write(f"Data rows: {len(rows)}\n")
    f.write(f"Configurations: {len(set(r.get('configuration','') for r in rows))}\n")
    f.write(f"Tenants: {len(set(r.get('tenant','') for r in rows))}\n")
    f.write(f"MSS values: {', '.join(map(str, all_msses))}\n")
    f.write(f"Rows with packet loss > 0%: {len(loss_rows)}\n")
    f.write("Status counts:\n")
    for status, count in sorted(status_counts.items()):
        f.write(f"  {status}: {count}\n")
    f.write("\nAll original rows are retained in the source CSV.\n")

print("Analysis complete.")
print(f"Input rows analysed: {len(rows)}")
print(f"Output directory: {OUT}")
print("Files created:")
for path in sorted(OUT.iterdir()):
    print(f"  {path.name}")
