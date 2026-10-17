# P4 VXLAN Multi-Tenancy Experiment Design

## Objective
Evaluate VXLAN network performance and tenant isolation using P4,
BMv2, and Mininet in a software-emulated environment.

## Logical topology
- Tenant A: Host h1 and Host h2
- Tenant B: Host h3 and Host h4
- Shared software-switch infrastructure
- P4 pipeline handles VXLAN-related packet processing
- Mininet provides the virtual hosts and links

## Configurations
A. Baseline: ordinary network forwarding without VXLAN.
B. VXLAN: tenant traffic carried through a shared underlay.
C. VNI separation: distinct VXLAN Network Identifiers for tenants.
D. Isolation enforcement: reject traffic that violates tenant policy.

## Metrics
- Throughput (Mbps)
- Round-trip latency (ms)
- Packet loss (%)
- VXLAN encapsulation overhead (bytes)
- Unauthorized cross-tenant packets delivered

## Experimental controls
- Keep host count and traffic parameters consistent where possible.
- Run repeated trials.
- Record software versions and test settings.
- Save raw results before calculating averages.
- Report actual measurements only; do not fabricate results.

## Limitations
Results describe the BMv2/Mininet software-emulation environment.
They do not directly establish hardware-switch or SmartNIC performance.
