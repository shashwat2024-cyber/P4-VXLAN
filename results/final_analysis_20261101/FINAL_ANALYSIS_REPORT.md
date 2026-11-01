# Consolidated Final Experimental Analysis

Generated from the recorded experiment CSV files. Raw experiment files were not modified.

## 1. TCP methodology

TCP results are grouped by configuration, tenant and MSS. Each group contains 20 successful trials.
The corrected VXLAN MSS-1400 dataset uses the successful recovery records for Tenant B trials 17 and 19.
The additional recovery run and diagnostic runs are excluded from the primary sample.

`latency_ms` is the mean RTT from the 10-ping measurement after the TCP transfer; it is not RTT measured under TCP load.

## 2. TCP throughput comparison

| Tenant | MSS | L2 mean Mbps | VXLAN mean Mbps | VXLAN change |
|---|---:|---:|---:|---:|
| A | 500 | 33.698 | 13.379 | -60.30% |
| A | 1400 | 100.776 | 39.514 | -60.79% |
| B | 500 | 34.560 | 13.907 | -59.76% |
| B | 1400 | 102.812 | 38.111 | -62.93% |

## 3. TCP memory and latency

The detailed group means, standard deviations and sample counts are in `tcp_trial_summary.csv`.
The matched configuration differences are in `tcp_comparison.csv`.

RSS is the recorded resident memory of the simple_switch process set. Interpret small differences in light of the sampling interval and process-level measurement scope.

## 4. CPU comparison

| Configuration | Mean CPU (% one core) | Peak CPU (% one core) | Throughput (Mbps) | Mean RSS (MiB) | CPU percentage points per Mbps |
|---|---:|---:|---:|---:|---:|
| P4_L2_BASELINE | 413.82 | 435.02 | 72.74 | 93.00 | 5.689 |
| P4_VXLAN | 330.25 | 340.20 | 29.01 | 107.64 | 11.384 |

CPU utilisation is expressed as a percentage of one CPU core. Values above 100% are valid when multiple cores are used.
The CPU campaign compares Tenant A only, with 10 trials per configuration. CPU-per-throughput is a descriptive ratio, not a causal efficiency measurement.

## 5. UDP analysis

The existing UDP payload and offered-load/scalability analyses were reused. Their summary and Welch/Holm test CSVs are included alongside this report.
The payload and scalability campaigns used concurrent ping measurements to capture under-load RTT.
Consult the included CSVs for per-metric sample sizes, confidence intervals and adjusted p-values.

## 6. Interpretation and limitations

- TCP post-transfer RTT must not be described as under-load latency.
- TCP comparisons are descriptive; this report does not claim statistical significance for TCP differences.
- UDP inferential results should be interpreted using the Holm-adjusted p-values in the existing test tables.
- CPU measurements cover the single-tenant CPU campaign and should not be generalised to Tenant B.
- The plain L2 baseline is a forwarding baseline, not a tenant-isolation baseline.
- BMv2 measurements characterise the tested software environment and should not be treated as hardware-switch performance.
- Failed original trial records remain in the raw evidence. The corrected primary dataset replaces the two failed Tenant B MSS-1400 records with successful recoveries.

## 7. Generated figures

- `tcp_throughput.png`
- `tcp_rss.png`
- `tcp_post_transfer_rtt.png`
- `cpu_mean.png`
- `cpu_throughput.png`

## 8. Source data

- `results/final_evaluation_20261031/`
- `results/cpu_utilisation_20261101/`
- `results/udp_rss_analysis/`
