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
