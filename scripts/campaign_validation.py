#!/usr/bin/env python3
"""Validate completeness and uniqueness of measured benchmark trials."""

import csv


CAMPAIGN_CSV_COLUMNS = [
    "campaign_id", "trial_number", "experiment_id", "timestamp_utc",
    "git_commit", "configuration", "tenant", "transport", "mss_bytes",
    "payload_bytes", "duration_seconds", "mtu", "offload", "sender_mbps",
    "receiver_mbps", "retransmissions", "latency_ms", "packet_loss_percent",
    "status", "command", "notes",
]

REQUIRED_COLUMNS = {
    "campaign_id",
    "configuration",
    "tenant",
    "mss_bytes",
    "trial_number",
    "status",
}


def validate_campaign_rows(
    rows,
    campaign_id,
    configurations,
    tenants,
    mss_values,
    trials_per_condition,
):
    """Return a list of validation errors for one campaign's CSV rows."""
    errors = []
    expected_conditions = {
        (config, tenant, str(mss))
        for config in configurations
        for tenant in tenants
        for mss in mss_values
    }
    expected_trial_numbers = {
        str(number) for number in range(1, trials_per_condition + 1)
    }
    seen = {}
    campaign_rows = 0

    for line_number, row in enumerate(rows, start=2):
        #ignore rows belonging to other campaigns.
        if row.get("campaign_id")!= campaign_id:
           continue

        if None in row:
            errors.append(
                f"CSV line {line_number}: extra fields beyond the header"
            )
            continue

        if any(value is None for value in row.values()):
            errors.append(
                f"CSV line {line_number}: missing fields in CSV row"
            )
            continue




        campaign_rows += 1
        condition = (
            row.get("configuration"),
            row.get("tenant"),
            row.get("mss_bytes"),
        )

        if condition not in expected_conditions:
            errors.append(
                f"CSV line {line_number}: unexpected condition {condition}"
            )
            continue

        trial_number = (row.get("trial_number") or "").strip()
        if trial_number not in expected_trial_numbers:
            errors.append(
                f"CSV line {line_number}: invalid trial_number "
                f"{trial_number!r} for {condition}"
            )
            continue

        key = (*condition, trial_number)
        if key in seen:
            errors.append(
                f"Duplicate trial {trial_number} for {condition} "
                f"on CSV lines {seen[key]} and {line_number}"
            )
            continue

        seen[key] = line_number

        status = (row.get("status") or "").strip().lower()
        if status != "success":
            errors.append(
                f"CSV line {line_number}: trial {trial_number} for "
                f"{condition} has status {status!r}, not 'success'"
            )

    if campaign_rows == 0:
        errors.append(f"No rows found for campaign {campaign_id!r}")

    for condition in sorted(expected_conditions):
        for trial_number in sorted(
            expected_trial_numbers, key=int
        ):
            key = (*condition, trial_number)
            if key not in seen:
                errors.append(
                    f"Missing trial {trial_number} for condition {condition}"
                )

    return errors


def validate_campaign_csv(
    path,
    campaign_id,
    configurations,
    tenants,
    mss_values,
    trials_per_condition,
):
    """Validate CSV schema and trial completeness; return error messages."""
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return ["CSV has no header"]

            missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing_columns:
                return [
                    "CSV missing required columns: "
                    + ", ".join(sorted(missing_columns))
                ]
            if reader.fieldnames != CAMPAIGN_CSV_COLUMNS:
                return [
                    "CSV header does not match the campaign schema. "
                    "Use a separate output file rather than mixing schemas."
                ]

            return validate_campaign_rows(
                reader,
                campaign_id,
                configurations,
                tenants,
                mss_values,
                trials_per_condition,
            )
    except (OSError, csv.Error) as exc:
        return [f"Unable to read campaign CSV: {exc}"]


def validate_campaign_schema(path):
    """Check an existing output file's header without requiring campaign rows."""
    from pathlib import Path

    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
        if header != CAMPAIGN_CSV_COLUMNS:
            return [
                f"CSV header mismatch in {path}; expected the campaign schema. "
                "Choose a new output file; existing data was not changed."
            ]
        return []
    except (OSError, csv.Error) as exc:
        return [f"Unable to validate campaign CSV schema: {exc}"]
