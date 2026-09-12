#!/usr/bin/env python3
"""
Replace green_patent_stock in the analysis-ready dataset with the company-level perpetual-inventory stock
built by 13_recalculate_company_patent_stock.py, and recompute the variables derived from it.
Inputs : data/analysis_ready/analysis_ready_company_year_latest.csv,
         data/processed/4_panels/company_year_green_patent_stock_corrected_20251025.csv
Outputs: data/analysis_ready/analysis_ready_company_year_20251025_v2_<date>.csv and analysis_ready_company_year_latest.csv
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
        logging.FileHandler(ROOT / 'logs' / 'update_analysis_dataset.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_DIR = DATA / 'analysis_ready'
CORRECTED_STOCK_FILE = DATA / 'processed' / '4_panels' / 'company_year_green_patent_stock_corrected_20251025.csv'
INPUT_FILE = DATA_DIR / 'analysis_ready_company_year_latest.csv'
OUTPUT_FILE = DATA_DIR / f'analysis_ready_company_year_20251025_v2_{datetime.now().strftime("%Y%m%d")}.csv'

logger.info("="*80)
logger.info("UPDATE ANALYSIS-READY DATASET WITH COMPANY-LEVEL GREEN PATENT STOCK")
logger.info("="*80)
logger.info("")

# ============================================================================
# STEP 1: Load analysis-ready dataset
# ============================================================================

logger.info("[STEP 1] Loading analysis-ready dataset...")
try:
    analysis_df = pd.read_csv(INPUT_FILE)
    logger.info(f"  Loaded {len(analysis_df):,} company-year records")
    logger.info(f"  Columns: {len(analysis_df.columns)}")
    logger.info(f"  Companies: {analysis_df['company_id'].nunique():,}")
    logger.info(f"  Year range: {analysis_df['year'].min()}-{analysis_df['year'].max()}")
    logger.info(f"  Current green_patent_stock range: "
                f"min={analysis_df['green_patent_stock'].min():.2f}, "
                f"max={analysis_df['green_patent_stock'].max():.2f}, "
                f"mean={analysis_df['green_patent_stock'].mean():.2f}")

    # Large maxima indicate the stock was summed across facilities rather than built at company level
    if analysis_df['green_patent_stock'].max() > 700:
        logger.warning("  Current dataset has very large stock values (likely from summing)")

except Exception as e:
    logger.error(f"  Error loading analysis dataset: {e}")
    raise

# ============================================================================
# STEP 2: Load corrected stock
# ============================================================================

logger.info("\n[STEP 2] Loading company-level green patent stock...")
try:
    corrected_stock = pd.read_csv(CORRECTED_STOCK_FILE)
    logger.info(f"  Loaded {len(corrected_stock):,} company-year records")
    logger.info(f"  Columns: {list(corrected_stock.columns)}")
    logger.info(f"  Corrected stock range: "
                f"min={corrected_stock['green_patent_stock_corrected'].min():.2f}, "
                f"max={corrected_stock['green_patent_stock_corrected'].max():.2f}, "
                f"mean={corrected_stock['green_patent_stock_corrected'].mean():.2f}")

except Exception as e:
    logger.error(f"  Error loading corrected stock: {e}")
    raise

# ============================================================================
# STEP 3: Create company ID mapping and standardize
# ============================================================================

logger.info("\n[STEP 3] Creating company ID mapping...")
try:
    # analysis_df has company_id in upper case (e.g. "102078290 SASKATCHEWAN LTD");
    # corrected_stock has company_id equal to the company legal name (e.g. "102078290 Saskatchewan Ltd.").
    # Match corrected_stock company_id to analysis_df company_name, which is also the legal name.

    logger.info(f"  Analysis dataset company_id format: {analysis_df['company_id'].head(3).values}")
    logger.info(f"  Corrected stock company_id format: {corrected_stock['company_id'].head(3).values}")

    logger.info(f"  Creating mapping from company_name to company_id...")

    # Create mapping: company_name -> company_id from analysis_df
    legal_name_to_analysis_id = {}
    for _, row in analysis_df[['company_id', 'company_name']].drop_duplicates().iterrows():
        company_id_analysis = str(row['company_id']).strip()
        company_name_analysis = str(row['company_name']).strip()
        legal_name_to_analysis_id[company_name_analysis] = company_id_analysis

    logger.info(f"  Built mapping for {len(legal_name_to_analysis_id):,} companies")

    # Apply mapping to corrected_stock
    corrected_stock['company_id_from_analysis'] = corrected_stock['company_id'].map(legal_name_to_analysis_id)

    unmatched = corrected_stock['company_id_from_analysis'].isna().sum()
    logger.info(f"  Matched {len(corrected_stock) - unmatched:,} records")
    logger.info(f"  Unmatched: {unmatched} records")

    if unmatched > 0:
        logger.warning(f"  Some company_ids could not be matched.")
        logger.info(f"     Sample unmatched: {corrected_stock[corrected_stock['company_id_from_analysis'].isna()]['company_id'].head(3).values}")
        logger.info(f"     This is expected for companies in the corrected data but not in the analysis data")

except Exception as e:
    logger.error(f"  Error creating mapping: {e}")
    import traceback
    traceback.print_exc()
    raise

# ============================================================================
# STEP 4: Merge corrected stock into analysis dataset
# ============================================================================

logger.info("\n[STEP 4] Merging corrected stock...")
try:
    # Prepare corrected stock for merge
    corrected_stock_for_merge = corrected_stock[['company_id_from_analysis', 'year', 'green_patent_stock_corrected']].copy()
    corrected_stock_for_merge.rename(
        columns={'company_id_from_analysis': 'company_id'},
        inplace=True
    )

    # Remove rows with null company_id (unmatched)
    corrected_stock_for_merge = corrected_stock_for_merge.dropna(subset=['company_id'])

    # Drop the old green_patent_stock columns from analysis_df
    cols_to_drop = ['green_patent_stock']
    analysis_df_updated = analysis_df.drop(columns=cols_to_drop)

    # Merge with corrected stock
    analysis_df_updated = analysis_df_updated.merge(
        corrected_stock_for_merge,
        on=['company_id', 'year'],
        how='left'
    )

    # Rename corrected stock column to original name
    analysis_df_updated.rename(
        columns={'green_patent_stock_corrected': 'green_patent_stock'},
        inplace=True
    )

    logger.info(f"  Merged successfully")
    logger.info(f"  Records with matched corrected stock: {analysis_df_updated['green_patent_stock'].notna().sum():,}")
    logger.info(f"  Records with missing corrected stock: {analysis_df_updated['green_patent_stock'].isna().sum():,}")

    # Check if there are any null values (shouldn't be)
    if analysis_df_updated['green_patent_stock'].isna().sum() > 0:
        logger.warning("  Some records have missing corrected stock")
        logger.warning("     This might indicate company_id mismatch or year mismatch")
        unmatched_samples = analysis_df_updated[analysis_df_updated['green_patent_stock'].isna()].head(3)
        logger.warning(f"     Sample unmatched: {unmatched_samples[['company_id', 'year']].values.tolist()}")

except Exception as e:
    logger.error(f"  Error merging: {e}")
    import traceback
    traceback.print_exc()
    raise

# ============================================================================
# STEP 5: Recalculate dependent variables
# ============================================================================

logger.info("\n[STEP 5] Recalculating dependent variables...")
try:
    # Recalculate green_patent_intensity (if it exists and depends on stock)
    if 'green_patent_intensity' in analysis_df_updated.columns:
        # Original might have been: stock / total_emissions
        analysis_df_updated['green_patent_intensity'] = np.where(
            analysis_df_updated['total_emissions_co2e'] > 0,
            analysis_df_updated['green_patent_stock'] / analysis_df_updated['total_emissions_co2e'],
            0
        )
        logger.info(f"  Recalculated green_patent_intensity")

    # Check other dependent variables
    if 'has_green_patents' in analysis_df_updated.columns:
        analysis_df_updated['has_green_patents'] = (analysis_df_updated['green_patent_stock'] > 0).astype(int)
        logger.info(f"  Recalculated has_green_patents")

    if 'ln_green_patents' in analysis_df_updated.columns:
        analysis_df_updated['ln_green_patents'] = np.log(
            analysis_df_updated['green_patent_stock'] + 1  # Add 1 to avoid log(0)
        )
        logger.info(f"  Recalculated ln_green_patents")

except Exception as e:
    logger.error(f"  Error recalculating dependent variables: {e}")
    raise

# ============================================================================
# STEP 6: Validation and comparison
# ============================================================================

logger.info("\n[STEP 6] Validation and comparison...")
try:
    logger.info(f"  Old vs New green_patent_stock:")
    logger.info(f"    Old mean: {analysis_df['green_patent_stock'].mean():.2f}")
    logger.info(f"    New mean: {analysis_df_updated['green_patent_stock'].mean():.2f}")
    logger.info(f"    Ratio (old/new): {analysis_df['green_patent_stock'].mean() / analysis_df_updated['green_patent_stock'].mean():.2f}")

    logger.info(f"\n  Stock value distribution:")
    logger.info(f"    Old - Min: {analysis_df['green_patent_stock'].min():.2f}, "
                f"Max: {analysis_df['green_patent_stock'].max():.2f}")
    logger.info(f"    New - Min: {analysis_df_updated['green_patent_stock'].min():.2f}, "
                f"Max: {analysis_df_updated['green_patent_stock'].max():.2f}")

    # Count non-zero values
    old_nonzero = (analysis_df['green_patent_stock'] > 0).sum()
    new_nonzero = (analysis_df_updated['green_patent_stock'] > 0).sum()
    logger.info(f"\n  Non-zero stock values:")
    logger.info(f"    Old: {old_nonzero:,} ({100*old_nonzero/len(analysis_df):.1f}%)")
    logger.info(f"    New: {new_nonzero:,} ({100*new_nonzero/len(analysis_df_updated):.1f}%)")

except Exception as e:
    logger.error(f"  Error during validation: {e}")
    raise

# ============================================================================
# STEP 7: Save updated dataset
# ============================================================================

logger.info("\n[STEP 7] Saving updated dataset...")
try:
    # Dated copy
    analysis_df_updated.to_csv(OUTPUT_FILE, index=False)
    logger.info(f"  Saved to: {OUTPUT_FILE}")

    # Also refresh the canonical dataset used by downstream steps
    simple_output = DATA_DIR / 'analysis_ready_company_year_latest.csv'
    analysis_df_updated.to_csv(simple_output, index=False)
    logger.info(f"  Also saved as: {simple_output}")

    logger.info(f"  Records: {len(analysis_df_updated):,}")
    logger.info(f"  Columns: {len(analysis_df_updated.columns)}")

except Exception as e:
    logger.error(f"  Error saving: {e}")
    raise

# ============================================================================
# STEP 8: Summary
# ============================================================================

logger.info("\n[STEP 8] Summary...")
logger.info(f"  Original dataset: {len(analysis_df):,} records")
logger.info(f"  Updated dataset: {len(analysis_df_updated):,} records")
logger.info(f"  All columns preserved: {len(analysis_df_updated.columns)} columns")
logger.info(f"\n  Key changes:")
logger.info(f"    - green_patent_stock: replaced by the company-level perpetual-inventory stock")
logger.info(f"    - green_patent_intensity: recalculated from the new stock")
logger.info(f"    - green_patent_count: preserved from original")
logger.info(f"    - All other variables: unchanged")

logger.info("\n" + "="*80)
logger.info("ANALYSIS DATASET UPDATE COMPLETE")
logger.info("="*80)
logger.info(f"\nOutput file: {OUTPUT_FILE}")
logger.info("")
