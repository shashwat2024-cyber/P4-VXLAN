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
| scripts/benchmark.py | Process-local Mininet benchmark for one VXLAN MSS condition |
| scripts/repeated_benchmark.py | Repeated TCP MSS campaign orchestrator; optionally runs the plain-L2 baseline |
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
The repository contains historical measurements for short same-tenant ping/iperf3 tests and cross-tenant probes. Those observations are useful functional checks but are not a substitute for controlled repeated measurements. The current three MSS-1000 diagnostic throughput values (26.9 and 26.2 Mbps for Tenant A; 26.5 Mbps for Tenant B) are historical values, not outputs of the new repeated campaign. Conditions with different duration, MTU, MSS, or endpoint offload settings must be kept separate.

Mam's correction sheet asks for a VXLAN-free baseline, at least 10 x 30-second runs per condition, MSS/payload sweeps, direct crafted-packet isolation tests, scale testing, and clear checksum handling. The baseline and TCP MSS campaign code are now present, but no live results are claimed until the actual BMv2/Mininet environment produces raw output.

## Run and analyse
Run the repeated MSS campaign inside the target system:

```bash
p4c --target bmv2 --arch v1model -o build/vxlan.json src/p4/vxlan.p4
p4c --target bmv2 --arch v1model -o build/baseline.json src/p4/baseline.p4
sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --mss 500 700 900 1100 1300 1400 --with-baseline
```

This campaign records tool versions, then runs each MSS condition in a child process that owns its own Mininet topology. With `--with-baseline`, it also runs the P4 plain-L2 no-VXLAN baseline in a matching topology and alternates condition order across MSS values. It writes actual per-tenant, per-trial observations to the raw CSV. Use `--preflight-only` to check the environment without sending traffic. UDP payload sweep, spoofing tests, and scale experiment remain separate work.

Once actual per-trial records are saved in the schema documented at results/REPEATED_TRIALS_SCHEMA.md, summarize them:

```bash
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
```

The analyzer excludes failed trials from throughput summaries and reports sample means, sample standard deviations, and approximate two-sided 95% Student-t confidence intervals for conditions with at least two successful measurements. Failed runs should remain in the raw CSV with their status and reason.

## Limitations and reporting rules
- BMv2/Mininet/WSL2 throughput is software-emulation performance, not physical switching performance.
- A failed ping shows non-delivery of the tested probe, not the exact location or mechanism of a drop.
- Default-drop forwarding rules are a design property; isolation testing should also use crafted VNI/wrong-destination packets, endpoint captures and per-VNI/per-port counters.
- The P4 checksum control recalculates the emitted IPv4 header. On encapsulation this is the new outer IPv4 header; on decapsulation the inner IPv4 header is copied into the outer IPv4 header and recalculated before emission. Outer UDP checksum is set to zero (permitted for IPv4 UDP); validate actual packets with captures. The P4 verify-checksum control is empty, so input checksum verification is not performed by P4.
- Do not invent data or combine measurements collected under different conditions.

## References for reproduction
- Research methodology: paper/methodology.md
- Existing results and conditions: paper/results.md
- Isolation test report: docs/experiments/isolation-test-report.md
- Baseline and sweep plan: docs/experiments/baseline-and-sweeps.md
