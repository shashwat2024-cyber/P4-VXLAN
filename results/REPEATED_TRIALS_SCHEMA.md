# Repeated measurement data format

`repeated_trials.csv` stores exactly one row per attempted condition. The analyzer accepts these columns (unavailable fields may be empty, but do not put invented values in them):

```csv
experiment_id,timestamp_utc,git_commit,configuration,tenant,transport,mss_bytes,payload_bytes,duration_seconds,mtu,offload,sender_mbps,receiver_mbps,retransmissions,latency_ms,packet_loss_percent,status,command,notes
```

Use a unique experiment ID for each complete campaign. Record failed attempts with `status=failed` and an explanatory `notes` field; do not silently drop them. Throughput statistics include only rows with `status=success` and a numeric `receiver_mbps`. Summaries are grouped by configuration, tenant, transport, MSS, payload, duration, MTU, and offload so unlike conditions are not pooled.

Analyze results using:

```bash
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
```

For each group with at least two successful values, the script reports the sample mean, sample standard deviation, and an approximate two-sided 95% Student-t confidence interval. With one value, the interval is omitted. For large samples the 1.96 normal approximation is used for the critical value.
