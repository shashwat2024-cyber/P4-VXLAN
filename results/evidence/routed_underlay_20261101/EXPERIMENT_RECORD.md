# Routed VXLAN Underlay Experiment

Date: 1 November 2026
Project: Performance Evaluation and Tenant Isolation of P4-Based VXLAN
Environment: WSL2, Mininet, BMv2 simple_switch, Linux router

## 1. Objective

Verify that VXLAN traffic between two P4 VTEPs can traverse a
routed Layer-3 underlay through an intermediate Linux router.

## 2. Topology and addressing

| Component | Interface | IP address |
|---|---|---|
| VTEP1 | vtep1-eth2 | 10.0.1.2/24 |
| Router | r1-eth0 | 10.0.1.1/24 |
| Router | r1-eth1 | 10.0.2.1/24 |
| VTEP2 | vtep2-eth2 | 10.0.2.2/24 |

VTEP1 and VTEP2 were run in separate network namespaces.
The router connected the two underlay subnets.

## 3. Routing verification

VTEP1 route lookup:
10.0.2.2 via 10.0.1.1 dev vtep1-eth2 src 10.0.1.2

VTEP2 route lookup:
10.0.1.2 via 10.0.2.1 dev vtep2-eth2 src 10.0.2.2

Router IPv4 forwarding:
net.ipv4.ip_forward = 1

Router connected routes:
10.0.1.0/24 dev r1-eth0 src 10.0.1.1
10.0.2.0/24 dev r1-eth1 src 10.0.2.1

Underlay connectivity:
- VTEP1 to router: 3/3 packets, 0% loss.
- VTEP2 to router: 3/3 packets, 0% loss.
- VTEP1 to VTEP2: 3/3 packets, 0% loss.

## 4. Tenant connectivity

Tenant A:
h1 -> 192.168.10.2
5/5 packets received, 0% loss.
One recorded average RTT: 4.281 ms.

Tenant B:
h3 -> 192.168.20.2
5/5 packets received, 0% loss.
One recorded average RTT: 3.411 ms.

Additional Tenant A verification runs also achieved 5/5 packets,
with 0% loss.

These are functional connectivity checks, not performance benchmarks.

## 5. Packet capture evidence

Ingress capture:
routed_ingress.pcap

Capture interface:
r1-eth0

Observed:
- 10 VXLAN packets captured.
- 10 packets received by filter.
- 0 packets dropped by kernel.

Egress capture:
routed_egress.pcap

Capture interface:
r1-eth1

Observed:
- 10 VXLAN packets captured.
- 10 packets received by filter.
- 0 packets dropped by kernel.

Both captures contain VNI 1001 traffic.

## 6. TTL verification

Forward direction, VTEP1 to VTEP2:
- Outer IP TTL at router ingress: 64.
- Outer IP TTL at router egress: 63.
- Inner IP TTL: 64.

Reverse direction, VTEP2 to VTEP1:
- Outer IP TTL at router ingress: 63.
- Outer IP TTL at router egress: 64.
- Inner IP TTL: 64.

The captures were collected during separate ping runs, so packets
were not matched individually. The observed TTL changes are
consistent with IPv4 forwarding across the router.

## 7. Evidence files

- routed_ingress.pcap
- routed_egress.pcap
- EXPERIMENT_RECORD.md

## 8. Conclusion

The experiment demonstrated functional VXLAN connectivity across
a routed Layer-3 underlay. Both tenant connectivity tests passed.
VXLAN packets were captured on the router's ingress and egress
interfaces, and the outer IP TTL observations were consistent
with router forwarding while the inner IP TTL remained unchanged.

This experiment verifies functional routed-underlay operation.
It does not establish Linux VXLAN device interoperability or
performance under a routed underlay; those require separate tests.
