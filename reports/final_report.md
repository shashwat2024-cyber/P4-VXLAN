# P4-Based VXLAN Multi-Tenant Overlay: Implementation and Evaluation

## Abstract
This project implements a two-tenant VXLAN overlay using a P4_16 program on the BMv2 software switch and a Mininet-emulated topology. Tenant A uses VNI 1001 and tenant B uses VNI 1002. The evaluation records same-tenant connectivity, exploratory TCP throughput, and cross-tenant reachability checks. Results are reported as software-emulation measurements, not hardware line-rate results. The current evidence is sufficient to document a working prototype, but not to claim statistically robust performance or adversarially proven isolation.

## 1. Objectives
1. Implement VXLAN encapsulation and decapsulation in a P4 data plane.
2. Connect two isolated tenant networks through a shared underlay.
3. Measure basic connectivity and TCP receiver throughput.
4. Document configuration, raw observations, reproducibility steps, and limitations.

## 2. Architecture
The testbed uses two BMv2 VTEPs connected through an underlay switch. Mininet hosts are h1 (Tenant A, 192.168.10.1), h2 (Tenant A, 192.168.10.2), h3 (Tenant B, 192.168.20.1), and h4 (Tenant B, 192.168.20.2). VTEP1 attaches h1 on port 1, h3 on port 2 and the underlay on port 3. VTEP2 uses the same port arrangement for h2, h4 and the underlay. Tenant A maps to VNI 1001; tenant B maps to VNI 1002. The underlay endpoints are 10.0.0.1 and 10.0.0.2. The configured MTU in the recorded 1450-byte test is 1450 bytes.

## 3. Implementation
The P4 pipeline parses relevant Ethernet, IPv4, UDP and VXLAN headers; selects encapsulation rules using ingress-port/tenant mappings; and decapsulates based on the VNI and inner destination mapping. Entries not matched by the decapsulation table follow the configured drop behavior. BMv2 and Mininet are software components, so throughput is influenced by host CPU scheduling, virtualization and per-packet processing overhead.

VXLAN adds 50 bytes of outer headers in the basic IPv4 case considered here: outer Ethernet (14 B) + outer IPv4 (20 B) + UDP (8 B) + VXLAN (8 B). This is header arithmetic, not a measurement of performance overhead.

## 4. Methodology and available observations
The available records are preserved in datasets/iperf3_confirmed_trials.csv. Each row records its own configuration, direction, duration, MSS, sender and receiver throughput, retransmissions, MTU knowledge and status. Rows have different durations and settings and must not be treated as repeated trials of a single controlled condition.

### 4.1 Connectivity
Previously recorded same-tenant checks showed successful communication from h1 to h2 and from h3 to h4. A later interactive run also returned one reply for each individual ping. A pingall run dropped 4 of 12 probes, while individual same-tenant pings succeeded afterward. This inconsistency may reflect ARP/warm-up effects or test-order effects; it should not be presented as a clean packet-loss estimate. Exact command output and repeated measurements should be retained when reproducing the test.

### 4.2 Throughput
The confirmed-trial dataset includes:
- Tenant A, h1-to-h2, MTU 1450: three recorded runs of 5 or 10 seconds with receiver throughput 36.8, 35.8 and 34.5 Mbit/s. The latter two runs recorded TCP retransmissions.
- MSS 1000 diagnostic runs of 3 seconds: Tenant A receiver throughput 26.9 and 26.2 Mbit/s; Tenant B receiver throughput 26.5 Mbit/s. These rows recorded zero retransmissions and the MTU was not confirmed for these diagnostic runs.

These observations are descriptive only. Since duration, MSS and endpoint settings differ, they do not establish a controlled causal comparison or confidence interval. The observed 26–37 Mbit/s range is specific to this BMv2/Mininet/WSL2-style software environment and is not VXLAN hardware line-rate performance.

### 4.3 Tenant isolation
The initial tests observed failed cross-tenant probes and successful same-tenant connectivity. However, a failed ping alone does not identify where a packet was dropped, and a drop-default table entry is not an adversarial test. Therefore, the evidence supports only an initial reachability check—not a proof of isolation against spoofed VNIs, wrong inner destinations, or malformed packets.

## 5. Results summary
| Property | Observation | Interpretation |
|---|---|---|
| Same-tenant reachability | h1→h2 and h3→h4 individually succeeded in recorded checks | Basic intended forwarding works in the tested configuration |
| TCP receiver throughput | 26.2–36.8 Mbit/s across heterogeneous recorded trials | Exploratory software-switch measurements only |
| TCP retransmissions | 0 in MSS-1000 diagnostics; 137 and 191 in two MTU-1450 10-second runs | Endpoint and TCP conditions differ; do not pool as one condition |
| Cross-tenant probes | Earlier probes failed | Initial reachability evidence, not adversarial isolation proof |
| VXLAN-free baseline | No validated comparable baseline available in reviewed records | Encapsulation overhead cannot currently be quantified |
| Variance / confidence interval | Insufficient comparable repeated trials | No inferential statistical claim is made |

## 6. Response to instructor comments
The accompanying reports/instructor_comments_response.md maps each major comment to changes made and remaining work. Key changes in this report are to treat the project as a lab prototype rather than a publication-ready research paper; separate raw confirmed iperf3 observations into a standalone CSV; distinguish MSS changes from checksum/offload settings; avoid unsupported performance and isolation claims; and state that baseline, repeated trials, confidence intervals, MSS sweeps and scale testing are not complete.

## 7. Limitations and future work
1. Establish a VXLAN-free forwarding baseline using the same topology and host settings.
2. Run at least 10 independent 30-second trials per condition; preserve raw outputs and report mean and a clearly defined confidence interval.
3. Sweep MSS/payload sizes while holding all other conditions constant.
4. Record exact checksum-offload settings and review checksum recomputation in the P4 pipeline where required.
5. Test crafted frames with spoofed VNIs, wrong inner destinations and VNI collisions; capture packets or use counters at the egress to identify where they are dropped.
6. Scale the testbed to more tenants and VTEPs and record resource use.
7. Record versions of p4c, BMv2, Mininet, Python, iperf3, host OS and virtualization environment.

## 8. Reproducibility and data availability
The code, topology and scripts are in this repository. Reviewed throughput observations are provided separately in datasets/iperf3_confirmed_trials.csv; field meanings and caveats are documented in datasets/README.md. Existing project result files should be preserved. No missing baseline values or repeated-trial measurements have been invented.

## Conclusion
The project demonstrates a P4/BMv2 prototype for a two-tenant VXLAN overlay and records preliminary connectivity and TCP throughput observations. The dataset is useful for transparent reporting and as a starting point for repeatable experiments. Current evidence does not quantify VXLAN overhead, provide statistical performance estimates, or prove isolation against adversarial traffic. Those claims require the controlled baseline, repeated trials and explicit attack tests listed above.
