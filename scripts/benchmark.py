#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
import csv
import json
import time
import re
import statistics

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.log import setLogLevel

from topology.vxlan_topology import VXLANTopo, JSON, add_rules

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEASUREMENTS = os.path.join(ROOT, "results", "measurements.csv")
RUNLOG = os.path.join(ROOT, "results", "run-log.csv")
CAPTURE = "/tmp/vxlan-cross-tenant-capture.txt"


def ping_stats(host, destination, count=10):
    output = host.cmd("ping -c %d -W 1 %s" % (count, destination))
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    rtt = re.search(r"= [\d.]+/([\d.]+)/", output)
    if not loss:
        raise RuntimeError("Could not parse ping output:\n" + output)
    return float(rtt.group(1)) if rtt else None, float(loss.group(1))


def throughput(client, destination, duration):
    output = client.cmd(
        "iperf3 -c %s -t %d -J" % (destination, duration)
    )
    try:
        data = json.loads(output)
        return data["end"]["sum_received"]["bits_per_second"] / 1_000_000
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Could not parse iperf3 output:\n" + output[-1500:])


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    if os.geteuid() != 0:
        sys.exit("Run with sudo: sudo python3 scripts/benchmark.py")
    if not os.path.isfile(JSON):
        sys.exit("Compiled P4 JSON missing: " + JSON)

    os.makedirs(os.path.dirname(MEASUREMENTS), exist_ok=True)
    net = Mininet(topo=VXLANTopo(), controller=None, autoSetMacs=False)

    try:
        print("Starting P4 VXLAN multi-tenant benchmark...")
        net.start()

        v1, v2 = net.get("vtep1"), net.get("vtep2")
        v1.cmd("ip link set dev vtep1-eth3 address 02:00:00:00:01:01")
        v2.cmd("ip link set dev vtep2-eth3 address 02:00:00:00:01:02")

        hosts = {name: net.get(name) for name in ("h1", "h2", "h3", "h4")}
        # Leave room for VXLAN encapsulation on every endpoint.
        for name, host in hosts.items():
            host.cmd("ip link set dev %s-eth0 mtu 1450" % name)
        neighbors = [
            ("h1", "192.168.10.2", "00:00:00:00:10:02"),
            ("h2", "192.168.10.1", "00:00:00:00:10:01"),
            ("h3", "192.168.20.2", "00:00:00:00:20:02"),
            ("h4", "192.168.20.1", "00:00:00:00:20:01"),
        ]
        for name, ip, mac in neighbors:
            hosts[name].cmd(
                "ip neigh replace %s lladdr %s nud permanent dev %s-eth0"
                % (ip, mac, name)
            )

        add_rules()

        hosts["h2"].cmd("iperf3 -s > /tmp/iperf3-h2.log 2>&1 &")
        hosts["h4"].cmd("iperf3 -s > /tmp/iperf3-h4.log 2>&1 &")
        time.sleep(1)

        # Force cross-subnet packets to be sent for the isolation test.
        hosts["h1"].cmd("ip route replace 192.168.20.0/24 dev h1-eth0")
        hosts["h1"].cmd(
            "ip neigh replace 192.168.20.2 lladdr 00:00:00:00:20:02 "
            "nud permanent dev h1-eth0"
        )

        measurement_exists = os.path.exists(MEASUREMENTS)
        runlog_exists = os.path.exists(RUNLOG)

        with open(MEASUREMENTS, "a", newline="") as mf, \
             open(RUNLOG, "a", newline="") as lf:
            mw = csv.writer(mf)
            lw = csv.writer(lf)

            if not measurement_exists or os.path.getsize(MEASUREMENTS) == 0:
                mw.writerow([
                    "configuration", "trial", "throughput_mbps",
                    "latency_ms", "packet_loss_percent", "overhead_bytes",
                    "unauthorized_packets_delivered"
                ])
            if not runlog_exists or os.path.getsize(RUNLOG) == 0:
                lw.writerow([
                    "date", "configuration", "trial", "packet_size_bytes",
                    "offered_rate_mbps", "duration_seconds", "iperf3_command",
                    "ping_command", "notes"
                ])

            for trial in range(1, trials + 1):
                print("\nTrial %d/%d" % (trial, trials))

                # Measure each tenant's permitted path.
                t_a = throughput(hosts["h1"], "192.168.10.2", duration)
                t_b = throughput(hosts["h3"], "192.168.20.2", duration)
                lat_a, loss_a = ping_stats(hosts["h1"], "192.168.10.2")
                lat_b, loss_b = ping_stats(hosts["h3"], "192.168.20.2")

                # Capture on the destination host to count any unauthorized
                # ICMP echo requests actually delivered to Tenant B.
                hosts["h4"].cmd("rm -f " + CAPTURE)
                hosts["h4"].cmd(
                    "timeout 6 tcpdump -n -l -i h4-eth0 "
                    "'icmp and src host 192.168.10.1' > "
                    + CAPTURE + " 2>&1 &"
                )
                time.sleep(1)
                cross_output = hosts["h1"].cmd(
                    "ping -c 3 -W 1 192.168.20.2"
                )
                time.sleep(1)
                capture = hosts["h4"].cmd("cat " + CAPTURE)
                delivered = sum(
                    1 for line in capture.splitlines()
                    if "ICMP echo request" in line
                    and "192.168.10.1" in line
                )

                avg_throughput = (t_a + t_b) / 2
                valid_latencies = [x for x in (lat_a, lat_b) if x is not None]
                avg_latency = statistics.mean(valid_latencies) if valid_latencies else ""
                avg_loss = (loss_a + loss_b) / 2

                mw.writerow([
                    "C-multitenant-vxlan", trial,
                    round(avg_throughput, 4), avg_latency,
                    round(avg_loss, 2), 50, delivered
                ])
                mf.flush()

                lw.writerow([
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    "C-multitenant-vxlan", trial, 1500, "",
                    duration,
                    "iperf3 -c <tenant-peer> -t %d -J" % duration,
                    "ping -c 10 <tenant-peer>",
                    "Tenant A throughput=%.4f Mbps; Tenant B throughput=%.4f Mbps; "
                    "cross-test replies=%d; captured unauthorized echo requests=%d"
                    % (t_a, t_b,
                       cross_output.count("bytes from"), delivered)
                ])
                lf.flush()

                print("Tenant A throughput: %.3f Mbps" % t_a)
                print("Tenant B throughput: %.3f Mbps" % t_b)
                print("Average latency: %s ms" % avg_latency)
                print("Average allowed-path packet loss: %.2f%%" % avg_loss)
                print("Unauthorized echo requests observed at h4: %d" % delivered)

        print("\nMeasurements appended to:")
        print(MEASUREMENTS)
        print(RUNLOG)
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("warning")
    main()
