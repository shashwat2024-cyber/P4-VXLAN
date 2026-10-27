# Consolidated WSL2 Experiment Addendum — 27 October 2026

This report consolidates the completed WSL2/BMv2/Mininet work described by the project operator. It supplements the existing methodology and historical results documents; it does not overwrite earlier observations or claim that local artifacts have been uploaded unless they are present in this repository.

## Status at a glance

| Work package | Status | Evidence / qualification |
|---|---|---|
| P4 VXLAN data plane and plain-L2 forwarding baseline | Implemented in repository | `src/p4/vxlan.p4`, `src/p4/baseline.p4` |
| Repeated benchmark tooling and statistical analyzer | Implemented | See `scripts/repeated_benchmark.py`, `scripts/analyze_repeated_trials.py` |
| Main 240-trial comparison | Completed in the user's WSL2 environment | Local raw dataset is reported as `results/combined_240_trials_20261027.csv`; upload the file from WSL2 to publish the raw observations in GitHub |
| Six TCP MSS conditions | Completed as part of the 240-trial campaign | MSS = 500, 700, 900, 1100, 1300, 1400 bytes; preserve each condition as its own group |
| Statistical comparison | Completed | User reports Welch tests significant and 95% CIs for baseline–VXLAN throughput difference excluded zero for the tested MSS conditions |
| Tenant scalability | Completed | 2, 4, 6 and 8 tenants; observed connectivity checks 4/4, 8/8, 12/12 and 16/16 |
| VTEP scalability | Completed | 2, 3 and 4 VTEPs with two tenants; observed connectivity checks 4/4, 12/12 and 24/24 |
| Crafted-packet isolation verification | Completed for the stated test cases, with explicit evidence limitations | See isolation section below; endpoint non-delivery alone does not identify the exact drop point |
| CPU utilisation comparison | Completed as a supplementary three-trial-per-configuration campaign | Sample-aligned CPU values are estimates; brief run, approximate trial window, two BMv2 processes |
| Reproduction and analysis code | Present | Environment-specific verification remains necessary for other systems |

## Main 240-trial TCP experiment

The completed campaign used two configurations: `P4_VXLAN` and `P4_L2_BASELINE`, with 120 trials per configuration (240 total), six MSS settings (500, 700, 900, 1100, 1300 and 1400 bytes), 30-second runs, MTU 1450 bytes and TCP transmit offload disabled (`tx_off`). The recorded result dataset on the user's machine is:

- `results/combined_240_trials_20261027.csv`

The reported analysis found lower VXLAN receiver throughput at each tested MSS, statistically significant Welch tests, and baseline-minus-VXLAN 95% confidence intervals that excluded zero. The reported estimated throughput reduction was approximately 59–63%, depending on MSS.

**Data publication note:** the exact 240-trial CSV and generated statistical outputs are not present among the files currently committed to this branch at the time this addendum was authored. The path above identifies the operator's local file, not an already-published GitHub asset. Add the exact CSV and analyzer outputs from the WSL2 worktree before citing them as repository artifacts. Do not reconstruct trial rows from summary values or invent confidence intervals, p-values, or graph data.

## Scalability experiments

### Tenant count

| Tenant count | Connectivity checks passed |
|---:|---:|
| 2 | 4/4 |
| 4 | 8/8 |
| 6 | 12/12 |
| 8 | 16/16 |

CSV artifacts reported on the operator's WSL2 system include:
- `results/scalability/tenants_scalability_20261027_133423.csv`
- `results/scalability/tenants_scalability_20261027_133450.csv`
- `results/scalability/tenants_scalability_20261027_133533.csv`
- `results/scalability/tenants_scalability_20261027_133702.csv`
- `results/scalability/tenants_scalability_20261027_134148.csv`
- `results/scalability/tenants_scalability_20261027_134240.csv`

### VTEP count

Two tenants were used while scaling the VTEP count.

| VTEP count | Connectivity checks passed |
|---:|---:|
| 2 | 4/4 |
| 3 | 12/12 |
| 4 | 24/24 |

Reported local CSV: `results/scalability/vteps_scalability_20261027_134316.csv`.

### Scalability graphs

The operator reports these generated local figures:
- `results/scalability/tenant_scalability_test_time.png`
- `results/scalability/vtep_scalability_test_time.png`
- `results/scalability/scalability_connectivity.png`

The image files need to be copied from the WSL2 worktree into this repository to be directly viewable in GitHub. Do not recreate these plots from summary text alone; regenerate them from the original CSVs if the originals are unavailable.

## Crafted VXLAN isolation experiment

The implemented test set used VXLAN VNI and inner-destination cases:
- valid: VNI 1001, inner destination 192.168.10.2;
- wrong destination: VNI 1001, inner destination 192.168.20.2;
- unknown VNI: VNI 1003, inner destination 192.168.10.2.

The destination VTEP's runtime decapsulation table was inspected and showed tenant-specific entries keyed by VNI and inner IPv4 destination, together with a default `MyIngress.drop_packet` action. Underlay captures observed the injected VXLAN packets at the VTEPs. A fresh host-capture directory was recorded as `results/scalability/isolation_verification_final_20261027_153206/`; evidence was copied to `results/evidence/vxlan_isolation_20261027/`, including `h2.pcap`, `h4.pcap`, capture logs, the crafted-packet test script, and `isolation_verification_report.txt`.

Observed host evidence: the valid UDP packet appeared at h2, followed by ICMP port-unreachable because no application was listening on UDP port 9999. The h4 capture was empty during the wrong-destination test. The test injected crafted VXLAN frames from the vtep1 underlay interface and observed them at vtep2, thereby exercising destination-VTEP decapsulation behaviour. It did not amount to injection directly into the VTEP1 P4 pipeline.

Interpretation is deliberately bounded: the combination of the live table's default drop action and non-delivery at h4 is consistent with isolation for these specific cases. The host capture alone does not independently prove the exact internal point/action at which every frame was discarded. No exhaustive claim is made for every protocol, packet, table state or forwarding path.

Evidence checksum for the recorded test script:
`561e01df5a4286a4a2289597c456b3c2fe27f69140aca1fd82ff58715acc89db`.

## Supplementary CPU utilisation comparison

The CPU campaign was captured separately from the main 240-trial campaign. It used Tenant A, TCP MSS 1000 bytes, MTU 1450 bytes, `tx_off`, one warm-up and three measured 30-second trials for each configuration. Samples were gathered at approximately one-second intervals and then aligned to an approximate traffic window ending before each recorded trial timestamp.

| Metric | P4 VXLAN | Plain L2 baseline |
|---|---:|---:|
| CPU samples recorded | 332 | 324 |
| Sampled BMv2 switch processes | 2 | 2 |
| Mean receiver throughput in these three trials | 28.14 Mbps | 71.81 Mbps |
| Mean estimated aggregate switch CPU | 319.5% of one core | 403.4% of one core |
| Packet loss in measured trials | 0% | 0% |

VXLAN throughput mean is calculated from 28.9251, 27.3866 and 28.1117 Mbps. Baseline throughput mean is calculated from 69.7839, 68.2220 and 77.4383 Mbps. The supplementary CPU values are sums of per-process CPU percentages measured relative to one core; they may exceed 100% because there are two switch processes and CPU usage can span cores.

These three-run measurements are exploratory. They do not establish that VXLAN is more CPU-efficient: the VXLAN throughput was substantially lower, measurement windows are approximate, and the sample size is small. The separate trial and sample artifacts recorded in the operator's WSL2 worktree are:
- `results/cpu_utilisation_20261027/final_comparison/vxlan_cpu_aligned_trials.csv`
- `results/cpu_utilisation_20261027/final_comparison/baseline_cpu_aligned_trials.csv`
- `results/cpu_utilisation_20261027/final_comparison/vxlan_cpu_samples.csv`
- `results/cpu_utilisation_20261027/final_comparison/baseline_cpu_samples.csv`

As with the 240-trial dataset, these local paths are not GitHub links until those files are copied into this repository.

## Relevant implementation details and corrections documented

- VXLAN VNI assignments: Tenant A uses VNI 1001; Tenant B uses VNI 1002.
- Host subnets: Tenant A uses 192.168.10.0/24, Tenant B uses 192.168.20.0/24.
- Decapsulation exact-match key uses VNI and inner IPv4 destination, with a default drop action.
- Header overhead arithmetic for this implementation is 50 bytes: outer Ethernet 14 + outer IPv4 20 + UDP 8 + VXLAN 8. This is protocol-header accounting, not an empirical throughput prediction.
- The P4 checksum discussion should state what is implemented: recomputation for the emitted IPv4 header; outer UDP checksum set to zero for IPv4 UDP; and no claim that the currently empty P4 verify-checksum control validates incoming checksums.
- Endpoint TCP TX offload was disabled consistently in the recorded performance campaigns and must be listed as an experimental setting, not represented as a replacement for P4 checksum handling.
- The no-VXLAN baseline is a performance-forwarding comparison. It is not a tenant-isolation control because it does not implement the same VXLAN tenant boundary.
- Keep raw per-trial rows, failed runs and their failure reasons. Do not mix 3-second, 5-second, 10-second and 30-second runs; different MSS, MTU, transport, tenant, and offload conditions must remain separate.
- Explain the BMv2/Mininet/WSL2 environment as a software emulation. Do not imply physical-switch line-rate results or hardware offload performance.
- Manuscript cleanup noted in the review: remove course-only running headers, replace generic fixed “Prepared October 2026” text with a real revision date or omit it, prefer tables/plots over terminal screenshots, and make related work specifically discuss P4 tunnel/overlay processing rather than attributing limitations to foundational P4 language work without evidence.

## Figures and data inventory

Already present in the repository branch:
- `results/graphs/iperf3_receiver_throughput.png` (historical diagnostic plot; do not label it as the 240-trial campaign plot).

Reported on the operator's WSL2 machine but not confirmed present in this branch:
- Main campaign: `results/combined_240_trials_20261027.csv` and analysis outputs.
- Scalability CSVs and three PNGs listed above.
- Isolation capture PCAPs/logs/report.
- CPU sample CSVs and aligned-trial CSVs.

Do not create placeholder files with invented data to make these paths appear populated. Upload the real artifacts from the WSL2 worktree to make the repository fully self-contained.

## Test and reproducibility status

The operator reports that the repeated analysis/unit tests passed previously (10/10 in the associated validation suite); this addendum does not rerun or re-certify those tests. Reproduction commands, tool checks and statistical analysis workflow are documented under `docs/experiments/reproduction.md` and `scripts/analyze_repeated_trials.py`. All numerical results must be traceable to actual raw rows in their corresponding CSV files.

## Final project status

The core implementation, 240-trial performance campaign, six-MSS comparison, statistical analysis, tenant/VTEP scaling tests, crafted-packet check, and supplementary CPU campaign have been completed by the operator in WSL2 according to the supplied run summaries. The remaining repository-publishing task is to copy the original local datasets, graph images, packet captures and logs into version control, then update the paper's final results section to cite those actual files. This report does not claim those uncommitted artifacts have already been uploaded.
