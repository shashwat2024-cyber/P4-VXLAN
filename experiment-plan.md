# P4-Based VXLAN Multi-Tenancy Evaluation

## Research objective
Evaluate network performance and tenant isolation using P4,
BMv2, and Mininet in a reproducible software testbed.

## Proposed configurations
A. Baseline network without VXLAN.
B. VXLAN encapsulation with a shared underlay.
C. VXLAN with separate tenant VNIs.
D. VXLAN with explicit tenant-isolation enforcement.

## Metrics
- Throughput (Mbps)
- Round-trip latency (ms)
- Packet loss (%)
- Encapsulation overhead (bytes)
- Unauthorized cross-tenant packet delivery

## Experimental controls
- Keep host count and traffic patterns consistent where possible.
- Repeat each measurement multiple times.
- Record software versions and topology.
- Report measured results; do not fabricate values.
- Document limitations of the BMv2/Mininet environment.

## Current status
- [x] Ubuntu 24.04 environment prepared
- [x] Project directory structure created
- [ ] P4 toolchain installation verified
- [ ] Topology implemented
- [ ] Configurations implemented
- [ ] Isolation tests executed
- [ ] Performance measurements collected
- [ ] Research paper completed
