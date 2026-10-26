# Correction Roadmap: P4 VXLAN Evaluation

This document translates the first-level review into an actionable plan. It deliberately distinguishes changes to the source repository from experiments that must actually run on the target WSL2/Mininet setup.

## Review decision in plain language

The current code is a useful course/lab artifact, but the existing measurements do not support a full research-performance claim. The review identifies four substantive gaps: no controlled VXLAN-free baseline and too few short runs; isolation has only been tested with basic ICMP probes; the checksum workaround is not explained at the packet-processing layer; and the paper needs a narrower, more accurate related-work and presentation treatment.

## Priority 0 — Correctness and reproducibility

- [ ] Compile the P4 program with the installed P4C and save the complete compiler output.
- [ ] Confirm IPv4 checksum computation for every IPv4 header whose fields are created or modified.
- [ ] Inspect whether the P4 pipeline handles the supported inner protocols consistently; explicitly document unsupported or unparsed traffic.
- [ ] Run positive controls before all negative isolation tests.
- [ ] Record actual VNI, inner destination, ingress/egress port, and packet counters wherever the available BMv2 interface allows it.
- [ ] Preserve every raw run and configuration; do not overwrite historical measurements.

## Priority 1 — Controlled performance evaluation

### Configurations

A. **Direct / no-VXLAN reference:** forward the same tenant payload between equivalent endpoints without adding VXLAN headers. Keep host count, payload, MTU, offered load, and duration aligned with the VXLAN condition. Clearly document whether this baseline uses Linux bridge/OVS or a P4-only direct-forwarding mode; do not compare different forwarding implementations without saying so.

B. **VXLAN encapsulation:** run the same traffic through the P4 VXLAN overlay with VNI-specific forwarding enabled.

### Minimum protocol suggested by the review

- At least 10 independent runs per condition, with each throughput run lasting 30 seconds.
- Sweep TCP MSS values in the requested 500–1400 byte range, while respecting the effective MTU and recording the exact value used.
- Record receiver throughput, sender throughput, retransmissions, RTT, packet loss, CPU utilisation if available, and run duration.
- Record tool versions, host/VM conditions, checksum configuration, and any failed/invalid runs.
- Report mean and a 95% confidence interval for each condition, alongside the raw observations. Explain the interval method and do not treat packets within a single run as independent trials.
- Repeat a run only under a documented rule, preserving failed runs and their failure reason.

No baseline numbers, confidence intervals, or performance claims are supplied in advance; those must come from actual experiment output.

## Priority 2 — Adversarial isolation checks

At minimum, test each condition in both directions where applicable:

1. Valid VNI + valid inner destination (positive control).
2. Tenant A traffic carrying Tenant B's VNI.
3. Tenant B traffic carrying Tenant A's VNI.
4. Correct VNI + destination belonging to the other tenant.
5. Unknown VNI.
6. Unknown inner destination for a known VNI.
7. Non-IPv4 or malformed/truncated frames, with safe rejection expected where the parser can identify the condition.

Use Scapy to construct and send test frames only in the isolated Mininet lab. Capture packets at ingress, underlay and tenant-facing egress; save PCAPs and a CSV test matrix. Report exactly where packet observation confirms delivery or non-delivery. A failed ping alone cannot locate the drop.

Add counters for accepted and rejected decapsulation attempts if supported by the P4 architecture/compiler; validate their semantics on BMv2 before relying on them. Avoid claiming that counters exist until they have been implemented and queried successfully.

## Priority 3 — Explain checksum handling and limitations

The current P4 source uses `update_checksum` for the outer IPv4 header. Review the complete encapsulation/decapsulation and header-validity behaviour before changing it. The checksum issue must be diagnosed with packet captures and checksum validation rather than assuming that endpoint checksum offload is the only cause. Any source change must be compiled and checked against same-tenant TCP/ICMP tests before merging.

## Priority 4 — Paper and artefact presentation

- Remove course-manuscript running headers and the provisional preparation-date banner from the research-facing version.
- Replace terminal screenshots with concise runtime-table and test-matrix tables; retain raw captures/logs in the repository as supplementary evidence.
- Present the current work as a reproducible testbed/measurement artifact unless the stronger baseline, repeated-run and adversarial tests above have been completed.
- Update related work with directly relevant P4 tunnelling/VXLAN/GENEVE gateway work and cite sources that have actually been checked.
- Make authorship/affiliation and contribution statements accurate and agreed by all listed authors.
- Keep the old results traceable and label any new results by commit, test configuration and date.

## Completion gate

The project is ready for a revised, stronger evaluation only after: (1) P4 compiles, (2) functional positive controls pass, (3) baseline and overlay results have the required repeated trials, (4) crafted isolation checks and packet-level evidence are saved, (5) analysis is generated directly from raw observations, and (6) the manuscript describes only what the evidence establishes.

## Existing data that must remain unchanged

The repository's presently recorded results — including the 3-packet connectivity runs and three short MSS-1000 throughput runs — are historical observations. Keep them separate from any future repeated-run dataset; do not relabel or inflate their sample counts.
