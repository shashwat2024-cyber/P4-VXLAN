#!/usr/bin/env python3

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/udp_rss_analysis"
OUT.mkdir(parents=True, exist_ok=True)

DATASETS = {
    "scalability": (
        ROOT / "results/scalability/udp_scalability_rss_full_20261101.csv",
        "target_mbps",
    ),
    "payload": (
        ROOT / "results/scalability/udp_payload_sweep/udp_payload_rss_full_20261101.csv",
        "datagram_bytes",
    ),
}

METRICS = [
    "receiver_mbps",
    "udp_loss_percent",
    "under_load_rtt_mean_ms",
    "under_load_rtt_max_ms",
    "rss_mean_total_mib",
    "rss_peak_total_mib",
    "rss_mean_per_process_mib",
    "rss_peak_per_process_mib",
    "latency_ms",
    "jitter_ms",
]

BOOTSTRAP_REPLICATES = 20000
BOOTSTRAP_SEED = 20261101

# All metrics in this experiment are non-negative quantities.
LOWER_BOUND = 0.0


def clean_values(series):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return values.to_numpy(dtype=float)


def describe(series, rng):
    """Descriptive statistics with a percentile bootstrap CI for the mean."""
    x = clean_values(series)
    n = len(x)

    if n == 0:
        return {
            "n": 0,
            "mean": np.nan,
            "std": np.nan,
            "ci95_low": np.nan,
            "ci95_high": np.nan,
            "ci_method": "percentile_bootstrap",
        }

    mean = float(np.mean(x))
    sd = float(np.std(x, ddof=1)) if n > 1 else np.nan

    if n == 1:
        ci_low = np.nan
        ci_high = np.nan
    elif sd == 0:
        # Identical observations produce a degenerate bootstrap interval.
        ci_low = mean
        ci_high = mean
    else:
        indices = rng.integers(
            0, n, size=(BOOTSTRAP_REPLICATES, n)
        )
        bootstrap_means = x[indices].mean(axis=1)

        ci_low, ci_high = np.quantile(
            bootstrap_means, [0.025, 0.975]
        )

    # Numerical protection; all recorded metrics are non-negative.
    ci_low = max(LOWER_BOUND, float(ci_low)) if np.isfinite(ci_low) else np.nan
    ci_high = max(LOWER_BOUND, float(ci_high)) if np.isfinite(ci_high) else np.nan

    return {
        "n": n,
        "mean": mean,
        "std": sd,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "ci_method": "percentile_bootstrap",
    }


def welch_test(a, b):
    """Welch test with explicit handling of constant samples."""
    a = clean_values(a)
    b = clean_values(b)

    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan, "insufficient_samples"

    var_a = np.var(a, ddof=1)
    var_b = np.var(b, ddof=1)

    if var_a == 0 and var_b == 0:
        if np.mean(a) == np.mean(b):
            return 0.0, 1.0, "both_groups_constant_and_equal"
        return np.nan, np.nan, "both_groups_constant_but_different"

    result = stats.ttest_ind(a, b, equal_var=False)

    if not np.isfinite(result.statistic) or not np.isfinite(result.pvalue):
        return result.statistic, result.pvalue, "test_not_estimable"

    return float(result.statistic), float(result.pvalue), "ok"


def holm_adjust(p_values):
    """Holm-Bonferroni adjusted p-values; NaNs remain NaN."""
    p_values = np.asarray(p_values, dtype=float)
    adjusted = np.full(p_values.shape, np.nan, dtype=float)

    valid_indices = np.flatnonzero(np.isfinite(p_values))
    if len(valid_indices) == 0:
        return adjusted

    order = valid_indices[np.argsort(p_values[valid_indices])]
    m = len(order)
    running_max = 0.0

    for rank, index in enumerate(order):
        multiplier = m - rank
        candidate = multiplier * p_values[index]
        running_max = max(running_max, candidate)
        adjusted[index] = min(1.0, running_max)

    return adjusted


def analyse(name, path, factor, rng):
    df = pd.read_csv(path)

    required = {"status", "tenant", factor}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name}: missing required columns: {sorted(missing)}")

    if not (df["status"] == "success").all():
        raise ValueError(f"{name}: failed or incomplete trials found.")

    if not set(df["tenant"].dropna().unique()).issubset({"A", "B"}):
        raise ValueError(f"{name}: unexpected tenant labels found.")

    summary_rows = []
    test_rows = []

    for level, subset in df.groupby(factor, sort=True):
        for tenant, tenant_df in subset.groupby("tenant"):
            for metric in METRICS:
                if metric not in df.columns:
                    continue

                values = describe(tenant_df[metric], rng)
                summary_rows.append({
                    "dataset": name,
                    "factor": factor,
                    "level": level,
                    "tenant": tenant,
                    "metric": metric,
                    **values,
                })

        for metric in METRICS:
            if metric not in df.columns:
                continue

            a = subset.loc[subset["tenant"] == "A", metric]
            b = subset.loc[subset["tenant"] == "B", metric]

            a_values = clean_values(a)
            b_values = clean_values(b)

            t_stat, p_value, test_status = welch_test(a, b)

            mean_a = float(np.mean(a_values)) if len(a_values) else np.nan
            mean_b = float(np.mean(b_values)) if len(b_values) else np.nan

            test_rows.append({
                "dataset": name,
                "factor": factor,
                "level": level,
                "metric": metric,
                "n_A": len(a_values),
                "n_B": len(b_values),
                "tenant_A_mean": mean_a,
                "tenant_B_mean": mean_b,
                "difference_A_minus_B": mean_a - mean_b,
                "welch_t": t_stat,
                "p_value": p_value,
                "test_status": test_status,
            })

    summary = pd.DataFrame(summary_rows)
    tests = pd.DataFrame(test_rows)

    # Correct the complete family of tenant comparisons within this dataset.
    tests["holm_adjusted_p_value"] = holm_adjust(tests["p_value"])

    tests["holm_significant_0_05"] = (
        tests["holm_adjusted_p_value"] < 0.05
    )

    summary.to_csv(OUT / f"{name}_summary.csv", index=False)
    tests.to_csv(OUT / f"{name}_welch_tests.csv", index=False)

    # Generate one comparison graph per metric.
    for metric in METRICS:
        if metric not in df.columns:
            continue

        plot_data = summary[summary["metric"] == metric]
        if plot_data.empty:
            continue

        levels = sorted(plot_data["level"].unique())
        x = np.arange(len(levels))
        width = 0.34

        fig, ax = plt.subplots(figsize=(9, 5))

        for offset, tenant in [(-width / 2, "A"), (width / 2, "B")]:
            part = (
                plot_data[plot_data["tenant"] == tenant]
                .set_index("level")
                .reindex(levels)
            )

            means = part["mean"].to_numpy(dtype=float)
            lower = part["ci95_low"].to_numpy(dtype=float)
            upper = part["ci95_high"].to_numpy(dtype=float)

            lower_error = np.maximum(0, means - lower)
            upper_error = np.maximum(0, upper - means)

            errors = np.vstack([lower_error, upper_error])

            ax.bar(
                x + offset,
                means,
                width,
                yerr=errors,
                capsize=4,
                label=f"Tenant {tenant}",
            )

        ax.set_xticks(x)
        ax.set_xticklabels([str(v) for v in levels])
        ax.set_xlabel(factor)
        ax.set_ylabel(metric)
        ax.set_title(f"{name.title()}: {metric}")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()

        fig.savefig(
            OUT / f"{name}_{metric}.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)

    print(f"\n{name.upper()} ANALYSIS")
    print("-" * 65)
    print("Rows:", len(df))
    print("Successful:", (df["status"] == "success").sum())
    print("Factor:", factor)
    print("\nDescriptive summary:")
    print(summary.to_string(index=False))
    print("\nWelch tests with Holm correction:")
    print(tests.to_string(index=False))


def main():
    rng = np.random.default_rng(BOOTSTRAP_SEED)

    for name, (path, factor) in DATASETS.items():
        if not path.exists():
            raise FileNotFoundError(path)
        analyse(name, path, factor, rng)

    print("\nAnalysis completed.")
    print("Bootstrap replicates:", BOOTSTRAP_REPLICATES)
    print("Bootstrap seed:", BOOTSTRAP_SEED)
    print("Output directory:", OUT)


if __name__ == "__main__":
    main()
