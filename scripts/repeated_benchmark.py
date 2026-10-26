#!/usr/bin/env python3
"""Orchestrate repeated TCP measurements across the requested MSS values.

Run from the repository root inside the configured Ubuntu/WSL2 environment:
  sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30
  sudo python3 scripts/repeated_benchmark.py --trials 10 --duration 30 --mss 500 700 900 1100 1300 1400

The script checks the test environment, records tool versions, then launches the
process-local Mininet benchmark once per MSS. Each child writes real per-tenant
measurements into results/repeated_trials.csv. This is only the VXLAN path:
the matched no-VXLAN baseline, UDP payload sweep, crafted spoofing cases, and
multi-tenant scale experiment require separate test modes and are not claimed
to have been measured by this script.
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
BENCHMARK = ROOT / "scripts" / "benchmark.py"

def shell(command):
    p = subprocess.run(["bash", "-lc", command], text=True, capture_output=True)
    return (p.stdout + p.stderr).strip()

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
    parser.add_argument("--trials", type=int, default=10, help="recorded runs per tenant and MSS (default: 10)")
    parser.add_argument("--duration", type=int, default=30, help="seconds per iperf3 run (default: 30)")
    parser.add_argument("--mss", type=int, nargs="+", default=[500, 700, 900, 1100, 1300, 1400],
                        help="TCP MSS values to test as separate conditions")
    parser.add_argument("--tenant", choices=["A", "B", "both"], default="both")
    parser.add_argument("--warmup", type=int, default=1, help="excluded warm-up runs per tenant and MSS")
    parser.add_argument("--preflight-only", action="store_true", help="check tools and record environment without traffic")
    args = parser.parse_args()

    if args.trials < 2 or args.duration < 30:
        parser.error("Use at least 2 trials and 30 seconds per run; recommended 10 x 30 seconds.")
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
        parser.error("Missing build/vxlan.json. Compile src/p4/vxlan.p4 as described in docs/experiments/reproduction.md.")
    if not BENCHMARK.is_file():
        parser.error(f"Benchmark child script missing: {BENCHMARK}")

    RESULTS.mkdir(exist_ok=True)
    snapshot = environment_snapshot()
    snapshot.update({
        "trials_per_condition": args.trials,
        "duration_seconds": args.duration,
        "mss_values_bytes": args.mss,
        "tenant_selection": args.tenant,
        "warmup_runs_excluded": args.warmup,
        "traffic_experiment": "P4_VXLAN only; baseline and security/scale tests are separate",
    })
    ENVIRONMENT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print("Environment metadata recorded in", ENVIRONMENT)
    if args.preflight_only:
        print("Preflight only: no traffic trial was run.")
        return 0

    overall = 0
    for mss in args.mss:
        print(f"\n===== MSS {mss} bytes: {args.trials} recorded trials x {args.duration}s =====", flush=True)
        command = [
            sys.executable, str(BENCHMARK), "--trials", str(args.trials),
            "--duration", str(args.duration), "--mss", str(mss),
            "--tenant", args.tenant, "--warmup", str(args.warmup),
        ]
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            overall = result.returncode
            print(f"Condition MSS={mss} failed at process level; inspect the child output and raw CSV.", file=sys.stderr)
    print("\nCampaign finished. Some individual trials may be recorded with status=failed.")
    print("Raw data: results/repeated_trials.csv")
    print("Summary: python3 scripts/analyze_repeated_trials.py results/repeated_trials.csv")
    print("Reminder: this campaign does not provide the no-VXLAN baseline, UDP payload sweep, spoofing tests, or scale results.")
    return overall

if __name__ == "__main__":
    raise SystemExit(main())
