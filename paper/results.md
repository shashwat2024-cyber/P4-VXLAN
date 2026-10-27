# Experimental Results

## 1. Experimental setup

The experiments were conducted using a P4_16 VXLAN data plane with BMv2
simple_switch and Mininet. Two tenant networks were configured:
Tenant A (192.168.10.0/24) and Tenant B (192.168.20.0/24).
The throughput diagnostic trials used iperf3 with a TCP MSS of 1000 bytes.
TCP transmit checksum offloading was disabled on the endpoint hosts for
the successful diagnostic runs.

## 2. Connectivity results

Tenant A connectivity was verified by pinging h2 (192.168.10.2) from h1
(192.168.10.1). Three packets were transmitted and three received, with
0% packet loss and an average RTT of 4.142 ms.

Tenant B connectivity was verified by pinging h4 (192.168.20.2) from h3
(192.168.20.1). Three packets were transmitted and three received, with
0% packet loss and an average RTT of 3.388 ms.

## 3. Throughput results

Two successful 3-second diagnostic trials were completed for Tenant A.
The receiver throughput values were 26.9 Mbps and 26.2 Mbps, with zero
TCP retransmissions in both runs. Their arithmetic mean was 26.55 Mbps.

One successful 3-second diagnostic trial was completed for Tenant B.
Receiver throughput was 26.5 Mbps, with zero TCP retransmissions.

These short runs establish that TCP data transfer succeeded under the
tested settings. They are preliminary diagnostic measurements, not
long-duration performance benchmarks. The sample counts are too small
to establish a statistically meaningful performance difference between
tenants.

Earlier Tenant A trials used different conditions and recorded receiver
throughput values of 36.8 Mbps (5 seconds), 35.8 Mbps (10 seconds), and
34.5 Mbps (10 seconds). The two 10-second trials recorded 137 and 191
TCP retransmissions, respectively. These results are kept separate from
the later MSS-1000 diagnostic runs because the configurations and
outcomes differ.

## 4. Limitations

The current results demonstrate successful same-tenant connectivity and
short-duration throughput through the testbed. They do not, by themselves,
prove tenant isolation. Cross-tenant reachability must be tested with
valid routing and forwarding conditions before any isolation claim is made.

The short throughput trials have not been repeated enough to provide
robust estimates of average performance or variability. A final evaluation
should use longer runs, multiple repetitions, consistent settings, and
a documented baseline for comparison.

## 5. Additional connectivity and isolation tests (18 October 2026)

A subsequent test run verified same-tenant connectivity using the compiled
P4 program and runtime table configuration.

Tenant A: h1 (192.168.10.1) pinged h2 (192.168.10.2). Three packets
were transmitted and three received, with 0% packet loss. The measured
average RTT was 8.146 ms (minimum 4.799 ms, maximum 10.239 ms).

Tenant B: h3 (192.168.20.1) pinged h4 (192.168.20.2). Three packets
were transmitted and three received, with 0% packet loss. The measured
average RTT was 7.754 ms (minimum 3.796 ms, maximum 10.183 ms).

Cross-tenant reachability was then tested after adding explicit host
routes and static neighbour entries. The h1-to-192.168.20.2 test and
the h3-to-192.168.10.2 test each transmitted three packets and received
none (100% packet loss).

Runtime table inspection on both VTEPs showed tenant-specific
decapsulation entries keyed by VXLAN VNI and inner IPv4 destination.
Both decapsulation tables used MyIngress.drop_packet as the default
action. The P4 source defines the same exact-match keys and default
drop action.

Packet captures on vtep1-eth3 and vtep2-eth3 observed UDP traffic
from 10.0.0.1 to 10.0.0.2 with destination port 4789. Tcpdump reported
an unknown payload, so these captures did not independently establish
the inner destination address or directly demonstrate the P4 table's
drop decision for an individual cross-tenant packet.

These observations are consistent with the intended tenant-isolation
policy: the tested same-tenant flows succeeded, while the tested
cross-tenant flows failed. They do not constitute exhaustive proof of
isolation or a direct observation of the drop action for the captured
cross-tenant packet. Further packet-level verification would strengthen
this conclusion.

These RTT measurements are a separate test run and should not be
combined with the earlier connectivity measurements as if they were
repeated measurements under a controlled statistical protocol.


## 6. Repeated campaign status (27 October 2026)

A repeated-campaign runner and raw-trial analyzer have been added on the
`mam-corrections-repeatable-benchmarks` branch. The runner is configured
for six separate TCP MSS conditions (500, 700, 900, 1100, 1300 and 1400
bytes), with ten recorded 30-second runs per tenant/condition after one
excluded warm-up. It writes new rows to `results/repeated_trials.csv`
only when run inside the configured Ubuntu/WSL2 environment.

**These repeated campaign trials have not been run as part of this code
change.** The earlier values above remain historical observations. The
new script and analyzer do not add any result numbers to this document.
After execution, summarize the new raw rows with
`python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv`
and insert the measured summaries and confidence intervals here, keeping
the baseline and each MSS/payload condition separate.

## 7. Consolidated final evaluation status (27 October 2026)

The project operator subsequently completed the main repeated campaign and scalability work in the configured WSL2 environment. The detailed consolidated report, including reported conditions, summary values, cautions, and exact paths for artifacts that still need uploading, is maintained at [Final WSL2 Results and Evidence Inventory](../docs/experiments/final-results-addendum-2026-10-27.md).

That report records the main campaign as 240 trials: 120 each for P4 VXLAN and plain-L2 baseline across TCP MSS 500, 700, 900, 1100, 1300 and 1400 bytes, with 30-second measured trials, MTU 1450 and TX offload disabled. The operator reports statistically significant Welch comparisons and 95% confidence intervals for baseline-minus-VXLAN throughput differences that excluded zero at all tested MSS settings. Exact p-values, confidence limits and per-MSS means should be cited only from the original raw dataset and analyzer output; this document does not reconstruct them from rounded summary statements.

Tenant-scale connectivity checks passed at 2, 4, 6 and 8 tenants (4/4, 8/8, 12/12 and 16/16); VTEP-scale checks with two tenants passed at 2, 3 and 4 VTEPs (4/4, 12/12 and 24/24). The crafted-packet test and its evidence limitations are also documented in the addendum.

A separate exploratory CPU campaign used three measured 30-second Tenant A trials per configuration at MSS 1000, MTU 1450 and `tx_off`. Mean receiver throughput was 28.14 Mbps for VXLAN and 71.81 Mbps for plain L2. Mean estimated aggregate CPU was 319.5% versus 403.4% of one core, summing two BMv2 process measurements with approximate trial-window alignment. This small supplementary campaign does not prove superior VXLAN CPU efficiency and must remain separate from the 240-trial performance study.

The publication inventory in the addendum distinguishes artifacts already committed in the repository from raw CSVs, generated scalability figures, packet captures, logs and CPU samples reported on the operator's WSL2 machine. No uncommitted local file is represented as an existing GitHub artifact.
