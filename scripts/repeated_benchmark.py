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
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from campaign_validation import validate_campaign_csv, validate_campaign_schema

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
    parser.add_argument("--output", default=None, help="CSV output path")
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
    campaign_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + __import__("uuid").uuid4().hex[:8]
    output_csv = Path(args.output) if args.output else RESULTS / "final_tcp_trials.csv"
    if not output_csv.is_absolute():
        output_csv = ROOT / output_csv
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_csv = RESULTS / f"final_tcp_trials_summary_{campaign_id}.csv"
    schema_errors = validate_campaign_schema(output_csv)
    if schema_errors:
        for error in schema_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    configurations = ["P4_VXLAN"] + (["P4_L2_BASELINE"] if args.with_baseline else [])
    tenants = ["A", "B"] if args.tenant == "both" else [args.tenant]
    expected_rows = len(configurations) * len(tenants) * len(args.mss) * args.trials
    measured_seconds = expected_rows * args.duration
    warmup_seconds = len(configurations) * len(tenants) * len(args.mss) * args.warmup * args.duration

    print(f"Campaign ID: {campaign_id}")
    print(f"Campaign CSV: {output_csv}")
    print(f"Expected measured rows: {expected_rows}")
    print(f"Estimated traffic: {measured_seconds / 3600:.2f} hours measured + "
          f"{warmup_seconds / 60:.1f} minutes warm-up, plus setup/teardown.")

    snapshot = environment_snapshot()
    snapshot.update({
        "campaign_id": campaign_id,
        "output_csv": str(output_csv.relative_to(ROOT)),
        "expected_measured_rows": expected_rows,
        "configurations": configurations,
        "trials_per_condition": args.trials,
        "duration_seconds": args.duration,
        "mss_values_bytes": args.mss,
        "tenant_selection": args.tenant,
        "warmup_runs_excluded": args.warmup,
        "with_plain_l2_baseline": args.with_baseline,
        "estimated_measured_traffic_seconds": measured_seconds,
        "estimated_warmup_traffic_seconds": warmup_seconds,
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
        common = [
            "--trials", str(args.trials),
            "--duration", str(args.duration),
            "--mss", str(mss),
            "--tenant", args.tenant,
            "--warmup", str(args.warmup),
            "--campaign-id", campaign_id,
            "--output", str(output_csv),
        ]
        vxlan_command = [sys.executable, str(VXLAN_BENCH), *common]
        baseline_command = [sys.executable, str(BASELINE_BENCH), *common]

        # Alternate order across MSS conditions to reduce systematic order bias.
        commands = [vxlan_command, baseline_command] if i % 2 == 0 else [baseline_command, vxlan_command]
        if not args.with_baseline:
            commands = [vxlan_command]

        for command in commands:
            label = "baseline" if str(BASELINE_BENCH) in command else "P4 VXLAN"
            print(f"--- Running {label} condition ---", flush=True)
            process = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
            try:
                returncode = process.wait()
            except KeyboardInterrupt:
                overall = 130
                print(
                    f"Campaign interrupted while running {label} at MSS={mss}; "
                    "sending interrupt and waiting for child cleanup.",
                    file=sys.stderr,
                    flush=True,
                )
                # The child has its own process group. Signal the group so
                # benchmark subprocesses can also respond to interruption.
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass

                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    print(
                        "Child group did not exit after Ctrl+C; sending terminate.",
                        file=sys.stderr,
                        flush=True,
                    )
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass

                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(
                            "Child still running; sending kill to its process group.",
                            file=sys.stderr,
                            flush=True,
                        )
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                break

            if returncode:
                overall = 1
                print(
                    f"{label} MSS={mss} had a process-level failure "
                    f"(exit code {returncode}); stopping further benchmark runs.",
                    file=sys.stderr,
                )
                break

        if overall:
            break

    print("\n===== CAMPAIGN COMPLETENESS CHECK =====", flush=True)
    validation_errors = validate_campaign_csv(
        output_csv,
        campaign_id,
        configurations,
        tenants,
        args.mss,
        args.trials,
    )
    if validation_errors:
        for error in validation_errors:
            print(f"VALIDATION ERROR: {error}", file=sys.stderr)
        overall = 1
    else:
        print("PASS: every expected measured trial is present, unique, and successful.")

    if overall == 0:
        analyzer = ROOT / "scripts" / "analyze_repeated_trials.py"
        analysis = subprocess.run(
            [
                sys.executable, str(analyzer), str(output_csv),
                "--campaign-id", campaign_id,
                "--output", str(summary_csv),
            ],
            cwd=ROOT
        )
        if analysis.returncode:
            print("ERROR: campaign analysis failed.", file=sys.stderr)
            overall = 1

    print(f"Campaign CSV: {output_csv.relative_to(ROOT)}")
    if summary_csv.exists():
        print(f"Campaign summary: {summary_csv.relative_to(ROOT)}")
    else:
        print("Campaign summary not generated (campaign incomplete or analysis did not run).")
    if not args.with_baseline:
        print("Baseline was not run; this campaign measures P4 VXLAN only.")
    print("UDP payload, spoofed-VNI, and 8-tenant/multi-VTEP tests remain separate experiments.")
    return overall

if __name__ == "__main__":
    raise SystemExit(main())
