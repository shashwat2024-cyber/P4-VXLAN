# Response to instructor/reviewer comments

This response addresses the document “Team-12-CN-first Level Corrections”. The feedback correctly identifies that the implementation is a useful lab prototype but that the current evidence is not yet a publishable performance/security study.

| Comment | Response in this revision | Remaining work / honest status |
|---|---|---|
| Describe this as a lab exercise, not a finished research paper | The report now describes a two-tenant P4/BMv2/Mininet prototype and explicitly limits its claims. | Publication readiness is not claimed. |
| No VXLAN-free baseline; overhead not quantified | The report states that no validated comparable baseline is available and makes no overhead claim. | Implement a VXLAN-free path under the same conditions and measure both configurations. |
| Too few and too-short performance trials; no variance | The separate CSV preserves all six available iperf3 records and the report explains that they are heterogeneous. | Run at least 10 independent 30-second trials per condition, then calculate mean and a defined confidence interval. |
| Sweep MSS/payload sizes | MSS-1000 diagnostics and MTU-1450 runs are explicitly kept distinct. | Run a controlled MSS/payload sweep while holding other settings constant. |
| Isolation not tested against misuse | The report no longer treats drop-default behavior or failed pings as proof of isolation. | Generate spoofed-VNI, wrong-inner-destination and VNI-collision frames; verify at egress with captures/counters. |
| Scale beyond two tenants/two VTEPs | Included as future work. | Test at least 8 tenants and 3–4 VTEPs, and record table sizes and CPU/per-packet effects. |
| Explain checksum-offload/BMv2/WSL2 effects | The report notes that software-switch throughput depends on host/virtualization and that endpoint settings must be recorded; checksum handling is identified as an implementation item. | Record exact offload settings and verify/recompute checksums in P4 where necessary. |
| Remove manuscript-like headers and console screenshots | This report uses a concise lab-report structure and tables rather than claiming journal publication. | If a separate formatted paper is submitted, remove obsolete course/manuscript headers and replace console screenshots with reproducible result tables. |
| Improve related-work framing | The revised report avoids calling foundational P4 specifications' division of responsibility a research limitation. | Add and verify specific P4 VXLAN/GENEVE gateway, tunnelling tutorial and hardware-offload references if developing a publication manuscript. |

## Summary
The changes improve transparency and presentation and separate the data from the report. They do not fabricate missing measurements or claim that outstanding experiments have been completed. The project should be presented as a working implementation with preliminary observations until the baseline, repeated trials and adversarial isolation tests are actually run.
