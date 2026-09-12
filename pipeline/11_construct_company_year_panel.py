#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregate the facility-year panel to a company-year panel: emissions and patent variables are summed over a firm's
facilities, intensity is emission-weighted, and the principal province and NAICS-3 sector are the modal values.

Input:  data/processed/4_panels/facility_year_greenpatent_merged_*.csv (latest)
Output: data/processed/4_panels/company_year_panel_v1_<date>.csv, company_year_panel_metadata_<date>.txt
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
        logging.FileHandler(ROOT / 'logs' / 'construct_company_panel.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths - auto-detect latest facility file
DATA_PROCESSED = DATA / 'processed' / '4_panels'
facility_files = sorted(DATA_PROCESSED.glob('facility_year_greenpatent_merged_*.csv'))
if facility_files:
    INPUT_FILE = facility_files[-1]  # Get latest version
else:
    INPUT_FILE = DATA_PROCESSED / 'facility_year_greenpatent_merged_20251022.csv'

OUTPUT_DIR = DATA / 'processed' / '4_panels'
OUTPUT_FILE = OUTPUT_DIR / f'company_year_panel_v1_{datetime.now().strftime("%Y%m%d")}.csv'
METADATA_FILE = OUTPUT_DIR / f'company_year_panel_metadata_{datetime.now().strftime("%Y%m%d")}.txt'

# ============================================================================
# SECTION 1: Load and Prepare Data
# ============================================================================

logger.info("=" * 80)
logger.info("COMPANY-YEAR PANEL CONSTRUCTION")
logger.info("=" * 80)
logger.info("")

logger.info("[STEP 1] Loading facility-year panel...")
try:
    df = pd.read_csv(INPUT_FILE)
    logger.info(f"  Loaded {len(df):,} facility-year records")
    logger.info(f"  Columns: {df.shape[1]}")
    logger.info(f"  Time period: {df['year'].min()}-{df['year'].max()}")
except Exception as e:
    logger.error(f"  Failed to load input file: {e}")
    raise

# ============================================================================
# SECTION 2: Company Name Standardization
# ============================================================================

logger.info("")
logger.info("[STEP 2] Standardizing company names...")

# Use company_legal_name as primary key
df['company_name'] = df['company_legal_name'].str.strip()

# Create company_id by removing special characters and converting to uppercase
def create_company_id(name):
    """Create standardized company ID from legal name"""
    if pd.isna(name):
        return None
    # Remove extra spaces, standardize case
    clean_name = ' '.join(name.split()).upper()
    # Remove punctuation and special chars
    clean_name = clean_name.replace(',', '').replace('.', '').replace("'", '')
    return clean_name

df['company_id_raw'] = df['company_name'].apply(create_company_id)

logger.info(f"  Created company IDs")
logger.info(f"  Unique company legal names: {df['company_name'].nunique():,}")
logger.info(f"  Unique company IDs: {df['company_id_raw'].nunique():,}")

# Check for data quality issues
logger.info("")
logger.info("[STEP 2.1] Data quality checks...")
null_companies = df['company_name'].isna().sum()
logger.info(f"  - Null company names: {null_companies}")
logger.info(f"  - Rows with null company: {(df['company_name'].isna()).sum()}")

# For aggregation, we'll keep original company names but group by company_id_raw
df = df[df['company_name'].notna()].copy()
logger.info(f"  After dropping nulls: {len(df):,} records")

# ============================================================================
# SECTION 3: Company-Year Aggregation
# ============================================================================

logger.info("")
logger.info("[STEP 3] Aggregating to company-year level...")

def weighted_avg(values, weights):
    """Calculate weighted average, handling NaN values"""
    valid_idx = ~(np.isnan(values) | np.isnan(weights))
    if valid_idx.sum() == 0:
        return np.nan
    return np.average(values[valid_idx], weights=weights[valid_idx])

# Group by company_id_raw and year
groupby_cols = ['company_id_raw', 'year']
grouped = df.groupby(groupby_cols, as_index=False)

# Build aggregation dictionary
agg_dict = {
    # Emissions (sum)
    'total_emissions_co2e': 'sum',

    # Green patent variables (sum)
    'green_patent_count': 'sum',
    'green_patent_stock': 'sum',
    'unique_patents': 'sum',

    # Count facilities
    'facility_id': 'count',  # Will rename to num_facilities

    # Geographic info (mode - most common)
    'province': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
    'naics_code_3digit': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],

    # Company identifiers (first value)
    'company_name': 'first',
    'company_trade_name': 'first',

    # Intensity (weighted average by emissions)
    'intensity_co2e_per_m_gdp': lambda x: np.average(
        x.values,
        weights=df.loc[x.index, 'total_emissions_co2e'].values,
        returned=False
    ) if (x.notna().sum() > 0 and (df.loc[x.index, 'total_emissions_co2e'] > 0).sum() > 0) else np.nan,

    # Carbon price exposure (first value - same for all facilities in year)
    'exposure_price_it': 'first',
    'carbon_price_real_2015': 'first',
}

# Perform aggregation
company_year = grouped.agg(agg_dict)

# Rename columns
company_year.rename(columns={'facility_id': 'num_facilities'}, inplace=True)

logger.info(f"  Aggregated to {len(company_year):,} company-year records")
logger.info(f"  Unique companies: {company_year['company_id_raw'].nunique():,}")
logger.info(f"  Year range: {company_year['year'].min()}-{company_year['year'].max()}")

# ============================================================================
# SECTION 4: Calculate Company-Level Variables
# ============================================================================

logger.info("")
logger.info("[STEP 4] Computing company-level metrics...")

# Company ID (clean version)
company_year['company_id'] = company_year['company_id_raw'].copy()

# Handle multi-province operations
def get_province_list(group_df):
    """Get list of provinces where company operates"""
    provinces = group_df['province'].unique()
    return ', '.join(sorted(provinces))

multi_prov = df.groupby('company_id_raw').apply(
    lambda x: len(x['province'].unique())
).reset_index(name='num_provinces')
multi_prov.rename(columns={'company_id_raw': 'company_id_raw'}, inplace=True)

# Merge multi-province indicator
company_year = company_year.merge(
    multi_prov,
    on='company_id_raw',
    how='left'
)

# Multi-province dummy variable
company_year['multi_province_dummy'] = (company_year['num_provinces'] > 1).astype(int)

logger.info(f"  Computed multi-province indicator")
logger.info(f"  Single-province companies: {(company_year['multi_province_dummy']==0).sum():,}")
logger.info(f"  Multi-province companies: {(company_year['multi_province_dummy']==1).sum():,}")

# Green patent intensity (per tCO2e)
company_year['green_patent_intensity'] = np.where(
    company_year['total_emissions_co2e'] > 0,
    company_year['green_patent_stock'] / company_year['total_emissions_co2e'],
    0
)

logger.info(f"  Computed green patent intensity")

# ============================================================================
# SECTION 5: Data Quality and Validation
# ============================================================================

logger.info("")
logger.info("[STEP 5] Data quality checks...")

# Check for missing values
missing_summary = company_year[['total_emissions_co2e', 'green_patent_stock',
                                 'intensity_co2e_per_m_gdp']].isnull().sum()
logger.info(f"  - Missing emissions: {missing_summary['total_emissions_co2e']}")
logger.info(f"  - Missing green patents: {missing_summary['green_patent_stock']}")
logger.info(f"  - Missing intensity: {missing_summary['intensity_co2e_per_m_gdp']}")

# Replace NaN with 0 for green patent variables (not reported = no patents)
company_year['green_patent_stock'].fillna(0, inplace=True)
company_year['unique_patents'].fillna(0, inplace=True)
company_year['green_patent_count'].fillna(0, inplace=True)

# Descriptive statistics
logger.info("")
logger.info("[STEP 5.1] Descriptive statistics:")
logger.info(f"  Total emissions (tCO2e):")
logger.info(f"    Mean: {company_year['total_emissions_co2e'].mean():,.0f}")
logger.info(f"    Median: {company_year['total_emissions_co2e'].median():,.0f}")
logger.info(f"    Min: {company_year['total_emissions_co2e'].min():,.0f}")
logger.info(f"    Max: {company_year['total_emissions_co2e'].max():,.0f}")

logger.info(f"  Green patent stock:")
logger.info(f"    Mean: {company_year['green_patent_stock'].mean():.2f}")
logger.info(f"    Median: {company_year['green_patent_stock'].median():.2f}")
logger.info(f"    Companies with green patents: {(company_year['green_patent_stock'] > 0).sum():,}")
logger.info(f"    Pct with green patents: {100*(company_year['green_patent_stock'] > 0).mean():.1f}%")

logger.info(f"  Number of facilities per company (in given year):")
logger.info(f"    Mean: {company_year['num_facilities'].mean():.1f}")
logger.info(f"    Median: {company_year['num_facilities'].median():.0f}")
logger.info(f"    Max: {company_year['num_facilities'].max():.0f}")

# ============================================================================
# SECTION 6: Prepare Final Output
# ============================================================================

logger.info("")
logger.info("[STEP 6] Preparing final output...")

# Select and order columns
output_cols = [
    'company_id_raw',
    'company_id',
    'year',
    'company_name',
    'company_trade_name',
    'province',
    'num_provinces',
    'multi_province_dummy',
    'naics_code_3digit',
    'num_facilities',
    'total_emissions_co2e',
    'intensity_co2e_per_m_gdp',
    'carbon_price_real_2015',
    'exposure_price_it',
    'green_patent_count',
    'unique_patents',
    'green_patent_stock',
    'green_patent_intensity',
]

company_year_final = company_year[output_cols].copy()

# Sort by company and year
company_year_final.sort_values(['company_id', 'year'], inplace=True)
company_year_final.reset_index(drop=True, inplace=True)

# Save to CSV
company_year_final.to_csv(OUTPUT_FILE, index=False)
logger.info(f"  Saved to: {OUTPUT_FILE}")
logger.info(f"    File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB")

# ============================================================================
# SECTION 7: Generate Metadata
# ============================================================================

logger.info("")
logger.info("[STEP 7] Generating metadata...")

metadata_text = f"""
================================================================================
COMPANY-YEAR PANEL METADATA
================================================================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SOURCE DATA
-----------
Input file: {INPUT_FILE}
Records in input: {len(df):,}
Facility-year records processed: {len(df):,}

OUTPUT SUMMARY
--------------
Output file: {OUTPUT_FILE}
Company-year records: {len(company_year_final):,}
Unique companies: {company_year_final['company_id'].nunique():,}
Year range: {company_year_final['year'].min()}-{company_year_final['year'].max()}

VARIABLES
---------
Key identifiers:
  - company_id_raw: Standardized company legal name (uppercase, no punctuation)
  - company_id: Clean company identifier
  - year: Calendar year (2004-2023)
  - company_name: Original legal company name
  - company_trade_name: Trade/operating name

Geographic/structural:
  - province: Primary province (mode of facility locations)
  - num_provinces: Number of provinces where company operates
  - multi_province_dummy: Binary indicator for multi-province operations
  - naics_code_3digit: Primary NAICS code (3-digit, mode)
  - num_facilities: Number of facilities operated by company in year

Emissions variables:
  - total_emissions_co2e: Total CO2-equivalent emissions (tonnes)
  - intensity_co2e_per_m_gdp: Emissions per million dollars of GDP

Green patent variables:
  - green_patent_count: Number of green patents (fractional counting)
  - unique_patents: Number of unique patent IDs
  - green_patent_stock: Patent stock (perpetual inventory method, delta=0.15)
  - green_patent_intensity: Patent stock per tonne emissions

Policy variables:
  - carbon_price_real_2015: Real carbon price (2015 CAD)
  - exposure_price_it: Carbon price exposure indicator

DATA QUALITY NOTES
------------------
1. Null company names: Removed before aggregation
2. Green patent variables: NaN replaced with 0 (equivalent to no reported patents)
3. Intensity calculation: Weighted average using facility emissions as weights
4. Multi-province operations: Identified by parsing facility locations
5. Missing NAICS: Used mode; if no mode, used first facility's code

AGGREGATION RULES
------------------
Sum aggregation:
  - total_emissions_co2e
  - green_patent_count
  - unique_patents
  - green_patent_stock

Weighted average:
  - intensity_co2e_per_m_gdp (weights: facility emissions)

Mode (most frequent):
  - province
  - naics_code_3digit

First value:
  - company_name, company_trade_name
  - carbon_price_real_2015, exposure_price_it

Count:
  - num_facilities

SUMMARY STATISTICS
------------------
Total emissions (tCO2e):
  Mean: {company_year_final['total_emissions_co2e'].mean():,.0f}
  Median: {company_year_final['total_emissions_co2e'].median():,.0f}
  Std: {company_year_final['total_emissions_co2e'].std():,.0f}
  Min: {company_year_final['total_emissions_co2e'].min():,.0f}
  Max: {company_year_final['total_emissions_co2e'].max():,.0f}

Green patent stock:
  Mean: {company_year_final['green_patent_stock'].mean():.2f}
  Median: {company_year_final['green_patent_stock'].median():.2f}
  Std: {company_year_final['green_patent_stock'].std():.2f}
  Companies with patents: {(company_year_final['green_patent_stock'] > 0).sum():,} ({100*(company_year_final['green_patent_stock'] > 0).mean():.1f}%)

Facilities per company:
  Mean: {company_year_final['num_facilities'].mean():.1f}
  Median: {company_year_final['num_facilities'].median():.0f}
  Max: {company_year_final['num_facilities'].max():.0f}

NEXT STEPS
----------
1. Run 12_add_cfd_exposure.py to add CfD participation variables
2. Merge with control variables (revenue, employment, age, etc.)
3. Create balanced panel if needed for specific analysis
4. Run descriptive and regression analyses

================================================================================
"""

with open(METADATA_FILE, 'w', encoding='utf-8') as f:
    f.write(metadata_text)

logger.info(f"  Saved metadata to: {METADATA_FILE}")

# ============================================================================
# SUMMARY
# ============================================================================

logger.info("")
logger.info("=" * 80)
logger.info("COMPANY-YEAR PANEL CONSTRUCTION COMPLETE")
logger.info("=" * 80)
logger.info("")
logger.info(f"Output summary:")
logger.info(f"  - Company-year records: {len(company_year_final):,}")
logger.info(f"  - Unique companies: {company_year_final['company_id'].nunique():,}")
logger.info(f"  - Time period: {company_year_final['year'].min()}-{company_year_final['year'].max()}")
logger.info(f"  - Panel type: Unbalanced (not all companies present all years)")
logger.info(f"  - File: {OUTPUT_FILE.name}")
logger.info(f"  - Metadata: {METADATA_FILE.name}")
logger.info("")
logger.info("=" * 80)
