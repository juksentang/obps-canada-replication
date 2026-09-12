#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finalize the analysis-ready company-year dataset.
Inputs : data/processed/4_panels/company_year_panel_v1_*.csv (latest),
         data/processed/3_variables/exposure_cfd_enhanced_*.csv (latest; falls back to exposure_cfd_ct_*.csv)
Outputs: data/analysis_ready/analysis_ready_company_year_<date>.csv, descriptive_statistics_<date>.csv, CODEBOOK.md
Steps  : merge the company panel with the CfD exposure variables, add log transforms, indicators and company age,
         impute missing intensity, write descriptive statistics and the codebook.
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
(ROOT / 'logs').mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT / 'logs' / 'finalize_analysis_dataset.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths - auto-detect latest files
DATA_PANELS = DATA / 'processed' / '4_panels'
company_files = sorted(DATA_PANELS.glob('company_year_panel_v1_*.csv'))
if company_files:
    COMPANY_PANEL_FILE = company_files[-1]  # Get latest version
else:
    COMPANY_PANEL_FILE = DATA_PANELS / 'company_year_panel_v1_20251022.csv'

# Use enhanced CfD file from 15_integrate_cfd_and_matrices.py (or fall back to 12_add_cfd_exposure.py output)
DATA_VARS = DATA / 'processed' / '3_variables'
cfd_enhanced_files = sorted(DATA_VARS.glob('exposure_cfd_enhanced_*.csv'))
cfd_files = sorted(DATA_VARS.glob('exposure_cfd_ct_*.csv'))

if cfd_enhanced_files:
    CfD_FILE = cfd_enhanced_files[-1]
elif cfd_files:
    CfD_FILE = cfd_files[-1]
else:
    CfD_FILE = DATA_VARS / 'exposure_cfd_enhanced_20251023.csv'

OUTPUT_DIR = DATA / 'analysis_ready'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAIN_OUTPUT = OUTPUT_DIR / f'analysis_ready_company_year_{datetime.now().strftime("%Y%m%d")}.csv'
STATS_FILE = OUTPUT_DIR / f'descriptive_statistics_{datetime.now().strftime("%Y%m%d")}.csv'
CODEBOOK_FILE = OUTPUT_DIR / f'CODEBOOK.md'

# ============================================================================
# SECTION 1: Load Datasets
# ============================================================================

logger.info("=" * 80)
logger.info("FINALIZING ANALYSIS-READY DATASET")
logger.info("=" * 80)
logger.info("")

logger.info("[STEP 1] Loading datasets...")
try:
    company_panel = pd.read_csv(COMPANY_PANEL_FILE)
    cfd_data = pd.read_csv(CfD_FILE)
    logger.info(f"  Company panel: {len(company_panel):,} records")
    logger.info(f"  CfD data: {len(cfd_data):,} records")
except Exception as e:
    logger.error(f"  Failed to load data: {e}")
    raise

# ============================================================================
# SECTION 2: Merge Datasets
# ============================================================================

logger.info("")
logger.info("[STEP 2] Merging datasets...")

# Merge CfD data (enhanced variables from 15_integrate_cfd_and_matrices.py)
cfd_merge_cols = [
    'company_id', 'year', 'cfd_participant', 'cfd_type', 'cfd_contract_type',
    'cfd_start_year', 'cfd_end_year', 'cfd_term_years',
    'exposure_cfd_it', 'cfd_price_per_tonne', 'cfd_max_volume_tco2e',
    'cfd_contract_value_m_cad', 'cfd_ghgrp_match_status', 'cfd_spillover_potential'
]
df = company_panel.merge(
    cfd_data[cfd_merge_cols],
    on=['company_id', 'year'],
    how='left'
)

# Fill missing CfD indicators with 0/No/NaN as appropriate
df['cfd_participant'].fillna(0, inplace=True)
df['exposure_cfd_it'].fillna(0, inplace=True)
df['cfd_type'].fillna('No', inplace=True)
df['cfd_contract_type'].fillna('None', inplace=True)
df['cfd_ghgrp_match_status'].fillna('Non-CfD', inplace=True)
df['cfd_spillover_potential'].fillna(0, inplace=True)

logger.info(f"  Merged datasets: {len(df):,} company-year records")

# ============================================================================
# SECTION 3: Create Additional Variables
# ============================================================================

logger.info("")
logger.info("[STEP 3] Creating additional control variables...")

# Log transformations (for regression)
df['ln_emissions'] = np.log(df['total_emissions_co2e'] + 1)  # Add 1 to handle zeros
df['ln_green_patents'] = np.log(df['green_patent_stock'] + 1)
df['ln_patents_per_facility'] = np.log((df['green_patent_stock'] / df['num_facilities']) + 1)

# Squared emissions for nonlinear effects
df['emissions_squared'] = df['total_emissions_co2e'] ** 2

# Categorical variables for fixed effects
df['year_fe'] = df['year'].astype(str)
df['province_fe'] = df['province']
df['naics_fe'] = df['naics_code_3digit'].astype(str)

# Dummy for high emitters (top quartile)
emissions_q75 = df['total_emissions_co2e'].quantile(0.75)
df['high_emitter'] = (df['total_emissions_co2e'] > emissions_q75).astype(int)

# Dummy for green patent leaders (have green patents)
df['has_green_patents'] = (df['green_patent_stock'] > 0).astype(int)

# Company age (years since first appearance in data)
first_year_by_company = df.groupby('company_id')['year'].min().reset_index()
first_year_by_company.rename(columns={'year': 'company_start_year'}, inplace=True)
df = df.merge(first_year_by_company, on='company_id', how='left')
df['company_age'] = df['year'] - df['company_start_year']

# Growth indicator
df['emissions_growth_pct'] = df.groupby('company_id')['total_emissions_co2e'].pct_change() * 100

logger.info(f"  Created log transformations")
logger.info(f"  Created indicator variables")
logger.info(f"  Created company age variable")

# ============================================================================
# SECTION 4: Data Quality & Missing Values
# ============================================================================

logger.info("")
logger.info("[STEP 4] Data quality checks...")

# Check missing values
missing_summary = df.isnull().sum()
logger.info(f"  Missing values:")
for col in missing_summary[missing_summary > 0].index:
    pct_missing = 100 * missing_summary[col] / len(df)
    logger.info(f"    - {col}: {missing_summary[col]} ({pct_missing:.1f}%)")

# Handle missing intensity values
df['intensity_co2e_per_m_gdp'].fillna(df['intensity_co2e_per_m_gdp'].median(), inplace=True)

logger.info(f"  Missing values imputed")

# ============================================================================
# SECTION 5: Descriptive Statistics
# ============================================================================

logger.info("")
logger.info("[STEP 5] Computing descriptive statistics...")

# Summary statistics for key variables
summary_vars = [
    'total_emissions_co2e',
    'green_patent_stock',
    'green_patent_intensity',
    'num_facilities',
    'intensity_co2e_per_m_gdp',
    'carbon_price_real_2015',
    'company_age'
]

desc_stats = df[summary_vars].describe().T
desc_stats['missing'] = df[summary_vars].isnull().sum()
desc_stats['pct_missing'] = 100 * desc_stats['missing'] / len(df)

# Save descriptive statistics
desc_stats.to_csv(STATS_FILE)

logger.info(f"  Descriptive statistics:")
logger.info(f"    Total emissions (tCO2e): mean={df['total_emissions_co2e'].mean():,.0f}, "
            f"sd={df['total_emissions_co2e'].std():,.0f}")
logger.info(f"    Green patent stock: mean={df['green_patent_stock'].mean():.2f}, "
            f"sd={df['green_patent_stock'].std():.2f}")
logger.info(f"    Companies with green patents: {df['has_green_patents'].sum():,} "
            f"({100*df['has_green_patents'].mean():.1f}%)")
logger.info(f"    CfD participant obs: {df['cfd_participant'].sum():,} "
            f"({100*df['cfd_participant'].mean():.1f}%)")
logger.info(f"  Saved to: {STATS_FILE.name}")

# ============================================================================
# SECTION 6: Prepare Final Output
# ============================================================================

logger.info("")
logger.info("[STEP 6] Preparing final output...")

# Select and order key columns
key_cols = [
    # Identifiers
    'company_id', 'company_name', 'year',
    # Geographic
    'province', 'naics_code_3digit', 'multi_province_dummy',
    # Emissions variables
    'total_emissions_co2e', 'intensity_co2e_per_m_gdp',
    'ln_emissions', 'emissions_squared', 'high_emitter',
    # Green patent variables
    'green_patent_stock', 'green_patent_count', 'unique_patents',
    'green_patent_intensity', 'has_green_patents', 'ln_green_patents',
    # CfD variables
    'cfd_participant', 'cfd_type', 'exposure_cfd_it',
    # Carbon price variables
    'carbon_price_real_2015', 'exposure_price_it',
    # Structural variables
    'num_facilities', 'company_age', 'emissions_growth_pct',
    # Fixed effects
    'year_fe', 'province_fe', 'naics_fe'
]

df_final = df[key_cols].copy()
df_final.sort_values(['company_id', 'year'], inplace=True)
df_final.reset_index(drop=True, inplace=True)

# Save final dataset
df_final.to_csv(MAIN_OUTPUT, index=False)
logger.info(f"  Saved analysis-ready dataset: {MAIN_OUTPUT.name}")
logger.info(f"    Records: {len(df_final):,}")
logger.info(f"    Columns: {len(df_final.columns)}")
logger.info(f"    File size: {MAIN_OUTPUT.stat().st_size / 1024 / 1024:.2f} MB")

# ============================================================================
# SECTION 7: Generate Codebook
# ============================================================================

logger.info("")
logger.info("[STEP 7] Generating codebook...")

codebook = f"""
# ANALYSIS-READY DATASET CODEBOOK
## Company-Year Panel

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Dataset**: `{MAIN_OUTPUT.name}`

---

## TABLE OF CONTENTS
1. [Dataset Overview](#dataset-overview)
2. [Variable Dictionary](#variable-dictionary)
3. [Data Sources](#data-sources)
4. [Variable Construction](#variable-construction)
5. [Missing Values](#missing-values)
6. [Usage Notes](#usage-notes)

---

## DATASET OVERVIEW

### Dimensions
- **Records**: {len(df_final):,}
- **Unique companies**: {df_final['company_id'].nunique():,}
- **Time period**: {df_final['year'].min()}-{df_final['year'].max()}
- **Panel type**: Unbalanced (not all companies appear all years)

### Coverage
- **Provinces**: {df_final['province'].nunique()} (all Canadian provinces in data)
- **Industries**: {df_final['naics_code_3digit'].nunique()} NAICS 3-digit sectors
- **Years with data**: {sorted(df_final['year'].unique())}

---

## VARIABLE DICTIONARY

### IDENTIFIERS

| Variable | Type | Description | Range |
|----------|------|-------------|-------|
| `company_id` | String | Standardized company identifier | - |
| `company_name` | String | Company legal name | - |
| `year` | Integer | Calendar year | {df_final['year'].min()}-{df_final['year'].max()} |

### GEOGRAPHIC & STRUCTURAL

| Variable | Type | Description | Range |
|----------|------|-------------|-------|
| `province` | String | Primary province of operations | AB, BC, MB, NB, NL, NS, NT, ON, PE, QC, SK, YT |
| `naics_code_3digit` | String | North American Industry Classification (3-digit) | 221-562 |
| `multi_province_dummy` | Binary | 1 if company operates in multiple provinces | 0, 1 |
| `num_facilities` | Integer | Number of facilities operated by company (in year) | 1-98 |
| `company_age` | Integer | Years since company first appears in data | 0-20 |

### EMISSIONS VARIABLES

**Primary Outcome Variables** (main dependent variables for regression)

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `total_emissions_co2e` | Continuous | tCO2e | Total greenhouse gas emissions (CO2 equivalent) |
| `intensity_co2e_per_m_gdp` | Continuous | tCO2e/M GDP | Emission intensity (normalized by GDP) |
| `emissions_squared` | Continuous | (tCO2e)^2 | Squared emissions for nonlinear effects |
| `ln_emissions` | Continuous | log(tCO2e) | Natural log of emissions (for elasticity estimation) |

**Emission Indicators**

| Variable | Type | Description |
|----------|------|-------------|
| `high_emitter` | Binary | 1 if company emissions > 75th percentile |
| `emissions_growth_pct` | Continuous | Year-over-year % change in emissions |

### GREEN PATENT VARIABLES

**Patent Stocks** (main innovation indicator)

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `green_patent_stock` | Continuous | Patents | Patent stock (perpetual inventory method, delta=0.15) |
| `green_patent_count` | Continuous | Patents | Number of green patent flows (fractional counting) |
| `unique_patents` | Integer | Patents | Number of unique patent IDs |

**Patent Intensity**

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `green_patent_intensity` | Continuous | Patents/tCO2e | Patent stock per tonne CO2 equivalent |
| `ln_green_patents` | Continuous | log(Patents) | Natural log of patent stock (for elasticity) |
| `ln_patents_per_facility` | Continuous | log(Patents/facility) | Patent intensity per facility |

**Patent Indicators**

| Variable | Type | Description |
|----------|------|-------------|
| `has_green_patents` | Binary | 1 if company has any green patents (stock > 0) |

### POLICY EXPOSURE VARIABLES

**Carbon Price Exposure**

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `carbon_price_real_2015` | Continuous | CAD 2015 $/tonne | Real carbon price (constant 2015 dollars) |
| `exposure_price_it` | Binary | - | Carbon pricing policy exposure indicator |

**CfD (Contracts for Difference) Exposure**

| Variable | Type | Description |
|----------|------|-------------|
| `cfd_participant` | Binary | 1 if company is CfD/CCO participant |
| `cfd_type` | Categorical | Type: 'CCO', 'Carbon Policy CfD', or 'No' |
| `exposure_cfd_it` | Binary | 1 if year >= agreement year (treatment indicator) |

### FIXED EFFECT VARIABLES

| Variable | Type | Description | Usage |
|----------|------|-------------|-------|
| `year_fe` | String | Year indicator | Year fixed effects in regression |
| `province_fe` | String | Province indicator | Province fixed effects in regression |
| `naics_fe` | String | NAICS 3-digit indicator | Industry fixed effects in regression |

---

## DATA SOURCES

| Variable(s) | Source | Coverage | Last Updated |
|-------------|--------|----------|--------------|
| Emissions, intensity, facilities | GHGRP (Environment Canada) | 2004-2023 | 2024 |
| Green patents | CIPO (Canadian Patents) | 2000-2023 | 2024 |
| Carbon price | Federal carbon pricing policy | 2019-2023+ | Ongoing |
| CfD programs | CGF, Ministry of Energy | 2023-2025 | 2024 |

---

## VARIABLE CONSTRUCTION

### Emissions Variables

- **total_emissions_co2e**: Sum of all GHG emissions converted to CO2-equivalent using IPCC GWP values
- **intensity_co2e_per_m_gdp**: Emissions divided by provincial real GDP (millions 2015 CAD)
- **ln_emissions**: log(total_emissions_co2e + 1) to handle zero values

### Green Patent Variables

- **green_patent_stock**: Perpetual inventory model: Stock_t = (1 - delta) x Stock_{{t-1}} + Flow_t
  - Depreciation rate (delta) = 0.15
  - Flow = fractional count (1.0 per patent, distributed across NAICS sectors)
  - Allocated to companies using facility-level NAICS codes

- **green_patent_count**: Number of green patent grants (fractional counting)
  - Patents with multiple classifications distributed across industries
  - Weights sum to 1.0 per patent (weight conservation)

- **green_patent_intensity**: Stock per unit emissions (patents/tCO2e)

### Exposure Variables

- **exposure_price_it**: = 1 if carbon pricing was active in that year/province
- **exposure_cfd_it**: = 1 if company is CfD participant AND year >= agreement year

### Company Age

- First year: Earliest appearance of company in GHGRP data
- Age = current year - first year
- Can be interpreted as proxy for firm maturity

---

## MISSING VALUES

| Variable | N Missing | % Missing | Handling |
|----------|-----------|-----------|----------|
| intensity_co2e_per_m_gdp | {df['intensity_co2e_per_m_gdp'].isnull().sum()} | {100*df['intensity_co2e_per_m_gdp'].isnull().mean():.2f}% | Imputed with median |
| emissions_growth_pct | ~{df['emissions_growth_pct'].isnull().sum()} | ~{100*df['emissions_growth_pct'].isnull().mean():.1f}% | First year of company (expected) |
| Other variables | 0 | 0% | Complete |

**Note**: Missingness in green patent variables (set to 0) indicates no green patents reported/attributed.
This is substantively meaningful (absence of innovation) rather than a data quality issue.

---

## USAGE NOTES

### Panel Structure

- **Unbalanced panel**: Not all companies present all years
  - Total observations: {len(df_final):,}
  - Avg obs per company: {len(df_final) / df_final['company_id'].nunique():.1f}

- **Time span**: 2004-2023 ({df_final['year'].max() - df_final['year'].min() + 1} years)

- **Attrition**: Some companies exit after a certain year

### Variable Transformations

- **For elasticity estimation**: Use ln_emissions, ln_green_patents
- **For rate-of-change**: Use emissions_growth_pct
- **For threshold effects**: Use high_emitter, has_green_patents dummies
- **For heterogeneity**: Interact with multi_province_dummy, high_emitter, etc.

### Sample Restrictions

1. **Unbalanced vs balanced**:
   - Unbalanced: all data (current)
   - Balanced: companies with all 20 years (about {(df_final.groupby('company_id')['year'].count() == 20).sum()} companies)

2. **Industry restriction**: some analyses focus on specific NAICS sectors (e.g. energy-intensive industries)

---

## CITATIONS & REFERENCES

**GHGRP Data**:
Environment and Climate Change Canada. "Greenhouse Gas Reporting Program (GHGRP)."
https://www.canada.ca/en/environment-climate-change/services/climate-change/pricing-pollution-how-it-will-work/industry/facility-greenhouse-gas-emissions.html

**Patent Data**:
Canadian Intellectual Property Office (CIPO). "Canadian Patents Database."
https://www.ic.gc.ca/eic/site/cipointernet-internetopic.nsf/eng/Home

**IPC-NAICS Mapping**:
Based on OECD Technology Concordance tables mapping IPC codes to NAICS sectors.

---

**Generated**: {datetime.now().strftime('%Y-%m-%d')}

"""

with open(CODEBOOK_FILE, 'w', encoding='utf-8') as f:
    f.write(codebook)

logger.info(f"  Generated codebook: {CODEBOOK_FILE.name}")

# ============================================================================
# SECTION 8: Summary Report
# ============================================================================

logger.info("")
logger.info("=" * 80)
logger.info("ANALYSIS-READY DATASET FINALIZED")
logger.info("=" * 80)
logger.info("")

logger.info("FINAL DATASET SUMMARY")
logger.info("-" * 80)
logger.info(f"  Records: {len(df_final):,}")
logger.info(f"  Unique companies: {df_final['company_id'].nunique():,}")
logger.info(f"  Years: {df_final['year'].min()}-{df_final['year'].max()}")
logger.info(f"  Provinces: {df_final['province'].nunique()}")
logger.info(f"  Industries (NAICS 3-digit): {df_final['naics_code_3digit'].nunique()}")
logger.info("")

logger.info("KEY STATISTICS")
logger.info("-" * 80)
logger.info(f"  Mean emissions: {df_final['total_emissions_co2e'].mean():,.0f} tCO2e")
logger.info(f"  Mean green patents: {df_final['green_patent_stock'].mean():.2f}")
logger.info(f"  Companies with green patents: {df_final['has_green_patents'].sum():,} ({100*df_final['has_green_patents'].mean():.1f}%)")
logger.info(f"  CfD participant companies: {df_final['cfd_participant'].sum():,} ({100*df_final['cfd_participant'].mean():.1f}%)")
logger.info("")

logger.info("OUTPUT FILES")
logger.info("-" * 80)
logger.info(f"  1. Analysis dataset: {MAIN_OUTPUT.name}")
logger.info(f"  2. Descriptive statistics: {STATS_FILE.name}")
logger.info(f"  3. Codebook: {CODEBOOK_FILE.name}")
logger.info("")

logger.info("=" * 80)
