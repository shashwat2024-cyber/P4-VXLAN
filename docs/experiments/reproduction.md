# Reproducing the VXLAN Experiments

## 1. Environment

The tested environment used Ubuntu 24.04.5 under WSL2 on ARM64, P4C 1.2.5.18, BMv2 simple_switch 1.15.7, Mininet 2.3.0, Python 3.12.3, and iperf3 3.16.

Check installed tools:

```bash
p4c --version
simple_switch --version
mn --version
python3 --version
iperf3 --version
```

## 2. Compile the P4 program

From the repository root:

```bash
mkdir -p build
p4c --target bmv2 --arch v1model -o build/vxlan.json src/p4/vxlan.p4
```

In the tested environment, P4C created a directory named `build/vxlan.json/` containing the compiled `vxlan.json` and intermediate `vxlan.p4i`. The topology expects `build/vxlan.json` to be a regular JSON file.

Inspect the build output before moving files:

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

Only run those moves if the listed source files exist. Do not delete uninspected build output.

Validate the JSON:

```bash
python3 -m json.tool build/vxlan.json > /dev/null && echo "P4 JSON is valid"
```

## 3. Start the topology

```bash
sudo -E python3 topology/vxlan_topology.py
```

Leave the topology running. Use another terminal for switch inspection and configuration.

## 4. Inspect runtime tables

VTEP1:

```bash
sudo simple_switch_CLI --thrift-port 9090
```

At `RuntimeCmd:`, run:

```text
table_dump MyIngress.encap_by_port
table_dump MyIngress.decap_by_vni_and_dst
```

VTEP2:

```bash
sudo simple_switch_CLI --thrift-port 9091
```

At `RuntimeCmd:`, run:

```text
table_dump MyIngress.encap_by_port
table_dump MyIngress.decap_by_vni_and_dst
```

Inspect existing entries before adding anything. `DUPLICATE_ENTRY` means an entry already exists.

Expected decapsulation mappings:

- VTEP1: VNI 1001 and destination 192.168.10.1 → port 1.
- VTEP1: VNI 1002 and destination 192.168.20.1 → port 2.
- VTEP2: VNI 1001 and destination 192.168.10.2 → port 1.
- VTEP2: VNI 1002 and destination 192.168.20.2 → port 2.

Both decapsulation tables should use `MyIngress.drop_packet` as their default action.

## 5. Run connectivity tests

At the Mininet prompt:

```text
h1 ping -c 3 h2
h3 ping -c 3 h4
```

For cross-tenant tests, the experiment used explicit host routes and static neighbour entries:

```text
h1 ip route add 192.168.20.2/32 dev h1-eth0
h1 ip neigh replace 192.168.20.2 lladdr 00:00:00:00:20:02 dev h1-eth0
h1 ping -c 3 192.168.20.2

h3 ip route add 192.168.10.2/32 dev h3-eth0
h3 ip neigh replace 192.168.10.2 lladdr 00:00:00:00:10:02 dev h3-eth0
h3 ping -c 3 192.168.10.2
```

If routes already exist, inspect them before adding them again. Failed pings alone do not establish why packets were dropped.

## 6. Capture underlay traffic

Check interface names:

```bash
sudo ip -br link
```

Run a capture while generating traffic from Mininet:

```bash
sudo timeout 12 tcpdump -ni vtep1-eth3 -c 1 -vv 'udp dst port 4789'
sudo timeout 12 tcpdump -ni vtep2-eth3 -c 1 -vv 'udp dst port 4789'
```

If tcpdump reports `unknown payload`, its output does not independently establish the VXLAN VNI or inner destination. Save raw captures if detailed packet-level evidence is required.

## 7. Throughput experiments and reporting

The existing throughput measurements and their conditions are documented in `paper/results.md` and the files under `results/`. Review script arguments and configuration before rerunning experiments.

Keep measurements from different MSS values, durations, offload settings, and workloads separate. The existing short diagnostic trials do not establish statistically robust performance differences.

Cross-tenant ping failures and default-drop table configuration are consistent with the intended isolation policy, but are not exhaustive proof against every possible misconfiguration or attack.

Record actual command output, tool versions, test conditions, and units. Do not invent missing measurements.
