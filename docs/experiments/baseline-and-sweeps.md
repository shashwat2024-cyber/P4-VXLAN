# First-level corrections: baseline, repetitions, checksum handling and isolation

This plan follows the correction sheet supplied for Team 12. It distinguishes repository changes from live network experiments: no measurement should be described as completed until the actual BMv2/Mininet environment produces a raw result file.

## Status of this branch

- **Added:** per-tenant raw trial logging for the P4 VXLAN path in scripts/benchmark.py, configurable trial count/duration/MSS, warm-up exclusion, per-condition summary statistics, a campaign orchestrator for the six TCP MSS values, tool-version recording, raw schema and experiment guidance.
- **Not run in this environment:** live P4 compilation, Mininet/BMv2 traffic generation, repeated throughput trials, baseline trials, Scapy packet injection and multi-VTEP scaling. This execution environment does not have p4c, simple_switch, Mininet or iperf3 installed and cannot run your WSL2 namespaces.
- **Later local work recorded on 27 October 2026:** the operator's WSL2 worktree contained `scripts/udp_payload_sweep.py`, `scripts/analyze_udp_payload_sweep.py`, and `scripts/table_occupancy.py`, alongside additional local result directories. This supersedes the earlier statement that UDP payload-sweep automation was not implemented. The exact final UDP payload-sweep CSV and final table-occupancy/lookup-cost measurements are not confirmed in this repository snapshot; do not claim the experiments' final numerical results are published until the original output files are committed. The broader campaign and isolation work is documented in `docs/experiments/final-results-addendum-2026-10-27.md`.

## 1. Baseline and repeated trials

Mam asks for a forwarding baseline without VXLAN and at least 10 runs of 30 seconds per condition. The existing benchmark script now records individual tenant A/B rows rather than averaging the two tenants together, saves failures separately, and excludes a warm-up from recorded samples.

The baseline is implemented as plain L2 forwarding in a P4 program with a topology matching the same host and switch layout. It keeps the same sender/receiver pair, MTU, TCP MSS, duration and offload settings, but uses a different forwarding mechanism (no VXLAN); describe this as a baseline configuration, not an isolated control. Run at least ten trials in each condition and compute mean, sample standard deviation and a two-sided 95% Student-t confidence interval. The orchestrator alternates condition order across MSS values.

Current run command, inside Ubuntu/WSL2 after compiling the P4 program:
```bash
sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --mss 500 700 900 1100 1300 1400
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
```
The orchestrator launches a Mininet-owned benchmark for each MSS setting, appending both conditions to the same raw CSV when `--with-baseline` is used. Compile `src/p4/baseline.p4` to `build/baseline.json` first. The baseline is present in code but has not been runtime-validated here.

## 2. MSS and payload sweeps

Keep the TCP MSS sweep and UDP payload-size sweep separate. Suggested TCP MSS values: 500, 700, 900, 1100, 1300 and 1400 bytes, as six independent conditions with ten 30-second trials each. Confirm the negotiated MSS in a capture or iperf output; an endpoint command-line option alone is not evidence that every connection used the requested value. For UDP, specify an application datagram size, bandwidth, duration, receiver throughput, packet loss and jitter. Do not call the UDP datagram size a TCP MSS.

The campaign runner automates all six requested TCP MSS values in separate Mininet sessions. Each condition is kept separate in the raw CSV and summary. Separately, local WSL2 records show UDP payload-sweep scripts for 256, 512, 768, 1024 and 1200-byte application payloads at a fixed 5 Mbps, with five planned trials per payload size per tenant (50 planned observations total). This is distinct from the already summarised 5/15/25-Mbps offered-load sweep. The local script presence and planned protocol are evidenced; the final CSV contents and successful observation count must be checked before quoting final results.

## 3. Isolation tests against misuse

Ping failure is an end-to-end non-delivery result; it does not, by itself, prove which forwarding-table action dropped a packet. Next tests should craft VXLAN packets with Scapy, including a valid VNI, Tenant A source with Tenant B VNI, Tenant B VNI with an incorrect inner destination, unknown VNI, and malformed/unsupported header cases. Capture at the underlay and tenant-facing egress. Read counter snapshots before and after each test where BMv2 registers or table counters are added. Keep a same-tenant positive control in each campaign.

Report separately whether the packet was not delivered at the endpoint and whether the intended table-drop/counter change was directly observed. The current topology uses exact-match decapsulation on VNI plus inner IPv4 destination and a default drop action, but crafted input and counter evidence are still outstanding.

## 4. Scale experiments

After the two-tenant implementation is stable, add at least eight tenants and three or four VTEPs. Report table size, number of entries, throughput, packet rate or CPU cost, latency, failures and topology details. Test correctness after increasing scale; do not infer scale performance from the two-tenant data.

## 5. Checksum and encapsulation explanation

The current `src/p4/vxlan.p4` recomputes the outer IPv4 checksum in `MyComputeChecksum`. During decapsulation, the inner IPv4 header is copied into `hdr.outer_ipv4`; the same checksum control then recalculates that restored IPv4 header before emission. The outer UDP checksum is set to zero, which is permitted for IPv4 UDP; the inner UDP header is preserved rather than modified. The pipeline's checksum verification control is currently empty, so input checksum validation itself is not performed by P4. Confirm these details with captures and checksum validation for the packets actually tested. The P4 program has not yet been changed in this branch; this is an inspection of the current data path, not a claim that a new checksum fix was implemented. Endpoint TX checksum-offload settings are an experimental control to ensure the source host emits valid checksums; they are not a substitute for correct P4 checksum handling.

VXLAN adds 50 bytes of encapsulation headers in this implementation (outer Ethernet 14 + IPv4 20 + UDP 8 + VXLAN 8). Explain this as header overhead; measured throughput differences also depend on per-packet processing and the host/WSL2 virtual network, so they cannot be attributed to the VXLAN header alone without the baseline.

## 6. Manuscript changes

For the next revision: remove course-only headers and the “Prepared October 2026” line; replace console screenshots with clean, concise result tables; expand related work to discuss actual P4 tunnel/overlay implementations rather than treating foundational P4 language papers as having limitations; report every run condition and uncertainty; clearly qualify the isolation evidence; and avoid journal-level claims until the missing experiments are complete.

## Data handling

The campaign runner measures the requested TCP MSS values in separate runs. The raw CSV schema is documented in `results/REPEATED_TRIALS_SCHEMA.md`. Keep historical results unchanged and preserve failed attempts with a failure status/reason. The analyzer only includes successful numeric receiver-throughput values and keeps conditions with different MSS, duration, tenant, configuration, MTU, transport or offload setting separate. It writes intervals only when there are at least two observations. No fabricated or projected trial results should be added.


## 7. Table occupancy and lookup-cost experiment status

A local script named `scripts/table_occupancy.py` was present in the operator's WSL2 worktree. Its recorded code targets decapsulation-table occupancy levels, installs padding entries on both VTEPs, and writes a pilot CSV by default to `results/scalability/table_occupancy_pilot_20261027.csv`. This is evidence that a table-occupancy experiment was implemented or piloted, not by itself evidence that a controlled lookup-cost benchmark completed. Before claiming lookup-cost results, publish the original CSV and document the occupancy levels, repetitions, traffic load, measured metric, success/failure counts, and whether the metric measures forwarding latency/throughput or merely harness duration. Table occupancy must not be conflated with tenant/VTEP connectivity scalability.
