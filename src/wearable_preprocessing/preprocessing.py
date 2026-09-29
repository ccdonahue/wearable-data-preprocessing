"""
Oura Sleep Data Preprocessing
=============================

Utilities for cleaning and restructuring Oura sleep exports,
including sleep-stage sequences and HRV time series.

This script:
    1. Reads raw Oura sleep export files
    2. Cleans headers and malformed rows
    3. Standardizes sleep timestamps
    4. Converts sleep-duration variables from seconds to minutes
    5. Expands encoded sleep-stage sequences
    6. Expands HRV time series
    7. Performs basic data-quality checks
    8. Batch-processes all CSV files in a directory

No study-specific inclusion/exclusion criteria are applied.
"""

from pathlib import Path
import json
import re

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FOLDER = Path("data/raw")
OUTPUT_FOLDER = Path("data/processed")

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# FILE PARSING
# ============================================================

def read_oura_export(path):
    """
    Read a raw Oura sleep export with non-standard formatting.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the raw CSV file.

    Returns
    -------
    pandas.DataFrame
        Parsed Oura sleep data.

    Notes
    -----
    Some Oura exports contain semicolon-delimited records with
    inconsistent quoting and row lengths. This function normalizes
    rows before constructing the DataFrame.
    """

    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    if not lines:
        return pd.DataFrame()

    # ---------------- Header ----------------
    header_line = lines[0]
    data_lines = lines[1:]

    raw_header = header_line.strip('"')
    header_parts = raw_header.split(";")

    clean_header = []

    for header in header_parts:
        header = str(header).strip().strip('"')

        # Remove trailing material introduced by malformed exports
        header = header.split(",")[0]

        clean_header.append(header)

    n_cols = len(clean_header)

    # ---------------- Rows ----------------
    rows = []

    for line in data_lines:

        line_clean = line.strip('"')
        parts = line_clean.split(";")

        # Normalize row length to match header
        if len(parts) < n_cols:
            parts += [None] * (n_cols - len(parts))

        elif len(parts) > n_cols:
            parts = parts[:n_cols]

        rows.append(parts)

    return pd.DataFrame(rows, columns=clean_header)


# ============================================================
# GENERAL CLEANING
# ============================================================

def clean_type_column(df):
    """
    Clean the Oura sleep-record 'type' variable.

    This function does not filter sleep records. All sleep types
    present in the source data are retained.
    """

    df = df.copy()

    if "type" not in df.columns:
        return df

    df["type"] = (
        df["type"]
        .astype(str)
        .str.replace('"', "", regex=False)
        .str.strip()
        .str.split(",")
        .str[0]
        .str.strip()
    )

    return df


def clean_sleep_timestamps(df):
    """
    Clean Oura bedtime variables and convert them to timezone-naive
    pandas datetime objects for compatibility with Excel output.

    The timestamp itself is preserved while timezone information
    is removed.
    """

    df = df.copy()

    timestamp_columns = [
        "bedtime_start",
        "bedtime_end",
    ]

    for col in timestamp_columns:

        if col not in df.columns:
            continue

        cleaned = (
            df[col]
            .astype(str)
            .str.replace('"', "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

        df[col] = pd.to_datetime(
            cleaned,
            errors="coerce",
            utc=True,
        ).dt.tz_localize(None)

    return df


def convert_seconds_to_minutes(df):
    """
    Convert Oura sleep-duration variables from seconds to minutes.
    """

    df = df.copy()

    second_columns = [
        "awake_time",
        "deep_sleep_duration",
        "latency",
        "light_sleep_duration",
        "rem_sleep_duration",
        "total_sleep_duration",
        "sleep_midpoint",
        "time_in_bed",
        "bedtime_start_delta",
        "bedtime_end_delta",
    ]

    for col in second_columns:

        if col not in df.columns:
            continue

        df[col] = (
            pd.to_numeric(df[col], errors="coerce") / 60
        )

    return df


# ============================================================
# SLEEP-STAGE PROCESSING
# ============================================================

def expand_sleep_phase(
    df_in,
    phase_col,
    epoch_seconds,
    keep_original=True,
):
    """
    Expand an encoded sleep-stage sequence into epoch-level columns.

    Parameters
    ----------
    df_in : pandas.DataFrame
        Input sleep DataFrame.

    phase_col : str
        Column containing encoded sleep-stage strings.

    epoch_seconds : int
        Duration represented by each sleep-stage character,
        expressed in seconds.

    keep_original : bool, default=True
        Whether to retain the original encoded column.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing expanded sleep-stage columns.
    """

    if phase_col not in df_in.columns:
        return df_in.copy()

    df = df_in.copy()

    sequences = (
        df[phase_col]
        .fillna("")
        .astype(str)
        .str.replace('"', "", regex=False)
        .str.strip()
    )

    phase_lists = sequences.apply(list).tolist()

    max_len = max(
        (len(phase) for phase in phase_lists),
        default=0,
    )

    for i in range(max_len):

        elapsed_seconds = epoch_seconds * (i + 1)

        col_name = f"sleep_phase_{elapsed_seconds}sec"

        epoch_values = [
            phase[i] if i < len(phase) else None
            for phase in phase_lists
        ]

        df[col_name] = (
            pd.to_numeric(
                pd.Series(epoch_values),
                errors="coerce",
            )
            .astype("Int64")
        )

    if not keep_original:
        df = df.drop(columns=[phase_col])

    return df


# ============================================================
# HRV PROCESSING
# ============================================================

def _extract_hrv_values(value):
    """
    Extract the HRV 'items' array from an Oura HRV field.

    Valid JSON is parsed using the standard json library. A
    fallback parser is used for malformed JSON-like exports.
    """

    if pd.isna(value):
        return []

    text = str(value).strip()

    # --------------------------------------------------------
    # Attempt 1: proper JSON parsing
    # --------------------------------------------------------

    try:

        parsed = json.loads(text)

        if isinstance(parsed, dict):

            values = parsed.get("items", [])

            if isinstance(values, list):
                return values

    except (json.JSONDecodeError, TypeError):
        pass

    # --------------------------------------------------------
    # Attempt 2: fallback for malformed JSON-like strings
    # --------------------------------------------------------

    match = re.search(
        r'"items"\s*:\s*\[(.*?)\]',
        text,
    )

    if not match:
        return []

    item_string = match.group(1)

    values = []

    for item in item_string.split(","):

        item = item.strip().replace('"', "")

        if item.lower() in {
            "",
            "null",
            "none",
            "nan",
        }:
            values.append(None)

        else:
            try:
                values.append(float(item))

            except ValueError:
                values.append(None)

    return values


def expand_hrv(
    df_in,
    hrv_col="hrv",
    interval_minutes=5,
    keep_original=True,
):
    """
    Expand Oura HRV time-series data into interval-level columns.

    Parameters
    ----------
    df_in : pandas.DataFrame
        Input sleep DataFrame.

    hrv_col : str, default="hrv"
        Column containing Oura HRV data.

    interval_minutes : int, default=5
        Sampling interval represented by each HRV value.

    keep_original : bool, default=True
        Whether to retain the original HRV field.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing expanded HRV measurements.
    """

    if hrv_col not in df_in.columns:
        return df_in.copy()

    df = df_in.copy()

    hrv_lists = (
        df[hrv_col]
        .apply(_extract_hrv_values)
        .tolist()
    )

    max_len = max(
        (len(values) for values in hrv_lists),
        default=0,
    )

    for i in range(max_len):

        elapsed_minutes = interval_minutes * (i + 1)

        col_name = f"hrv_{elapsed_minutes}min"

        df[col_name] = [
            values[i] if i < len(values) else None
            for values in hrv_lists
        ]

    if not keep_original:
        df = df.drop(columns=[hrv_col])

    return df


# ============================================================
# BASIC QUALITY CONTROL
# ============================================================

def summarize_missingness(df):
    """
    Summarize missingness for each variable.

    Returns
    -------
    pandas.DataFrame
        Number and percentage of missing observations per variable.
    """

    n_rows = len(df)

    missing = df.isna().sum()

    if n_rows == 0:
        percent_missing = pd.Series(
            0.0,
            index=df.columns,
        )

    else:
        percent_missing = missing / n_rows * 100

    summary = pd.DataFrame(
        {
            "missing_n": missing,
            "missing_percent": percent_missing,
        }
    )

    return (
        summary
        .sort_values("missing_percent", ascending=False)
        .reset_index(names="variable")
    )


def find_duplicate_rows(df):
    """
    Return rows that are exact duplicates.
    """

    return df[df.duplicated(keep=False)].copy()


def flag_out_of_range(
    df,
    column,
    minimum=None,
    maximum=None,
):
    """
    Create a configurable QC flag for values outside a specified range.

    No study-specific thresholds are built into this function.

    Parameters
    ----------
    df : pandas.DataFrame

    column : str
        Variable to evaluate.

    minimum : float, optional
        Minimum acceptable value.

    maximum : float, optional
        Maximum acceptable value.

    Returns
    -------
    pandas.Series
        Boolean indicator where True represents a flagged value.
    """

    if column not in df.columns:
        raise KeyError(
            f"Column '{column}' not found in DataFrame."
        )

    values = pd.to_numeric(
        df[column],
        errors="coerce",
    )

    flag = pd.Series(
        False,
        index=df.index,
    )

    if minimum is not None:
        flag |= values < minimum

    if maximum is not None:
        flag |= values > maximum

    return flag


# ============================================================
# PREPROCESSING PIPELINE
# ============================================================

def clean_oura_sleep_data(df):
    """
    Apply general preprocessing steps to an Oura sleep DataFrame.

    No study-specific inclusion or exclusion criteria are applied.
    """

    df = clean_type_column(df)

    df = clean_sleep_timestamps(df)

    df = convert_seconds_to_minutes(df)

    return df


def process_one_file(
    path,
    output_folder,
):
    """
    Process one raw Oura sleep export and save structured outputs.
    """

    path = Path(path)
    output_folder = Path(output_folder)

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"\nProcessing: {path.name}")

    # ---------------- Read ----------------

    df = read_oura_export(path)

    if df.empty:

        print("  -> File is empty; skipping.")

        return

    # ---------------- Clean ----------------

    df = clean_oura_sleep_data(df)

    # ---------------- Expand time series ----------------

    df_30sec = expand_sleep_phase(
        df,
        phase_col="sleep_phase_30_sec",
        epoch_seconds=30,
    )

    df_5min = expand_sleep_phase(
        df,
        phase_col="sleep_phase_5_min",
        epoch_seconds=300,
    )

    df_hrv = expand_hrv(
        df,
        hrv_col="hrv",
        interval_minutes=5,
    )

    # ---------------- QC summaries ----------------

    missingness = summarize_missingness(df)

    duplicates = find_duplicate_rows(df)

    # ---------------- Save ----------------

    output_path = (
        output_folder
        / f"{path.stem}_sleep_clean.xlsx"
    )

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="clean",
            index=False,
        )

        df_30sec.to_excel(
            writer,
            sheet_name="sleep_30sec",
            index=False,
        )

        df_5min.to_excel(
            writer,
            sheet_name="sleep_5min",
            index=False,
        )

        df_hrv.to_excel(
            writer,
            sheet_name="hrv_5min",
            index=False,
        )

        missingness.to_excel(
            writer,
            sheet_name="missingness",
            index=False,
        )

        duplicates.to_excel(
            writer,
            sheet_name="duplicates",
            index=False,
        )

    print(f"  -> Saved: {output_path}")


# ============================================================
# BATCH PROCESSING
# ============================================================

def process_directory(
    input_folder,
    output_folder,
):
    """
    Process every CSV file within a directory.
    """

    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    csv_files = sorted(
        input_folder.glob("*.csv")
    )

    if not csv_files:

        print(
            f"No CSV files found in: "
            f"{input_folder.resolve()}"
        )

        return

    print(
        f"Found {len(csv_files)} CSV file(s)."
    )

    for path in csv_files:

        try:

            process_one_file(
                path,
                output_folder,
            )

        except Exception as exc:

            print(
                f"  -> ERROR processing "
                f"{path.name}: {exc}"
            )

    print("\nAll files processed.")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    process_directory(
        INPUT_FOLDER,
        OUTPUT_FOLDER,
    )