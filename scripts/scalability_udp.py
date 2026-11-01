#!/usr/bin/env python3
"""UDP offered-load experiment for the existing four-host P4 VXLAN topology."""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mininet.net import Mininet
from mininet.log import setLogLevel
from topology.vxlan_topology import VXLANTopo, JSON, add_rules
from scripts.measurement_utils import (
    run_with_concurrent_ping,
    SimpleSwitchRSSMonitor,
    run_with_rss_monitor,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = ROOT / "results/scalability/udp_scalability_20261027.csv"
RATES_MBPS = (5, 15, 25)

FIELDS = [
    "campaign_id", "trial_number", "experiment_id", "timestamp_utc",
    "configuration", "tenant", "transport", "target_mbps", "duration_seconds",
    "receiver_mbps", "udp_loss_percent",
    "under_load_rtt_min_ms", "under_load_rtt_mean_ms",
    "under_load_rtt_max_ms", "under_load_rtt_stddev_ms",
    "under_load_ping_loss_percent",
    "rss_sample_count", "rss_sample_interval_ms",
    "rss_mean_total_mib", "rss_peak_total_mib",
    "rss_mean_per_process_mib", "rss_peak_per_process_mib",
    "latency_ms", "ping_loss_percent",
    "status", "command", "notes",
]


def ping_stats(host, destination, count=10):
    output = host.cmd(f"ping -c {count} -W 1 {destination}")
    import re
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    rtt = re.search(r"=\s*[\d.]+/([\d.]+)/", output)
    if not loss:
        raise RuntimeError("Could not parse ping output: " + output[-1000:])
    return float(rtt.group(1)) if rtt else None, float(loss.group(1))


def append_row(path, row):
    new_file = not path.exists() or path.stat().st_size == 0
    if not new_file:
        with path.open(newline="", encoding="utf-8-sig") as f:
            if next(csv.reader(f), None) != FIELDS:
                raise RuntimeError(f"CSV header mismatch: {path}")
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def run_udp(client, destination, duration, rate):
    command = [
        "iperf3", "-c", destination, "-u", "-b", f"{rate}M",
        "-t", str(duration), "-J",
    ]

    output, under_load_ping = run_with_concurrent_ping(
        client,
        destination,
        command,
        duration,
        ping_interval=0.2,
    )

    try:
        obj = json.loads(output)
        end = obj["end"]
        receiver = end.get("sum_received") or end.get("sum")
        if not receiver:
            raise KeyError("receiver summary")

        return (
            float(receiver["bits_per_second"]) / 1e6,
            float(receiver.get("lost_percent", 0.0)),
            " ".join(command),
            under_load_ping,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            f"iperf3 UDP result could not be parsed ({exc}): {output[-1500:]}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials-per-rate", type=int, default=10)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--output", default=str(OUTPUT_DEFAULT))
    parser.add_argument("--campaign-id", default="udp_scalability_20261027")
    parser.add_argument("--tenant", choices=["A", "B"], help="Run only one tenant")
    parser.add_argument("--rate", type=int, choices=RATES_MBPS, help="Run only one target rate in Mbps")
    args = parser.parse_args()

    if args.trials_per_rate < 1 or args.duration < 5:
        parser.error("Use at least one trial per rate and a duration of at least 5 seconds.")
    if os.geteuid() != 0:
        parser.error("Run with sudo /usr/bin/python3 scripts/scalability_udp.py")
    if not os.path.isfile(JSON):
        parser.error(f"Compiled P4 JSON missing: {JSON}")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    experiment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True
    ).stdout.strip()

    net = Mininet(topo=VXLANTopo(), controller=None, autoSetMacs=False)
    try:
        print(f"Starting UDP load experiment: {experiment_id}")
        net.start()
        v1, v2 = net.get("vtep1"), net.get("vtep2")
        v1.cmd("ip link set dev vtep1-eth3 address 02:00:00:00:01:01")
        v2.cmd("ip link set dev vtep2-eth3 address 02:00:00:00:01:02")

        hosts = {name: net.get(name) for name in ("h1", "h2", "h3", "h4")}
        for name, host in hosts.items():
            host.cmd(f"ip link set dev {name}-eth0 mtu 1450")
            host.cmd(f"ethtool -K {name}-eth0 tx off 2>/dev/null || true")

        neighbors = [
            ("h1", "192.168.10.2", "00:00:00:00:10:02"),
            ("h2", "192.168.10.1", "00:00:00:00:10:01"),
            ("h3", "192.168.20.2", "00:00:00:00:20:02"),
            ("h4", "192.168.20.1", "00:00:00:00:20:01"),
        ]
        for name, ip, mac in neighbors:
            hosts[name].cmd(f"ip neigh replace {ip} lladdr {mac} nud permanent dev {name}-eth0")

        add_rules()
        pairs = [
            ("A", "h1", "h2", "192.168.10.2"),
            ("B", "h3", "h4", "192.168.20.2"),
        ]

        for tenant, client_name, server_name, destination in pairs:
            if args.tenant and tenant != args.tenant:
                continue
            client, server = hosts[client_name], hosts[server_name]
            rates = [args.rate] if args.rate is not None else RATES_MBPS
            for rate in rates:
                for trial in range(1, args.trials_per_rate + 1):
                    command_text = ""
                    row = {
                        "campaign_id": args.campaign_id,
                        "trial_number": trial,
                        "experiment_id": experiment_id,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "configuration": "P4_VXLAN_UDP",
                        "tenant": tenant,
                        "transport": "UDP",
                        "target_mbps": rate,
                        "duration_seconds": args.duration,
                        "status": "failed",
                        "command": "",
                        "notes": "",
                    }
                    try:
                        server.cmd("pkill -x iperf3 2>/dev/null || true")
                        server.cmd("iperf3 -s -1 > /tmp/iperf3-server.log 2>&1 &")
                        time.sleep(0.8)
                        if "iperf3" not in server.cmd("pgrep -a iperf3 || true"):
                            raise RuntimeError("UDP iperf3 server did not start")
                        rss_monitor = SimpleSwitchRSSMonitor(interval_seconds=0.5)
                        udp_result, rss_summary = run_with_rss_monitor(
                            rss_monitor,
                            run_udp,
                            client,
                            destination,
                            args.duration,
                            rate,
                        )
                        (
                            rx,
                            udp_loss,
                            command_text,
                            under_load_ping,
                        ) = udp_result

                        # Retain the original post-transfer RTT measurement.
                        latency, ping_loss = ping_stats(client, destination)

                        row.update(
                            receiver_mbps=rx,
                            udp_loss_percent=udp_loss,
                            under_load_rtt_min_ms=under_load_ping["rtt_min_ms"],
                            under_load_rtt_mean_ms=under_load_ping["rtt_mean_ms"],
                            under_load_rtt_max_ms=under_load_ping["rtt_max_ms"],
                            under_load_rtt_stddev_ms=under_load_ping["rtt_stddev_ms"],
                            under_load_ping_loss_percent=under_load_ping["ping_loss_percent"],
                            latency_ms=latency,
                            ping_loss_percent=ping_loss,
                            status="success",
                            command=command_text,
                            notes=f"git_commit={commit}; ping_interval=0.2s",
                            **rss_summary,
                        )
                        print(
                            f"Tenant {tenant}, target {rate} Mbps, "
                            f"trial {trial}/{args.trials_per_rate}: "
                            f"rx={rx:.3f} Mbps, UDP loss={udp_loss:.2f}%, "
                            f"under-load RTT={under_load_ping['rtt_mean_ms']} ms, "
                            f"under-load ping loss={under_load_ping['ping_loss_percent']}%"
                        )
                    except Exception as exc:
                        row["command"] = command_text
                        row["notes"] = str(exc)[:1000]
                        print(
                            f"FAILED: tenant={tenant}, target={rate}, "
                            f"trial={trial}: {exc}", file=sys.stderr
                        )
                    append_row(output_path, row)

        print(f"Raw results saved to: {output_path}")
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("warning")
    main()
