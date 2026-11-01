from pathlib import Path
import shutil
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(".")
TCP = ROOT / "results/final_evaluation_20261031"
CPU = ROOT / "results/cpu_utilisation_20261101"
UDP = ROOT / "results/udp_rss_analysis"
OUT = ROOT / "results/final_analysis_20261101"
OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# 1. Load primary TCP datasets.
# ------------------------------------------------------------
tcp_files = {
    ("P4_L2_BASELINE", 500): TCP / "tcp_rss_final_l2_mss500.csv",
    ("P4_L2_BASELINE", 1400): TCP / "tcp_rss_final_l2_mss1400.csv",
    ("P4_VXLAN", 500): TCP / "tcp_rss_final_vxlan_mss500.csv",
    ("P4_VXLAN", 1400): TCP / "tcp_rss_final_vxlan_mss1400_corrected.csv",
}

tcp_frames = []
for (config, mss), path in tcp_files.items():
    if not path.exists():
        raise FileNotFoundError(f"Missing TCP input: {path}")
    df = pd.read_csv(path)
    df = df[df["status"].eq("success")].copy()
    df["configuration"] = config
    df["mss_bytes"] = mss
    tcp_frames.append(df)

tcp = pd.concat(tcp_frames, ignore_index=True)

# Validate sample counts.
counts = tcp.groupby(["configuration", "tenant", "mss_bytes"]).size()
print("\nTCP sample counts:")
print(counts.to_string())

expected = {
    ("P4_L2_BASELINE", "A", 500): 20,
    ("P4_L2_BASELINE", "B", 500): 20,
    ("P4_VXLAN", "A", 500): 20,
    ("P4_VXLAN", "B", 500): 20,
    ("P4_L2_BASELINE", "A", 1400): 20,
    ("P4_L2_BASELINE", "B", 1400): 20,
    ("P4_VXLAN", "A", 1400): 20,
    ("P4_VXLAN", "B", 1400): 20,
}
for key, n in expected.items():
    if counts.get(key, 0) != n:
        raise ValueError(f"Unexpected TCP sample count for {key}: {counts.get(key, 0)}")

metrics = [
    "receiver_mbps",
    "latency_ms",
    "retransmissions",
    "rss_mean_total_mib",
    "rss_peak_total_mib",
]

summary = (
    tcp.groupby(["configuration", "tenant", "mss_bytes"])[metrics]
    .agg(["count", "mean", "std"])
)
summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
summary = summary.reset_index()
summary.to_csv(OUT / "tcp_trial_summary.csv", index=False)

# Matched configuration comparisons.
comparison_rows = []
for tenant in ["A", "B"]:
    for mss in [500, 1400]:
        base = tcp[
            (tcp.configuration == "P4_L2_BASELINE")
            & (tcp.tenant == tenant)
            & (tcp.mss_bytes == mss)
        ]
        vx = tcp[
            (tcp.configuration == "P4_VXLAN")
            & (tcp.tenant == tenant)
            & (tcp.mss_bytes == mss)
        ]

        row = {"tenant": tenant, "mss_bytes": mss}
        for metric in metrics:
            bmean = base[metric].mean()
            vmean = vx[metric].mean()
            row[f"l2_{metric}_mean"] = bmean
            row[f"vxlan_{metric}_mean"] = vmean
            row[f"{metric}_difference"] = vmean - bmean
            if bmean != 0:
                row[f"{metric}_change_percent"] = (vmean - bmean) / bmean * 100
        comparison_rows.append(row)

comparison = pd.DataFrame(comparison_rows)
comparison.to_csv(OUT / "tcp_comparison.csv", index=False)

# ------------------------------------------------------------
# 2. Load and combine CPU trials with throughput trials.
# ------------------------------------------------------------
cpu_frames = []
for label, cpu_file, throughput_file in [
    ("P4_L2_BASELINE", CPU / "baseline_cpu_trials.csv",
     CPU / "baseline_final_throughput.csv"),
    ("P4_VXLAN", CPU / "vxlan_cpu_trials.csv",
     CPU / "vxlan_final_throughput.csv"),
]:
    c = pd.read_csv(cpu_file)
    t = pd.read_csv(throughput_file)

    c = c.merge(
        t[["trial_number", "experiment_id", "receiver_mbps",
           "rss_mean_total_mib", "rss_peak_total_mib", "status"]],
        on=["trial_number", "experiment_id"],
        how="inner",
        suffixes=("_cpu", "_throughput"),
        validate="one_to_one",
    )
    c = c[c["status"].eq("success")].copy()
    c["configuration"] = label
    cpu_frames.append(c)

cpu = pd.concat(cpu_frames, ignore_index=True)

cpu_metrics = [
    "cpu_mean_aggregate_percent_one_core",
    "cpu_peak_aggregate_percent_one_core",
    "receiver_mbps",
    "rss_mean_total_mib",
    "rss_peak_total_mib",
]
cpu_summary = (
    cpu.groupby("configuration")[cpu_metrics]
    .agg(["count", "mean", "std"])
)
cpu_summary.columns = [f"{metric}_{stat}" for metric, stat in cpu_summary.columns]
cpu_summary = cpu_summary.reset_index()

cpu_summary["mean_cpu_percent_per_mbps"] = (
    cpu_summary["cpu_mean_aggregate_percent_one_core_mean"]
    / cpu_summary["receiver_mbps_mean"]
)
cpu_summary.to_csv(OUT / "cpu_comparison.csv", index=False)

if not (cpu.groupby("configuration").size() == 10).all():
    raise ValueError("Expected 10 successful CPU trials per configuration.")

# ------------------------------------------------------------
# 3. Preserve copies of the existing UDP analysis tables.
# ------------------------------------------------------------
udp_files = [
    "payload_summary.csv",
    "payload_welch_tests.csv",
    "scalability_summary.csv",
    "scalability_welch_tests.csv",
]
for filename in udp_files:
    source = UDP / filename
    if source.exists():
        shutil.copy2(source, OUT / filename)

# ------------------------------------------------------------
# 4. Graphs: TCP throughput, RSS, post-transfer RTT, CPU.
# ------------------------------------------------------------
def grouped_plot(data, metric, ylabel, filename):
    labels = []
    means = []
    errors = []

    for config in ["P4_L2_BASELINE", "P4_VXLAN"]:
        for tenant in ["A", "B"]:
            for mss in [500, 1400]:
                subset = data[
                    (data.configuration == config)
                    & (data.tenant == tenant)
                    & (data.mss_bytes == mss)
                ]
                labels.append(f"{config.replace('P4_', '')}\n{tenant}, MSS {mss}")
                means.append(subset[metric].mean())
                errors.append(subset[metric].std())

    plt.figure(figsize=(12, 6))
    plt.bar(range(len(means)), means, yerr=errors, capsize=4)
    plt.xticks(range(len(labels)), labels, rotation=25, ha="right")
    plt.ylabel(ylabel)
    plt.title(ylabel + " — mean and standard deviation")
    plt.tight_layout()
    plt.savefig(OUT / filename, dpi=180)
    plt.close()

grouped_plot(tcp, "receiver_mbps", "TCP receiver throughput (Mbps)",
             "tcp_throughput.png")
grouped_plot(tcp, "rss_mean_total_mib", "Mean simple_switch RSS (MiB)",
             "tcp_rss.png")
grouped_plot(tcp, "latency_ms", "Post-transfer ping RTT (ms)",
             "tcp_post_transfer_rtt.png")

def cpu_plot(metric, ylabel, filename):
    labels = ["P4 L2 baseline", "P4 VXLAN"]
    configs = ["P4_L2_BASELINE", "P4_VXLAN"]
    means, errors = [], []
    for config in configs:
        values = cpu[cpu.configuration.eq(config)][metric]
        means.append(values.mean())
        errors.append(values.std())

    plt.figure(figsize=(7, 5))
    plt.bar(labels, means, yerr=errors, capsize=5)
    plt.ylabel(ylabel)
    plt.title(ylabel + " — mean and standard deviation")
    plt.tight_layout()
    plt.savefig(OUT / filename, dpi=180)
    plt.close()

cpu_plot("cpu_mean_aggregate_percent_one_core",
         "Mean aggregate CPU utilisation (% of one core)", "cpu_mean.png")
cpu_plot("receiver_mbps", "TCP receiver throughput (Mbps)", "cpu_throughput.png")

# ------------------------------------------------------------
# 5. Markdown report.
# ------------------------------------------------------------
def fmt(value, digits=3):
    return f"{value:.{digits}f}"

lines = [
    "# Consolidated Final Experimental Analysis",
    "",
    "Generated from the recorded experiment CSV files. Raw experiment files were not modified.",
    "",
    "## 1. TCP methodology",
    "",
    "TCP results are grouped by configuration, tenant and MSS. Each group contains 20 successful trials.",
    "The corrected VXLAN MSS-1400 dataset uses the successful recovery records for Tenant B trials 17 and 19.",
    "The additional recovery run and diagnostic runs are excluded from the primary sample.",
    "",
    "`latency_ms` is the mean RTT from the 10-ping measurement after the TCP transfer; it is not RTT measured under TCP load.",
    "",
    "## 2. TCP throughput comparison",
    "",
    "| Tenant | MSS | L2 mean Mbps | VXLAN mean Mbps | VXLAN change |",
    "|---|---:|---:|---:|---:|",
]

for _, r in comparison.iterrows():
    lines.append(
        f"| {r.tenant} | {int(r.mss_bytes)} | "
        f"{fmt(r['l2_receiver_mbps_mean'])} | "
        f"{fmt(r['vxlan_receiver_mbps_mean'])} | "
        f"{fmt(r['receiver_mbps_change_percent'], 2)}% |"
    )

lines += [
    "",
    "## 3. TCP memory and latency",
    "",
    "The detailed group means, standard deviations and sample counts are in `tcp_trial_summary.csv`.",
    "The matched configuration differences are in `tcp_comparison.csv`.",
    "",
    "RSS is the recorded resident memory of the simple_switch process set. Interpret small differences in light of the sampling interval and process-level measurement scope.",
    "",
    "## 4. CPU comparison",
    "",
    "| Configuration | Mean CPU (% one core) | Peak CPU (% one core) | Throughput (Mbps) | Mean RSS (MiB) | CPU percentage points per Mbps |",
    "|---|---:|---:|---:|---:|---:|",
]

for _, r in cpu_summary.iterrows():
    lines.append(
        f"| {r.configuration} | "
        f"{fmt(r['cpu_mean_aggregate_percent_one_core_mean'], 2)} | "
        f"{fmt(r['cpu_peak_aggregate_percent_one_core_mean'], 2)} | "
        f"{fmt(r['receiver_mbps_mean'], 2)} | "
        f"{fmt(r['rss_mean_total_mib_mean'], 2)} | "
        f"{fmt(r['mean_cpu_percent_per_mbps'], 3)} |"
    )

lines += [
    "",
    "CPU utilisation is expressed as a percentage of one CPU core. Values above 100% are valid when multiple cores are used.",
    "The CPU campaign compares Tenant A only, with 10 trials per configuration. CPU-per-throughput is a descriptive ratio, not a causal efficiency measurement.",
    "",
    "## 5. UDP analysis",
    "",
    "The existing UDP payload and offered-load/scalability analyses were reused. Their summary and Welch/Holm test CSVs are included alongside this report.",
    "The payload and scalability campaigns used concurrent ping measurements to capture under-load RTT.",
    "Consult the included CSVs for per-metric sample sizes, confidence intervals and adjusted p-values.",
    "",
    "## 6. Interpretation and limitations",
    "",
    "- TCP post-transfer RTT must not be described as under-load latency.",
    "- TCP comparisons are descriptive; this report does not claim statistical significance for TCP differences.",
    "- UDP inferential results should be interpreted using the Holm-adjusted p-values in the existing test tables.",
    "- CPU measurements cover the single-tenant CPU campaign and should not be generalised to Tenant B.",
    "- The plain L2 baseline is a forwarding baseline, not a tenant-isolation baseline.",
    "- BMv2 measurements characterise the tested software environment and should not be treated as hardware-switch performance.",
    "- Failed original trial records remain in the raw evidence. The corrected primary dataset replaces the two failed Tenant B MSS-1400 records with successful recoveries.",
    "",
    "## 7. Generated figures",
    "",
    "- `tcp_throughput.png`",
    "- `tcp_rss.png`",
    "- `tcp_post_transfer_rtt.png`",
    "- `cpu_mean.png`",
    "- `cpu_throughput.png`",
    "",
    "## 8. Source data",
    "",
    "- `results/final_evaluation_20261031/`",
    "- `results/cpu_utilisation_20261101/`",
    "- `results/udp_rss_analysis/`",
    "",
]

(OUT / "FINAL_ANALYSIS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

print("\nGenerated analysis files in:", OUT)
for path in sorted(OUT.iterdir()):
    print(f"  {path.name} ({path.stat().st_size:,} bytes)")

print("\nCPU summary:")
print(cpu_summary.to_string(index=False))
print("\nTCP comparison:")
print(comparison[[
    "tenant", "mss_bytes",
    "l2_receiver_mbps_mean", "vxlan_receiver_mbps_mean",
    "receiver_mbps_change_percent"
]].to_string(index=False))

print("\nAnalysis generation and validations completed.")
