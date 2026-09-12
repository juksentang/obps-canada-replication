#!/usr/bin/env python3
"""
Recompute the company-level green patent stock with the perpetual inventory method: annual fractional green patent
counts are summed over a firm's facilities and the stock is then accumulated at the company level,
Stock_t = (1 - delta) * Stock_{t-1} + Count_t with delta = 0.15 (summing facility-level stocks would over-count).

Input:  data/processed/4_panels/facility_year_greenpatent_merged_20251022.csv
Output: data/processed/4_panels/company_year_green_patent_stock_corrected_<date>.csv
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
(ROOT / 'logs').mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT / 'logs' / 'recalculate_company_stock.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths
DATA_PROCESSED = DATA / 'processed' / '4_panels'
OUTPUT_DIR = DATA / 'processed' / '4_panels'
facility_file = DATA_PROCESSED / 'facility_year_greenpatent_merged_20251022.csv'
OUTPUT_FILE = OUTPUT_DIR / f'company_year_green_patent_stock_corrected_{datetime.now().strftime("%Y%m%d")}.csv'

# Constants
DELTA = 0.15  # PIM depreciation rate

logger.info("="*80)
logger.info("COMPANY-LEVEL GREEN PATENT STOCK (PERPETUAL INVENTORY METHOD)")
logger.info("="*80)
logger.info("")

# ============================================================================
# STEP 1: Load facility-year data
# ============================================================================

logger.info("[STEP 1] Loading facility-year green patent data...")
try:
    facility_df = pd.read_csv(facility_file)
    logger.info(f"  Loaded {len(facility_df):,} facility-year records")
    logger.info(f"  Facilities: {facility_df['facility_id'].nunique():,}")
    logger.info(f"  Companies: {facility_df['company_legal_name'].nunique():,}")
    logger.info(f"  Year range: {facility_df['year'].min()}-{facility_df['year'].max()}")

    # Check for green patent count column
    if 'green_patent_count' not in facility_df.columns:
        raise ValueError("Column 'green_patent_count' not found")

    logger.info(f"  Green patents: min={facility_df['green_patent_count'].min():.2f}, "
                f"max={facility_df['green_patent_count'].max():.2f}, "
                f"mean={facility_df['green_patent_count'].mean():.2f}")

except Exception as e:
    logger.error(f"  Error loading facility data: {e}")
    raise

# ============================================================================
# STEP 2: Create standardized company identifiers
# ============================================================================

logger.info("\n[STEP 2] Creating standardized company identifiers...")
try:
    # Use company_legal_name as the key, but also create a clean ID
    facility_df['company_id_clean'] = facility_df['company_legal_name'].str.strip()

    logger.info(f"  Company names standardized")
    logger.info(f"  Unique companies: {facility_df['company_id_clean'].nunique():,}")

except Exception as e:
    logger.error(f"  Error creating company IDs: {e}")
    raise

# ============================================================================
# STEP 3: Aggregate green_patent_count to company-year level
# ============================================================================

logger.info("\n[STEP 3] Aggregating green patent count to company-year level...")
try:
    # Group by company and year, sum the green patent counts
    company_year_counts = facility_df.groupby(
        ['company_id_clean', 'year'],
        as_index=False
    )['green_patent_count'].sum()

    company_year_counts.rename(
        columns={'company_id_clean': 'company_id', 'green_patent_count': 'patent_count'},
        inplace=True
    )

    # Sort for PIM calculation
    company_year_counts = company_year_counts.sort_values(['company_id', 'year']).reset_index(drop=True)

    logger.info(f"  Aggregated to {len(company_year_counts):,} company-year combinations")
    logger.info(f"  Unique companies: {company_year_counts['company_id'].nunique():,}")
    logger.info(f"  Year range: {company_year_counts['year'].min()}-{company_year_counts['year'].max()}")
    logger.info(f"  Count statistics:")
    logger.info(f"    - Min: {company_year_counts['patent_count'].min():.2f}")
    logger.info(f"    - Max: {company_year_counts['patent_count'].max():.2f}")
    logger.info(f"    - Mean: {company_year_counts['patent_count'].mean():.2f}")

except Exception as e:
    logger.error(f"  Error aggregating patent counts: {e}")
    raise

# ============================================================================
# STEP 4: Calculate PIM at company level
# ============================================================================

logger.info("\n[STEP 4] Calculating PIM patent stock at company level...")
logger.info(f"  Using depreciation rate delta = {DELTA}")

try:
    # Initialize stock column
    company_year_counts['patent_stock'] = 0.0

    # Calculate PIM for each company separately
    companies = company_year_counts['company_id'].unique()
    logger.info(f"  Processing {len(companies):,} companies...")

    for i, company_id in enumerate(companies):
        # Get all years for this company
        company_mask = company_year_counts['company_id'] == company_id
        company_data = company_year_counts[company_mask].sort_values('year').reset_index(drop=True)

        # Initialize stock from previous year
        prev_stock = 0.0

        # Calculate PIM for each year
        for idx, row in company_data.iterrows():
            if idx == 0:
                # First year: stock = flow
                stock = row['patent_count']
            else:
                # PIM formula: Stock_t = (1-delta)xStock_{t-1} + Flow_t
                stock = (1 - DELTA) * prev_stock + row['patent_count']

            # Update in main dataframe
            main_idx = company_year_counts[company_mask].index[idx]
            company_year_counts.loc[main_idx, 'patent_stock'] = stock

            # Update prev_stock for next iteration
            prev_stock = stock

        # Progress logging
        if (i + 1) % 100 == 0:
            logger.info(f"    - Processed {i + 1}/{len(companies)} companies")

    logger.info(f"  PIM calculation complete")
    logger.info(f"  Patent stock statistics:")
    logger.info(f"    - Min: {company_year_counts['patent_stock'].min():.2f}")
    logger.info(f"    - Max: {company_year_counts['patent_stock'].max():.2f}")
    logger.info(f"    - Mean: {company_year_counts['patent_stock'].mean():.2f}")
    logger.info(f"    - Median: {company_year_counts['patent_stock'].median():.2f}")

except Exception as e:
    logger.error(f"  Error calculating PIM: {e}")
    raise

# ============================================================================
# STEP 5: Verify PIM calculation
# ============================================================================

logger.info("\n[STEP 5] Verifying PIM calculation...")

try:
    # Check 1: Verify PIM formula for a few sample companies
    logger.info("  Sample verification (first 5 companies):")
    for company_id in companies[:5]:
        company_data = company_year_counts[company_year_counts['company_id'] == company_id].sort_values('year')

        # Check formula: Stock_t = (1-delta)xStock_{t-1} + Flow_t
        violations = 0
        for idx in range(1, len(company_data)):
            prev_row = company_data.iloc[idx-1]
            curr_row = company_data.iloc[idx]

            expected_stock = (1 - DELTA) * prev_row['patent_stock'] + curr_row['patent_count']
            actual_stock = curr_row['patent_stock']

            if abs(expected_stock - actual_stock) > 0.01:  # Allow small floating point errors
                violations += 1

        status = "OK" if violations == 0 else f"{violations} violations"
        logger.info(f"    - {company_id}: {status}")

    # Check 2: Verify stock is non-negative
    negative_stock = (company_year_counts['patent_stock'] < 0).sum()
    logger.info(f"  Negative stock values: {negative_stock} (should be 0)")

    # Check 3: Verify no stock decreases unless flow=0
    company_year_counts['stock_lag'] = company_year_counts.groupby('company_id')['patent_stock'].shift(1)
    anomalies = company_year_counts[
        (company_year_counts['patent_count'] > 0) &
        (company_year_counts['stock_lag'].notna()) &
        (company_year_counts['patent_stock'] < company_year_counts['stock_lag'])
    ]
    logger.info(f"  Anomalies (stock decrease with new patents): {len(anomalies)} (should be 0)")

    # Remove temporary columns
    company_year_counts = company_year_counts.drop(columns=['stock_lag'])

except Exception as e:
    logger.error(f"  Error verifying PIM: {e}")
    raise

# ============================================================================
# STEP 6: Prepare output
# ============================================================================

logger.info("\n[STEP 6] Preparing output...")

try:
    # Create output dataframe with clean names
    output_df = company_year_counts[['company_id', 'year', 'patent_count', 'patent_stock']].copy()
    output_df.rename(
        columns={
            'patent_count': 'green_patent_count',
            'patent_stock': 'green_patent_stock_corrected'
        },
        inplace=True
    )

    # Save to CSV
    output_df.to_csv(OUTPUT_FILE, index=False)
    logger.info(f"  Saved to: {OUTPUT_FILE}")
    logger.info(f"  Records: {len(output_df):,}")
    logger.info(f"  Columns: {list(output_df.columns)}")

except Exception as e:
    logger.error(f"  Error saving output: {e}")
    raise

# ============================================================================
# STEP 7: Summary statistics
# ============================================================================

logger.info("\n[STEP 7] Summary statistics...")

try:
    logger.info(f"  Data summary:")
    logger.info(f"    - Total company-year observations: {len(output_df):,}")
    logger.info(f"    - Unique companies: {output_df['company_id'].nunique():,}")
    logger.info(f"    - Year range: {output_df['year'].min()}-{output_df['year'].max()}")
    logger.info(f"    - Years per company (mean): {len(output_df) / output_df['company_id'].nunique():.1f}")

    logger.info(f"\n  Green patent count (flow):")
    logger.info(f"    - Total patents across all years: {output_df['green_patent_count'].sum():.0f}")
    logger.info(f"    - Mean per company-year: {output_df['green_patent_count'].mean():.2f}")
    logger.info(f"    - Std: {output_df['green_patent_count'].std():.2f}")

    logger.info(f"\n  Green patent stock (corrected):")
    logger.info(f"    - Mean: {output_df['green_patent_stock_corrected'].mean():.2f}")
    logger.info(f"    - Std: {output_df['green_patent_stock_corrected'].std():.2f}")
    logger.info(f"    - Min: {output_df['green_patent_stock_corrected'].min():.2f}")
    logger.info(f"    - Max: {output_df['green_patent_stock_corrected'].max():.2f}")

    logger.info(f"\n  Correlation between count and corrected stock:")
    corr = output_df['green_patent_count'].corr(output_df['green_patent_stock_corrected'])
    logger.info(f"    - Correlation: {corr:.4f}")

except Exception as e:
    logger.error(f"  Error generating summary: {e}")
    raise

# ============================================================================
# COMPLETION
# ============================================================================

logger.info("\n" + "="*80)
logger.info("COMPANY-LEVEL PIM CALCULATION COMPLETE")
logger.info("="*80)
logger.info(f"\nOutput file: {OUTPUT_FILE}")
logger.info(f"Next step: run 18_update_corrected_patent_stock.py")
logger.info("")
