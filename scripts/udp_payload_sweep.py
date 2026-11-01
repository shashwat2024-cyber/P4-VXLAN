#!/usr/bin/env python3
"""UDP application-datagram-size sweep over the existing P4 VXLAN topology."""

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
from topology.vxlan_topology import VXLANTopo, add_rules
from scripts.measurement_utils import (
    run_with_concurrent_ping,
    SimpleSwitchRSSMonitor,
    run_with_rss_monitor,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results/scalability/udp_payload_sweep"
DEFAULT_OUTPUT = OUT_DIR / "udp_payload_trials.csv"

SIZES = (256, 512, 768, 1024, 1200)
RATE_MBPS = 5
DURATION = 30
TRIALS = 5

FIELDS = [
    "campaign_id", "experiment_id", "timestamp_utc", "trial",
    "tenant", "transport", "datagram_bytes", "target_mbps",
    "duration_seconds", "receiver_mbps", "udp_loss_percent",
    "jitter_ms",
    "under_load_rtt_min_ms", "under_load_rtt_mean_ms",
    "under_load_rtt_max_ms", "under_load_rtt_stddev_ms",
    "under_load_ping_loss_percent",
    "rss_sample_count", "rss_sample_interval_ms",
    "rss_mean_total_mib", "rss_peak_total_mib",
    "rss_mean_per_process_mib", "rss_peak_per_process_mib",
    "status", "command", "notes",
]


def run_udp(client, destination, size, rate, duration):
    command = [
        "iperf3", "-c", destination, "-u",
        "-b", f"{rate}M", "-l", str(size),
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
            raise KeyError("receiver summary missing")

        jitter = receiver.get("jitter_ms")
        if jitter is None:
            jitter = end.get("sum", {}).get("jitter_ms")

        return (
            float(receiver["bits_per_second"]) / 1e6,
            float(receiver.get("lost_percent", 0.0)),
            float(jitter) if jitter is not None else None,
            " ".join(command),
            under_load_ping,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            f"Could not parse iperf3 UDP JSON ({exc}): {output[-1200:]}"
        )


def append_row(path, row):
    new_file = not path.exists() or path.stat().st_size == 0

    if not new_file:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            if next(csv.reader(handle), None) != FIELDS:
                raise RuntimeError(f"CSV header mismatch; refusing to append: {path}")

    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--rate", type=int, default=RATE_MBPS)
    parser.add_argument("--duration", type=int, default=DURATION)
    parser.add_argument("--trials", type=int, default=TRIALS)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--campaign-id", default="udp_payload_sweep_20261027")
    args = parser.parse_args()

    if os.geteuid() != 0:
        parser.error("Run with sudo /usr/bin/python3 scripts/udp_payload_sweep.py")
    if not os.path.isfile(ROOT / "build/vxlan.json"):
        parser.error("Missing build/vxlan.json; existing VXLAN build is required.")
    if any(size < 64 or size > 1400 for size in args.sizes):
        parser.error("Datagram sizes must be between 64 and 1400 bytes.")
    if args.rate < 1 or args.duration < 5 or args.trials < 1:
        parser.error("Rate must be positive, duration >= 5 seconds, trials >= 1.")
    if len(set(args.sizes)) != len(args.sizes):
        parser.error("Datagram sizes must not contain duplicates.")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size > 0:
        parser.error(
            f"Output already exists and is non-empty: {output_path}. "
            "Choose a new --output filename; existing results are preserved."
        )

    experiment_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + uuid.uuid4().hex[:8]
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True
    ).stdout.strip()

    net = Mininet(topo=VXLANTopo(), controller=None, autoSetMacs=False)

    try:
        print(f"Campaign: {args.campaign_id}")
        print(f"Experiment ID: {experiment_id}")
        print(f"Sizes: {args.sizes}; rate: {args.rate} Mbps; "
              f"duration: {args.duration}s; trials per size/tenant: {args.trials}")
        print(f"Raw CSV: {output_path}")

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
            hosts[name].cmd(
                f"ip neigh replace {ip} lladdr {mac} "
                f"nud permanent dev {name}-eth0"
            )

        add_rules()
        pairs = [
            ("A", "h1", "h2", "192.168.10.2"),
            ("B", "h3", "h4", "192.168.20.2"),
        ]

        # Abort before the long experiment if either tenant is unreachable.
        for tenant, client_name, server_name, destination in pairs:
            probe = hosts[client_name].cmd(
                f"ping -c 2 -W 2 {destination}"
            )
            print(f"Connectivity preflight — tenant {tenant}:\\n{probe}")
            if "0% packet loss" not in probe:
                raise RuntimeError(
                    f"Connectivity preflight failed for tenant {tenant}; "
                    "no payload trials were started."
                )

        for tenant, client_name, server_name, destination in pairs:
            client, server = hosts[client_name], hosts[server_name]

            for size in args.sizes:
                for trial in range(1, args.trials + 1):
                    row = {
                        "campaign_id": args.campaign_id,
                        "experiment_id": experiment_id,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "trial": trial,
                        "tenant": tenant,
                        "transport": "UDP",
                        "datagram_bytes": size,
                        "target_mbps": args.rate,
                        "duration_seconds": args.duration,
                        "status": "failed",
                        "command": "",
                        "notes": f"git_commit={commit}",
                    }

                    try:
                        server.cmd("pkill -x iperf3 2>/dev/null || true")
                        server.cmd("iperf3 -s -1 > /tmp/iperf3-payload-server.log 2>&1 &")
                        time.sleep(0.8)

                        if "iperf3" not in server.cmd("pgrep -a iperf3 || true"):
                            raise RuntimeError("UDP iperf3 server did not start")

                        rss_monitor = SimpleSwitchRSSMonitor(interval_seconds=0.5)
                        udp_result, rss_summary = run_with_rss_monitor(
                            rss_monitor,
                            run_udp,
                            client,
                            destination,
                            size,
                            args.rate,
                            args.duration,
                        )
                        rx, loss, jitter, command, under_load_ping = udp_result
                        row.update(
                            receiver_mbps=rx,
                            udp_loss_percent=loss,
                            jitter_ms=jitter,
                            under_load_rtt_min_ms=under_load_ping["rtt_min_ms"],
                            under_load_rtt_mean_ms=under_load_ping["rtt_mean_ms"],
                            under_load_rtt_max_ms=under_load_ping["rtt_max_ms"],
                            under_load_rtt_stddev_ms=under_load_ping["rtt_stddev_ms"],
                            under_load_ping_loss_percent=under_load_ping["ping_loss_percent"],
                            status="success",
                            command=command,
                            notes=f"git_commit={commit}; ping_interval=0.2s",
                            **rss_summary,
                        )
                        print(
                            f"Tenant {tenant}, size {size} B, "
                            f"trial {trial}/{args.trials}: "
                            f"RX={rx:.3f} Mbps, loss={loss:.3f}%, "
                            f"jitter={jitter}, "
                            f"under-load RTT={under_load_ping['rtt_mean_ms']} ms, "
                            f"ping loss={under_load_ping['ping_loss_percent']}%"
                        )
                    except Exception as exc:
                        row["notes"] += f"; error={str(exc)[:700]}"
                        print(
                            f"FAILED: tenant={tenant}, size={size}, "
                            f"trial={trial}: {exc}",
                            file=sys.stderr,
                        )

                    append_row(output_path, row)

        print(f"Raw results saved to: {output_path}")
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("warning")
    main()
