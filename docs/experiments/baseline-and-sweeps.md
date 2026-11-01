# Experiment Status: Baseline, Repeated Measurements, Isolation and Scale

This document records the status and scope of the implemented experiments. It distinguishes performance measurements from functional security/correctness checks. The research manuscript is maintained separately.

## 1. Plain-L2 baseline and repeated TCP measurements

A plain-L2 P4 forwarding configuration and matching Mininet topology are provided for forwarding-performance comparison with VXLAN. This is **not** a tenant-isolation baseline: it intentionally does not provide VXLAN VNI segmentation.

The final consolidated TCP analysis is in `results/final_analysis_20261101/FINAL_ANALYSIS_REPORT.md`. For the final MSS-500 and MSS-1400 comparison, each tenant/configuration/MSS group contains 20 successful trials. The corrected VXLAN MSS-1400 primary dataset replaces Tenant B trials 17 and 19, which failed in the original run, with successful recovery records. Additional recovery and diagnostic records remain separate and are excluded from the primary sample.

The reported throughput means are:

| Tenant | MSS | Plain-L2 (Mbps) | VXLAN (Mbps) |
|---|---:|---:|---:|
| A | 500 | 33.698 | 13.379 |
| A | 1400 | 100.776 | 39.514 |
| B | 500 | 34.560 | 13.907 |
| B | 1400 | 102.812 | 38.111 |

The TCP `latency_ms` measurement is a 10-ping mean RTT collected after the TCP transfer. It must not be described as RTT under TCP load.

The original six-MSS campaign (500, 700, 900, 1100, 1300 and 1400 bytes) is a separate historical campaign. Do not merge its observations with the final two-MSS dataset unless the analysis explicitly preserves each condition and dataset identity.

## 2. CPU measurements

A separate CPU campaign is recorded under `results/cpu_utilisation_20261101/`. It contains 10 trials per configuration for Tenant A, using TCP, MSS 1000, 30-second transfers, MTU 1450 and matched traffic/offload settings.

| Configuration | Mean CPU (% of one core) | Mean peak CPU (% of one core) | Receiver throughput (Mbps) |
|---|---:|---:|---:|
| Plain-L2 baseline | 413.82 | 435.02 | 72.74 |
| VXLAN | 330.25 | 340.20 | 29.01 |

CPU percentages above 100% are valid because the reported unit is percentage of one CPU core. CPU-per-throughput is a descriptive ratio, not a causal measure of efficiency. This CPU campaign covers Tenant A only; do not generalise it to Tenant B.

## 3. UDP payload and offered-load campaigns

UDP payload and offered-load/scalability analyses are recorded under `results/udp_rss_analysis/`. These campaigns used concurrent ping measurements and therefore report RTT while UDP traffic was running. This is distinct from the post-transfer TCP RTT measurement.

The payload summary and Welch/Holm test outputs are included in that directory. Use the adjusted p-values and sample counts in the recorded analysis tables. In the 256-byte payload condition, the recorded mean RTT difference between tenants was statistically significant after Holm adjustment, while the loss-rate difference was not. At 1200 bytes, the observed Tenant A loss-rate difference was not statistically significant after adjustment. Do not overstate these results or infer a cause for isolated loss observations.

## 4. Isolation and spoofing checks

The P4 data path was corrected so VXLAN decapsulation is accepted only on underlay-facing ingress, while encapsulation is performed on tenant-facing ingress. Tenant-originated forged VXLAN injection was tested: a forged packet attempting to use Tenant B's VNI from Tenant A was blocked, while a legitimate positive-control packet was delivered.

The scalable security implementation and recorded correctness results are documented in `results/scalability/SCALABILITY_SECURITY_REPORT_20261101.md`. The six final configurations passed their recorded legitimate-connectivity, cross-tenant blocking and spoofed-source blocking probes:

| Tenants | VTEPs | Legitimate | Cross-tenant blocked | Spoofed sources blocked |
|---:|---:|---:|---:|---:|
| 2 | 2 | 4/4 | 4/4 | 4/4 |
| 4 | 2 | 8/8 | 24/24 | 8/8 |
| 6 | 2 | 12/12 | 60/60 | 12/12 |
| 8 | 2 | 16/16 | 112/112 | 16/16 |
| 2 | 3 | 12/12 | 12/12 | 12/12 |
| 2 | 4 | 24/24 | 24/24 | 24/24 |

These are functional correctness/security probe counts. They do not establish throughput or latency scalability at each tenant/VTEP count.

Additional packet captures and routed-underlay/Linux VXLAN interoperability evidence are retained under `results/evidence/`. The isolation report describes what each evidence set demonstrates and what it does not demonstrate.

## 5. Checksum and encapsulation notes

The implementation recalculates the emitted IPv4 header checksum. On encapsulation, the outer IPv4 total length is the inner IPv4 length plus 50 bytes. The recorded packet-capture check included an outer IPv4 length of 134 bytes, an inner IPv4 length of 84 bytes and a VXLAN UDP length of 114 bytes. The outer UDP checksum is set to zero, which is permitted for IPv4 UDP. P4 input checksum verification is not implemented in the current verify-checksum control.

The 50-byte encapsulation overhead comprises outer Ethernet (14), outer IPv4 (20), UDP (8) and VXLAN (8) headers. Performance differences cannot be attributed to header overhead alone: per-packet processing and the host/WSL2 virtual network also affect the measurements.

## 6. Reporting rules and limitations

- Keep TCP MSS and UDP application-payload size as separate concepts.
- Keep TCP post-transfer RTT separate from UDP under-load RTT.
- Preserve failed original trial rows and their failure reasons. Recovery observations used in the corrected primary dataset must remain traceable to the recovery files.
- Do not pool different tenant, configuration, MSS, payload, duration, MTU, transport or offload conditions.
- Report sample counts, units, uncertainty and adjusted p-values where available.
- The plain-L2 baseline is not an isolation configuration.
- BMv2 results characterise the tested software environment and are not hardware-switch performance results.
- Tenant/VTEP scale correctness tests do not constitute scale performance tests.
- The recorded scenarios are not exhaustive proof against every possible attack or misconfiguration.

## 7. Manuscript and final PDF

Terminology and framing changes intended for the research manuscript—including precise ingress/egress wording, IP-forwarding description, ARP/BUM limitations, and positioning BMv2 as a functional reference rather than a hardware performance target—are deferred to the final manuscript/PDF revision. Do not treat this experiment-status document as a replacement for those manuscript edits.
