# P4 VXLAN: Multi-Tenant Networking and Isolation

## Overview

This project evaluates VXLAN-based multi-tenancy and tenant isolation in a P4-programmable software-emulated network using BMv2 and Mininet.

The project focuses on implementing VXLAN packet processing, separating network tenants, testing connectivity, evaluating network performance, and checking whether communication between different tenants is blocked as intended.

## Objectives

- Demonstrate VXLAN encapsulation and decapsulation using P4.
- Implement network segmentation using tenant-specific VXLAN Network Identifiers (VNIs).
- Test connectivity between hosts belonging to the same tenant.
- Evaluate network performance using throughput and latency measurements.
- Test cross-tenant isolation using network probes.
- Document the experimental procedure, results, and limitations.

## Technologies Used

- **P4:** Programmable data-plane packet processing.
- **BMv2:** Software-based P4 switch.
- **Mininet:** Network topology emulation.
- **p4c:** P4 compiler.
- **Ubuntu 24.04 under WSL2:** Experimental environment.
- **iperf3:** Network throughput measurement.
- **ICMP ping:** Connectivity and round-trip latency testing.
- **Python:** Benchmark automation and result processing.

## Network Architecture

The experimental topology consists of two tenants connected through a shared network infrastructure.

| Tenant | Hosts | Planned VNI |
|---|---|---|
| Tenant A | h1, h2 | 1001 |
| Tenant B | h3, h4 | 1002 |

The intended design allows communication between hosts belonging to the same tenant while preventing unauthorized communication across tenant boundaries.

The project uses P4-based packet processing and forwarding rules to support the intended VXLAN and isolation behavior.

## Evaluation Methodologies

Three evaluation methodologies are used to examine the network's behavior.

### 1. Same-Tenant Connectivity Testing

**Objective:** Verify that hosts belonging to the same tenant can communicate successfully.

**Method:**
- Use ICMP ping to test connectivity between hosts assigned to the same tenant.
- Record the number of transmitted and received packets.
- Observe packet loss and round-trip time (RTT).

**Recorded results:**

| Tested host pair | Packets received | Packet loss | Average RTT |
|---|---:|---:|---:|
| First tested pair | 3/3 | 0% | 8.146 ms |
| Second tested pair | 3/3 | 0% | 7.754 ms |

The recorded tests demonstrate successful connectivity for the tested host pairs. These results should not be interpreted as a guarantee for every possible host pair or network condition.

### 2. Network Performance Evaluation

**Objective:** Measure network performance and examine throughput and latency.

**Method:**
- Use `iperf3` to collect throughput measurements.
- Use ping measurements to observe round-trip latency and packet loss.
- Store measurement data and experiment logs for analysis.
- Use the recorded results and generated graph to examine performance.

The repository contains performance-related data under `results/`, including measurement files, test notes, run logs, and a throughput graph.

**Important consideration:** Performance results must be interpreted in the context of the experimental environment, test duration, traffic parameters, and number of trials. Short diagnostic runs alone are not sufficient to establish statistically robust performance differences.

### 3. Cross-Tenant Isolation Testing

**Objective:** Check whether traffic between different tenants is blocked as intended.

**Method:**
- Attempt communication from Tenant A to Tenant B.
- Attempt communication in the reverse direction.
- Record packet delivery and packet loss.
- Compare the observed behavior with the intended tenant-isolation policy.

**Recorded results:**

| Test direction | Packets sent | Packets received | Packet loss |
|---|---:|---:|---:|
| Tenant A to Tenant B | 3 | 0 | 100% |
| Tenant B to Tenant A | 3 | 0 | 100% |

The recorded results are consistent with the intended isolation policy for the tested flows.

However, these tests do not constitute exhaustive proof that every possible protocol, packet type, or communication path is isolated. The experiment report also notes that packet captures observed UDP traffic on port 4789, but did not independently verify the VXLAN VNI and inner destination for every captured packet.

## Results Summary

| Evaluation | Observation | Conclusion |
|---|---|---|
| Same-tenant connectivity | Both documented host-pair tests received 3/3 replies | Connectivity succeeded in the recorded tests |
| Cross-tenant isolation | Both tested directions experienced 100% packet loss | Results are consistent with isolation for the tested flows |
| Network performance | `iperf3` measurements and related result files are available | Raw measurements and test notes should be consulted before drawing performance comparisons |

These results describe the documented experimental runs in a software-emulated network environment.

## Repository Structure

Important project files and directories include:

| Path | Purpose |
|---|---|
| `paper/methodology.md` | Research objective, environment, configurations, metrics, and experimental procedure |
| `docs/experiments/isolation-test-report.md` | Recorded connectivity and isolation test results |
| `docs/experiments/reproduction.md` | Instructions and notes for reproducing experiments |
| `scripts/benchmark.py` | Benchmark automation for throughput, ping statistics, and cross-tenant checks |
| `results/` | Measurement files, test notes, run logs, and generated performance graph(s) |

## Experimental Procedure

The documented methodology follows these general steps:

1. Set up the P4 compiler, BMv2, and Mininet environment.
2. Configure the network topology and tenant-specific forwarding behavior.
3. Verify connectivity between hosts belonging to the same tenant.
4. Attempt communication between hosts belonging to different tenants.
5. Measure throughput and latency using the available benchmark tools.
6. Save experiment outputs and measurement data.
7. Compare observations against the intended connectivity and isolation policies.
8. Document limitations and preserve raw results for reproducibility.

For the exact commands and environment-specific instructions, consult `docs/experiments/reproduction.md`.

## Limitations

- The connectivity and isolation conclusions apply to the specific host pairs and traffic flows tested.
- ICMP packet loss alone does not establish that every possible form of cross-tenant communication is blocked.
- Performance comparisons require sufficient repeated trials and appropriate analysis before statistically strong conclusions can be made.
- BMv2 and Mininet results characterize a software-emulated environment; they do not establish physical-switch line-rate performance or hardware VXLAN offload capability.
- Experiment results should be based on recorded measurements rather than assumed or fabricated values.

## Conclusion

This project investigates VXLAN-based multi-tenancy and tenant isolation using a P4-programmable software-emulated network.

The documented experiments cover three main areas: same-tenant connectivity, network performance, and cross-tenant isolation. The connectivity tests succeeded for the tested host pairs, while the cross-tenant probes experienced complete packet loss in both tested directions, consistent with the intended isolation policy.

Performance measurements are available in the repository and should be interpreted alongside their associated test notes and experimental conditions.

Further testing across additional flows, protocols, and repeated performance trials would strengthen the evaluation.

## Further Documentation

- [Research Methodology](paper/methodology.md)
- [Isolation Test Report](docs/experiments/isolation-test-report.md)
- [Experiment Reproduction Guide](docs/experiments/reproduction.md)
