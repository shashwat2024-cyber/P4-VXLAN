# Repeated measurement data format

`repeated_trials.csv` contains one row per attempted measured condition. The active benchmark script writes the fields below; fields that are not available remain empty rather than being guessed.

```csv
experiment_id,timestamp_utc,git_commit,configuration,tenant,transport,mss_bytes,payload_bytes,duration_seconds,mtu,offload,sender_mbps,receiver_mbps,retransmissions,latency_ms,packet_loss_percent,status,command,notes
```

Keep failed attempts with `status=failed` and a reason in `notes`; do not delete failures silently. The analysis script includes only successful rows with finite numeric receiver throughput. Rows are grouped by experiment ID, configuration, tenant, transport, MSS, payload, duration, MTU and offload, so unlike conditions are not pooled.

Analyze the results:

```bash
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
```

For groups with at least two successful values, the output includes mean, sample standard deviation and an approximate two-sided 95% Student-t confidence interval. For one observation, the interval is omitted. These statistics are descriptive and do not establish causality by themselves.
