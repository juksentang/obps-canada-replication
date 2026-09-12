#!/usr/bin/env python3
"""
Merge the green-patent panel (NAICS-3 x province x year) onto the facility-year panel by a left join on
NAICS-3, province and year; missing patent values are set to zero and facility-level intensity metrics are added.

Input:  data/processed/4_panels/facility_year_panel_v1_*.csv (latest), data/processed/4_panels/greenpatent_naics_prov_year_v2_*.csv (latest)
Output: data/processed/4_panels/facility_year_greenpatent_merged_20251022.csv, facility_greenpatent_merge_summary_20251022.txt
"""

import pandas as pd
import logging
import numpy as np
from pathlib import Path
from datetime import datetime

# ============================================================================
# SETUP
# ============================================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
(ROOT / 'logs').mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT / 'logs' / 'merge_greenpatent_facility.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_PROCESSED = DATA / 'processed' / '4_panels'
DATA_OUTPUT = DATA / 'processed' / '4_panels'

logger.info("="*80)
logger.info("MERGING GREEN PATENT PANEL WITH FACILITY-YEAR PANEL")
logger.info("="*80)

# ============================================================================
# STEP 1: LOAD INPUT FILES
# ============================================================================

logger.info("\n[STEP 1] Loading input data...")

try:
    # Load facility-year panel (find latest version)
    from pathlib import Path
    facility_files = sorted(Path(DATA_PROCESSED).glob('facility_year_panel_v1_*.csv'))
    if facility_files:
        facility_file = facility_files[-1]  # Get latest
    else:
        facility_file = DATA_PROCESSED / 'facility_year_panel_v1_20251022.csv'
    facility_df = pd.read_csv(facility_file)

    logger.info(f"  Facility-Year panel loaded: {len(facility_df)} rows")
    logger.info(f"  File: {facility_file.name}")
    logger.info(f"  Columns: {list(facility_df.columns)}")
    logger.info(f"  Facilities: {facility_df['facility_id'].nunique()}")
    logger.info(f"  Years: {facility_df['year'].min()}-{facility_df['year'].max()}")
    logger.info(f"  Provinces: {facility_df['province'].nunique()}")

    # Load green patent panel (v2) - find latest version
    greenpatent_files = sorted(Path(DATA_PROCESSED).glob('greenpatent_naics_prov_year_v2_*.csv'))
    if greenpatent_files:
        greenpatent_file = greenpatent_files[-1]  # Get latest
    else:
        greenpatent_file = DATA_PROCESSED / 'greenpatent_naics_prov_year_v2_20251022.csv'
    greenpatent_df = pd.read_csv(greenpatent_file)

    logger.info(f"\n  Green patent panel loaded: {len(greenpatent_df)} rows")
    logger.info(f"  Columns: {list(greenpatent_df.columns)}")
    logger.info(f"  NAICS codes: {greenpatent_df['naics_3digit'].nunique()}")
    logger.info(f"  Provinces: {greenpatent_df['province'].nunique()}")
    logger.info(f"  Years: {greenpatent_df['year'].min()}-{greenpatent_df['year'].max()}")

except Exception as e:
    logger.error(f"  Error loading input files: {str(e)}")
    raise

# ============================================================================
# STEP 2: DATA VALIDATION AND PREPARATION
# ============================================================================

logger.info("\n[STEP 2] Validating and preparing data...")

try:
    # Province name to code mapping (facility uses full names, green patent uses codes)
    province_name_to_code = {
        'Alberta': 'A1',
        'British Columbia': 'B1',
        'Manitoba': 'M1',
        'New Brunswick': 'N1',
        'Newfoundland and Labrador': 'N2',
        'Nova Scotia': 'N3',
        'Nunavut': 'N4',
        'Ontario': 'O1',
        'Prince Edward Island': 'P1',
        'Quebec': 'Q1',
        'Saskatchewan': 'S1',
        'Northwest Territories': 'XX',
        'Yukon': 'Y1',
    }

    # Create reverse mapping (code to name)
    province_code_to_name = {v: k for k, v in province_name_to_code.items()}

    # Map facility province names to codes
    facility_df['province_code'] = facility_df['province'].map(province_name_to_code)

    # Count unmapped provinces
    unmapped = facility_df['province_code'].isna().sum()
    if unmapped > 0:
        logger.warning(f"  {unmapped} facility records have unmapped province (likely null or non-standard)")
        logger.info(f"      Unmapped values: {facility_df[facility_df['province_code'].isna()]['province'].unique()}")

    # Check facility NAICS column name
    facility_naics_col = None
    if 'naics_code_3digit' in facility_df.columns:
        facility_naics_col = 'naics_code_3digit'
    elif 'naics_3digit' in facility_df.columns:
        facility_naics_col = 'naics_3digit'
    else:
        raise ValueError(f"Cannot find NAICS column in facility data. Available: {facility_df.columns.tolist()}")

    logger.info(f"  Facility NAICS column: {facility_naics_col}")
    logger.info(f"  Province mapping applied: facility province names to codes")

    # Check year columns
    facility_year_col = 'year'
    greenpatent_year_col = 'year'

    # Validate NAICS codes are numeric in both datasets
    facility_df[facility_naics_col] = pd.to_numeric(facility_df[facility_naics_col], errors='coerce')
    greenpatent_df['naics_3digit'] = pd.to_numeric(greenpatent_df['naics_3digit'], errors='coerce')

    # Check for missing values in join keys
    facility_missing = facility_df[[facility_naics_col, 'province_code', facility_year_col]].isnull().sum()
    greenpatent_missing = greenpatent_df[['naics_3digit', 'province', greenpatent_year_col]].isnull().sum()

    logger.info(f"  Facility missing in join keys: {facility_missing.sum()}")
    logger.info(f"  GreenPatent missing in join keys: {greenpatent_missing.sum()}")

    # Log NAICS overlap
    facility_naics = set(facility_df[facility_naics_col].dropna().unique())
    greenpatent_naics = set(greenpatent_df['naics_3digit'].dropna().unique())

    overlap = facility_naics & greenpatent_naics
    facility_only = facility_naics - greenpatent_naics
    greenpatent_only = greenpatent_naics - facility_naics

    logger.info(f"  NAICS overlap: {len(overlap)} codes")
    logger.info(f"    - Facility only: {len(facility_only)} codes (e.g., {list(facility_only)[:5]})")
    logger.info(f"    - GreenPatent only: {len(greenpatent_only)} codes")

    # Log province mapping results
    logger.info(f"  Province codes in facility (after mapping): {sorted(facility_df['province_code'].dropna().unique())}")
    logger.info(f"  Province codes in green patents: {sorted(greenpatent_df['province'].unique())}")

except Exception as e:
    logger.error(f"  Error validating data: {str(e)}")
    raise

# ============================================================================
# STEP 3: PERFORM LEFT JOIN
# ============================================================================

logger.info("\n[STEP 3] Merging datasets...")

try:
    # Perform LEFT JOIN to keep all facilities
    # facility (LEFT) <- greenpatent (RIGHT) on (NAICS, Province Code, Year)
    merged_df = facility_df.merge(
        greenpatent_df,
        left_on=[facility_naics_col, 'province_code', facility_year_col],
        right_on=['naics_3digit', 'province', greenpatent_year_col],
        how='left'
    )

    logger.info(f"  Merge completed")
    logger.info(f"  Output records: {len(merged_df)}")
    logger.info(f"  Merged successfully: {merged_df['green_patent_count'].notna().sum()} rows")
    logger.info(f"  Unmatched (no green patents): {merged_df['green_patent_count'].isna().sum()} rows")

    # Clean up duplicate columns from the merge
    cols_to_drop = []

    # Drop duplicate NAICS column (right side had naics_3digit)
    if 'naics_3digit' in merged_df.columns and facility_naics_col != 'naics_3digit':
        cols_to_drop.append('naics_3digit')

    # Drop duplicate province column from right side (we kept left side 'province')
    # The merge creates 'province_x' and 'province_y', we want to drop 'province_y'
    if 'province_x' in merged_df.columns:
        # Keep province_x (from facility, full name), drop province_y (from green patent, code)
        if 'province_y' in merged_df.columns:
            cols_to_drop.append('province_y')
        merged_df = merged_df.rename(columns={'province_x': 'province'})

    if cols_to_drop:
        merged_df = merged_df.drop(cols_to_drop, axis=1)
        logger.info(f"  Cleaned up duplicate columns: {cols_to_drop}")

    logger.info(f"  Output columns: {len(merged_df.columns)}")

except Exception as e:
    logger.error(f"  Error during merge: {str(e)}")
    raise

# ============================================================================
# STEP 4: FILL MISSING VALUES AND CREATE METRICS
# ============================================================================

logger.info("\n[STEP 4] Processing missing values and creating metrics...")

try:
    # Fill missing green patent metrics with zeros
    gp_cols = ['green_patent_count', 'unique_patents', 'green_patent_stock']

    for col in gp_cols:
        if col in merged_df.columns:
            missing_count = merged_df[col].isna().sum()
            merged_df[col] = merged_df[col].fillna(0.0)
            logger.info(f"  Filled {missing_count} missing values in '{col}' with 0.0")

    # Fill green_domains with empty string
    if 'green_domains' in merged_df.columns:
        merged_df['green_domains'] = merged_df['green_domains'].fillna('No green patents')

    # Create facility-level green patent intensity metrics
    # Green intensity = green_patent_stock / total_emissions
    merged_df['green_patent_intensity'] = np.where(
        merged_df['total_emissions_co2e'] > 0,
        merged_df['green_patent_stock'] / merged_df['total_emissions_co2e'],
        0
    )

    logger.info(f"  Created green_patent_intensity metric")

    # Create facility-level green patent count per ton CO2e
    merged_df['green_patents_per_tco2e'] = np.where(
        merged_df['total_emissions_co2e'] > 0,
        merged_df['green_patent_count'] / merged_df['total_emissions_co2e'],
        0
    )

    logger.info(f"  Created green_patents_per_tco2e metric")

    # Log statistics
    logger.info(f"\n  Statistics on green patent metrics:")
    logger.info(f"    - Mean green_patent_stock: {merged_df['green_patent_stock'].mean():.4f}")
    logger.info(f"    - Median green_patent_stock: {merged_df['green_patent_stock'].median():.4f}")
    logger.info(f"    - Max green_patent_stock: {merged_df['green_patent_stock'].max():.4f}")
    logger.info(f"    - Mean green_patent_intensity: {merged_df['green_patent_intensity'].mean():.6f}")
    logger.info(f"    - Non-zero intensity records: {(merged_df['green_patent_intensity'] > 0).sum()}")

except Exception as e:
    logger.error(f"  Error processing values: {str(e)}")
    raise

# ============================================================================
# STEP 5: QUALITY CHECKS
# ============================================================================

logger.info("\n[STEP 5] Performing quality checks...")

try:
    # Check for duplicates
    facility_year_combo = merged_df[['facility_id', 'year']].copy()
    duplicates = facility_year_combo.duplicated().sum()
    logger.info(f"  Duplicate (facility_id, year) combinations: {duplicates}")

    # Check data types
    numeric_cols = ['total_emissions_co2e', 'green_patent_stock', 'green_patent_count']
    for col in numeric_cols:
        if col in merged_df.columns:
            non_numeric = merged_df[col].apply(lambda x: not isinstance(x, (int, float, np.number))).sum()
            logger.info(f"  Non-numeric values in '{col}': {non_numeric}")

    # Check coverage by year
    logger.info(f"\n  Coverage by year:")
    year_coverage = merged_df.groupby('year').agg({
        'facility_id': 'count',
        'green_patent_stock': lambda x: (x > 0).sum(),
        'total_emissions_co2e': 'sum'
    }).rename(columns={
        'facility_id': 'total_records',
        'green_patent_stock': 'with_green_patents'
    })

    for year, row in year_coverage.iterrows():
        logger.info(f"    {year}: {int(row['total_records'])} records, {int(row['with_green_patents'])} with green patents")

except Exception as e:
    logger.error(f"  Error in quality checks: {str(e)}")
    raise

# ============================================================================
# STEP 6: SAVE OUTPUT
# ============================================================================

logger.info("\n[STEP 6] Saving merged dataset...")

try:
    output_file = DATA_OUTPUT / 'facility_year_greenpatent_merged_20251022.csv'
    merged_df.to_csv(output_file, index=False)

    output_size_mb = output_file.stat().st_size / (1024 * 1024)
    logger.info(f"  Saved to: {output_file.name}")
    logger.info(f"  File size: {output_size_mb:.2f} MB")
    logger.info(f"  Rows: {len(merged_df)}")
    logger.info(f"  Columns: {len(merged_df.columns)}")

except Exception as e:
    logger.error(f"  Error saving output: {str(e)}")
    raise

# ============================================================================
# STEP 7: CREATE SUMMARY REPORT
# ============================================================================

logger.info("\n[STEP 7] Creating summary statistics...")

try:
    summary_stats = {
        'Total Records': len(merged_df),
        'Facilities': merged_df['facility_id'].nunique(),
        'Years': merged_df['year'].nunique(),
        'Provinces': merged_df['province'].nunique(),
        'NAICS Codes': merged_df[facility_naics_col].nunique(),
        'Records with Green Patents': (merged_df['green_patent_stock'] > 0).sum(),
        'Mean Emissions (tCO2e)': merged_df['total_emissions_co2e'].mean(),
        'Mean Green Patent Stock': merged_df['green_patent_stock'].mean(),
        'Max Green Patent Stock': merged_df['green_patent_stock'].max(),
        'Total Emissions (tCO2e)': merged_df['total_emissions_co2e'].sum(),
        'Total Green Patents': merged_df['green_patent_count'].sum(),
    }

    summary_file = DATA_OUTPUT / 'facility_greenpatent_merge_summary_20251022.txt'

    with open(summary_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("FACILITY-YEAR x GREEN PATENT MERGE SUMMARY\n")
        f.write("="*80 + "\n\n")

        for key, value in summary_stats.items():
            if isinstance(value, float):
                f.write(f"{key:.<40} {value:>15,.2f}\n")
            else:
                f.write(f"{key:.<40} {value:>15,}\n")

        f.write("\n" + "="*80 + "\n")
        f.write("MERGE STATISTICS\n")
        f.write("="*80 + "\n\n")

        f.write(f"Join Type: LEFT JOIN\n")
        f.write(f"Left Table (Facility): {len(facility_df)} records\n")
        f.write(f"Right Table (GreenPatent): {len(greenpatent_df)} records\n")
        f.write(f"Merged Result: {len(merged_df)} records\n")
        f.write(f"Match Rate: {(merged_df['green_patent_stock'] > 0).sum() / len(merged_df) * 100:.2f}%\n\n")

        f.write("Join Keys:\n")
        f.write(f"  - NAICS (3-digit)\n")
        f.write(f"  - Province\n")
        f.write(f"  - Year\n\n")

        f.write("New Columns Created:\n")
        f.write(f"  - green_patent_count (from the NAICS x province x year panel)\n")
        f.write(f"  - green_patent_stock (PIM, delta=0.15)\n")
        f.write(f"  - green_patent_intensity (stock / emissions)\n")
        f.write(f"  - green_patents_per_tco2e\n")
        f.write(f"  - green_domains (list of domains)\n")

    logger.info(f"  Summary saved to: {summary_file.name}")

    # Print summary
    logger.info(f"\n  Summary Statistics:")
    for key, value in summary_stats.items():
        if isinstance(value, float):
            logger.info(f"    {key}: {value:,.2f}")
        else:
            logger.info(f"    {key}: {value:,}")

except Exception as e:
    logger.error(f"  Error creating summary: {str(e)}")
    raise

# ============================================================================
# SUMMARY
# ============================================================================

logger.info("\n[SUMMARY]")
logger.info(f"  Merge completed successfully")
logger.info(f"  Output file: facility_year_greenpatent_merged_20251022.csv")
logger.info(f"  Records: {len(merged_df)}")
logger.info(f"  Green patent matches: {(merged_df['green_patent_stock'] > 0).sum()}")
logger.info(f"  Coverage: {(merged_df['green_patent_stock'] > 0).sum() / len(merged_df) * 100:.2f}%")

logger.info("\nMerge Complete!")
logger.info("="*80)
