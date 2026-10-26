# Correction plan: baseline, repetition, checksum handling, and isolation tests

This document translates the first-level correction sheet into testable work. The numbers in the current report are historical observations, not new trial results.

## What the correction requires

1. **Baseline and repeatability:** compare baseline forwarding without VXLAN against the P4 VXLAN path with the same hosts, MTU, traffic settings, and test duration. Run at least 10 independent 30-second trials per condition and report mean, sample standard deviation, and a 95% confidence interval.
2. **MSS and payload sweep:** test TCP MSS values 500, 700, 900, 1100, 1300, and 1400 bytes as separate conditions. If also measuring UDP application payload sizes, record them as a separate UDP experiment (not as TCP MSS).
3. **Isolation misuse tests:** craft packets with Scapy for the correct VNI, wrong VNI, spoofed VNI, and wrong inner destination; observe the receiving tenant-facing interface and packet counters. Save the packet capture and exact command/output for each test.
4. **Scale:** extend the topology to at least eight tenants and measure packet-processing cost alongside table size. Use 3–4 VTEPs only after the two-VTEP experiment remains correct.
5. **Mechanisms:** explain that BMv2 does not behave like a NIC that repairs checksum offload on behalf of the P4 program. Recompute outer IPv4 checksum in P4 and validate inner IPv4/UDP checksum behaviour separately. Do not describe endpoint offload changes as a substitute for correct protocol checksum handling.
6. **Manuscript:** remove course-only manuscript headers, replace terminal screenshots with clean tables, improve related work with actual P4 tunnel/overlay implementations, and describe the limitations precisely.

## Important current-code observation

The current `src/p4/vxlan.p4` implements an outer IPv4 `update_checksum` in `MyComputeChecksum`. It sets the outer UDP checksum to zero. The encapsulation action transfers the original Ethernet and IPv4 headers into the inner headers; the decapsulation action restores the inner headers. This file does not recompute an inner IPv4 checksum. The appropriate fix must be validated against supported packet types and the P4 v1model target before making broad correctness claims.

A TCP MSS sweep should not be represented as a payload-size sweep: they influence different layers. Run conditions separately and include the actual iperf3 command/configuration in the raw CSV.

## Trial design and reporting

- Perform a warm-up run and do not include it in the ten recorded trials.
- Alternate condition order or use a seeded, recorded order to reduce time/order bias.
- Preserve raw per-trial records. Never overwrite old observations; add an experiment ID, git commit, timestamp, tenant, transport, MSS/payload, duration, MTU, offload settings, sender and receiver throughput, retransmissions/loss, and exit status.
- Summarise each condition separately. Do not pool old 5-second and 10-second MTU 1450 runs with the 3-second MSS-1000 diagnostics.
- Compute a two-sided 95% Student-t confidence interval from independent trial values. A single trial cannot provide a meaningful sample standard deviation or confidence interval.
- Report the results as BMv2/Mininet/WSL2 performance, not physical switching performance.

## Commands for environment preflight

From Ubuntu/WSL2 in the repository root:

```bash
p4c --version
simple_switch --version
mn --version
python3 --version
iperf3 --version
sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30
```

The current preflight script only records environment information and confirms tool availability. It intentionally does not write synthetic benchmark values. Full trials must run while the Mininet host objects and BMv2 topology are alive; a separate Python process cannot access process-local Mininet Host objects without a designed controller or wrapper.

## Isolation evidence standard

A failed ping is an end-to-end observation, not proof of which table action dropped a packet. For every crafted frame test, retain:

- packet construction parameters (source host/interface, VNI, inner source/destination, protocol);
- ingress/egress PCAPs where possible;
- per-VNI/per-port counters before and after the trial;
- whether the correct same-tenant control succeeded in the same run;
- complete raw output, timestamp, and configuration/commit ID.

A test should distinguish *not delivered at the endpoint* from *confirmed dropped by the intended P4 table*. State which one was actually observed.

## Work that can be done outside the WSL2 network runtime

Analysis scripts, documentation, report structure, and configuration checks can be prepared in any Python environment. Actual throughput, latency, Scapy injection, CPU/packet-rate measurements, and multi-VTEP behaviour require the configured BMv2/Mininet environment and must be run there. Do not invent or extrapolate those observations.
