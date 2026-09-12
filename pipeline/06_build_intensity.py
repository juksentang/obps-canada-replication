#!/usr/bin/env python3
"""
Stage 2: aggregate facility emissions to NAICS-province-year cells, the numerator of the sector emission
intensity (emissions / sector GDP); the GDP denominator is merged in a later step.
Input : data/processed/3_variables/emiss_ft_v1_20251022.csv
Output: data/processed/3_variables/intensity_ft_v1_20251022.csv
Log   : data/metadata/intensity_variable_log_20251022.txt
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
EMISS_FILE = DATA_DIR / 'processed' / '3_variables' / 'emiss_ft_v1_20251022.csv'
OUTPUT_FILE = DATA_DIR / 'processed' / '3_variables' / 'intensity_ft_v1_20251022.csv'
METADATA_FILE = DATA_DIR / 'metadata' / 'intensity_variable_log_20251022.txt'

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
        f.write(f"Intensity_ft Variable Construction Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting Intensity_ft variable construction")
    log_message(f"Variable definition: Emission intensity (tCO2e per unit output)")

    # Step 1: Load Emiss_ft variable
    log_message("\n[Step 1] Loading Emiss_ft variable...")
    try:
        df_emiss = pd.read_csv(EMISS_FILE)
        log_message(f"OK: Loaded {len(df_emiss)} facility-year observations")
    except Exception as e:
        log_message(f"FAILED: Error loading file: {str(e)}")
        sys.exit(1)

    # Step 2: Aggregate to industry-year level
    log_message("\n[Step 2] Aggregating to industry-year level...")

    # Check for NAICS code
    if 'naics_code' not in df_emiss.columns:
        log_message("FAILED: NAICS code column not found in emissions data")
        log_message("Note: NAICS code is required for industry-level GDP matching")
        log_message("   Proceeding with available data structure")

    # Aggregate emissions by province, industry (NAICS), and year
    # This enables matching with GDP data at the same aggregation level
    try:
        agg_dict = {
            'emissions_co2e': 'sum',
            'facility_name': 'count'  # Count of facilities
        }

        if 'naics_code' in df_emiss.columns and 'province' in df_emiss.columns:
            df_intensity = df_emiss.groupby(['year', 'naics_code', 'province']).agg(agg_dict).reset_index()
            df_intensity.rename(columns={'facility_name': 'facility_count'}, inplace=True)
            log_message(f"OK: Aggregated to {len(df_intensity)} industry-province-year observations")
            log_message(f"  - Unique NAICS codes: {df_intensity['naics_code'].nunique()}")
            log_message(f"  - Unique provinces: {df_intensity['province'].nunique()}")
        else:
            # Fallback: aggregate by province and year only
            agg_cols = [col for col in ['year', 'province'] if col in df_emiss.columns]
            df_intensity = df_emiss.groupby(agg_cols).agg(agg_dict).reset_index()
            log_message(f"Warning: Aggregating by limited dimensions: {agg_cols}")

    except Exception as e:
        log_message(f"FAILED: Error aggregating data: {str(e)}")
        sys.exit(1)

    # Step 3: Create intensity calculation framework
    log_message("\n[Step 3] Creating intensity framework...")

    # Explanation of output proxy approach
    log_message("  Note: Emission intensity calculation")
    log_message("  - Numerator: Total facility emissions (tCO2e)")
    log_message("  - Denominator: Industry output (using industry GDP as proxy from StatCan)")
    log_message("  - Result: tCO2e per CAD of output")
    log_message("  - Data source: StatCan Table 36-10-0402 (GDP by industry)")

    # Add a temporary intensity column (placeholder for GDP data)
    # In practice, this would be merged with StatCan GDP data
    df_intensity['intensity_numerator'] = df_intensity['emissions_co2e']
    df_intensity['intensity_denominator'] = np.nan  # To be filled from GDP data
    df_intensity['intensity_co2e_per_gdp'] = np.nan  # Final intensity value

    log_message(f"OK: Created intensity framework with {len(df_intensity)} observations")

    # Step 4: Summary statistics
    log_message("\n[Step 4] Aggregated Emissions Summary")

    total_emiss_agg = df_intensity['emissions_co2e'].sum()
    log_message(f"  - Total emissions (aggregated): {total_emiss_agg:,.0f} tCO2e")
    log_message(f"  - Year range: {df_intensity['year'].min()} - {df_intensity['year'].max()}")
    log_message(f"  - Observations: {len(df_intensity)}")

    # By year
    log_message(f"\n[Step 5] Aggregated emissions by year")
    yearly = df_intensity.groupby('year')['emissions_co2e'].agg(['sum', 'count'])
    log_message(f"  Year | Total Emissions | Count")
    for year in sorted(df_intensity['year'].unique()):
        if year in yearly.index:
            row = yearly.loc[year]
            log_message(f"  {year} | {row['sum']:>14,.0f} | {int(row['count']):>5}")

    # Step 6: Data quality checks
    log_message("\n[Step 6] Data quality checks")

    missing_naics = df_intensity['naics_code'].isnull().sum() if 'naics_code' in df_intensity.columns else 0
    missing_province = df_intensity['province'].isnull().sum() if 'province' in df_intensity.columns else 0

    log_message(f"  - Missing NAICS codes: {missing_naics}")
    log_message(f"  - Missing provinces: {missing_province}")
    log_message(f"OK: Quality check complete")

    # Step 7: Prepare for GDP merging
    log_message("\n[Step 7] Preparing for GDP merging")
    log_message("  Next step: Merge with StatCan GDP data (36-10-0402)")
    log_message("  Match keys: [year, naics_code, province]")
    log_message("  Expected: GDP in CAD (will be converted to thousands or millions)")

    # Step 8: Save intermediate output
    log_message("\n[Step 8] Saving intermediate intensity dataset...")

    # Keep only necessary columns
    output_cols = ['year', 'province', 'emissions_co2e', 'facility_count']
    if 'naics_code' in df_intensity.columns:
        output_cols.insert(2, 'naics_code')

    df_intensity_output = df_intensity[output_cols].copy()

    try:
        df_intensity_output.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
        log_message(f"OK: Saved to {OUTPUT_FILE}")
        log_message(f"  - File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
    except Exception as e:
        log_message(f"FAILED: Error saving file: {str(e)}")
        sys.exit(1)

    # Final summary
    log_message("\n" + "="*80)
    log_message("OK: Intensity_ft FRAMEWORK CREATED")
    log_message(f"Output: {OUTPUT_FILE}")
    log_message(f"  - {len(df_intensity_output)} aggregated observations")
    log_message(f"  - Ready for GDP data merge")
    log_message("\nNext step: Merge with StatCan GDP data to calculate final intensity")
    log_message("="*80)

if __name__ == "__main__":
    main()
