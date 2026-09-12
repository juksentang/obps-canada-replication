#!/usr/bin/env python3
"""
Stage 3: build the facility-year panel from the cleaned GHGRP file, merge the sector emission intensity
(3-digit NAICS x province x year) and the carbon-price exposure variable, and add entry/exit indicators.
Input : data/processed/1_raw_clean/ghgrp_cleaned_v1_20251022.csv,
        data/processed/3_variables/intensity_ft_final_v1_20251022.csv, exposure_price_it_v1_20251022.csv
Output: data/processed/4_panels/facility_year_panel_v1_20251022.csv
Log   : data/metadata/facility_year_log_v1_20251022.txt
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ==================== CONFIGURATION ====================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA_DIR = DATA

GHGRP_INPUT = DATA_DIR / 'processed' / '1_raw_clean' / 'ghgrp_cleaned_v1_20251022.csv'
INTENSITY_INPUT = DATA_DIR / 'processed' / '3_variables' / 'intensity_ft_final_v1_20251022.csv'
EXPOSURE_INPUT = DATA_DIR / 'processed' / '3_variables' / 'exposure_price_it_v1_20251022.csv'

PANEL_OUTPUT = DATA_DIR / 'processed' / '4_panels' / 'facility_year_panel_v1_20251022.csv'
METADATA_FILE = DATA_DIR / 'metadata' / 'facility_year_log_v1_20251022.txt'

# Ensure output directories exist
os.makedirs(PANEL_OUTPUT.parent, exist_ok=True)
os.makedirs(METADATA_FILE.parent, exist_ok=True)

def log_message(msg, print_also=True):
    """Log message to both console and file"""
    with open(METADATA_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

# ==================== STEP 1: LOAD AND VALIDATE DATA ====================

def load_and_validate_data():
    """Load and validate all input datasets"""
    log_message("\n[Step 1] Loading and validating input data...")

    try:
        # Load GHGRP data
        log_message("\n[1.1] Loading GHGRP data...")
        ghgrp = pd.read_csv(GHGRP_INPUT)
        log_message(f"OK: Loaded {len(ghgrp)} GHGRP records")
        log_message(f"  Year range: {ghgrp['year'].min()}-{ghgrp['year'].max()}")
        log_message(f"  Unique facilities: {ghgrp['ghgrp_id'].nunique()}")
        log_message(f"  Provinces: {ghgrp['province'].nunique()}")

        # Load intensity data
        log_message("\n[1.2] Loading Intensity_ft data...")
        intensity = pd.read_csv(INTENSITY_INPUT)
        log_message(f"OK: Loaded {len(intensity)} intensity records")
        log_message(f"  3-digit NAICS codes: {intensity['naics_code'].nunique()}")
        log_message(f"  Year range: {intensity['year'].min()}-{intensity['year'].max()}")

        # Load exposure data
        log_message("\n[1.3] Loading Exposure^Price data...")
        exposure = pd.read_csv(EXPOSURE_INPUT)
        log_message(f"OK: Loaded {len(exposure)} exposure records")
        log_message(f"  Year range: {exposure['year'].min()}-{exposure['year'].max()}")

        return ghgrp, intensity, exposure

    except Exception as e:
        log_message(f"FAILED: Error loading data: {str(e)}")
        sys.exit(1)

# ==================== STEP 2: PREPARE FACILITY PANEL ====================

def prepare_facility_panel(ghgrp):
    """Create basic facility-year panel from GHGRP data"""
    log_message("\n[Step 2] Creating basic facility-year panel...")

    try:
        # Select and rename key columns
        panel = ghgrp[[
            'ghgrp_id', 'year', 'facility_name', 'facility_city', 'province',
            'latitude', 'longitude', 'naics_code', 'company_legal_name',
            'company_trade_name', 'total_emissions_co2e'
        ]].copy()

        panel.columns = [
            'facility_id', 'year', 'facility_name', 'facility_city', 'province',
            'latitude', 'longitude', 'naics_code_6digit', 'company_legal_name',
            'company_trade_name', 'total_emissions_co2e'
        ]

        # Create 3-digit NAICS for merging
        panel['naics_code_3digit'] = panel['naics_code_6digit'].astype(str).str[:3].astype(int)

        log_message(f"OK: Created basic panel: {len(panel)} records")

        return panel

    except Exception as e:
        log_message(f"FAILED: Error preparing panel: {str(e)}")
        sys.exit(1)

# ==================== STEP 3: COMPUTE FACILITY CHARACTERISTICS ====================

def compute_facility_characteristics(panel):
    """Compute facility-level characteristics (entry/exit years, continuity)"""
    log_message("\n[Step 3] Computing facility characteristics...")

    try:
        # For each facility, compute first and last year observed
        facility_years = panel.groupby('facility_id').agg({
            'year': ['min', 'max', 'count']
        }).reset_index()
        facility_years.columns = ['facility_id', 'first_year', 'last_year', 'obs_count']

        # Merge back to panel
        panel = panel.merge(facility_years, on='facility_id', how='left')

        # Compute characteristics
        panel['years_active'] = panel['last_year'] - panel['first_year'] + 1

        # Check continuity (no missing years for this facility)
        panel['is_continuous'] = panel['obs_count'] == panel['years_active']

        # Entry/exit indicators
        min_year = panel['year'].min()
        max_year = panel['year'].max()

        panel['is_entrant'] = panel['first_year'] > min_year
        panel['is_exiter'] = panel['last_year'] < max_year

        log_message(f"OK: Computed facility characteristics")
        log_message(f"  Unique facilities: {panel['facility_id'].nunique()}")
        log_message(f"  Continuous facilities: {(panel['is_continuous'] == True).sum() // panel.groupby('facility_id').size().iloc[0]}")
        log_message(f"  Entrants: {panel[panel['is_entrant']]['facility_id'].nunique()}")
        log_message(f"  Exiters: {panel[panel['is_exiter']]['facility_id'].nunique()}")

        return panel

    except Exception as e:
        log_message(f"FAILED: Error computing characteristics: {str(e)}")
        sys.exit(1)

# ==================== STEP 4: MERGE INTENSITY ====================

def merge_intensity(panel, intensity):
    """Merge Intensity_ft data by NAICS (3-digit) + province + year"""
    log_message("\n[Step 4] Merging Intensity_ft data...")

    try:
        # Rename intensity columns for clarity
        intensity_merge = intensity[[
            'naics_code', 'province', 'year', 'intensity_co2e_per_m_gdp'
        ]].copy()
        intensity_merge.columns = [
            'naics_code_3digit', 'province', 'year', 'intensity_co2e_per_m_gdp'
        ]

        # Merge
        panel_with_intensity = panel.merge(
            intensity_merge,
            on=['naics_code_3digit', 'province', 'year'],
            how='left'
        )

        # Check merge results
        matched = panel_with_intensity['intensity_co2e_per_m_gdp'].notna().sum()
        matched_pct = 100 * matched / len(panel_with_intensity)

        log_message(f"OK: Merged Intensity_ft data")
        log_message(f"  Matched records: {matched}/{len(panel_with_intensity)} ({matched_pct:.1f}%)")
        log_message(f"  Unmatched: {len(panel_with_intensity) - matched} records")

        return panel_with_intensity

    except Exception as e:
        log_message(f"FAILED: Error merging intensity: {str(e)}")
        sys.exit(1)

# ==================== STEP 5: MERGE EXPOSURE ====================

def merge_exposure(panel, exposure):
    """Merge Exposure^Price_it data by NAICS (3-digit) + province + year"""
    log_message("\n[Step 5] Merging Exposure^Price data...")

    try:
        # Extract key columns from exposure
        exposure_merge = exposure[[
            'naics_code', 'province', 'year', 'baseline_intensity_2015',
            'carbon_price_nominal', 'carbon_price_real_2015',
            'delta_price_real_2015', 'exposure_price_it'
        ]].copy()
        exposure_merge.columns = [
            'naics_code_3digit', 'province', 'year', 'baseline_intensity_2015',
            'carbon_price_nominal', 'carbon_price_real_2015',
            'delta_price_real_2015', 'exposure_price_it'
        ]

        # Merge
        panel_with_exposure = panel.merge(
            exposure_merge,
            on=['naics_code_3digit', 'province', 'year'],
            how='left'
        )

        # Check merge results
        matched = panel_with_exposure['exposure_price_it'].notna().sum()
        matched_pct = 100 * matched / len(panel_with_exposure)

        log_message(f"OK: Merged Exposure^Price data")
        log_message(f"  Matched records: {matched}/{len(panel_with_exposure)} ({matched_pct:.1f}%)")
        log_message(f"  Unmatched: {len(panel_with_exposure) - matched} records")

        return panel_with_exposure

    except Exception as e:
        log_message(f"FAILED: Error merging exposure: {str(e)}")
        sys.exit(1)

# ==================== STEP 6: QUALITY CONTROL ====================

def quality_control_checks(panel):
    """Perform quality control checks on the facility panel"""
    log_message("\n[Step 6] Quality control checks...")

    try:
        # Check 1: Unique records
        log_message("\n[Check 1] Record uniqueness...")
        duplicates = panel[panel.duplicated(subset=['facility_id', 'year'], keep=False)]
        log_message(f"  Duplicate records: {len(duplicates)}")
        if len(duplicates) > 0:
            log_message(f"  Warning: Found {len(duplicates)} duplicate records")

        # Check 2: Missing values
        log_message("\n[Check 2] Missing value check...")
        missing_intensity = panel['intensity_co2e_per_m_gdp'].isna().sum()
        missing_exposure = panel['exposure_price_it'].isna().sum()
        log_message(f"  Missing intensity: {missing_intensity}/{len(panel)} ({100*missing_intensity/len(panel):.1f}%)")
        log_message(f"  Missing exposure: {missing_exposure}/{len(panel)} ({100*missing_exposure/len(panel):.1f}%)")

        # Check 3: Negative values
        log_message("\n[Check 3] Negative value check...")
        neg_emissions = (panel['total_emissions_co2e'] < 0).sum()
        neg_intensity = (panel['intensity_co2e_per_m_gdp'] < 0).sum()
        neg_exposure = (panel['exposure_price_it'] < 0).sum()
        log_message(f"  Negative emissions: {neg_emissions}")
        log_message(f"  Negative intensity: {neg_intensity}")
        log_message(f"  Negative exposure: {neg_exposure}")

        if neg_emissions > 0 or neg_intensity > 0 or neg_exposure > 0:
            log_message(f"  Warning: Found negative values")

        # Check 4: Anomalies in emissions
        log_message("\n[Check 4] Emission anomalies...")
        # Check for extreme values
        q99 = panel['total_emissions_co2e'].quantile(0.99)
        extreme = (panel['total_emissions_co2e'] > q99).sum()
        log_message(f"  99th percentile: {q99:.0f} tCO2e")
        log_message(f"  Extreme records (>99%ile): {extreme}")

        # Check 5: Year coverage
        log_message("\n[Check 5] Year coverage...")
        year_min = panel['year'].min()
        year_max = panel['year'].max()
        years_covered = panel['year'].nunique()
        log_message(f"  Year range: {year_min}-{year_max}")
        log_message(f"  Years with data: {years_covered}")

        log_message(f"\nOK: Quality control checks completed")

    except Exception as e:
        log_message(f"FAILED: Error in quality control: {str(e)}")
        sys.exit(1)

# ==================== STEP 7: PREPARE OUTPUT ====================

def prepare_output(panel):
    """Prepare final output with proper column ordering and sorting"""
    log_message("\n[Step 7] Preparing output dataset...")

    try:
        # Define output columns in logical order
        output_cols = [
            # Identifiers
            'facility_id', 'year',
            # Facility info
            'facility_name', 'facility_city', 'province',
            'latitude', 'longitude',
            # Industry classification
            'naics_code_6digit', 'naics_code_3digit',
            # Company info
            'company_legal_name', 'company_trade_name',
            # Emissions data
            'total_emissions_co2e',
            # Intensity
            'intensity_co2e_per_m_gdp',
            # Policy variables
            'baseline_intensity_2015', 'carbon_price_nominal',
            'carbon_price_real_2015', 'delta_price_real_2015',
            'exposure_price_it',
            # Panel characteristics
            'first_year', 'last_year', 'years_active', 'obs_count',
            'is_continuous', 'is_entrant', 'is_exiter'
        ]

        # Select and sort
        panel_output = panel[output_cols].copy()
        panel_output = panel_output.sort_values(
            ['facility_id', 'year']
        ).reset_index(drop=True)

        log_message(f"OK: Output dataset prepared")
        log_message(f"  Columns: {len(output_cols)}")
        log_message(f"  Records: {len(panel_output)}")

        return panel_output

    except Exception as e:
        log_message(f"FAILED: Error preparing output: {str(e)}")
        sys.exit(1)

# ==================== STEP 8: SAVE OUTPUT ====================

def save_output(panel):
    """Save facility-year panel to CSV"""
    log_message("\n[Step 8] Saving output...")

    try:
        panel.to_csv(PANEL_OUTPUT, index=False, encoding='utf-8')
        file_size_kb = os.path.getsize(PANEL_OUTPUT) / 1024
        log_message(f"OK: Saved facility-year panel: {PANEL_OUTPUT}")
        log_message(f"  File size: {file_size_kb:.1f} KB")
        log_message(f"  Records: {len(panel)}")

    except Exception as e:
        log_message(f"FAILED: Error saving output: {str(e)}")
        sys.exit(1)

# ==================== MAIN ====================

def main():
    """Main execution"""

    # Initialize log
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Facility-Year Panel Build Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting Facility-Year panel construction")
    log_message(f"  Input 1: GHGRP data")
    log_message(f"  Input 2: Intensity_ft")
    log_message(f"  Input 3: Exposure^Price_it")

    # Execute steps
    ghgrp, intensity, exposure = load_and_validate_data()
    panel = prepare_facility_panel(ghgrp)
    panel = compute_facility_characteristics(panel)
    panel = merge_intensity(panel, intensity)
    panel = merge_exposure(panel, exposure)
    quality_control_checks(panel)
    panel = prepare_output(panel)
    save_output(panel)

    # Final summary
    log_message("\n" + "="*80)
    log_message("OK: Facility-Year Panel CONSTRUCTION COMPLETED")
    log_message(f"Output file: {PANEL_OUTPUT}")
    log_message("="*80)

if __name__ == "__main__":
    main()
