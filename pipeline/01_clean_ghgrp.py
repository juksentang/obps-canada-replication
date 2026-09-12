#!/usr/bin/env python3
"""
Stage 1: verify and clean the GHGRP facility emissions file.
Input : data/raw/ghgrp/PDGES-GHGRP-GHGEmissionsGES-2004-Present.csv
Output: data/processed/1_raw_clean/ghgrp_cleaned_v1_20251022.csv
Log   : data/metadata/ghgrp_cleaning_log_20251022.txt
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
INPUT_FILE = DATA_DIR / 'raw' / 'ghgrp' / 'PDGES-GHGRP-GHGEmissionsGES-2004-Present.csv'
OUTPUT_FILE = DATA_DIR / 'processed' / '1_raw_clean' / 'ghgrp_cleaned_v1_20251022.csv'
METADATA_FILE = DATA_DIR / 'metadata' / 'ghgrp_cleaning_log_20251022.txt'

# Ensure output directory exists
os.makedirs(OUTPUT_FILE.parent, exist_ok=True)
os.makedirs(METADATA_FILE.parent, exist_ok=True)

def log_message(msg, print_also=True):
    """Log message to both console and file"""
    with open(METADATA_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

def main():
    # Initialize log file
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(f"GHGRP Data Cleaning Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting GHGRP data verification and cleaning")
    log_message(f"Input file: {INPUT_FILE}")

    # Step 1: Load data
    log_message("\n[Step 1] Loading GHGRP CSV file...")
    try:
        df = pd.read_csv(INPUT_FILE, encoding='utf-8')
        log_message(f"OK: Successfully loaded {len(df)} rows and {len(df.columns)} columns")
    except Exception as e:
        log_message(f"FAILED: Error loading CSV: {str(e)}")
        sys.exit(1)

    # Step 2: Basic data inspection
    log_message("\n[Step 2] Basic Data Inspection")
    log_message(f"  - Shape: {df.shape}")
    log_message(f"  - Date range: {df['Reference Year / Année de référence'].min()} - {df['Reference Year / Année de référence'].max()}")
    log_message(f"  - Missing values per column:")

    missing_summary = df.isnull().sum()
    for col, count in missing_summary[missing_summary > 0].items():
        log_message(f"    - {col}: {count} ({100*count/len(df):.1f}%)")

    # Step 3: Standardize column names
    log_message("\n[Step 3] Standardizing column names...")
    column_mapping = {
        'GHGRP ID No. / No d\'identification du PDGES': 'ghgrp_id',
        'Reference Year / Année de référence': 'year',
        'Facility Name / Nom de l\'installation': 'facility_name',
        'Facility Location / Emplacement de l\'installation': 'facility_location',
        'Facility City or District or Municipality / Ville ou District ou Municipalité de l\'installation': 'facility_city',
        'Facility Province or Territory / Province ou territoire de l\'installation': 'province',
        'Facility Postal Code / Code postal de l\'installation': 'postal_code',
        'Latitude': 'latitude',
        'Longitude': 'longitude',
        'Facility NAICS Code / Code SCIAN de l\'installation': 'naics_code',
        'English Facility NAICS Code Description / Description du code SCIAN de l\'installation en anglais': 'naics_description_en',
        'Reporting Company Legal Name / Dénomination sociale de la société déclarante': 'company_legal_name',
        'Reporting Company Trade Name / Nom commercial de la société déclarante': 'company_trade_name',
        'Reporting Company Business Number / Numéro d\'entreprise de la société déclarante': 'business_number',
        'CO2 (tonnes)': 'co2_tonnes',
        'CH4 (tonnes CO2e / tonnes éq. CO2)': 'ch4_co2e',
        'N2O (tonnes CO2e / tonnes éq. CO2)': 'n2o_co2e',
        'HFC Total (tonnes CO2e / tonnes éq. CO2)': 'hfc_co2e',
        'PFC Total (tonnes CO2e / tonnes éq. CO2)': 'pfc_co2e',
        'SF6 (tonnes CO2e / tonnes éq. CO2)': 'sf6_co2e',
        'Total Emissions (tonnes CO2e) / Émissions totales (tonnes éq. CO2)': 'total_emissions_co2e'
    }

    # Rename columns that exist
    existing_mappings = {k: v for k, v in column_mapping.items() if k in df.columns}
    df.rename(columns=existing_mappings, inplace=True)
    log_message(f"OK: Renamed {len(existing_mappings)} columns")

    # Step 4: Data type conversion
    log_message("\n[Step 4] Converting data types...")

    # Convert year to int
    df['year'] = pd.to_numeric(df['year'], errors='coerce').astype('Int64')

    # Convert numeric columns
    numeric_cols = [col for col in df.columns if 'co2e' in col or 'tonnes' in col or col in ['latitude', 'longitude']]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    log_message(f"OK: Converted {len(numeric_cols)} columns to numeric")

    # Step 5: Data validation and cleaning
    log_message("\n[Step 5] Data validation and cleaning...")

    initial_rows = len(df)

    # Remove rows with missing critical fields
    critical_cols = ['ghgrp_id', 'year', 'facility_name', 'total_emissions_co2e']
    df_clean = df.dropna(subset=[col for col in critical_cols if col in df.columns])

    rows_removed = initial_rows - len(df_clean)
    log_message(f"OK: Removed {rows_removed} rows with missing critical fields")

    # Remove rows with negative emissions (data errors)
    if 'total_emissions_co2e' in df_clean.columns:
        invalid_emissions = (df_clean['total_emissions_co2e'] < 0).sum()
        df_clean = df_clean[df_clean['total_emissions_co2e'] >= 0]
        log_message(f"OK: Removed {invalid_emissions} rows with negative emissions")

    # Standardize company names (remove extra spaces, convert to title case)
    if 'company_legal_name' in df_clean.columns:
        df_clean['company_legal_name'] = df_clean['company_legal_name'].str.strip().str.title()

    log_message(f"OK: Final dataset: {len(df_clean)} rows (from {initial_rows})")

    # Step 6: Facility-year aggregation check
    log_message("\n[Step 6] Facility-year structure analysis...")
    if 'ghgrp_id' in df_clean.columns and 'year' in df_clean.columns:
        facility_year_count = df_clean.groupby(['ghgrp_id', 'year']).size()
        duplicates = (facility_year_count > 1).sum()
        log_message(f"  - Total facility-year observations: {len(facility_year_count)}")
        log_message(f"  - Duplicate facility-year entries: {duplicates}")

        if duplicates > 0:
            log_message("  Warning: Some facility-year combinations have multiple rows")
            log_message("  Solution: Will aggregate by summing emissions for duplicates")
            df_clean = df_clean.groupby(['ghgrp_id', 'year'], as_index=False).agg({
                'total_emissions_co2e': 'sum',
                'facility_name': 'first',
                'company_legal_name': 'first',
                'province': 'first',
                'naics_code': 'first',
                'co2_tonnes': 'sum' if 'co2_tonnes' in df_clean.columns else 'first',
            })
            log_message(f"  OK: Aggregated to {len(df_clean)} unique facility-year observations")

    # Step 7: Save cleaned data
    log_message("\n[Step 7] Saving cleaned data...")
    try:
        df_clean.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
        log_message(f"OK: Saved cleaned data to {OUTPUT_FILE}")
        log_message(f"  - File size: {os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.1f} MB")
    except Exception as e:
        log_message(f"FAILED: Error saving file: {str(e)}")
        sys.exit(1)

    # Step 8: Final summary statistics
    log_message("\n[Step 8] Summary Statistics")
    log_message(f"  - Years covered: {df_clean['year'].min()} - {df_clean['year'].max()}")
    log_message(f"  - Total emissions (tCO2e): {df_clean['total_emissions_co2e'].sum():,.0f}")
    log_message(f"  - Mean facility emissions: {df_clean['total_emissions_co2e'].mean():,.0f}")
    log_message(f"  - Median facility emissions: {df_clean['total_emissions_co2e'].median():,.0f}")

    if 'province' in df_clean.columns:
        log_message(f"  - Provinces represented: {df_clean['province'].nunique()}")
        top_provinces = df_clean.groupby('province')['total_emissions_co2e'].sum().nlargest(5)
        log_message("  - Top 5 provinces by emissions:")
        for prov, emissions in top_provinces.items():
            log_message(f"    - {prov}: {emissions:,.0f} tCO2e")

    log_message("\n" + "="*80)
    log_message("OK: GHGRP data verification and cleaning COMPLETED")
    log_message(f"Output file: {OUTPUT_FILE}")
    log_message(f"Log file: {METADATA_FILE}")
    log_message("="*80)

if __name__ == "__main__":
    main()
