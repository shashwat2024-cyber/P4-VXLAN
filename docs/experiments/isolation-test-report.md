# VXLAN Tenant-Isolation and Security Experiment Report

## Test environment and tenant layout

- BMv2 `simple_switch`, P4C and Mininet
- Tenant A: `192.168.10.0/24`, VNI 1001
- Tenant B: `192.168.20.0/24`, VNI 1002
- Underlay endpoints in the two-VTEP topology: `10.0.0.1` and `10.0.0.2`
- VXLAN UDP destination port: 4789

The recorded environment used Ubuntu 24.04.5 under WSL2 on ARM64, P4C 1.2.5.18, BMv2 `simple_switch` 1.15.7, Mininet 2.3.0, Python 3.12.3 and iperf3 3.16.

## Same-tenant connectivity

In the recorded two-tenant functional run:

- h1 → h2: 3/3 replies, 0% packet loss; average RTT 8.146 ms.
- h3 → h4: 3/3 replies, 0% packet loss; average RTT 7.754 ms.

These small ping tests establish functional reachability for the tested host pairs. They are not statistical latency benchmarks.

## Cross-tenant connectivity

Explicit host routes and static neighbour entries were configured before testing reachability.

- h1 → `192.168.20.2`: 3 packets transmitted, 0 received; 100% packet loss.
- h3 → `192.168.10.2`: 3 packets transmitted, 0 received; 100% packet loss.

The observed failures are consistent with the configured tenant separation policy. A failed ping alone does not identify the exact data-plane drop point.

## Runtime table configuration

The two-VTEP topology uses tenant-specific decapsulation entries keyed by VXLAN VNI and inner IPv4 destination.

- VTEP1: VNI 1001 + `192.168.10.1` → port 1.
- VTEP1: VNI 1002 + `192.168.20.1` → port 2.
- VTEP2: VNI 1001 + `192.168.10.2` → port 1.
- VTEP2: VNI 1002 + `192.168.20.2` → port 2.

Both decapsulation tables use `MyIngress.drop_packet` as their default action. The P4 source uses exact-match VNI and inner-destination keys.

## Tenant-originated VXLAN injection

The P4 ingress-role handling was corrected so VXLAN decapsulation is restricted to underlay-facing ingress, while encapsulation is restricted to tenant-facing ingress. This prevents a tenant-facing port from being treated as a trusted VXLAN underlay ingress.

A crafted tenant-originated packet attempting to inject VXLAN traffic using Tenant B's VNI from Tenant A was blocked. A legitimate positive-control packet was delivered. The corresponding regression/evidence material is retained in the repository under `results/evidence/` and in the test sources.

This result supports the specific tested ingress-injection scenario. It should not be presented as proof against every possible malformed VXLAN packet or attack class.

## Encapsulation length and packet-capture checks

The implementation adds 50 bytes for the outer Ethernet, IPv4, UDP and VXLAN headers. A recorded packet-capture length check observed:

- Inner IPv4 total length: 84 bytes.
- Outer IPv4 total length: 134 bytes.
- VXLAN UDP length: 114 bytes.

Thus, the observed outer IPv4 total length matched the inner IPv4 length plus 50 bytes. The outer UDP checksum is set to zero for IPv4 UDP. The P4 verify-checksum control does not implement input checksum validation.

## Routed underlay and Linux VXLAN interoperability

Separate evidence sets are retained under:

- `results/evidence/routed_underlay_20261101/`
- `results/evidence/linux_p4_interop_20261101/`

The recorded tests demonstrated bidirectional connectivity over the routed L3 underlay and bidirectional interoperability between the P4 VXLAN implementation and Linux VXLAN. These are functional interoperability checks in the tested setup; they are not hardware performance measurements.

## Tenant and VTEP scale correctness

The scalable security report, `results/scalability/SCALABILITY_SECURITY_REPORT_20261101.md`, records the following results:

| Experiment | Tenants | VTEPs | Legitimate | Cross-tenant blocked | Spoofed sources blocked |
|---|---:|---:|---:|---:|---:|
| tenant_scaling | 2 | 2 | 4/4 | 4/4 | 4/4 |
| tenant_scaling | 4 | 2 | 8/8 | 24/24 | 8/8 |
| tenant_scaling | 6 | 2 | 12/12 | 60/60 | 12/12 |
| tenant_scaling | 8 | 2 | 16/16 | 112/112 | 16/16 |
| vtep_scaling | 2 | 3 | 12/12 | 12/12 | 12/12 |
| vtep_scaling | 2 | 4 | 24/24 | 24/24 | 24/24 |

All six final configurations passed their recorded checks. The initial six-tenant campaign had one inconclusive packet capture; the six-tenant retest passed all 60 cross-tenant probes. The original configuration CSVs retain setup and test timings.

These results demonstrate correctness for the recorded probes at the listed scales. They do not demonstrate throughput, latency or resource scalability at those scales.

## Interpretation and limitations

The successful same-tenant tests, failed cross-tenant tests, crafted tenant-originated injection test with a legitimate positive control, packet-length check, routed-underlay interoperability tests and scale correctness probes collectively support the intended policy in the tested configurations.

The evidence remains bounded by the tested topology, software versions, traffic patterns and attack cases. It is not exhaustive proof against every spoofing method, malformed packet, VNI collision, table misconfiguration or deployment condition. BMv2 is a software reference target; no hardware-switch performance claim follows from these experiments.

Retain the raw captures, CSV files, test outputs and failure records alongside this report. The consolidated analysis is in `results/final_analysis_20261101/FINAL_ANALYSIS_REPORT.md`.
