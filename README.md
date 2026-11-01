# P4 VXLAN: Multi-Tenant Networking and Isolation

## Final WSL2 results (27 October 2026)

See the detailed [consolidated experiment addendum](docs/experiments/final-results-addendum-2026-10-27.md) for the completed main 240-trial campaign (reported 120 trials/configuration across six TCP MSS conditions), Welch/95% CI analysis, tenant and VTEP scalability results, crafted-packet isolation evidence and limitations, supplementary CPU measurements, manuscript corrections, and an explicit inventory of which raw files/figures still need publication from the operator's WSL2 worktree.

The principal reported conclusions are that VXLAN receiver throughput was lower than the plain-L2 forwarding baseline for every tested MSS in the main campaign; tenant reachability checks passed through eight tenants and VTEP connectivity checks passed through four VTEPs; and the separate, exploratory CPU campaign reported mean estimated aggregate CPU of 319.5% of one core (VXLAN) versus 403.4% (baseline), alongside mean receiver throughput of 28.14 versus 71.81 Mbps. The CPU figures are small-sample, approximate-window estimates—not proof that VXLAN is more CPU-efficient.

**Artifact integrity:** the addendum names the exact local WSL2 paths for the 240-trial CSV, scalability CSVs/plots, packet captures/logs, and CPU CSVs. These are not described as published GitHub files until the original artifacts themselves are committed. Keep historical short runs separate from the 30-second campaign and do not fabricate missing raw rows or plots.

## Overview
This project evaluates P4-based VXLAN encapsulation, connectivity, performance and tenant separation using BMv2 and Mininet. Results describe software emulation on the specified host/WSL2 environment; they are not hardware-switch line-rate measurements.

## Topology
| Tenant | Hosts | VNI | Subnet |
|---|---|---:|---|
| Tenant A | h1, h2 | 1001 | 192.168.10.0/24 |
| Tenant B | h3, h4 | 1002 | 192.168.20.0/24 |

The VXLAN path encapsulates by tenant-facing ingress port and decapsulates using the VNI and inner IPv4 destination. Unmatched table entries use a drop action.

## Repository map
| Path | Purpose |
|---|---|
| src/p4/vxlan.p4 | P4_16 VXLAN parser, encapsulation, decapsulation and forwarding |
| src/p4/baseline.p4 | Plain-L2 P4 forwarding baseline without VXLAN headers |
| topology/vxlan_topology.py | Two-VTEP Mininet VXLAN topology |
| topology/baseline_topology.py | Matching no-VXLAN baseline topology |
| scripts/benchmark.py | Repeated measurements on one VXLAN condition |
| scripts/baseline_benchmark.py | Repeated measurements on one plain-L2 baseline condition |
| scripts/repeated_benchmark.py | MSS campaign orchestration, optional paired baseline, tool metadata |
| scripts/analyze_repeated_trials.py | Mean, sample SD, and 95% confidence intervals from raw CSV |
| scripts/test_repeated_analysis.py | Statistics unit tests |
| docs/experiments/reproduction.md | Compile, run, repeat and analyze instructions |
| docs/experiments/baseline-and-sweeps.md | Corrections checklist and remaining tests |
| results/REPEATED_TRIALS_SCHEMA.md | Raw measurement schema and reporting rules |
| results/ | Historical data, new raw measurements and plots |

## Toolchain and compilation
Run these from the repository root in the configured Ubuntu/WSL2 environment. Confirm tool versions using the commands in the reproduction guide.

```bash
mkdir -p build
p4c --target bmv2 --arch v1model -o build/vxlan.json src/p4/vxlan.p4
p4c --target bmv2 --arch v1model -o build/baseline.json src/p4/baseline.p4
```

P4C may create a directory at an output path depending on the installed version. Inspect build output and ensure the final JSON files are regular files at `build/vxlan.json` and `build/baseline.json` before running Mininet. Do not delete uninspected compiler output.

## Repeated benchmark campaign
To run six TCP MSS conditions (500, 700, 900, 1100, 1300 and 1400 bytes), each with ten recorded 30-second trials for both tenants, and also run the no-VXLAN baseline, use:

```bash
sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --mss 500 700 900 1100 1300 1400 --with-baseline
```

This launches a fresh Mininet topology for each condition. Each tenant/condition has one excluded warm-up, then the specified measured trials. The orchestrator alternates baseline/VXLAN order across MSS values and records tool metadata to `results/environment.json`. Raw trial rows (including failed attempts and their reasons) append to `results/repeated_trials.csv`.

The plain-L2 baseline is a forwarding-performance comparison, **not** a tenant-isolation configuration. It deliberately uses no VXLAN VNI or encapsulation. The campaign code and baseline are newly added but have **not been compiled or run in this ChatGPT environment**; verify on your actual WSL2 P4C/BMv2/Mininet setup before relying on the results.

Analyze actual observations after execution:

```bash
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
python3 -m unittest scripts/test_repeated_analysis.py
```

The analyzer groups by experiment, configuration, tenant, transport, MSS, payload, duration, MTU and offload so unlike conditions are not pooled. It reports mean, sample standard deviation and approximate two-sided 95% Student-t confidence intervals where there are at least two successful throughput observations. Failed or malformed rows do not contribute to throughput summaries, but stay in the raw file.

## UDP RSS campaigns and analysis (1 November 2026)

The RSS-instrumented UDP campaigns were completed in the operator's WSL2 environment. RSS was sampled every 500 ms from the running `simple_switch` processes. Each successful 30-second trial contains 61 RSS samples.

### Full campaigns

| Campaign | Conditions | Successful trials |
|---|---|---:|
| Offered-load scalability | Ten trials per tenant at 5, 15 and 25 Mbps | 60 |
| Application payload sweep | Five trials per tenant at 256, 512, 768, 1024 and 1200 bytes; 5 Mbps | 50 |
| **Total** | | **110** |

Local raw CSVs:
- `results/scalability/udp_scalability_rss_full_20261101.csv`
- `results/scalability/udp_payload_sweep/udp_payload_rss_full_20261101.csv`

The campaigns were validated as 60/60 and 50/50 successful rows, respectively, with ten or five trials per tenant/condition as specified and 61 RSS samples in every row.

### Analysis outputs

The local analysis script `scripts/analyze_udp_rss.py` produces descriptive means and standard deviations, percentile-bootstrap 95% confidence intervals (20,000 resamples; fixed seed 20261101), Welch comparisons, Holm-adjusted p-values, and per-metric graphs. Comparisons with constant observations in both groups are flagged rather than assigned a misleading Welch p-value.

Local analysis outputs are under `results/udp_rss_analysis/`, including:
- `scalability_summary.csv` and `scalability_welch_tests.csv`
- `payload_summary.csv` and `payload_welch_tests.csv`
- the `scalability_*.png` and `payload_*.png` graphs
- `original_vs_new_udp_comparison.csv`
- `revised_analysis_log.txt`

The comparison file contains 30 payload rows and 18 offered-load rows. The original payload campaign and new payload campaign each have five successful trials per tenant/payload condition. For offered-load comparison, the separate 30-row original campaign contains one failed trial and only four successful Tenant B trials at 15 Mbps; failed rows are excluded from means but retained in the original raw file. The separate 39-row original campaign is not pooled with that comparison because its Tenant B coverage is incomplete.

### Interpretation and limitations

The new campaigns achieved receiver throughput close to the configured offered rates. The earlier 256-byte Tenant B payload result (mean loss 2.0674% in the original five-trial campaign) was not reproduced in the new five-trial campaign (0% observed mean loss). This is a campaign-to-campaign descriptive difference, not proof of a fix or a causal explanation. RSS readings that are constant across all trials are reported descriptively; they are not treated as inferential evidence. The bootstrap intervals and tests are exploratory given the small number of trials, and statistical significance must be interpreted with the Holm correction.

The local CSVs, script, analysis summaries and PNGs are not yet claimed as published repository artifacts until the original files are committed. Do not reconstruct raw trial data from the summary values in this README.

### P4 correctness update

The project branch now contains an ingress-gated VXLAN pipeline change in `src/p4/vxlan.p4`: decapsulation is restricted to underlay ingress port 3; encapsulation is restricted to tenant-facing ports 1 and 2; tenant-originated packets parsed as VXLAN are dropped. The outer IPv4 total-length assignment is set to inner IPv4 total length +50, while the outer UDP length remains inner IPv4 total length +30, following the project's correction specification.

This source update has not yet been recompiled or exercised in the user's WSL2 environment after publication. Runtime attack verification, before/after packet captures, Linux VXLAN/Wireshark interoperability and routed-underlay validation remain required. Port numbers are specific to the current two-VTEP topology.

## Evidence status and remaining corrections
The existing 3-second MSS-1000 figures (Tenant A 26.9 and 26.2 Mbps; Tenant B 26.5 Mbps) and earlier 5-/10-second MTU-1450 figures are historical measurements. They are not the output of the new campaign and must not be pooled across different conditions.

The main repeated VXLAN campaign, plain-L2 baseline, tenant/VTEP scalability checks, crafted-packet isolation work, and the previously reported UDP application-payload sweep are documented in the consolidated addendum. The additional RSS-instrumented UDP offered-load and payload pilots are recorded above; their full campaigns and publication of the new local scripts/raw CSVs remain outstanding. A failed ping does not prove exactly where a packet was dropped. See docs/experiments/baseline-and-sweeps.md and docs/experiments/final-results-addendum-2026-10-27.md.

## Checksum notes
The P4 checksum control recalculates the emitted IPv4 header: the new outer IPv4 header on encapsulation, and the restored inner IPv4 header after decapsulation. Outer UDP checksum is set to zero (permitted for IPv4 UDP). P4 input checksum verification is not implemented in the current verify-checksum control. Validate packet captures and checksum behaviour for the actual tested traffic types; do not use endpoint offload settings to obscure a data-plane checksum problem.

## References and reports
- Historical results and conditions: paper/results.md
- Research methodology: paper/methodology.md
- Testbed reproduction: docs/experiments/reproduction.md
- Correction checklist and limitations: docs/experiments/baseline-and-sweeps.md
- Isolation report: docs/experiments/isolation-test-report.md
