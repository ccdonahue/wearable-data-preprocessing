# Wearable Data Preprocessing

A reproducible Python workflow for cleaning and restructuring longitudinal wearable sleep and physiologic data.

## Overview

Wearable devices generate intensive longitudinal data that often require substantial preprocessing before they can be used for analysis. Raw exports may contain non-standard formatting, nested time-series fields, variable-length sequences, missing observations, and measurements reported in formats that are not immediately analysis-ready.

This repository demonstrates a Python workflow for preprocessing these data using a synthetic dataset modeled on the structure of an Oura sleep export.

The workflow includes:

- parsing non-standard wearable data exports
- cleaning and standardizing timestamps
- converting sleep-duration variables to analysis-ready units
- restructuring encoded sleep-stage sequences
- extracting interval-level HRV measurements
- preserving the temporal position of missing observations
- summarizing missingness and identifying duplicate records
- batch processing multiple wearable data files

The preprocessing functions are designed to remain separate from study-specific inclusion criteria and analytic decisions.

## Workflow

Raw wearable export  
↓  
File parsing and structural validation  
↓  
Timestamp and unit standardization  
↓  
Sleep-stage and HRV time-series restructuring  
↓  
Data-quality assessment  
↓  
Analysis-ready output

## Example

The demonstration notebook walks through the preprocessing workflow using synthetic wearable data.

[`notebooks/preprocessing_demo.ipynb`](notebooks/preprocessing_demo.ipynb)

For example, HRV measurements stored within a nested field are extracted into their corresponding measurement intervals while retaining missing observations in their original temporal positions.

This prevents later measurements from being inadvertently shifted when intermittent observations are unavailable.

## Repository Structure

```text
wearable-data-preprocessing/
│
├── data/
│   └── raw/
│       └── synthetic_oura_sleep.csv
│
├── notebooks/
│   └── preprocessing_demo.ipynb
│
├── src/
│   └── wearable_preprocessing/
│       ├── __init__.py
│       └── preprocessing.py
│
├── tests/
│   └── test_preprocessing.py
│
├── .gitignore
├── README.md
└── requirements.txt
## Installation

Clone the repository and install the required Python packages:

```bash
pip install -r requirements.txt
```

Requirements include:

- pandas
- openpyxl
- matplotlib
- pytest

## Testing

Automated tests evaluate the core preprocessing functions and the complete raw-to-processed workflow.

Tests currently cover:

- sleep-stage sequence expansion
- unequal sequence lengths and missing epochs
- HRV time-series extraction
- preservation of missing HRV observations
- seconds-to-minutes conversion
- missingness summaries
- configurable range-based quality-control flags
- end-to-end preprocessing and output generation

Run the test suite with:

```bash
python -m pytest -v
```

## Data

All example data included in this repository are synthetically generated and contain no participant or protected health information.

The synthetic dataset is intended only to demonstrate the structure and functionality of the preprocessing workflow.

## Research Context

This repository reflects preprocessing challenges encountered when working with intensive longitudinal wearable data in clinical and behavioral research. My broader research uses wearable-derived sleep, activity, and physiologic measures to characterize recovery following adolescent concussion.

The public code here focuses on generalizable data-processing methods rather than study-specific analytic pipelines or unpublished research methods.

## Author

Catherine Donahue, PhD, ATC

Postdoctoral Research Fellow  
Children's Hospital Colorado / University of Colorado Anschutz Medical Campus

Research interests: wearable and digital health data, intensive longitudinal methods, sleep and 24-hour behavior, and adolescent concussion recovery.