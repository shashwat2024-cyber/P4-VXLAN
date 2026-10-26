#!/usr/bin/env python3
"""Repeat per-tenant TCP throughput and ping measurements on the P4 VXLAN testbed.

Run from repository root inside the configured Ubuntu/WSL2 environment:
  sudo python3 scripts/benchmark.py --trials 10 --duration 30 --mss 1000

The topology and its hosts live in this Python process. This records only actual
measurements from Mininet/BMv2. It does not implement the no-VXLAN baseline,
crafted VNI spoofing, or scale sweep yet.
"""
import argparse, csv, json, os, re, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mininet.net import Mininet
from mininet.log import setLogLevel
from topology.vxlan_topology import VXLANTopo, JSON, add_rules

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RAW = RESULTS / "repeated_trials.csv"

def ping_stats(host, destination, count=10):
    output = host.cmd(f"ping -c {count} -W 1 {destination}")
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    rtt = re.search(r"=\s*[\d.]+/([\d.]+)/", output)
    if not loss:
        raise RuntimeError("Could not parse ping output:\n" + output[-1500:])
    return (float(rtt.group(1)) if rtt else None, float(loss.group(1)), output)

def iperf_result(client, destination, duration, mss):
    command = ["iperf3", "-c", destination, "-t", str(duration), "-J", "-M", str(mss)]
    output = client.cmd(" ".join(command))
    try:
        obj = json.loads(output)
        end = obj["end"]
        sent = end.get("sum_sent", {})
        received = end.get("sum_received") or end.get("sum")
        if not received:
            raise KeyError("end.sum_received")
        return {
            "sender_mbps": float(sent["bits_per_second"]) / 1e6 if sent.get("bits_per_second") else "",
            "receiver_mbps": float(received["bits_per_second"]) / 1e6,
            "retransmissions": sent.get("retransmits", ""),
            "command": " ".join(command),
            "json": output,
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Unable to parse iperf3 result ({exc}):\n{output[-2000:]}") from exc

def write_row(row):
    fields = ["experiment_id","timestamp_utc","git_commit","configuration","tenant","transport",
              "mss_bytes","payload_bytes","duration_seconds","mtu","offload","sender_mbps",
              "receiver_mbps","retransmissions","latency_ms","packet_loss_percent","status",
              "command","notes"]
    create_header = not RAW.exists() or RAW.stat().st_size == 0
    with RAW.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if create_header:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trials", type=int, default=10)
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--mss", type=int, default=1000)
    p.add_argument("--tenant", choices=["A","B","both"], default="both")
    p.add_argument("--warmup", type=int, default=1)
    args = p.parse_args()
    if args.trials < 2 or args.duration < 30:
        p.error("Use at least 2 trials and 30 seconds per trial; recommended 10 x 30 seconds.")
    if not 500 <= args.mss <= 9000:
        p.error("MSS must be between 500 and 9000 bytes.")
    if os.geteuid() != 0:
        p.error("Run with sudo: sudo python3 scripts/benchmark.py --trials 10 --duration 30")
    if not os.path.isfile(JSON):
        p.error("Compiled P4 JSON missing: " + JSON)

    RESULTS.mkdir(exist_ok=True)
    exp_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    commit = subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    net = Mininet(topo=VXLANTopo(), controller=None, autoSetMacs=False)
    try:
        print(f"Starting P4 VXLAN topology; experiment={exp_id}")
        net.start()
        v1, v2 = net.get("vtep1"), net.get("vtep2")
        v1.cmd("ip link set dev vtep1-eth3 address 02:00:00:00:01:01")
        v2.cmd("ip link set dev vtep2-eth3 address 02:00:00:00:01:02")
        hosts = {name: net.get(name) for name in ("h1","h2","h3","h4")}
        for name, host in hosts.items():
            host.cmd(f"ip link set dev {name}-eth0 mtu 1450")
            host.cmd(f"ethtool -K {name}-eth0 tx off 2>/dev/null || true")
        neighbors = [
            ("h1","192.168.10.2","00:00:00:00:10:02"), ("h2","192.168.10.1","00:00:00:00:10:01"),
            ("h3","192.168.20.2","00:00:00:00:20:02"), ("h4","192.168.20.1","00:00:00:00:20:01")]
        for name, ip, mac in neighbors:
            hosts[name].cmd(f"ip neigh replace {ip} lladdr {mac} nud permanent dev {name}-eth0")
        add_rules()

        # Confirm the permitted paths before measuring them.
        for src, dst in (("h1","192.168.10.2"),("h3","192.168.20.2")):
            _, loss, output = ping_stats(hosts[src], dst, count=3)
            if loss != 0:
                raise RuntimeError(f"Positive control failed before benchmark: {src}->{dst}\n{output}")

        pairs = [("A","h1","h2","192.168.10.2"), ("B","h3","h4","192.168.20.2")]
        if args.tenant != "both":
            pairs = [pair for pair in pairs if pair[0] == args.tenant]

        for tenant, client_name, server_name, destination in pairs:
            client, server = hosts[client_name], hosts[server_name]
            for number in range(1, args.warmup + args.trials + 1):
                measured = number > args.warmup
                label = f"{number-args.warmup}/{args.trials}" if measured else "warm-up"
                try:
                    # Keep all namespace interaction in the process owning Mininet.
                    server.cmd("pkill -x iperf3 2>/dev/null || true")
                    server.cmd("iperf3 -s -1 > /tmp/iperf3-server.log 2>&1 &")
                    time.sleep(0.5)
                    result = iperf_result(client, destination, args.duration, args.mss)
                    latency, loss, _ = ping_stats(client, destination, count=10)
                    print(f"Tenant {tenant} trial {label}: rx={result['receiver_mbps']:.3f} Mbps, RTT={latency}, loss={loss}%")
                    if measured:
                        write_row(dict(
                            experiment_id=exp_id, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                            git_commit=commit, configuration="P4_VXLAN", tenant=tenant, transport="TCP",
                            mss_bytes=args.mss, payload_bytes="", duration_seconds=args.duration, mtu=1450,
                            offload="tx_off", sender_mbps=result["sender_mbps"],
                            receiver_mbps=result["receiver_mbps"], retransmissions=result["retransmissions"],
                            latency_ms=latency, packet_loss_percent=loss, status="success",
                            command=result["command"], notes=""))
                except Exception as exc:
                    print(f"Tenant {tenant} trial {label} failed: {exc}", file=sys.stderr)
                    if measured:
                        write_row(dict(
                            experiment_id=exp_id, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                            git_commit=commit, configuration="P4_VXLAN", tenant=tenant, transport="TCP",
                            mss_bytes=args.mss, payload_bytes="", duration_seconds=args.duration, mtu=1450,
                            offload="tx_off", status="failed", command="iperf3 plus ping",
                            notes=str(exc)[:1200]))
        print(f"Raw trial results appended to {RAW}")
        print("Summary: python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv")
    finally:
        net.stop()

if __name__ == "__main__":
    setLogLevel("warning")
    main()
