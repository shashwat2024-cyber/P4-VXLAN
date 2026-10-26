#!/usr/bin/env python3
"""Run repeated, controlled throughput trials for P4 VXLAN and a no-VXLAN baseline.

From Ubuntu/WSL2 at the repository root:
  p4c --target bmv2 --arch v1model -o build/vxlan.json src/p4/vxlan.p4
  p4c --target bmv2 --arch v1model -o build/baseline.json src/p4/baseline.p4
  sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --with-baseline

Each condition runs in a child process that owns its Mininet network. Trials
are recorded as actual results; no synthetic measurements are generated.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
ENVIRONMENT = RESULTS / "environment.json"
VXLAN_BENCH = ROOT / "scripts" / "benchmark.py"
BASELINE_BENCH = ROOT / "scripts" / "baseline_benchmark.py"

def shell(command):
    result = subprocess.run(["bash", "-lc", command], text=True, capture_output=True)
    return (result.stdout + result.stderr).strip()

def environment_snapshot():
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "uname": shell("uname -a"),
        "python": sys.version,
        "p4c": shell("p4c --version"),
        "bmv2": shell("simple_switch --version"),
        "mininet": shell("mn --version"),
        "iperf3": shell("iperf3 --version"),
        "ethtool": shell("ethtool --version"),
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--mss", type=int, nargs="+", default=[500, 700, 900, 1100, 1300, 1400])
    parser.add_argument("--tenant", choices=["A", "B", "both"], default="both")
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--with-baseline", action="store_true",
                        help="also run plain L2 P4 baseline for every MSS condition; requires build/baseline.json")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    if args.trials < 2 or args.duration < 30:
        parser.error("Use at least 2 trials and 30 seconds per run.")
    if args.warmup < 0:
        parser.error("--warmup cannot be negative.")
    if not args.mss or any(m < 500 or m > 9000 for m in args.mss):
        parser.error("Each MSS must be between 500 and 9000 bytes.")
    if len(set(args.mss)) != len(args.mss):
        parser.error("Specify each MSS value only once.")
    if os.geteuid() != 0:
        parser.error("Run with sudo inside Ubuntu/WSL2.")
    missing = [tool for tool in ("mn", "iperf3", "simple_switch", "p4c") if not shell(f"command -v {tool}")]
    if missing:
        parser.error("Missing required tools: " + ", ".join(missing))
    if not (ROOT / "build" / "vxlan.json").is_file():
        parser.error("Missing build/vxlan.json; compile src/p4/vxlan.p4 first.")
    if not VXLAN_BENCH.is_file():
        parser.error(f"Benchmark child script missing: {VXLAN_BENCH}")
    if args.with_baseline and not (ROOT / "build" / "baseline.json").is_file():
        parser.error("--with-baseline requires build/baseline.json; compile src/p4/baseline.p4 first.")

    RESULTS.mkdir(exist_ok=True)
    snapshot = environment_snapshot()
    snapshot.update({
        "trials_per_condition": args.trials,
        "duration_seconds": args.duration,
        "mss_values_bytes": args.mss,
        "tenant_selection": args.tenant,
        "warmup_runs_excluded": args.warmup,
        "with_plain_l2_baseline": args.with_baseline,
        "note": "All trials must run in the configured BMv2/Mininet environment; no data is simulated."
    })
    ENVIRONMENT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print("Environment metadata saved to", ENVIRONMENT)
    if args.preflight_only:
        print("Preflight only; no traffic trial was run.")
        return 0

    overall = 0
    for i, mss in enumerate(args.mss):
        print(f"\n===== MSS {mss} bytes: {args.trials} trials x {args.duration}s =====", flush=True)
        vxlan_command = [sys.executable, str(VXLAN_BENCH), "--trials", str(args.trials),
                         "--duration", str(args.duration), "--mss", str(mss),
                         "--tenant", args.tenant, "--warmup", str(args.warmup)]
        baseline_command = [sys.executable, str(BASELINE_BENCH), "--trials", str(args.trials),
                            "--duration", str(args.duration), "--mss", str(mss),
                            "--tenant", args.tenant, "--warmup", str(args.warmup)]
        # Alternate order across MSS conditions to reduce systematic order bias.
        commands = [vxlan_command, baseline_command] if i % 2 == 0 else [baseline_command, vxlan_command]
        if not args.with_baseline:
            commands = [vxlan_command]
        for command in commands:
            label = "baseline" if str(BASELINE_BENCH) in command else "P4 VXLAN"
            print(f"--- Running {label} condition ---", flush=True)
            result = subprocess.run(command, cwd=ROOT)
            if result.returncode:
                overall = result.returncode
                print(f"{label} MSS={mss} campaign had a process-level failure; inspect output and CSV.", file=sys.stderr)

    print("\nCampaign process completed. Individual trial failures may exist in the raw CSV.")
    print("Raw rows: results/repeated_trials.csv")
    print("Summary: python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv")
    if not args.with_baseline:
        print("Baseline not run; repeat with --with-baseline after compiling build/baseline.json.")
    print("UDP payload, spoofed-VNI, and 8-tenant/multi-VTEP tests remain separate experiments.")
    return overall

if __name__ == "__main__":
    raise SystemExit(main())
