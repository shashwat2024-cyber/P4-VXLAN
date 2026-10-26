# First-Level Review Response and Revised Experimental Protocol

This file is a technical response to the review supplied with the project. It separates work completed in the correction branch from work requiring a real BMv2/Mininet execution. No new measurements are claimed here.

## Response to the review

### 1. Baseline, repeats, and uncertainty
**Review concern:** The original evidence consists of a few short trials and has no VXLAN-free baseline or quantified uncertainty.

**Response:** The correction branch adds a repeated-run raw CSV harness and an analysis utility. The harness logs individual Tenant A and Tenant B observations, preserves failed trials, and does not overwrite the existing historical CSVs. It is deliberately labelled VXLAN-only; a valid no-VXLAN baseline still needs its own explicitly implemented topology/configuration. It must be run under comparable MTU, payload, offered load and duration conditions. Run at least 10 independent 30-second trials per condition and MSS, then report mean, sample standard deviation and 95% confidence interval from the independent run-level observations.

### 2. Isolation evidence
**Review concern:** Two failed cross-tenant pings and a drop-by-default table do not prove security against crafted packets.

**Response:** The revised protocol requires positive controls plus crafted VNI and inner-destination mismatch tests, unknown VNIs and unknown destinations. The evidence should include packet captures at ingress, underlay and tenant-side egress, and counters only after their semantics have been verified on the actual target. A failed ping alone will not be described as proof of where a packet was dropped. These crafted tests still need to be executed in the isolated Mininet lab.

### 3. Checksum handling
**Review concern:** Successful TCP required endpoint settings, but the packet-processing mechanism is not explained.

**Response:** The current source's compute-checksum control calls `update_checksum` for the outer IPv4 header. Any diagnosis must examine all headers that are created, modified, or reconstructed and verify actual packets. The endpoint workaround should not be treated as proof that the pipeline is correct. After a source correction, P4C compilation and ICMP/TCP positive controls must pass before new throughput measurements are accepted.

### 4. Manuscript and related work
**Review concern:** The manuscript contains course framing and console screenshots, and the related-work table mislabels features of foundational P4 work as limitations.

**Response:** The README and roadmap now frame the work as a software testbed with preliminary measurements, not a publishable measurement study. The final paper should remove course running headers/date banners, replace console screenshots with test and table summaries, retain screenshots/captures as supporting artefacts, and cite only directly relevant P4 tunnel/VXLAN/GENEVE and measurement work that has actually been verified.

## Revised test matrix

| ID | Packet condition | Expected outcome | Evidence to save |
|---|---|---|---|
| P1 | Tenant A valid VNI and destination | Delivered to h2 | ping/iperf log, egress capture |
| P2 | Tenant B valid VNI and destination | Delivered to h4 | ping/iperf log, egress capture |
| N1 | Tenant A frame with Tenant B VNI | Not delivered to Tenant B | crafted packet spec, underlay/egress PCAP |
| N2 | Tenant B frame with Tenant A VNI | Not delivered to Tenant A | crafted packet spec, underlay/egress PCAP |
| N3 | Valid VNI with other tenant's inner destination | Not delivered cross-tenant | input/output capture, table/counter state |
| N4 | Unknown VNI | Rejected | packet bytes and result |
| N5 | Known VNI with unknown inner destination | Rejected | packet bytes and result |
| N6 | Truncated/malformed supported header case | Safely rejected if identifiable by parser | compiler/runtime evidence, PCAP |

Scapy tests must run only within this project's isolated Mininet environment. The expected outcome is a policy target, not an observed result; mark actual outcomes only after each test runs.

## Revised performance matrix

| Dimension | Baseline | VXLAN condition |
|---|---|---|
| Host endpoints and application payload | fixed | same |
| MTU and MSS | recorded and aligned | recorded and aligned |
| Trial duration | 30 s | 30 s |
| Independent repeats | at least 10 | at least 10 |
| MSS sweep | 500–1400 byte values documented individually | same values |
| Raw records | one row per run, including failures | one row per run, including failures |
| Analysis | run-level mean, SD and 95% CI | same |
| Environment | exact versions and CPU/WSL2 context | same |

Do not combine runs whose MSS, duration, offload settings, payload or configuration differ into one average.

## Definition of done

- [ ] P4 source compiles cleanly with the recorded target toolchain.
- [ ] Same-tenant positive controls pass after changes.
- [ ] Checksum behaviour is validated from packet data.
- [ ] A no-VXLAN reference condition is genuinely implemented and documented.
- [ ] Repeated trials are completed and raw output committed.
- [ ] Crafted isolation cases are run, with PCAP and runtime evidence saved.
- [ ] Summary tables/graphs are generated from the raw CSV with scripts.
- [ ] The paper describes the observed scope honestly and removes course/template artefacts.
