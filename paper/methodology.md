# Research Methodology

## 1. Research Objective
Evaluate VXLAN-based multi-tenancy and tenant-isolation enforcement
in a P4-programmable software-emulated network.

## 2. Experimental Environment
- Operating system: Ubuntu 24.04 under WSL2
- Data plane: P4-programmable BMv2 software switch
- Network emulation: Mininet
- Compiler: p4c
- Hardware architecture: ARM64
- Physical hardware-switch performance is outside the scope.

Record exact installed software versions after setup completes.

## 3. Network Design
Create two tenants, each with two hosts:
- Tenant A: h1 and h2; planned VNI 1001
- Tenant B: h3 and h4; planned VNI 1002

Use a shared underlay and implement the required VXLAN packet-processing
behavior in the P4 pipeline.

## 4. Experimental Configurations
A. Baseline forwarding without VXLAN.
B. VXLAN encapsulation and decapsulation.
C. Separate VNIs for the two tenants.
D. Explicit tenant-isolation policy enforcement.

Document which features are implemented and tested in each configuration.

## 5. Metrics
- Throughput in Mbps
- Round-trip latency in milliseconds
- Packet loss percentage
- Encapsulation overhead in bytes
- Unauthorized cross-tenant packet delivery

## 6. Procedure
1. Verify the topology and connectivity.
2. Test allowed communication within each tenant.
3. Attempt communication across tenants.
4. Measure throughput, latency, and packet loss.
5. Repeat trials with consistent traffic parameters.
6. Save raw measurements and calculate summary statistics.

## 7. Data Integrity
Use only measured results. Record commands, packet sizes, traffic rates,
trial duration, software versions, and failures. Do not invent or
substitute expected values for experimental observations.

## 8. Limitations
BMv2 and Mininet results characterize a software-emulated environment.
They do not establish physical-switch line-rate performance or
hardware VXLAN offload capability.
