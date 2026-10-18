# VXLAN Tenant-Isolation Experiment

## Test environment

- BMv2 `simple_switch`, P4C, and Mininet
- Tenant A: `192.168.10.0/24`, VNI 1001
- Tenant B: `192.168.20.0/24`, VNI 1002
- Underlay endpoints: `10.0.0.1` and `10.0.0.2`
- VXLAN UDP destination port: 4789

## Same-tenant connectivity

In the latest recorded run:

- h1 → h2: 3/3 replies, 0% packet loss; average RTT 8.146 ms.
- h3 → h4: 3/3 replies, 0% packet loss; average RTT 7.754 ms.

Earlier runs also succeeded, but these small individual tests are functional checks, not statistical performance benchmarks.

## Cross-tenant tests

Explicit host routes and static neighbour entries were added before testing reachability.

- h1 → `192.168.20.2`: 3 packets transmitted, 0 received; 100% packet loss.
- h3 → `192.168.10.2`: 3 packets transmitted, 0 received; 100% packet loss.

## Runtime table configuration

Inspection of both VTEPs showed tenant-specific decapsulation entries keyed by VXLAN VNI and inner IPv4 destination.

- VTEP1: VNI 1001 + `192.168.10.1` → port 1.
- VTEP1: VNI 1002 + `192.168.20.1` → port 2.
- VTEP2: VNI 1001 + `192.168.10.2` → port 1.
- VTEP2: VNI 1002 + `192.168.20.2` → port 2.

Both decapsulation tables had `MyIngress.drop_packet` as their default action. The P4 source also defines exact-match keys for VNI and inner destination and sets the default action to `drop_packet()`.

## Underlay packet captures

Captures on `vtep1-eth3` and `vtep2-eth3` observed UDP traffic from `10.0.0.1` to `10.0.0.2`, with destination port 4789 and a reported packet length of 114 bytes.

Tcpdump reported `unknown payload`. These captures therefore did not independently confirm the VXLAN VNI or inner destination address, nor did they directly show the P4 table's action for an individual packet.

## Interpretation and limitations

The successful same-tenant tests, failed cross-tenant tests, and observed table configuration are consistent with the intended tenant-isolation policy.

The results cover only the tested flows. They do not constitute exhaustive proof against all spoofing, malformed-packet, VNI-collision, or table-misconfiguration scenarios. Direct packet-level confirmation of the decapsulation decision remains a possible follow-up experiment.

The report records interactive observations. Save raw packet captures and complete command output in future runs if reproducible packet-level evidence is required.
