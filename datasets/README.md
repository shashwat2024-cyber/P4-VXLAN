# Dataset documentation

## File
- iperf3_confirmed_trials.csv: six previously recorded iperf3 observations transcribed from the project's confirmed-trial record.

## Columns
- configuration: human-readable test configuration label.
- tenant: tenant identifier (A or B).
- direction: sender host to receiver host.
- duration_seconds: test duration recorded for that run.
- mss_bytes: TCP maximum segment size used/reported for the run.
- sender_mbps: sender-side reported throughput in Mbit/s.
- receiver_mbps: receiver-side reported throughput in Mbit/s.
- retransmissions: TCP retransmission count recorded for the run.
- mtu: configured/known MTU, or unknown if not recorded for that diagnostic run.
- status: descriptive status from the original record.

## Important caveats
These rows are existing observations, not newly run experiments. They are heterogeneous: durations and MSS/MTU settings differ. Do not calculate a pooled mean or claim a controlled comparison from them. The MTU value is deliberately unknown for MSS-1000 diagnostics because it was not confirmed in the source record. No baseline data are present in this file. For a proper comparison, store every future run as a new row with exact configuration, timestamps, environment, endpoint settings and raw iperf3 output preserved separately.
