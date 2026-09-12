#!/usr/bin/env python3
"""
Stage 2: build the facility-year emissions variable Emiss_ft (total tCO2e of facility f in year t) from the cleaned GHGRP file.
Input : data/processed/1_raw_clean/ghgrp_cleaned_v1_20251022.csv
Output: data/processed/3_variables/emiss_ft_v1_20251022.csv
Log   : data/metadata/emiss_variable_log_20251022.txt
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA_DIR = DATA

# Configuration
INPUT_FILE = DATA_DIR / 'processed' / '1_raw_clean' / 'ghgrp_cleaned_v1_20251022.csv'
OUTPUT_FILE = DATA_DIR / 'processed' / '3_variables' / 'emiss_ft_v1_20251022.csv'
METADATA_FILE = DATA_DIR / 'metadata' / 'emiss_variable_log_20251022.txt'

# Ensure output directory exists
os.makedirs(OUTPUT_FILE.parent, exist_ok=True)
os.makedirs(METADATA_FILE.parent, exist_ok=True)

# Analysis period
ANALYSIS_START_YEAR = 2016
ANALYSIS_END_YEAR = 2025

def log_message(msg, print_also=True):
    """Log message to both console and file"""
    with open(METADATA_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

def main():
    # Initialize log file
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Emiss_ft Variable Construction Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting Emiss_ft variable construction")
    log_message(f"Variable definition: Total emissions (tCO2e) for facility f in year t")

    # Step 1: Load cleaned GHGRP data
    log_message("\n[Step 1] Loading cleaned GHGRP data...")
    try:
        df = pd.read_csv(INPUT_FILE)
        log_message(f"OK: Loaded {len(df)} facility-year observations")
    except Exception as e:
        log_message(f"FAILED: Error loading file: {str(e)}")
        sys.exit(1)

    # Step 2: Select relevant columns
    log_message("\n[Step 2] Selecting relevant columns...")

    required_cols = ['ghgrp_id', 'year', 'facility_name', 'company_legal_name',
                     'total_emissions_co2e', 'province', 'naics_code']

    available_cols = [col for col in required_cols if col in df.columns]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        log_message(f"Warning: Missing columns: {missing_cols}")

    df_emiss = df[available_cols].copy()
    log_message(f"OK: Selected {len(available_cols)} columns")

    # Step 3: Standardize column names for output
    log_message("\n[Step 3] Standardizing output column names...")

    column_rename = {
        'ghgrp_id': 'facility_id',
        'year': 'year',
        'facility_name': 'facility_name',
        'company_legal_name': 'company_name',
        'total_emissions_co2e': 'emissions_co2e',
        'province': 'province',
        'naics_code': 'naics_code'
    }

    df_emiss.rename(columns={k: v for k, v in column_rename.items() if k in df_emiss.columns}, inplace=True)
    log_message(f"OK: Columns standardized")

    # Step 4: Validate emissions values
    log_message("\n[Step 4] Data validation...")

    # Check for missing emissions values
    missing_emissions = df_emiss['emissions_co2e'].isnull().sum()
    log_message(f"  - Missing emissions: {missing_emissions} ({100*missing_emissions/len(df_emiss):.2f}%)")

    # Check for negative values (should not occur after cleaning)
    negative_emissions = (df_emiss['emissions_co2e'] < 0).sum()
    if negative_emissions > 0:
        log_message(f"  Warning: {negative_emissions} negative emissions found")
        df_emiss = df_emiss[df_emiss['emissions_co2e'] >= 0]

    # Check for zeros (reasonable for some facilities in some years)
    zero_emissions = (df_emiss['emissions_co2e'] == 0).sum()
    log_message(f"  - Zero emissions: {zero_emissions} ({100*zero_emissions/len(df_emiss):.2f}%)")

    log_message(f"OK: Validation complete: {len(df_emiss)} valid observations")

    # Step 5: Summary statistics
    log_message("\n[Step 5] Summary Statistics (all years)")
    log_message(f"  - Time coverage: {df_emiss['year'].min()} - {df_emiss['year'].max()}")
    log_message(f"  - Facilities (unique): {df_emiss['facility_id'].nunique()}")
    log_message(f"  - Facility-year observations: {len(df_emiss)}")
    log_message(f"  - Total emissions (tCO2e): {df_emiss['emissions_co2e'].sum():,.0f}")
    log_message(f"  - Mean facility emissions: {df_emiss['emissions_co2e'].mean():,.0f}")
    log_message(f"  - Median facility emissions: {df_emiss['emissions_co2e'].median():,.0f}")
    log_message(f"  - Std dev emissions: {df_emiss['emissions_co2e'].std():,.0f}")
    log_message(f"  - Max facility emissions: {df_emiss['emissions_co2e'].max():,.0f}")
    log_message(f"  - Min facility emissions: {df_emiss['emissions_co2e'].min():,.0f}")

    # Step 6: Analysis period summary
    log_message(f"\n[Step 6] Summary Statistics ({ANALYSIS_START_YEAR}-{ANALYSIS_END_YEAR})")
    df_analysis = df_emiss[(df_emiss['year'] >= ANALYSIS_START_YEAR) &
                           (df_emiss['year'] <= ANALYSIS_END_YEAR)].copy()

    log_message(f"  - Observations in analysis period: {len(df_analysis)}")
    log_message(f"  - Facilities in analysis period: {df_analysis['facility_id'].nunique()}")
    log_message(f"  - Total emissions: {df_analysis['emissions_co2e'].sum():,.0f}")
    log_message(f"  - Mean facility emissions: {df_analysis['emissions_co2e'].mean():,.0f}")

    # Step 7: By province summary
    log_message(f"\n[Step 7] Top provinces by emissions ({ANALYSIS_START_YEAR}-{ANALYSIS_END_YEAR})")
    top_provinces = df_analysis.groupby('province')['emissions_co2e'].sum().nlargest(5)
    for prov, emissions in top_provinces.items():
        log_message(f"  - {prov}: {emissions:,.0f} tCO2e")

    # Step 8: Year-by-year trend
    log_message(f"\n[Step 8] Year-by-year emissions trend")
    yearly_emissions = df_emiss.groupby('year')['emissions_co2e'].agg(['sum', 'mean', 'count'])
    log_message(f"  Year | Total (tCO2e) | Mean | Count")
    for year in [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]:
        if year in yearly_emissions.index:
            row = yearly_emissions.loc[year]
            log_message(f"  {year} | {row['sum']:>13,.0f} | {row['mean']:>10,.0f} | {int(row['count']):>5}")

    # Step 9: Save output
    log_message("\n[Step 9] Saving Emiss_ft variable...")

    # Sort by facility and year for clarity
    df_emiss = df_emiss.sort_values(['facility_id', 'year']).reset_index(drop=True)

    try:
        df_emiss.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
        log_message(f"OK: Saved to {OUTPUT_FILE}")
        log_message(f"  - File size: {os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.1f} MB")
    except Exception as e:
        log_message(f"FAILED: Error saving file: {str(e)}")
        sys.exit(1)

    # Final summary
    log_message("\n" + "="*80)
    log_message("OK: Emiss_ft VARIABLE CONSTRUCTION COMPLETED")
    log_message(f"Output: {OUTPUT_FILE}")
    log_message(f"  - {len(df_emiss)} facility-year observations")
    log_message(f"  - {df_emiss['facility_id'].nunique()} unique facilities")
    log_message(f"  - Total emissions: {df_emiss['emissions_co2e'].sum():,.0f} tCO2e")
    log_message("="*80)

if __name__ == "__main__":
    main()
