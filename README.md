# P4 VXLAN: Multi-Tenant Networking and Isolation

## Overview

This project evaluates P4-based VXLAN encapsulation, tenant separation, functional interoperability, and software-emulated performance using BMv2 and Mininet. Measurements describe the tested Ubuntu/WSL2 ARM64 environment; they are not hardware-switch line-rate results.

The repository contains a two-tenant reference topology, a plain-L2 forwarding comparison, security-oriented ingress and decapsulation checks, repeatable TCP and UDP measurement scripts, and larger tenant/VTEP correctness experiments.

## Topology

| Tenant | Hosts | VNI | Subnet |
|---|---|---:|---|
| Tenant A | h1, h2 | 1001 | 192.168.10.0/24 |
| Tenant B | h3, h4 | 1002 | 192.168.20.0/24 |

The P4 VXLAN implementation restricts VXLAN decapsulation to underlay-facing ingress and VXLAN encapsulation to tenant-facing ingress. Tenant and VNI-related validation is used to prevent tenant-originated traffic from injecting forged VXLAN packets into the overlay. Unmatched forwarding entries use drop behaviour.

## Repository map

| Path | Purpose |
|---|---|
| `src/p4/vxlan.p4` | P4_16 VXLAN parser, encapsulation, decapsulation and forwarding |
| `src/p4/baseline.p4` | Plain-L2 P4 forwarding comparison without VXLAN |
| `src/p4/vxlan_scalability.p4` | Scalable tenant/VTEP security implementation used for correctness experiments |
| `topology/vxlan_topology.py` | Two-VTEP Mininet VXLAN topology |
| `topology/baseline_topology.py` | Matching no-VXLAN baseline topology |
| `topology/vxlan_routed_topology.py` | Routed-underlay topology |
| `scripts/benchmark.py`, `scripts/baseline_benchmark.py` | Individual VXLAN and plain-L2 benchmark runners |
| `scripts/repeated_benchmark.py` | Repeated TCP campaign orchestration |
| `scripts/analyze_repeated_trials.py` | Repeated-trial statistical summaries |
| `scripts/udp_payload_sweep.py`, `scripts/scalability_udp.py` | UDP payload and offered-load measurement campaigns |
| `scripts/run_scalability_experiments.py` | Tenant/VTEP security correctness experiments |
| `scripts/build_final_analysis.py` | Consolidates final TCP, CPU, UDP and scalability analysis outputs |
| `docs/experiments/reproduction.md` | Environment, build and reproduction guidance |
| `docs/experiments/baseline-and-sweeps.md` | Experiment status, scope and reporting rules |
| `docs/experiments/isolation-test-report.md` | Tenant-isolation and security evidence |
| `results/` | Raw observations, analysis tables, plots and experiment reports |

## Toolchain and compilation

The recorded environment was Ubuntu 24.04.5 under WSL2 on ARM64, P4C 1.2.5.18, BMv2 `simple_switch` 1.15.7, Mininet 2.3.0, Python 3.12.3 and iperf3 3.16. Check the installed versions on the machine used for reproduction.

From the repository root:

```bash
mkdir -p build
p4c --target bmv2 --arch v1model -o build/vxlan.json src/p4/vxlan.p4
p4c --target bmv2 --arch v1model -o build/baseline.json src/p4/baseline.p4
```

P4C may create a directory at an output path depending on the installed version. Inspect the build output and ensure the final JSON files are regular files before starting Mininet. Do not delete uninspected compiler output.

## Experimental evidence

### TCP throughput, memory and post-transfer RTT

The final matched TCP analysis is in `results/final_analysis_20261101/`. It uses 20 successful trials in each tenant/configuration/MSS group for the two final MSS conditions (500 and 1400 bytes). The corrected VXLAN MSS-1400 primary dataset replaces the two failed Tenant B records (trials 17 and 19) with their successful recovery records. The additional recovery and diagnostic runs are retained separately and are not counted in the primary sample.

| Tenant | MSS | Plain-L2 mean (Mbps) | VXLAN mean (Mbps) | VXLAN change |
|---|---:|---:|---:|---:|
| A | 500 | 33.698 | 13.379 | -60.30% |
| A | 1400 | 100.776 | 39.514 | -60.79% |
| B | 500 | 34.560 | 13.907 | -59.76% |
| B | 1400 | 102.812 | 38.111 | -62.93% |

The TCP `latency_ms` field is the mean RTT from a 10-ping measurement performed after the TCP transfer. It is **not** an under-load latency measurement. RSS is the recorded resident memory of the monitored `simple_switch` process set.

### CPU comparison

The separate CPU campaign is in `results/cpu_utilisation_20261101/`. It contains 10 trials per configuration for Tenant A, using TCP, MSS 1000, 30-second transfers, MTU 1450 and the same recorded traffic/offload settings.

| Configuration | Mean CPU (% of one core) | Mean receiver throughput (Mbps) | Mean RSS (MiB) |
|---|---:|---:|---:|
| Plain-L2 baseline | 413.82 | 72.74 | 93.00 |
| VXLAN | 330.25 | 29.01 | 107.64 |

CPU percentages can exceed 100% because they are expressed relative to one CPU core and the monitored process set can use multiple cores. The CPU-per-throughput ratio is descriptive only. This campaign covers Tenant A only and should not be generalised to Tenant B.

### UDP measurements

The UDP payload and offered-load analyses are in `results/udp_rss_analysis/`. These campaigns used concurrent ping measurements, so their RTT observations are under-load measurements. Consult the included CSV summaries and Holm-adjusted statistical test results for sample sizes and metric-specific results. Do not conflate these UDP under-load RTT values with the TCP post-transfer ping measurements.

### Isolation and scalability correctness

The security/scalability report is `results/scalability/SCALABILITY_SECURITY_REPORT_20261101.md`. Its six recorded configurations passed the reported legitimate-connectivity, cross-tenant blocking and spoofed-source blocking checks, covering 2–8 tenants and 2–4 VTEPs. The report includes the per-configuration probe counts.

Additional packet-level and interoperability evidence is stored under `results/evidence/`. See `docs/experiments/isolation-test-report.md` for the scope and limitations of those tests.

## Interpretation and limitations

- BMv2 is a software reference environment. These results do not establish hardware-switch throughput, latency or line-rate capability.
- The plain-L2 configuration is a forwarding-performance comparison, not a tenant-isolation baseline.
- TCP performance comparisons are descriptive; the consolidated report does not claim statistical significance for the TCP differences.
- CPU measurements cover Tenant A only.
- TCP latency is measured after the transfer; UDP latency is measured concurrently with traffic. They are different metrics and must be labelled separately.
- Correctness tests cover the recorded scenarios. They are not exhaustive proof against every malformed packet, attack, configuration error or deployment environment.
- Do not infer scalability performance from the tenant/VTEP correctness tests. Those experiments report functional probe outcomes, not a complete performance characterisation at every scale.

## Reports and reproduction

- Consolidated analysis and figures: `results/final_analysis_20261101/FINAL_ANALYSIS_REPORT.md`
- TCP primary datasets: `results/final_evaluation_20261031/`
- CPU raw samples and summaries: `results/cpu_utilisation_20261101/`
- UDP summaries and tests: `results/udp_rss_analysis/`
- Tenant/VTEP correctness results: `results/scalability/SCALABILITY_SECURITY_REPORT_20261101.md`
- Reproduction instructions: `docs/experiments/reproduction.md`
- Isolation evidence: `docs/experiments/isolation-test-report.md`

The research manuscript files (`paper/methodology.md` and `paper/results.md`) are maintained separately and will be revised as part of the final PDF preparation.
