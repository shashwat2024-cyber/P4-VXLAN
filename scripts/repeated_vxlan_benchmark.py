#!/usr/bin/env python3
"""Repeated VXLAN-only benchmark; preserves failed trials and never fabricates data.

Run from repo root:
  sudo -E python3 scripts/repeated_vxlan_benchmark.py --runs 10 --duration 30 --mss 1000

This intentionally does not pretend to be a no-VXLAN baseline. A comparable baseline
requires its own topology/configuration and must be measured separately.
"""
import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "repeated_vxlan_trials.csv")
COLUMNS = [
    "run_group", "timestamp_utc", "configuration", "tenant", "trial",
    "duration_seconds", "mss_bytes", "client", "server",
    "sender_mbps", "receiver_mbps", "retransmissions",
    "ping_mean_ms", "ping_packet_loss_percent", "status", "error"
]


def parse_iperf(output):
    data = json.loads(output)
    end = data["end"]
    received = end.get("sum_received") or end.get("sum")
    sent = end.get("sum_sent") or end.get("sum")
    if not received or "bits_per_second" not in received:
        raise ValueError("iperf3 JSON has no receiver throughput")
    sender_mbps = (
        sent.get("bits_per_second", 0) / 1_000_000 if sent else None
    )
    retrans = None
    streams = end.get("streams", [])
    if streams:
        retrans_values = [
            s.get("sender", {}).get("retransmits")
            for s in streams if s.get("sender", {}).get("retransmits") is not None
        ]
        if retrans_values:
            retrans = sum(retrans_values)
    if retrans is None:
        retrans = end.get("sum_sent", {}).get("retransmits")
    return sender_mbps, received["bits_per_second"] / 1_000_000, retrans


def parse_ping(output):
    loss_match = re.search(r"([0-9.]+)% packet loss", output)
    rtt_match = re.search(r"rtt min/avg/max/(?:mdev|stddev) = [0-9.]+/([0-9.]+)/", output)
    if not loss_match:
        raise ValueError("Could not parse packet loss from ping output")
    return (float(rtt_match.group(1)) if rtt_match else None,
            float(loss_match.group(1)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=10, help="independent trials per tenant (default: 10)")
    ap.add_argument("--duration", type=int, default=30, help="iperf3 seconds per trial (default: 30)")
    ap.add_argument("--mss", type=int, default=1000, help="TCP MSS bytes; run different values separately")
    ap.add_argument("--output", default=OUT, help="CSV output path (append; never overwrites)")
    ap.add_argument("--warmup", type=int, default=2, help="seconds to wait for servers")
    args = ap.parse_args()

    if args.runs < 1 or args.duration < 1 or args.mss < 500 or args.mss > 1400:
        ap.error("--runs and --duration must be positive; --mss must be 500..1400")
    if os.geteuid() != 0:
        ap.error("Run in the isolated lab with sudo: sudo -E python3 scripts/repeated_vxlan_benchmark.py ...")

    sys.path.insert(0, ROOT)
    try:
        from mininet.net import Mininet
        from mininet.log import setLogLevel
        from topology.vxlan_topology import VXLANTopo, JSON, add_rules
    except ImportError as exc:
        ap.error("Mininet imports failed: %s" % exc)
    setLogLevel("warning")

    if not os.path.isfile(JSON):
        ap.error("Compiled P4 JSON missing: %s. Compile src/p4/vxlan.p4 first." % JSON)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    run_group = str(uuid.uuid4())
    exists = os.path.exists(args.output) and os.path.getsize(args.output) > 0
    net = Mininet(topo=VXLANTopo(), controller=None, autoSetMacs=False)
    rows = []

    try:
        print("Starting P4 VXLAN benchmark. run_group=%s" % run_group)
        net.start()
        v1, v2 = net.get("vtep1"), net.get("vtep2")
        v1.cmd("ip link set dev vtep1-eth3 address 02:00:00:00:01:01")
        v2.cmd("ip link set dev vtep2-eth3 address 02:00:00:00:01:02")
        hosts = {n: net.get(n) for n in ("h1", "h2", "h3", "h4")}

        # 1450-byte interface MTU leaves room for 50 bytes of VXLAN outer headers.
        for name, host in hosts.items():
            host.cmd("ip link set dev %s-eth0 mtu 1450" % name)

        neighbors = [
            ("h1", "192.168.10.2", "00:00:00:00:10:02"),
            ("h2", "192.168.10.1", "00:00:00:00:10:01"),
            ("h3", "192.168.20.2", "00:00:00:00:20:02"),
            ("h4", "192.168.20.1", "00:00:00:00:20:01"),
        ]
        for host, ip, mac in neighbors:
            hosts[host].cmd(
                "ip neigh replace %s lladdr %s nud permanent dev %s-eth0"
                % (ip, mac, host)
            )

        add_rules()
        hosts["h2"].cmd("pkill -x iperf3 2>/dev/null; iperf3 -s > /tmp/iperf3-h2-repeated.log 2>&1 &")
        hosts["h4"].cmd("pkill -x iperf3 2>/dev/null; iperf3 -s > /tmp/iperf3-h4-repeated.log 2>&1 &")
        time.sleep(args.warmup)

        with open(args.output, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            if not exists:
                writer.writeheader()
                handle.flush()

            for trial in range(1, args.runs + 1):
                for tenant, client, server_ip in (
                    ("A", "h1", "192.168.10.2"),
                    ("B", "h3", "192.168.20.2"),
                ):
                    timestamp = datetime.now(timezone.utc).isoformat()
                    row = dict.fromkeys(COLUMNS, "")
                    row.update({
                        "run_group": run_group,
                        "timestamp_utc": timestamp,
                        "configuration": "P4-BMv2-VXLAN",
                        "tenant": tenant,
                        "trial": trial,
                        "duration_seconds": args.duration,
                        "mss_bytes": args.mss,
                        "client": client,
                        "server": server_ip,
                        "status": "failed",
                    })
                    try:
                        # Start every trial with a recorded positive-control ping.
                        ping = hosts[client].cmd(
                            "ping -c 10 -W 1 %s" % server_ip
                        )
                        ping_mean, ping_loss = parse_ping(ping)
                        if ping_loss >= 100:
                            raise RuntimeError("positive-control ping failed: " + ping[-500:])

                        cmd = [
                            "iperf3", "-c", server_ip, "-t", str(args.duration),
                            "-M", str(args.mss), "-J"
                        ]
                        output = hosts[client].cmd(" ".join(cmd) + " 2>&1")
                        sender, receiver, retrans = parse_iperf(output)
                        row.update({
                            "sender_mbps": "" if sender is None else round(sender, 6),
                            "receiver_mbps": round(receiver, 6),
                            "retransmissions": "" if retrans is None else retrans,
                            "ping_mean_ms": "" if ping_mean is None else ping_mean,
                            "ping_packet_loss_percent": ping_loss,
                            "status": "ok",
                        })
                    except Exception as exc:  # retain failed trials with reason
                        row["error"] = str(exc).replace("\n", " ")[:1500]
                    writer.writerow(row)
                    handle.flush()
                    rows.append(row)
                    print(
                        "trial=%d tenant=%s status=%s receiver_mbps=%s error=%s"
                        % (trial, tenant, row["status"], row["receiver_mbps"], row["error"])
                    )
    finally:
        net.stop()

    valid = [r for r in rows if r["status"] == "ok" and r["receiver_mbps"] != ""]
    print("\nRaw results appended to: %s" % args.output)
    print("run_group=%s; successful tenant trials=%d/%d" %
          (run_group, len(valid), args.runs * 2))
    for tenant in ("A", "B"):
        vals = [
            float(r["receiver_mbps"]) for r in valid if r["tenant"] == tenant
        ]
        if vals:
            print("Tenant %s receiver Mbps: n=%d mean=%.4f median=%.4f" %
                  (tenant, len(vals), statistics.mean(vals), statistics.median(vals)))
        else:
            print("Tenant %s: no valid measurements" % tenant)
    print("Summary is descriptive only; repeat the baseline in an equivalent topology before claiming VXLAN overhead.")


if __name__ == "__main__":
    main()
