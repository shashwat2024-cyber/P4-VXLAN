#!/usr/bin/env python3
"""Summarise raw repeated trial CSVs and calculate a Student-t 95% CI.

No rows are synthesised. Failed trials are excluded from numeric summaries but counted.
The confidence interval uses independent run-level values (not packet-level samples).
"""
import argparse
import csv
import math
import statistics
from collections import defaultdict


# Two-sided 95% Student-t critical values for small sample sizes.
T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def critical_t(df):
    if df in T95:
        return T95[df]
    if df > 30:
        # Normal approximation is conservative enough for larger n as a practical display.
        return 1.96
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path", help="raw trial CSV path")
    ap.add_argument("--metric", default="receiver_mbps")
    ap.add_argument("--group-by", default="configuration,tenant,mss_bytes")
    args = ap.parse_args()

    group_fields = [x.strip() for x in args.group_by.split(",") if x.strip()]
    groups = defaultdict(list)
    failures = defaultdict(int)
    with open(args.csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = set(group_fields + [args.metric, "status"])
        missing = required - set(reader.fieldnames or [])
        if missing:
            ap.error("CSV missing columns: " + ", ".join(sorted(missing)))
        for row in reader:
            key = tuple(row.get(field, "") for field in group_fields)
            if row.get("status", "").lower() != "ok":
                failures[key] += 1
                continue
            try:
                value = float(row[args.metric])
                if math.isfinite(value):
                    groups[key].append(value)
                else:
                    failures[key] += 1
            except (TypeError, ValueError):
                failures[key] += 1

    if not groups:
        print("No valid rows found for metric %s." % args.metric)
        return

    print("metric=%s; CI=two-sided 95%% Student-t interval over independent run-level rows" % args.metric)
    print("Groups: %s" % ", ".join(group_fields))
    print("\t".join(group_fields + [
        "n_valid", "n_failed", "mean", "sd_sample", "ci95_low", "ci95_high", "median"
    ]))
    for key in sorted(set(groups) | set(failures)):
        vals = groups.get(key, [])
        n = len(vals)
        if n == 0:
            stats = ["0", str(failures[key]), "", "", "", "", ""]
        else:
            mean = statistics.mean(vals)
            sd = statistics.stdev(vals) if n > 1 else None
            critical = critical_t(n - 1) if n > 1 else None
            margin = critical * sd / math.sqrt(n) if sd is not None and critical else None
            low = mean - margin if margin is not None else None
            high = mean + margin if margin is not None else None
            stats = [
                str(n), str(failures[key]), "%.6f" % mean,
                "" if sd is None else "%.6f" % sd,
                "" if low is None else "%.6f" % low,
                "" if high is None else "%.6f" % high,
                "%.6f" % statistics.median(vals),
            ]
        print("\t".join(list(key) + stats))
    print("Note: n=1 has no estimable sample SD or confidence interval; >30 uses a normal critical-value approximation.")


if __name__ == "__main__":
    main()
