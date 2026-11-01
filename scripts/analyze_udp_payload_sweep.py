#!/usr/bin/env python3
"""Summarize UDP payload-size trials and generate CSV, graphs, and a report."""
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/scalability/udp_payload_sweep"
RAW = OUT / "udp_payload_trials.csv"
SUMMARY = OUT / "udp_payload_summary.csv"
REPORT = OUT / "udp_payload_report.md"
GRAPHS = {
    "throughput": OUT / "udp_payload_throughput.png",
    "loss": OUT / "udp_payload_loss.png",
    "jitter": OUT / "udp_payload_jitter.png",
}
SIZES = [256, 512, 768, 1024, 1200]
TENANTS = ["A", "B"]
METRICS = {
    "receiver_mbps": ("Receiver throughput (Mbps)", "UDP receiver throughput"),
    "udp_loss_percent": ("Packet loss (%)", "UDP packet loss"),
    "jitter_ms": ("Jitter (ms)", "UDP receiver-reported jitter"),
}


def numeric(row, field):
    value = row.get(field, "")
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def mean_sd(values):
    if not values:
        return None, None
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def fmt(value, digits=4):
    return "NA" if value is None else f"{value:.{digits}f}"


def main():
    if not RAW.is_file():
        raise SystemExit(f"ERROR: raw dataset not found: {RAW}")

    output_paths = [SUMMARY, REPORT, *GRAPHS.values()]
    existing = [str(p) for p in output_paths if p.exists()]
    if existing:
        raise SystemExit(
            "Refusing to overwrite existing analysis outputs:\n  "
            + "\n  ".join(existing)
            + "\nMove or rename those files before rerunning."
        )

    with RAW.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("ERROR: raw CSV contains no data rows.")

    required = {
        "tenant", "datagram_bytes", "status", "receiver_mbps",
        "udp_loss_percent", "jitter_ms", "duration_seconds",
        "target_mbps", "experiment_id", "campaign_id", "notes",
    }
    missing = required - set(rows[0])
    if missing:
        raise SystemExit(f"ERROR: required CSV columns missing: {sorted(missing)}")

    successful = [r for r in rows if r["status"].strip().lower() == "success"]
    failed = [r for r in rows if r["status"].strip().lower() != "success"]
    if not successful:
        raise SystemExit("ERROR: no successful trials to analyze.")

    groups = defaultdict(list)
    for row in successful:
        try:
            key = (row["tenant"], int(row["datagram_bytes"]))
        except (ValueError, TypeError):
            continue
        groups[key].append(row)

    summary_rows = []
    for tenant in TENANTS:
        for size in SIZES:
            group = groups.get((tenant, size), [])
            out = {
                "tenant": tenant,
                "datagram_bytes": size,
                "trials_recorded": sum(
                    r.get("tenant") == tenant
                    and r.get("datagram_bytes", "") == str(size)
                    for r in rows
                ),
                "successful_trials": len(group),
            }
            for field in METRICS:
                vals = [v for r in group if (v := numeric(r, field)) is not None]
                avg, sd = mean_sd(vals)
                out[field + "_mean"] = avg
                out[field + "_sd"] = sd
                out[field + "_n"] = len(vals)
            summary_rows.append(out)

    fields = list(summary_rows[0].keys())
    with SUMMARY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    # Plot separate tenant series; error bars are sample standard deviations.
    for metric, (ylabel, title) in METRICS.items():
        fig, ax = plt.subplots(figsize=(8, 5))
        for tenant in TENANTS:
            subset = [r for r in summary_rows if r["tenant"] == tenant]
            xs, ys, errs = [], [], []
            for r in subset:
                avg = r[metric + "_mean"]
                if avg is not None:
                    xs.append(r["datagram_bytes"])
                    ys.append(avg)
                    errs.append(r[metric + "_sd"] or 0.0)
            if xs:
                ax.errorbar(xs, ys, yerr=errs, marker="o", capsize=4, label=f"Tenant {tenant}")
        ax.set_xlabel("UDP application datagram size (bytes)")
        ax.set_ylabel(ylabel)
        ax.set_title(title + " vs datagram size")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        graph_key = {
            "receiver_mbps": "throughput",
            "udp_loss_percent": "loss",
            "jitter_ms": "jitter",
        }[metric]
        fig.savefig(GRAPHS[graph_key], dpi=160)
        plt.close(fig)

    campaigns = sorted({r.get("campaign_id", "") for r in rows})
    experiment_ids = sorted({r.get("experiment_id", "") for r in rows})
    commits = sorted({
        r.get("notes", "").split("git_commit=", 1)[1].split(";", 1)[0]
        for r in rows if "git_commit=" in r.get("notes", "")
    })
    sizes_present = sorted({
        int(r["datagram_bytes"]) for r in rows
        if r.get("datagram_bytes", "").isdigit()
    })
    tenants_present = sorted({r.get("tenant", "") for r in rows})
    rates = sorted({r.get("target_mbps", "") for r in rows})
    durations = sorted({r.get("duration_seconds", "") for r in rows})

    report = [
        "# UDP Payload-Size Sweep Report",
        "",
        "## Experiment design",
        "",
        f"- Raw dataset: `{RAW.relative_to(ROOT)}`",
        f"- Total recorded trials: {len(rows)}",
        f"- Successful trials: {len(successful)}",
        f"- Failed/non-success trials: {len(failed)}",
        f"- Tenants recorded: {', '.join(tenants_present)}",
        f"- Datagram sizes recorded (bytes): {', '.join(map(str, sizes_present))}",
        f"- Target rate(s) recorded (Mbps): {', '.join(rates)}",
        f"- Trial duration(s) recorded: {', '.join(durations)}",
        f"- Campaign ID(s): {', '.join(campaigns)}",
        f"- Experiment ID(s): {', '.join(experiment_ids)}",
        f"- Git commit(s) recorded: {', '.join(commits) if commits else 'Not recorded'}",
        "- Transport: UDP using iperf3.",
        "- Summary statistics use successful trials with valid numeric values.",
        "- Error bars in the graphs represent sample standard deviation, not confidence intervals.",
        "",
        "## Results by tenant and datagram size",
        "",
        "| Tenant | Datagram (B) | Successful n | RX Mbps (mean ± SD) | Loss % (mean ± SD) | Jitter ms (mean ± SD) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in summary_rows:
        report.append(
            f"| {r['tenant']} | {r['datagram_bytes']} | {r['successful_trials']} "
            f"| {fmt(r['receiver_mbps_mean'], 3)} ± {fmt(r['receiver_mbps_sd'], 3)} "
            f"| {fmt(r['udp_loss_percent_mean'], 4)} ± {fmt(r['udp_loss_percent_sd'], 4)} "
            f"| {fmt(r['jitter_ms_mean'], 4)} ± {fmt(r['jitter_ms_sd'], 4)} |"
        )

    report.extend([
        "",
        "## Generated artifacts",
        "",
        f"- Summary CSV: `{SUMMARY.relative_to(ROOT)}`",
        f"- Throughput graph: `{GRAPHS['throughput'].relative_to(ROOT)}`",
        f"- Packet-loss graph: `{GRAPHS['loss'].relative_to(ROOT)}`",
        f"- Jitter graph: `{GRAPHS['jitter'].relative_to(ROOT)}`",
        "",
        "## Interpretation and limitations",
        "",
        "- Receiver throughput, packet loss, and jitter are reported from the recorded iperf3 results.",
        "- The offered rate was configured by the experiment command; measured receiver throughput may differ.",
        "- These results describe this topology, host environment, configuration, and tested payload sizes. They should not be generalized to all VXLAN deployments.",
        "- A small number of repetitions (five per tenant and size in the planned campaign) limits the precision of estimates.",
        "- Standard deviations describe observed trial variability; they are not confidence intervals.",
        "- If any metric is missing for a successful trial, that value is excluded from that metric's summary rather than treated as zero.",
        "- Successful trial status indicates the measurement command completed; it does not imply zero packet loss.",
        "",
    ])
    REPORT.write_text("\n".join(report), encoding="utf-8")

    print(f"Raw rows: {len(rows)}; successful: {len(successful)}; failed/non-success: {len(failed)}")
    print(f"Summary CSV: {SUMMARY}")
    for key, path in GRAPHS.items():
        print(f"{key.capitalize()} graph: {path}")
    print(f"Report: {REPORT}")
    print("\nSummary:")
    for r in summary_rows:
        print(
            f"Tenant {r['tenant']} | {r['datagram_bytes']:4} B | "
            f"n={r['successful_trials']} | "
            f"RX={fmt(r['receiver_mbps_mean'], 3)} ± {fmt(r['receiver_mbps_sd'], 3)} Mbps | "
            f"loss={fmt(r['udp_loss_percent_mean'], 4)}% | "
            f"jitter={fmt(r['jitter_ms_mean'], 4)} ms"
        )


if __name__ == "__main__":
    main()
