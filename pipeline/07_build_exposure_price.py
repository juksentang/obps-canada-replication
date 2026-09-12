#!/usr/bin/env python3
"""
Stage 2: build the carbon-price exposure variable Exposure^Price_it = Intensity_i,2015 x dPrice_t (real 2015 CAD):
rebases the StatCan CPI to 2015=100, deflates the federal benchmark price path (2019-2030), and multiplies it by the
2015 (main) or 2010-2015 average (robust) sector-province emission intensity.
Input : data/CPI/1810000501-eng.csv, data/processed/3_variables/intensity_ft_final_v1_20251022.csv
Output: data/processed/3_variables/exposure_price_it_v1_20251022.csv, exposure_price_it_robust_v1_20251022.csv, cpi_2015_base_v1_20251022.csv
Log   : data/metadata/exposure_price_log_v1_20251022.txt
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
INTENSITY_INPUT = DATA_DIR / 'processed' / '3_variables' / 'intensity_ft_final_v1_20251022.csv'
CPI_INPUT = DATA_DIR / 'CPI' / '1810000501-eng.csv'
EXPOSURE_OUTPUT = DATA_DIR / 'processed' / '3_variables' / 'exposure_price_it_v1_20251022.csv'
EXPOSURE_ROBUST_OUTPUT = DATA_DIR / 'processed' / '3_variables' / 'exposure_price_it_robust_v1_20251022.csv'
CPI_PROCESSED_OUTPUT = DATA_DIR / 'processed' / '3_variables' / 'cpi_2015_base_v1_20251022.csv'
METADATA_FILE = DATA_DIR / 'metadata' / 'exposure_price_log_v1_20251022.txt'

# Ensure output directories exist
os.makedirs(EXPOSURE_OUTPUT.parent, exist_ok=True)
os.makedirs(METADATA_FILE.parent, exist_ok=True)

def log_message(msg, print_also=True):
    """Log message to both console and file"""
    with open(METADATA_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

# ==================== PART 1: CPI PROCESSING ====================

def parse_cpi_csv():
    """
    Parse StatCan wide-format CPI CSV (Table 18-10-0005-01)
    Format: Rows are product categories, columns are years
    Returns: year -> CPI mapping for All-items
    """
    log_message("\n[Part 1.1] Loading StatCan CPI data (Table 18-10-0005-01)...")

    try:
        # Read raw file with proper header location
        # Row 9 contains geography info, Row 10 contains year headers
        df = pd.read_csv(CPI_INPUT, skiprows=9)

        # First column is "Products and product groups"
        # Column names should be year strings like "2000", "2001", etc.

        # Find "All-items" row
        all_items = df[df.iloc[:, 0].str.contains('All-items', case=False, na=False, regex=False)]

        if len(all_items) == 0:
            raise ValueError("Could not find 'All-items' row in CPI data")

        # Extract All-items row (should be first match)
        all_items_row = all_items.iloc[0]

        # Parse year columns (skip first column which is product name)
        # Column names should be year strings like "2000", "2001", etc.
        cpi_dict = {}
        for col in df.columns[1:]:  # Skip first column (product names)
            try:
                year = int(col)
                cpi_value = float(all_items_row[col])
                cpi_dict[year] = cpi_value
            except (ValueError, TypeError):
                # Skip non-numeric columns or values
                continue

        log_message(f"OK: Parsed CPI data for {len(cpi_dict)} years")
        log_message(f"  Year range: {min(cpi_dict.keys())}-{max(cpi_dict.keys())}")

        # Show sample values
        sample_years = [2010, 2015, 2020]
        log_message(f"  Sample CPI (2002=100):")
        for year in sample_years:
            if year in cpi_dict:
                log_message(f"    {year}: {cpi_dict[year]:.1f}")

        return cpi_dict

    except Exception as e:
        log_message(f"FAILED: Error parsing CPI data: {str(e)}")
        sys.exit(1)

def build_cpi_deflators(cpi_dict):
    """
    Convert CPI from 2002=100 to 2015=100 baseline
    Calculate deflators for converting nominal to real prices (2015 constant dollars)
    """
    log_message("\n[Part 1.2] Converting CPI to 2015=100 baseline...")

    # CPI for 2015 (2002=100 baseline)
    cpi_2015_old_base = 126.6

    # Convert to 2015=100 baseline
    cpi_2015_base = {}
    for year, cpi_2002_base in cpi_dict.items():
        cpi_2015_base[year] = cpi_2002_base * (100.0 / cpi_2015_old_base)

    log_message(f"OK: CPI converted to 2015=100 baseline")
    log_message(f"  CPI_2015 = 100.0 (by definition)")

    # Calculate deflators (for converting nominal to 2015 constant dollars)
    deflators = {}
    for year, cpi_val in cpi_2015_base.items():
        deflators[year] = 100.0 / cpi_val  # Price_real = Price_nominal x deflator

    # Project 2025-2030 (assuming 2% annual inflation)
    cpi_2024 = cpi_2015_base.get(2024, 127.1)  # Use 2024 if available
    inflation_rate = 0.02

    for year in range(2025, 2031):
        years_from_2024 = year - 2024
        cpi_2015_base[year] = cpi_2024 * ((1 + inflation_rate) ** years_from_2024)
        deflators[year] = 100.0 / cpi_2015_base[year]

    log_message(f"  Projected CPI 2025-2030 (2% annual inflation)")
    log_message(f"    2030: {cpi_2015_base[2030]:.1f}")

    return cpi_2015_base, deflators

def build_carbon_price_trajectory(deflators):
    """
    Construct federal carbon price path (nominal and real 2015 prices)
    Federal benchmark: starts 2019 at $20/tonne, increases annually
    """
    log_message("\n[Part 1.3] Building carbon price trajectory (federal benchmark)...")

    # Nominal federal carbon price path ($/tonne CO2e)
    nominal_prices = {
        2004: 0, 2005: 0, 2006: 0, 2007: 0, 2008: 0,  # Pre-policy
        2009: 0, 2010: 0, 2011: 0, 2012: 0, 2013: 0, 2014: 0, 2015: 0, 2016: 0, 2017: 0, 2018: 0,
        2019: 20,   # Federal policy starts
        2020: 30,
        2021: 40,
        2022: 50,
        2023: 65,   # Accelerated increase
        2024: 80,
        2025: 95,
        2026: 110,
        2027: 125,
        2028: 140,
        2029: 155,
        2030: 170
    }

    # Convert to real prices (2015 constant dollars)
    real_prices = {}
    for year, nominal in nominal_prices.items():
        if year in deflators:
            real_prices[year] = nominal * deflators[year]
        else:
            real_prices[year] = nominal  # Use nominal if no deflator

    log_message(f"OK: Carbon price trajectory (2019-2030)")
    log_message(f"  Nominal: ${nominal_prices[2019]}-${nominal_prices[2030]}/tonne")
    log_message(f"  Real (2015$): ${real_prices[2019]:.2f}-${real_prices[2030]:.2f}/tonne")

    # Calculate delta prices (relative to 2015=0)
    delta_prices = {year: price - 0 for year, price in real_prices.items()}

    log_message(f"  dPrice (real 2015$):")
    for year in [2015, 2020, 2025, 2030]:
        log_message(f"    {year}: ${delta_prices[year]:.2f}/tonne")

    return nominal_prices, real_prices, delta_prices

def save_processed_cpi(cpi_dict, cpi_2015_base, deflators, nominal_prices, real_prices):
    """Save processed CPI data for reference"""
    log_message("\n[Part 1.4] Saving processed CPI data...")

    cpi_df = pd.DataFrame({
        'year': sorted(cpi_2015_base.keys()),
        'cpi_2002_base': [cpi_dict.get(y, np.nan) for y in sorted(cpi_2015_base.keys())],
        'cpi_2015_base': [cpi_2015_base[y] for y in sorted(cpi_2015_base.keys())],
        'deflator_2015': [deflators[y] for y in sorted(cpi_2015_base.keys())],
        'carbon_price_nominal': [nominal_prices.get(y, np.nan) for y in sorted(cpi_2015_base.keys())],
        'carbon_price_real_2015': [real_prices.get(y, np.nan) for y in sorted(cpi_2015_base.keys())],
        'source': ['actual' if y <= 2024 else 'projected' for y in sorted(cpi_2015_base.keys())]
    })

    cpi_df.to_csv(CPI_PROCESSED_OUTPUT, index=False, encoding='utf-8')
    log_message(f"OK: Saved to {CPI_PROCESSED_OUTPUT}")

    return cpi_df

# ==================== PART 2: BASELINE INTENSITY EXTRACTION ====================

def extract_baseline_intensity():
    """
    Extract 2015 baseline emission intensity (main and robust approaches)
    Main: 2015 single year
    Robust: 2010-2015 average (noise reduction)
    """
    log_message("\n[Part 2] Extracting baseline emission intensity...")

    try:
        intensity = pd.read_csv(INTENSITY_INPUT)
        log_message(f"OK: Loaded {len(intensity)} intensity records")
    except Exception as e:
        log_message(f"FAILED: Error loading intensity data: {str(e)}")
        sys.exit(1)

    # Main approach: 2015 only
    log_message("\n[Part 2.1] Main approach - 2015 single year...")
    intensity_2015 = intensity[intensity['year'] == 2015][
        ['naics_code', 'province', 'intensity_co2e_per_m_gdp']
    ].copy()
    intensity_2015.columns = ['naics_code', 'province', 'baseline_intensity_2015']

    log_message(f"  2015 baseline: {len(intensity_2015)} industry-province combinations")
    log_message(f"    Mean: {intensity_2015['baseline_intensity_2015'].mean():.2f} tCO2e/$M")
    log_message(f"    Median: {intensity_2015['baseline_intensity_2015'].median():.2f} tCO2e/$M")
    log_message(f"    Missing: {intensity_2015['baseline_intensity_2015'].isna().sum()} records")

    # Robust approach: 2010-2015 average
    log_message("\n[Part 2.2] Robust approach - 2010-2015 average...")
    intensity_2010_2015 = intensity[
        (intensity['year'] >= 2010) & (intensity['year'] <= 2015)
    ].groupby(['naics_code', 'province']).agg({
        'intensity_co2e_per_m_gdp': 'mean'
    }).reset_index()
    intensity_2010_2015.columns = ['naics_code', 'province', 'baseline_intensity_2010_2015_avg']

    log_message(f"  2010-2015 average: {len(intensity_2010_2015)} industry-province combinations")
    log_message(f"    Mean: {intensity_2010_2015['baseline_intensity_2010_2015_avg'].mean():.2f} tCO2e/$M")
    log_message(f"    Median: {intensity_2010_2015['baseline_intensity_2010_2015_avg'].median():.2f} tCO2e/$M")

    return intensity_2015, intensity_2010_2015

# ==================== PART 3: EXPOSURE CALCULATION ====================

def calculate_exposure(intensity_2015, intensity_2010_2015, delta_prices, cpi_2015_base,
                      nominal_prices, real_prices):
    """
    Calculate Exposure^Price_it = Intensity_i,2015 x dPrice_t,real
    """
    log_message("\n[Part 3] Calculating policy exposure...")

    # Create year and price data
    price_df = pd.DataFrame({
        'year': sorted(delta_prices.keys()),
        'delta_price_real_2015': [delta_prices[y] for y in sorted(delta_prices.keys())],
        'carbon_price_nominal': [nominal_prices.get(y, 0) for y in sorted(delta_prices.keys())],
        'carbon_price_real_2015': [real_prices.get(y, 0) for y in sorted(delta_prices.keys())],
        'cpi_2015_base': [cpi_2015_base[y] for y in sorted(delta_prices.keys())]
    })

    # Main exposure: intensity_2015 x delta_price
    log_message("\n[Part 3.1] Main exposure calculation...")
    exposure = intensity_2015.merge(price_df, how='cross')
    exposure['exposure_price_it'] = (
        exposure['baseline_intensity_2015'] *
        exposure['delta_price_real_2015']
    )

    log_message(f"OK: Main exposure: {len(exposure)} records")
    exposure_2030 = exposure[exposure['year'] == 2030]
    log_message(f"  2030 exposure (sample):")
    log_message(f"    Mean: ${exposure_2030['exposure_price_it'].mean():.0f}/M GDP")
    log_message(f"    Median: ${exposure_2030['exposure_price_it'].median():.0f}/M GDP")
    log_message(f"    Max: ${exposure_2030['exposure_price_it'].max():.0f}/M GDP")

    # Robust exposure: intensity average x delta price
    log_message("\n[Part 3.2] Robust exposure calculation (2010-2015 average)...")
    exposure_robust = intensity_2010_2015.merge(price_df, how='cross')
    exposure_robust['exposure_price_it_robust'] = (
        exposure_robust['baseline_intensity_2010_2015_avg'] *
        exposure_robust['delta_price_real_2015']
    )

    log_message(f"OK: Robust exposure: {len(exposure_robust)} records")
    exposure_robust_2030 = exposure_robust[exposure_robust['year'] == 2030]
    log_message(f"  2030 robust exposure (sample):")
    log_message(f"    Mean: ${exposure_robust_2030['exposure_price_it_robust'].mean():.0f}/M GDP")
    log_message(f"    Median: ${exposure_robust_2030['exposure_price_it_robust'].median():.0f}/M GDP")

    return exposure, exposure_robust

# ==================== PART 4: QUALITY CHECKS ====================

def quality_checks(exposure, exposure_robust):
    """
    Validate exposure calculations
    """
    log_message("\n[Part 4] Quality control checks...")

    # Check 1: Exposure should be 0 before 2019
    log_message("\n[Check 1] Pre-policy period (2004-2018) should have zero exposure...")
    pre_policy = exposure[exposure['year'] < 2019]
    zero_exposure = (pre_policy['exposure_price_it'] == 0).sum()
    log_message(f"  Zero exposure records: {zero_exposure}/{len(pre_policy)}")

    # Check 2: Monotonic increase in exposure over time
    log_message("\n[Check 2] Exposure should increase monotonically (2019-2030)...")
    post_policy = exposure[exposure['year'] >= 2019].groupby('year')['exposure_price_it'].mean()
    monotonic = all(post_policy.iloc[i] <= post_policy.iloc[i+1] for i in range(len(post_policy)-1))
    log_message(f"  Monotonic increase: {monotonic}")

    # Check 3: Missing values
    log_message("\n[Check 3] Missing value check...")
    missing_main = exposure['exposure_price_it'].isna().sum()
    missing_robust = exposure_robust['exposure_price_it_robust'].isna().sum()
    log_message(f"  Main exposure missing: {missing_main}/{len(exposure)}")
    log_message(f"  Robust exposure missing: {missing_robust}/{len(exposure_robust)}")

    # Check 4: Heterogeneity check (2030)
    log_message("\n[Check 4] Heterogeneity check (2030)...")
    exp_2030 = exposure[exposure['year'] == 2030]
    log_message(f"  Exposure std dev: ${exp_2030['exposure_price_it'].std():.0f}/M GDP")
    log_message(f"  Min industry-province: ${exp_2030['exposure_price_it'].min():.0f}/M GDP")
    log_message(f"  Max industry-province: ${exp_2030['exposure_price_it'].max():.0f}/M GDP")
    log_message(f"  Ratio (max/min): {exp_2030['exposure_price_it'].max() / max(exp_2030['exposure_price_it'].min(), 0.1):.0f}x")

# ==================== PART 5: OUTPUT ====================

def save_outputs(exposure, exposure_robust):
    """
    Save main and robust exposure datasets
    """
    log_message("\n[Part 5] Saving outputs...")

    # Order columns for clarity
    output_cols = [
        'naics_code', 'province', 'year',
        'baseline_intensity_2015',
        'carbon_price_nominal',
        'carbon_price_real_2015',
        'delta_price_real_2015',
        'cpi_2015_base',
        'exposure_price_it'
    ]

    exposure_output = exposure[output_cols].copy()
    exposure_output = exposure_output.sort_values(
        ['naics_code', 'province', 'year']
    ).reset_index(drop=True)

    try:
        exposure_output.to_csv(EXPOSURE_OUTPUT, index=False, encoding='utf-8')
        log_message(f"OK: Saved main exposure: {EXPOSURE_OUTPUT}")
        log_message(f"  File size: {os.path.getsize(EXPOSURE_OUTPUT) / 1024:.1f} KB")
        log_message(f"  Records: {len(exposure_output)}")
    except Exception as e:
        log_message(f"FAILED: Error saving main exposure: {str(e)}")
        sys.exit(1)

    # Robust version
    robust_cols = [
        'naics_code', 'province', 'year',
        'baseline_intensity_2010_2015_avg',
        'carbon_price_nominal',
        'carbon_price_real_2015',
        'delta_price_real_2015',
        'cpi_2015_base',
        'exposure_price_it_robust'
    ]

    exposure_robust_output = exposure_robust[robust_cols].copy()
    exposure_robust_output = exposure_robust_output.sort_values(
        ['naics_code', 'province', 'year']
    ).reset_index(drop=True)

    try:
        exposure_robust_output.to_csv(EXPOSURE_ROBUST_OUTPUT, index=False, encoding='utf-8')
        log_message(f"OK: Saved robust exposure: {EXPOSURE_ROBUST_OUTPUT}")
        log_message(f"  File size: {os.path.getsize(EXPOSURE_ROBUST_OUTPUT) / 1024:.1f} KB")
    except Exception as e:
        log_message(f"FAILED: Error saving robust exposure: {str(e)}")
        sys.exit(1)

# ==================== MAIN ====================

def main():
    """Main execution"""

    # Initialize log
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Exposure^Price_it Variable Build Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting Exposure^Price_it variable construction")
    log_message(f"  Method: federal benchmark price path")
    log_message(f"  Baseline year: 2015 (main) + 2010-2015 avg (robust)")
    log_message(f"  Price deflation: 2015 constant dollars")

    # ===== PART 1: CPI =====
    cpi_dict = parse_cpi_csv()
    cpi_2015_base, deflators = build_cpi_deflators(cpi_dict)
    nominal_prices, real_prices, delta_prices = build_carbon_price_trajectory(deflators)
    cpi_df = save_processed_cpi(cpi_dict, cpi_2015_base, deflators, nominal_prices, real_prices)

    # ===== PART 2: BASELINE INTENSITY =====
    intensity_2015, intensity_2010_2015 = extract_baseline_intensity()

    # ===== PART 3: EXPOSURE CALCULATION =====
    exposure, exposure_robust = calculate_exposure(
        intensity_2015, intensity_2010_2015, delta_prices,
        cpi_2015_base, nominal_prices, real_prices
    )

    # ===== PART 4: QUALITY CHECKS =====
    quality_checks(exposure, exposure_robust)

    # ===== PART 5: OUTPUT =====
    save_outputs(exposure, exposure_robust)

    # Final summary
    log_message("\n" + "="*80)
    log_message("OK: Exposure^Price_it CONSTRUCTION COMPLETED")
    log_message(f"Output files:")
    log_message(f"  1. {EXPOSURE_OUTPUT} (main)")
    log_message(f"  2. {EXPOSURE_ROBUST_OUTPUT} (robust)")
    log_message(f"  3. {CPI_PROCESSED_OUTPUT} (CPI reference)")
    log_message(f"  4. {METADATA_FILE} (this log)")
    log_message("="*80)

if __name__ == "__main__":
    main()
