# P4 VXLAN: Multi-Tenant Networking and Isolation

## Overview
This project evaluates P4-based VXLAN encapsulation, connectivity, performance, and tenant separation using BMv2 and Mininet in a software-emulated network. Measurements describe the specific host/WSL2 environment and should not be interpreted as hardware-switch line-rate results.

## Topology
| Tenant | Hosts | VNI | Subnet |
|---|---|---:|---|
| Tenant A | h1, h2 | 1001 | 192.168.10.0/24 |
| Tenant B | h3, h4 | 1002 | 192.168.20.0/24 |

Each VTEP performs encapsulation on tenant-facing ingress and decapsulation using the VNI and inner IPv4 destination. Default table actions drop unmatched packets.

## Repository map
| Path | Purpose |
|---|---|
| src/p4/vxlan.p4 | P4_16 parsing, encapsulation, decapsulation, and forwarding |
| topology/vxlan_topology.py | Mininet topology and runtime table entries |
| scripts/benchmark.py | Existing process-local Mininet benchmark for the VXLAN path |
| scripts/repeated_benchmark.py | Toolchain/environment preflight for repeat campaigns; does not fabricate trials |
| scripts/analyze_repeated_trials.py | Raw CSV analysis with mean, sample SD, and 95% confidence intervals |
| docs/experiments/reproduction.md | Toolchain setup, compilation and topology reproduction |
| docs/experiments/baseline-and-sweeps.md | Mam's baseline, repeatability, checksum, isolation, and scale corrections |
| results/REPEATED_TRIALS_SCHEMA.md | Raw measurement fields and data-integrity rules |
| results/ | Raw recorded measurements and existing graphs |

## Toolchain
The documented setup is Ubuntu under WSL2 with p4c, BMv2 simple_switch, Mininet, Python 3, and iperf3. Verify the locally installed versions; do not assume the documented versions exactly match your machine.

```bash
p4c --version
simple_switch --version
mn --version
python3 --version
iperf3 --version
```

Compile the P4 program as described in the reproduction guide. Inspect the output of the compiler before moving any files.

## Existing evidence versus next experiments
The repository contains historical measurements for short same-tenant ping/iperf3 tests and cross-tenant probes. Those observations are useful functional checks but are not a substitute for controlled repeated measurements. Conditions with different duration, MTU, MSS, or endpoint offload settings must be kept separate.

Mam's correction sheet asks for a VXLAN-free baseline, at least 10 x 30-second runs per condition, an MSS/payload sweep, direct crafted-packet isolation tests, scale testing, and clear checksum handling. These items are not claimed complete until raw outputs from the actual BMv2/Mininet environment have been saved.

## Run and analyse
Run the repeated MSS campaign inside the target system:

```bash
sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --mss 500 700 900 1100 1300 1400
```

This script records tool versions, then runs each MSS condition through a child process that owns its own Mininet topology. It writes actual per-tenant, per-trial observations to the raw CSV. Use `--preflight-only` to check the environment without sending traffic. The campaign currently measures the P4 VXLAN path only; it does not run the no-VXLAN baseline, UDP payload sweep, spoofing tests, or scale experiment.

Once actual per-trial records are saved in the schema documented at results/REPEATED_TRIALS_SCHEMA.md, summarize them:

```bash
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
```

The analyzer excludes failed trials from throughput summaries and reports sample means, sample standard deviations, and approximate two-sided 95% Student-t confidence intervals for conditions with at least two successful measurements. Failed runs should remain in the raw CSV with their status and reason.

## Limitations and reporting rules
- BMv2/Mininet/WSL2 throughput is software-emulation performance, not physical switching performance.
- A failed ping shows non-delivery of the tested probe, not the exact location or mechanism of a drop.
- Default-drop forwarding rules are a design property; isolation testing should also use crafted VNI/wrong-destination packets, endpoint captures and per-VNI/per-port counters.
- The current P4 program recomputes the outer IPv4 checksum. Its UDP checksum is set to zero. Inner IPv4 checksum behaviour and TCP/UDP handling should be verified explicitly; endpoint offload settings should not hide data-plane checksum deficiencies.
- Do not invent data or combine measurements collected under different conditions.

## References for reproduction
- Research methodology: paper/methodology.md
- Existing results and conditions: paper/results.md
- Isolation test report: docs/experiments/isolation-test-report.md
- Baseline and sweep plan: docs/experiments/baseline-and-sweeps.md
