# First-level corrections: baseline, repetitions, checksum handling and isolation

This plan follows the correction sheet supplied for Team 12. It distinguishes repository changes from live network experiments: no measurement should be described as completed until the actual BMv2/Mininet environment produces a raw result file.

## Status of this branch

- **Added:** per-tenant raw trial logging for the P4 VXLAN path in scripts/benchmark.py, configurable trial count/duration/MSS, warm-up exclusion, per-condition summary statistics, a campaign orchestrator for the six TCP MSS values, tool-version recording, raw schema and experiment guidance.
- **Not run in this environment:** live P4 compilation, Mininet/BMv2 traffic generation, repeated throughput trials, baseline trials, Scapy packet injection and multi-VTEP scaling. This execution environment does not have p4c, simple_switch, Mininet or iperf3 installed and cannot run your WSL2 namespaces.
- **Not yet implemented:** a matched no-VXLAN baseline topology, six-value MSS sweep automation, UDP payload sweep automation, Scapy VNI-spoof/wrong-destination tests, per-VNI counters, and an 8-tenant/3–4-VTEP topology. These remain necessary to call the whole correction sheet complete.

## 1. Baseline and repeated trials

Mam asks for a forwarding baseline without VXLAN and at least 10 runs of 30 seconds per condition. The existing benchmark script now records individual tenant A/B rows rather than averaging the two tenants together, saves failures separately, and excludes a warm-up from recorded samples.

The baseline must be a **real matched data path** on the same Mininet topology with the same sender/receiver pair, MTU, offered load, transport, duration and offload settings. Do not compare a Linux/OVS baseline to the VXLAN path unless you clearly describe the difference in switching implementation. Run at least ten trials in each condition and compute mean, sample standard deviation and a two-sided 95% Student-t confidence interval. Alternate the order of conditions or use a recorded random seed to reduce order effects.

Current run command, inside Ubuntu/WSL2 after compiling the P4 program:
```bash
sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --mss 500 700 900 1100 1300 1400
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
```
The campaign orchestrator now launches one Mininet-owned benchmark for each MSS setting, appending each condition to the same raw CSV. This campaign still measures only the existing VXLAN path; the no-VXLAN baseline is not yet implemented.

## 2. MSS and payload sweeps

Keep the TCP MSS sweep and UDP payload-size sweep separate. Suggested TCP MSS values: 500, 700, 900, 1100, 1300 and 1400 bytes, as six independent conditions with ten 30-second trials each. Confirm the negotiated MSS in a capture or iperf output; an endpoint command-line option alone is not evidence that every connection used the requested value. For UDP, specify an application datagram size, bandwidth, duration, receiver throughput, packet loss and jitter. Do not call the UDP datagram size a TCP MSS.

The current interface supports one TCP MSS per invocation. Repeat it for each requested value and do not pool rows across different MSS values.

## 3. Isolation tests against misuse

Ping failure is an end-to-end non-delivery result; it does not, by itself, prove which forwarding-table action dropped a packet. Next tests should craft VXLAN packets with Scapy, including a valid VNI, Tenant A source with Tenant B VNI, Tenant B VNI with an incorrect inner destination, unknown VNI, and malformed/unsupported header cases. Capture at the underlay and tenant-facing egress. Read counter snapshots before and after each test where BMv2 registers or table counters are added. Keep a same-tenant positive control in each campaign.

Report separately whether the packet was not delivered at the endpoint and whether the intended table-drop/counter change was directly observed. The current topology uses exact-match decapsulation on VNI plus inner IPv4 destination and a default drop action, but crafted input and counter evidence are still outstanding.

## 4. Scale experiments

After the two-tenant implementation is stable, add at least eight tenants and three or four VTEPs. Report table size, number of entries, throughput, packet rate or CPU cost, latency, failures and topology details. Test correctness after increasing scale; do not infer scale performance from the two-tenant data.

## 5. Checksum and encapsulation explanation

The current `src/p4/vxlan.p4` recomputes the outer IPv4 checksum in `MyComputeChecksum`. During decapsulation, the inner IPv4 header is copied into `hdr.outer_ipv4`; the same checksum control then recalculates that restored IPv4 header before emission. The outer UDP checksum is set to zero, which is permitted for IPv4 UDP; the inner UDP header is preserved rather than modified. Confirm these details with captures and checksum validation for the packets actually tested. Endpoint TX checksum-offload settings are an experimental control to ensure the source host emits valid checksums; they are not a substitute for correct P4 checksum handling.

VXLAN adds 50 bytes of encapsulation headers in this implementation (outer Ethernet 14 + IPv4 20 + UDP 8 + VXLAN 8). Explain this as header overhead; measured throughput differences also depend on per-packet processing and the host/WSL2 virtual network, so they cannot be attributed to the VXLAN header alone without the baseline.

## 6. Manuscript changes

For the next revision: remove course-only headers and the “Prepared October 2026” line; replace console screenshots with clean, concise result tables; expand related work to discuss actual P4 tunnel/overlay implementations rather than treating foundational P4 language papers as having limitations; report every run condition and uncertainty; clearly qualify the isolation evidence; and avoid journal-level claims until the missing experiments are complete.

## Data handling

The campaign runner measures the requested TCP MSS values in separate runs. The raw CSV schema is documented in `results/REPEATED_TRIALS_SCHEMA.md`. Keep historical results unchanged and preserve failed attempts with a failure status/reason. The analyzer only includes successful numeric receiver-throughput values and keeps conditions with different MSS, duration, tenant, configuration, MTU, transport or offload setting separate. It writes intervals only when there are at least two observations. No fabricated or projected trial results should be added.
