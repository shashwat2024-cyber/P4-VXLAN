# Reproducible VXLAN Evaluation Harness

This script runs the existing P4 VXLAN topology for repeated, fixed-duration trials and writes one raw row per tenant per trial. It does **not** fabricate or pre-populate results.

The direct/no-VXLAN baseline requires a separately implemented forwarding topology and should not be simulated by merely changing a CSV label. Use the protocol in `correction-roadmap.md` and keep conditions comparable.

## Usage

From repository root after compiling `src/p4/vxlan.p4` to `build/vxlan.json`:

```bash
sudo -E python3 scripts/repeated_vxlan_benchmark.py --runs 10 --duration 30 --mss 1000
```

Test other MSS values in separate runs, for example 500, 700, 900, 1100, 1300, and 1400, after confirming the value is compatible with the endpoint MTU. The recorded MSS is passed with `iperf3 -M`; the script will log actual output and failures.

The generated CSV is `results/repeated_vxlan_trials.csv`. Existing historical files are not overwritten. Each invocation appends rows and includes a run-group identifier.

## Important interpretation limits

- Each row is a single trial for one tenant flow, not a packet-level observation.
- This script evaluates VXLAN only; it does not create the no-VXLAN baseline.
- BMv2/Mininet under WSL2 results describe the software-emulated environment, not hardware line rate.
- If a run fails or does not yield receiver data, the row is retained with a failure message and blank measurement fields.
