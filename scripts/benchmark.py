#!/usr/bin/env python3
"""Run repeated VXLAN measurements within one process-local Mininet topology.

Run from repository root:
  sudo python3 scripts/benchmark.py --trials 10 --duration 30 --mss 1000

Raw measurements are appended to results/repeated_trials.csv. Each tenant and
each trial gets its own row. This script measures only the currently
implemented VXLAN topology; a no-VXLAN baseline and spoofed-VNI tests require
separate topology/test modes and are documented separately.
"""
import argparse
import csv
import json
import os
import re
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

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RAW = RESULTS / "repeated_trials.csv"
CAPTURE = "/tmp/vxlan-cross-tenant-capture.txt"

def ping_stats(host, destination, count=10):
    output = host.cmd(f"ping -c {count} -W 1 {destination}")
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    rtt = re.search(r"=\s*[\d.]+/([\d.]+)/", output)
    if not loss:
        raise RuntimeError("Could not parse ping output:\n" + output[-1500:])
    return (float(rtt.group(1)) if rtt else None, float(loss.group(1)), output)

def iperf_result(client, destination, duration, mss):
    command = ["iperf3", "-c", destination, "-t", str(duration), "-J"]
    if mss is not None:
        command += ["-M", str(mss)]
    # Run inside the Mininet host namespace; preserve raw JSON in the exception
    # message in case a test fails.
    output = client.cmd(" ".join(command))
    try:
        obj = json.loads(output)
        end = obj["end"]
        sent = end.get("sum_sent", {})
        recv = end.get("sum_received") or end.get("sum")
        if not recv:
            raise KeyError("end.sum_received")
        return {
            "sender_mbps": float(sent["bits_per_second"]) / 1e6 if sent.get("bits_per_second") else "",
            "receiver_mbps": float(recv["bits_per_second"]) / 1e6,
            "retransmissions": sent.get("retransmits", ""),
            "command": " ".join(command),
            "raw": output,
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"iperf3 JSON could not be parsed ({exc}):\n{output[-2000:]}") from exc

def save_row(row):
    fields = [
        "experiment_id","timestamp_utc","git_commit","configuration","tenant","transport",
        "mss_bytes","payload_bytes","duration_seconds","mtu","offload","sender_mbps",
        "receiver_mbps","retransmissions","latency_ms","packet_loss_percent","status",
        "command","notes"
    ]
    new = not RAW.exists() or RAW.stat().st_size == 0
    with RAW.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()
        os.fsync(f.fileno())

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--mss", type=int, default=1000)
    ap.add_argument("--tenant", choices=["A","B","both"], default="both")
    ap.add_argument("--warmup", type=int, default=1)
    args = ap.parse_args()
    if args.trials < 2 or args.duration < 30:
        ap.error("Use at least 2 trials and 30 seconds; recommended 10 x 30 seconds.")
    if args.mss < 500 or args.mss > 9000:
        ap.error("MSS must be between 500 and 9000 bytes.")
    if os.geteuid() != 0:
        ap.error("Run with sudo: sudo python3 scripts/benchmark.py --trials 10 --duration 30")
    if not os.path.isfile(JSON):
        ap.error("Compiled P4 JSON missing: " + JSON)

    RESULTS.mkdir(exist_ok=True)
    experiment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    commit = subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    net = Mininet(topo=VXLANTopo(), controller=None, autoSetMacs=False)
    try:
        print(f"Starting P4 VXLAN topology; experiment ID {experiment_id}")
        net.start()
        v1, v2 = net.get("vtep1"), net.get("vtep2")
        v1.cmd("ip link set dev vtep1-eth3 address 02:00:00:00:01:01")
        v2.cmd("ip link set dev vtep2-eth3 address 02:00:00:00:01:02")
        hosts = {n: net.get(n) for n in ("h1","h2","h3","h4")}
        for n,h in hosts.items():
            h.cmd(f"ip link set dev {n}-eth0 mtu 1450")
            h.cmd(f"ethtool -K {n}-eth0 tx off 2>/dev/null || true")
        neighbors = [
            ("h1","192.168.10.2","00:00:00:00:10:02"), ("h2","192.168.10.1","00:00:00:00:10:01"),
            ("h3","192.168.20.2","00:00:00:00:20:02"), ("h4","192.168.20.1","00:00:00:00:20:01")]
        for name,ip,mac in neighbors:
            hosts[name].cmd(f"ip neigh replace {ip} lladdr {mac} nud permanent dev {name}-eth0")
        add_rules()
        hosts["h2"].cmd("iperf3 -s -1 > /tmp/iperf3-h2.log 2>&1 &")
        hosts["h4"].cmd("iperf3 -s -1 > /tmp/iperf3-h4.log 2>&1 &")
        time.sleep(1)
        # Explicit routes/neighbours force a real cross-tenant packet attempt.
        hosts["h1"].cmd("ip route replace 192.168.20.2/32 dev h1-eth0")
        hosts["h1"].cmd("ip neigh replace 192.168.20.2 lladdr 00:00:00:00:20:02 nud permanent dev h1-eth0")
        hosts["h3"].cmd("ip route replace 192.168.10.2/32 dev h3-eth0")
        hosts["h3"].cmd("ip neigh replace 192.168.10.2 lladdr 00:00:00:00:10:02 nud permanent dev h3-eth0")

        conditions = [("A",hosts["h1"],"192.168.10.2"),("B",hosts["h3"],"192.168.20.2")]
        if args.tenant != "both":
            conditions = [x for x in conditions if x[0] == args.tenant]

        # Verify baseline functionality before throughput and negative tests.
        for tenant,host,destination in conditions:
            lat,loss,_ = ping_stats(host,destination,count=3)
            if loss != 0:
                raise RuntimeError(f"Positive control failed for Tenant {tenant}: packet loss {loss}%")

        for tenant,host,destination in conditions:
            server = hosts["h2"] if tenant == "A" else hosts["h4"]
            for trial in range(1, args.warmup + args.trials + 1):
                recorded = trial > args.warmup
                try:
                    # iperf3 -s -1 exits after a single client. Restart for each trial.
                    server.cmd("pkill -x iperf3 2>/dev/null || true")
                    server.cmd("iperf3 -s -1 > /tmp/iperf3-server.log 2>&1 &")
                    time.sleep(0.4)
                    result = iperf_result(host,destination,args.duration,args.mss)
                    lat,loss,pingout = ping_stats(host,destination,count=10)
                    row = dict(experiment_id=experiment_id,timestamp_utc=datetime.now(timezone.utc).isoformat(),
                        git_commit=commit,configuration="P4_VXLAN",tenant=tenant,transport="TCP",
                        mss_bytes=args.mss,payload_bytes="",duration_seconds=args.duration,mtu=1450,
                        offload="tx_off",sender_mbps=result["sender_mbps"],receiver_mbps=result["receiver_mbps"],
                        retransmissions=result["retransmissions"],latency_ms=lat,packet_loss_percent=loss,
                        status="success",command=result["command"],notes=("warm-up excluded from analysis" if not recorded else ""))
                    if recorded:
                        save_row(row)
                    label = "warm-up" if not recorded else f"trial {trial-args.warmup}/{args.trials}"
                    print(f"Tenant {tenant} {label}: receiver={result['receiver_mbps']:.3f} Mbps; "
                          f"RTT={lat}; loss={loss}%")
                except Exception as exc:
                    if recorded:
                        save_row(dict(experiment_id=experiment_id,timestamp_utc=datetime.now(timezone.utc).isoformat(),
                            git_commit=commit,configuration="P4_VXLAN",tenant=tenant,transport="TCP",
                            mss_bytes=args.mss,payload_bytes="",duration_seconds=args.duration,mtu=1450,
                            offload="tx_off",status="failed",command="iperf3/ping",notes=str(exc)[:1000]))
                    print(f"Trial failed for Tenant {tenant}: {exc}",file=sys.stderr)
        print("\nRaw per-tenant measurements appended to", RAW)
        print("Analyse with: python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv")
    finally:
        net.stop()

if __name__ == "__main__":
    setLogLevel("warning")
    main()
