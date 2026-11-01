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
from measurement_utils import SimpleSwitchRSSMonitor, SimpleSwitchCPUMonitor, run_with_rss_monitor
from mininet.net import Mininet
from mininet.log import setLogLevel
from topology.vxlan_topology import VXLANTopo, JSON, add_rules

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RAW = RESULTS / "repeated_trials_v2.csv"  # default for standalone legacy runs


def write_cpu_measurement(monitor, summary, campaign_id, trial_number,
                          experiment_id, tenant, duration_seconds):
    """Append raw CPU samples and one summary row for a measured trial."""
    if monitor is None or summary is None:
        return

    out_dir = RESULTS / "cpu_utilisation_20261101"
    out_dir.mkdir(parents=True, exist_ok=True)

    sample_path = out_dir / "vxlan_cpu_samples.csv"
    trial_path = out_dir / "vxlan_cpu_trials.csv"

    metadata = {
        "campaign_id": campaign_id,
        "trial_number": trial_number,
        "experiment_id": experiment_id,
        "configuration": "P4_VXLAN",
        "tenant": tenant,
        "duration_seconds": duration_seconds,
    }

    sample_fields = [
        "campaign_id", "trial_number", "experiment_id", "configuration",
        "tenant", "duration_seconds", "timestamp_utc", "elapsed_seconds",
        "pid", "process", "process_cpu_percent_one_core",
        "sample_interval_seconds",
    ]
    trial_fields = [
        "campaign_id", "trial_number", "experiment_id", "configuration",
        "tenant", "duration_seconds", "cpu_sample_count",
        "cpu_sample_interval_ms", "cpu_mean_aggregate_percent_one_core",
        "cpu_peak_aggregate_percent_one_core", "cpu_process_sample_count",
    ]

    write_header = not sample_path.exists() or sample_path.stat().st_size == 0
    with sample_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sample_fields)
        if write_header:
            writer.writeheader()
        for sample in monitor.samples:
            writer.writerow({**metadata, **sample})

    write_header = not trial_path.exists() or trial_path.stat().st_size == 0
    with trial_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=trial_fields)
        if write_header:
            writer.writeheader()
        writer.writerow({**metadata, **summary})

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
    fields = ["campaign_id","trial_number","experiment_id","timestamp_utc","git_commit","configuration","tenant","transport",
              "mss_bytes","payload_bytes","duration_seconds","mtu","offload","sender_mbps",
              "receiver_mbps","retransmissions","latency_ms","packet_loss_percent","rss_sample_count","rss_mean_total_mib","rss_peak_total_mib","rss_mean_per_process_mib","rss_peak_per_process_mib","rss_sample_interval_ms","status",
              "command","notes"]
    create_header = not RAW.exists() or RAW.stat().st_size == 0
    if not create_header:
        with RAW.open("r", newline="", encoding="utf-8-sig") as existing:
            existing_header = next(csv.reader(existing), None)
        if existing_header != fields:
            raise RuntimeError(f"CSV header mismatch in {RAW}; choose a new output file.")
    with RAW.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if create_header:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trials", type=int, default=10)
    p.add_argument(
        "--trial-start",
        type=int,
        default=None,
        help="Original trial number to start from (for targeted recovery runs)."
    )
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--mss", type=int, default=1000)
    p.add_argument("--tenant", choices=["A","B","both"], default="both")
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--campaign-id", default=None)
    p.add_argument("--output", default=None, help="CSV output path")
    args = p.parse_args()
    if args.trials < 1 or args.duration < 30:
        p.error("Use at least 1 trial and 30 seconds per trial.")
    if args.trial_start is not None and args.trial_start < 1:
        p.error("--trial-start must be at least 1.")
    if not 500 <= args.mss <= 9000:
        p.error("MSS must be between 500 and 9000 bytes.")
    if os.geteuid() != 0:
        p.error("Run with sudo: sudo python3 scripts/benchmark.py --trials 10 --duration 30")
    if not os.path.isfile(JSON):
        p.error("Compiled P4 JSON missing: " + JSON)

    RESULTS.mkdir(exist_ok=True)
    campaign_id = args.campaign_id or ("standalone-" + uuid.uuid4().hex[:12])
    global RAW
    if args.output:
        output_path = Path(args.output)
        RAW = output_path if output_path.is_absolute() else ROOT / output_path
    RAW.parent.mkdir(parents=True, exist_ok=True)
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
            warmup_count = args.warmup if args.trial_start is None else 0

            for number in range(1, warmup_count + args.trials + 1):
                trial_number = (
                    number - warmup_count
                    if args.trial_start is None
                    else args.trial_start + number - 1
                )
                measured = number > warmup_count
                label = f"{trial_number}"
                rss_monitor = SimpleSwitchRSSMonitor(interval_seconds=0.5) if measured else None
                cpu_monitor = SimpleSwitchCPUMonitor(interval_seconds=1.0) if measured else None
                rss_data = {
                    "rss_sample_count": 0,
                    "rss_mean_total_mib": None,
                    "rss_peak_total_mib": None,
                    "rss_mean_per_process_mib": None,
                    "rss_peak_per_process_mib": None,
                    "rss_sample_interval_ms": 500,
                }
                try:
                    # Keep all namespace interaction in the process owning Mininet.
                    server.cmd("pkill -x iperf3 2>/dev/null || true")
                    server.cmd("iperf3 -s -1 > /tmp/iperf3-server.log 2>&1 &")
                    time.sleep(0.8)
                    # Fail quickly with server evidence rather than recording a
                    # mysterious client connection error if startup failed.
                    if "iperf3" not in server.cmd("pgrep -a iperf3 || true"):
                        raise RuntimeError("iperf3 server did not start: " +
                                           server.cmd("cat /tmp/iperf3-server.log 2>/dev/null"))
                    result, measured_rss, measured_cpu = run_with_rss_monitor(
                        rss_monitor, iperf_result,
                        client, destination, args.duration, args.mss,
                        cpu_monitor=cpu_monitor
                    )
                    if measured_rss is not None:
                        rss_data = measured_rss
                    if measured_cpu is not None:
                        write_cpu_measurement(
                            cpu_monitor, measured_cpu, campaign_id,
                            trial_number, exp_id, tenant, args.duration
                        )
                    latency, loss, _ = ping_stats(client, destination, count=10)
                    print(f"Tenant {tenant} trial {label}: rx={result['receiver_mbps']:.3f} Mbps, RTT={latency}, loss={loss}%")
                    if measured:
                        write_row(dict(
                            campaign_id=campaign_id, trial_number=trial_number, experiment_id=exp_id, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                            git_commit=commit, configuration="P4_VXLAN", tenant=tenant, transport="TCP",
                            mss_bytes=args.mss, payload_bytes="", duration_seconds=args.duration, mtu=1450,
                            offload="tx_off", sender_mbps=result["sender_mbps"],
                            receiver_mbps=result["receiver_mbps"], retransmissions=result["retransmissions"],
                            latency_ms=latency, packet_loss_percent=loss, **rss_data, status="success",
                            command=result["command"], notes=""))
                except Exception as exc:
                    print(f"Tenant {tenant} trial {label} failed: {exc}", file=sys.stderr)
                    if measured:
                        if rss_monitor is not None:
                            rss_data = rss_monitor.summary()
                            rss_data["rss_sample_interval_ms"] = 500
                        write_row(dict(
                            campaign_id=campaign_id, trial_number=trial_number, experiment_id=exp_id, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                            git_commit=commit, configuration="P4_VXLAN", tenant=tenant, transport="TCP",
                            mss_bytes=args.mss, payload_bytes="", duration_seconds=args.duration, mtu=1450,
                            offload="tx_off", **rss_data, status="failed", command="iperf3 plus ping",
                            notes=str(exc)[:1200]))
        print(f"Raw trial results appended to {RAW}")
        print("Summary: python3 scripts/analyze_repeated_trials.py results/repeated_trials_v2.csv")
    finally:
        # Preserve the original exception (including Ctrl+C) if cleanup also fails.
        original_exception_active = sys.exc_info()[0] is not None
        try:
            net.stop()
        except Exception as cleanup_error:
            print(
                f"WARNING: Mininet cleanup failed: {cleanup_error}",
                file=sys.stderr,
            )
            if not original_exception_active:
                raise

if __name__ == "__main__":
    setLogLevel("warning")
    main()
