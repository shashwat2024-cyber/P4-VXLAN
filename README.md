# P4 VXLAN: Multi-Tenant Networking and Isolation

## Project status

This repository contains a P4_16 VXLAN software prototype using BMv2 and Mininet. The current recorded data are preliminary functional checks and short throughput diagnostics. They should not be presented as statistically robust performance evidence or as exhaustive proof of tenant isolation.

The corrected working branch adds a repeatable raw-run benchmark harness, a run-level summary script, and a correction roadmap based on the team's first-level review. New scripts have been committed to `corrections/reproducible-evaluation`; no new network result is claimed until you execute the experiment on the configured Ubuntu/WSL2 system.

## Research question

How do same-tenant connectivity and TCP throughput behave in this P4-based VXLAN software testbed, and how effectively do the implemented VNI and inner-destination forwarding rules reject cross-tenant packets under both normal and crafted tests?

## Existing testbed

| Component | Configuration |
|---|---|
| Data plane | P4_16 on BMv2 `simple_switch` |
| Emulation | Mininet with a virtual OVS underlay |
| Tenant A | h1–h2; subnet 192.168.10.0/24; VNI 1001 |
| Tenant B | h3–h4; subnet 192.168.20.0/24; VNI 1002 |
| Underlay endpoints | 10.0.0.1 and 10.0.0.2 |
| VXLAN UDP destination | 4789 |
| Platform described in the current report | Ubuntu 24.04 under WSL2, ARM64 |

## Recorded preliminary evidence

The following are historical measurements already documented in this repository, not results of the new harness.

- Same-tenant ICMP controls succeeded in the reported three-packet runs.
- The short MSS-1000 TCP diagnostic runs reported receiver throughput of 26.9 and 26.2 Mbit/s for Tenant A and 26.5 Mbit/s for Tenant B; the reported retransmission count was zero in these three runs.
- Cross-tenant three-packet pings received no replies in the two tested directions, while the decapsulation tables used a default-drop action.

These observations are limited in sample size and scope. A failed ping by itself does not identify where the packet was dropped. The observed table configuration and test results are consistent with the intended policy for the tested flows; they are not exhaustive proof against spoofing, malformed frames, VNI collisions, or all possible table errors.

## Reproduce existing P4 topology

Read [`docs/experiments/reproduction.md`](docs/experiments/reproduction.md) before running. In summary, compile the P4 program, validate the JSON, launch the topology with root privileges, and verify the runtime table entries and same-tenant positive controls.

## New repeated VXLAN-only harness

The correction branch adds:

- [`scripts/repeated_vxlan_benchmark.py`](scripts/repeated_vxlan_benchmark.py) — appends individual run observations to a new CSV and retains failed runs.
- [`scripts/summarise_trials.py`](scripts/summarise_trials.py) — summarizes run-level data and reports a two-sided 95% Student-t confidence interval when sample size permits.
- [`docs/experiments/repeated-benchmark.md`](docs/experiments/repeated-benchmark.md) — usage and interpretation.
- [`docs/experiments/correction-roadmap.md`](docs/experiments/correction-roadmap.md) — prioritized implementation and evaluation plan.

Example:

```bash
sudo -E python3 scripts/repeated_vxlan_benchmark.py --runs 10 --duration 30 --mss 1000
python3 scripts/summarise_trials.py results/repeated_vxlan_trials.csv --metric receiver_mbps
```

Run different MSS values as separate invocations and record the exact command and environment for each. The harness measures the existing VXLAN topology only. It does not create a no-VXLAN control. A baseline must use an explicitly implemented, documented configuration with matched endpoints, MTU, traffic, duration, and offered load. Do not compare rows from unlike topologies as if the only difference were VXLAN.

## Required work before stronger research claims

1. Compile and validate the P4 program on the target toolchain after any checksum change.
2. Diagnose checksum validity using packet capture and explicit checks, then test ICMP and TCP again.
3. Implement and measure a well-defined no-VXLAN baseline.
4. Execute at least 10 independent 30-second runs per condition and MSS; retain raw rows and failures.
5. Run crafted VNI/destination/unknown-VNI isolation tests in both directions in the isolated Mininet environment and capture ingress, underlay, and destination-side evidence.
6. Add/query counters only after their semantics are validated on the actual BMv2/P4 toolchain.
7. Replace terminal screenshots in the paper with concise tables; retain raw logs and captures as artefacts.
8. Add verified, directly relevant P4 tunnelling/VXLAN/GENEVE literature and ensure the manuscript reflects only evidence actually collected.

## Research integrity

Do not fabricate measurements, fill in missing confidence intervals, claim a test passed before running it, or alter the old results to resemble the new protocol. Report CPU/WSL2/BMv2 limitations clearly. A software-emulator result is not a claim about physical-switch line rate.
