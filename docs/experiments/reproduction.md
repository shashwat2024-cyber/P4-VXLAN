# Reproducing the VXLAN Experiments

## 1. Recorded environment

The tested environment used Ubuntu 24.04.5 under WSL2 on ARM64, P4C 1.2.5.18, BMv2 `simple_switch` 1.15.7, Mininet 2.3.0, Python 3.12.3 and iperf3 3.16.

Check the installed tools:

```bash
p4c --version
simple_switch --version
mn --version
python3 --version
iperf3 --version
```

## 2. Compile the P4 programs

From the repository root:

```bash
mkdir -p build
p4c --target bmv2 --arch v1model -o build/vxlan.json src/p4/vxlan.p4
p4c --target bmv2 --arch v1model -o build/baseline.json src/p4/baseline.p4
```

In the tested environment, P4C may create a directory named `build/vxlan.json/` containing the compiled JSON and intermediate file. Inspect the output before moving anything:

```bash
find build -maxdepth 3 -type f -print
```

If `build/vxlan.json/vxlan.json` exists and `build/vxlan.json` is a directory, move the compiled file and intermediate output safely:

```bash
mv build/vxlan.json/vxlan.json build/vxlan-compiled.json
mv build/vxlan.json/vxlan.p4i build/vxlan.p4i
rmdir build/vxlan.json
mv build/vxlan-compiled.json build/vxlan.json
```

Only run those moves if the listed source files exist. Do not delete uninspected build output. Validate the resulting JSON:

```bash
python3 -m json.tool build/vxlan.json > /dev/null && echo "P4 JSON is valid"
python3 -m json.tool build/baseline.json > /dev/null && echo "Baseline JSON is valid"
```

## 3. Start and inspect the two-VTEP topology

Start the VXLAN topology:

```bash
sudo -E python3 topology/vxlan_topology.py
```

Leave the topology running. Use another terminal for switch inspection and configuration.

VTEP1:

```bash
sudo simple_switch_CLI --thrift-port 9090
```

At `RuntimeCmd:`, inspect:

```text
table_dump MyIngress.encap_by_port
table_dump MyIngress.decap_by_vni_and_dst
```

VTEP2:

```bash
sudo simple_switch_CLI --thrift-port 9091
```

Inspect the same tables:

```text
table_dump MyIngress.encap_by_port
table_dump MyIngress.decap_by_vni_and_dst
```

Expected decapsulation mappings:

- VTEP1: VNI 1001 and destination 192.168.10.1 → port 1.
- VTEP1: VNI 1002 and destination 192.168.20.1 → port 2.
- VTEP2: VNI 1001 and destination 192.168.10.2 → port 1.
- VTEP2: VNI 1002 and destination 192.168.20.2 → port 2.

Both decapsulation tables should use `MyIngress.drop_packet` as their default action. Inspect existing entries before adding anything; `DUPLICATE_ENTRY` means an entry already exists.

## 4. Connectivity and isolation checks

At the Mininet prompt, test legitimate same-tenant connectivity:

```text
h1 ping -c 3 h2
h3 ping -c 3 h4
```

For the recorded cross-tenant checks, explicit host routes and static neighbour entries were used:

```text
h1 ip route add 192.168.20.2/32 dev h1-eth0
h1 ip neigh replace 192.168.20.2 lladdr 00:00:00:00:20:02 dev h1-eth0
h1 ping -c 3 192.168.20.2

h3 ip route add 192.168.10.2/32 dev h3-eth0
h3 ip neigh replace 192.168.10.2 lladdr 00:00:00:00:10:02 dev h3-eth0
h3 ping -c 3 192.168.10.2
```

If routes already exist, inspect them before adding them again. Failed pings alone do not establish why packets were dropped.

The tenant-originated VXLAN injection regression test and scalable tenant/VTEP correctness tests are represented by the test sources and evidence under `tests/`, `scripts/run_scalability_experiments.py`, `src/p4/vxlan_scalability.p4`, and `results/scalability/`. Consult `docs/experiments/isolation-test-report.md` and the scalability report for the recorded outcomes. The report's probe counts are functional correctness results, not scale-performance measurements.

## 5. Capture underlay traffic

Check interface names:

```bash
sudo ip -br link
```

Run a capture while generating traffic from Mininet:

```bash
sudo timeout 12 tcpdump -ni vtep1-eth3 -c 1 -vv 'udp dst port 4789'
sudo timeout 12 tcpdump -ni vtep2-eth3 -c 1 -vv 'udp dst port 4789'
```

Save packet captures when packet-level inspection is required. The recorded capture length check found an 84-byte inner IPv4 packet, a 134-byte outer IPv4 packet and a 114-byte VXLAN UDP datagram.

## 6. Repeated TCP baseline and VXLAN measurements

The repeated campaign runner supports the six-MSS campaign. Compile both P4 programs first and inspect the output paths as described above.

Run the paired repeated MSS campaign from the repository root:

```bash
sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --mss 500 700 900 1100 1300 1400 --with-baseline
```

This starts a fresh Mininet topology for each condition. The runner records each tenant and measured run in `results/repeated_trials.csv`, excludes the warm-up, preserves failed attempts and writes tool/version metadata to `results/environment.json`. It alternates baseline/VXLAN order across MSS values. The plain-L2 baseline is a performance comparison, not an isolation configuration.

Compute per-condition summaries:

```bash
python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv
```

The summary reports mean, sample standard deviation and a 95% Student-t confidence interval when at least two successful observations exist. Do not pool different MSS, duration, MTU, tenant, configuration or offload conditions.

## 7. Final analysis outputs

The consolidated analysis script is:

```bash
python3 scripts/build_final_analysis.py
```

The recorded consolidated outputs are under `results/final_analysis_20261101/`, including the report, CSV comparison tables and generated TCP/CPU figures. The corrected TCP MSS-1400 primary dataset uses successful recovery records for Tenant B trials 17 and 19; the additional recovery and diagnostic runs are retained separately.

The separate CPU campaign is under `results/cpu_utilisation_20261101/` and covers Tenant A only. UDP payload and offered-load analysis outputs are under `results/udp_rss_analysis/`. Read the generated report before interpreting any metric: TCP RTT is post-transfer, while UDP RTT is measured under load.

## 8. UDP and scale/security evidence

The UDP payload and offered-load campaigns and their statistical summaries are retained under `results/udp_rss_analysis/`. The campaign scripts are `scripts/udp_payload_sweep.py` and `scripts/scalability_udp.py`. Inspect each script's `--help` output before launching a new campaign so that the arguments match the checked-in version and the intended test conditions.

Tenant/VTEP correctness experiments are run by `scripts/run_scalability_experiments.py`; the scalable P4 source is `src/p4/vxlan_scalability.p4`. The recorded six-configuration results are in `results/scalability/SCALABILITY_SECURITY_REPORT_20261101.md`. They test legitimate reachability, cross-tenant blocking and spoofed-source blocking across the reported tenant/VTEP counts. They do not measure performance at every scale.

## 9. Evidence and reporting cautions

- Preserve raw CSV files, captures, failed trials and recovery records.
- Record tool versions, command lines, traffic settings, units and sample counts.
- Do not conflate TCP MSS with UDP application-payload size.
- Do not describe TCP post-transfer ping RTT as under-load latency.
- Do not describe the plain-L2 baseline as a tenant-isolation configuration.
- Do not treat BMv2 software-emulation results as hardware-switch performance.
- Do not claim exhaustive security or scale-performance proof from the finite functional test cases.
