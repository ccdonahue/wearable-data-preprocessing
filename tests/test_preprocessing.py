import pandas as pd
from pathlib import Path

from src.wearable_preprocessing.preprocessing import (
    expand_sleep_phase,
    expand_hrv,
    convert_seconds_to_minutes,
    summarize_missingness,
    flag_out_of_range,
    process_one_file,
)


# ------------------------------------------------------------
# Sleep-stage expansion
# ------------------------------------------------------------

def test_expand_sleep_phase():

    df = pd.DataFrame({
        "sleep_phase_30_sec": [
            "1234",
            "4321"
        ]
    })

    result = expand_sleep_phase(
        df,
        phase_col="sleep_phase_30_sec",
        epoch_seconds=30,
    )

    assert result["sleep_phase_30sec"].tolist() == [1, 4]
    assert result["sleep_phase_60sec"].tolist() == [2, 3]
    assert result["sleep_phase_90sec"].tolist() == [3, 2]
    assert result["sleep_phase_120sec"].tolist() == [4, 1]


def test_expand_sleep_phase_unequal_lengths():

    df = pd.DataFrame({
        "sleep_phase_30_sec": [
            "1234",
            "12"
        ]
    })

    result = expand_sleep_phase(
        df,
        phase_col="sleep_phase_30_sec",
        epoch_seconds=30,
    )

    assert result.loc[0, "sleep_phase_120sec"] == 4

    assert pd.isna(
        result.loc[1, "sleep_phase_120sec"]
    )


# ------------------------------------------------------------
# HRV expansion
# ------------------------------------------------------------

def test_expand_hrv():

    df = pd.DataFrame({
        "hrv": [
            '{"items": [45, 50, 55], "timestamp": "example"}',
            '{"items": [60, null, 70], "timestamp": "example"}'
        ]
    })

    result = expand_hrv(
        df,
        hrv_col="hrv",
        interval_minutes=5,
    )

    assert result.loc[0, "hrv_5min"] == 45
    assert result.loc[0, "hrv_10min"] == 50
    assert result.loc[0, "hrv_15min"] == 55

    assert result.loc[1, "hrv_5min"] == 60
    assert pd.isna(result.loc[1, "hrv_10min"])
    assert result.loc[1, "hrv_15min"] == 70


# ------------------------------------------------------------
# Unit conversion
# ------------------------------------------------------------

def test_seconds_to_minutes():

    df = pd.DataFrame({
        "total_sleep_duration": [21600, 25200],
        "awake_time": [1800, 3600],
    })

    result = convert_seconds_to_minutes(df)

    assert result["total_sleep_duration"].tolist() == [360, 420]
    assert result["awake_time"].tolist() == [30, 60]


# ------------------------------------------------------------
# Missingness
# ------------------------------------------------------------

def test_missingness_summary():

    df = pd.DataFrame({
        "sleep": [400, None, 450, None],
        "hrv": [50, 55, 60, 65],
    })

    result = summarize_missingness(df)

    sleep_row = result[
        result["variable"] == "sleep"
    ].iloc[0]

    hrv_row = result[
        result["variable"] == "hrv"
    ].iloc[0]

    assert sleep_row["missing_n"] == 2
    assert sleep_row["missing_percent"] == 50

    assert hrv_row["missing_n"] == 0
    assert hrv_row["missing_percent"] == 0


# ------------------------------------------------------------
# Configurable QC flag
# ------------------------------------------------------------

def test_out_of_range_flag():

    df = pd.DataFrame({
        "sleep_efficiency": [
            92,
            85,
            105,
            -5
        ]
    })

    result = flag_out_of_range(
        df,
        column="sleep_efficiency",
        minimum=0,
        maximum=100,
    )

    assert result.tolist() == [
        False,
        False,
        True,
        True,
    ]

# ------------------------------------------------------------
# Full preprocessing pipeline
# ------------------------------------------------------------

def test_full_preprocessing_pipeline(tmp_path):

    # Create temporary folders for the test
    raw_folder = tmp_path / "raw"
    output_folder = tmp_path / "processed"

    raw_folder.mkdir()
    output_folder.mkdir()

    # Create a synthetic Oura-like raw file
    synthetic_file = raw_folder / "synthetic_oura_sleep.csv"

    header = (
        '"type;bedtime_start;bedtime_end;awake_time;'
        'deep_sleep_duration;light_sleep_duration;'
        'rem_sleep_duration;total_sleep_duration;'
        'time_in_bed;sleep_phase_30_sec;'
        'sleep_phase_5_min;hrv"'
    )

    rows = [
        (
            '"long_sleep;2026-01-01T23:00:00.000+00:00;'
            '2026-01-02T07:00:00.000+00:00;1800;'
            '5400;12600;5400;23400;28800;'
            '12341234;1234;'
            '{"items": [45, 50, 55], "timestamp": "example"}"'
        ),
        (
            '"long_sleep;2026-01-02T23:30:00.000+00:00;'
            '2026-01-03T07:15:00.000+00:00;2400;'
            '4800;12000;5100;21900;27900;'
            '123412;123;'
            '{"items": [60, null, 70], "timestamp": "example"}"'
        ),
        (
            '"rest;2026-01-03T14:00:00.000+00:00;'
            '2026-01-03T14:30:00.000+00:00;300;'
            '0;1200;0;1200;1800;'
            '1212;12;'
            '{"items": [52, 54], "timestamp": "example"}"'
        ),
    ]

    with synthetic_file.open(
        "w",
        encoding="utf-8",
    ) as f:

        f.write(header + "\n")

        for row in rows:
            f.write(row + "\n")

    # Run the complete preprocessing pipeline
    process_one_file(
        synthetic_file,
        output_folder,
    )

    # Confirm that an output workbook was created
    output_file = (
        output_folder
        / "synthetic_oura_sleep_sleep_clean.xlsx"
    )

    assert output_file.exists()

    # --------------------------------------------------------
    # Check cleaned data
    # --------------------------------------------------------

    clean = pd.read_excel(
        output_file,
        sheet_name="clean",
    )

    # All three records should be retained
    assert len(clean) == 3

    # Generic preprocessing should not remove non-long-sleep records
    assert clean["type"].tolist() == [
        "long_sleep",
        "long_sleep",
        "rest",
    ]

    # Seconds should have been converted to minutes
    assert clean.loc[0, "total_sleep_duration"] == 390
    assert clean.loc[0, "awake_time"] == 30
    assert clean.loc[0, "time_in_bed"] == 480

    # --------------------------------------------------------
    # Check sleep-stage expansion
    # --------------------------------------------------------

    sleep = pd.read_excel(
        output_file,
        sheet_name="sleep_30sec",
    )

    assert sleep.loc[0, "sleep_phase_30sec"] == 1
    assert sleep.loc[0, "sleep_phase_60sec"] == 2
    assert sleep.loc[0, "sleep_phase_90sec"] == 3
    assert sleep.loc[0, "sleep_phase_120sec"] == 4

    # Shorter sequence should remain missing rather than being
    # shifted or filled
    assert pd.isna(
        sleep.loc[2, "sleep_phase_150sec"]
    )

    # --------------------------------------------------------
    # Check HRV expansion
    # --------------------------------------------------------

    hrv = pd.read_excel(
        output_file,
        sheet_name="hrv_5min",
    )

    assert hrv.loc[0, "hrv_5min"] == 45
    assert hrv.loc[0, "hrv_10min"] == 50
    assert hrv.loc[0, "hrv_15min"] == 55

    # Missing HRV value must preserve temporal position
    assert hrv.loc[1, "hrv_5min"] == 60
    assert pd.isna(hrv.loc[1, "hrv_10min"])
    assert hrv.loc[1, "hrv_15min"] == 70