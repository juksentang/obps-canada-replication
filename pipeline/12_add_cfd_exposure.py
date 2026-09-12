#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add carbon contract-for-difference (CfD / carbon credit offtake) participation and exposure indicators to the
company-year panel by matching the names of the publicly announced Canada Growth Fund counterparties
(Entropy, Gibson Energy / Varme Energy, Markham District Energy) and their agreement start years.

Input:  data/processed/4_panels/company_year_panel_v1_20251022.csv
Output: data/processed/3_variables/exposure_cfd_ct_v1_<date>.csv, exposure_cfd_metadata_<date>.txt
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
(ROOT / 'logs').mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT / 'logs' / 'add_cfd_exposure.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths
COMPANY_PANEL_FILE = DATA / 'processed' / '4_panels' / 'company_year_panel_v1_20251022.csv'
OUTPUT_DIR = DATA / 'processed' / '3_variables'
OUTPUT_FILE = OUTPUT_DIR / f'exposure_cfd_ct_v1_{datetime.now().strftime("%Y%m%d")}.csv'
METADATA_FILE = OUTPUT_DIR / f'exposure_cfd_metadata_{datetime.now().strftime("%Y%m%d")}.txt'

# ============================================================================
# SECTION 1: Define CfD Participants
# ============================================================================

logger.info("=" * 80)
logger.info("CfD EXPOSURE VARIABLE CONSTRUCTION")
logger.info("=" * 80)
logger.info("")

# CfD database: company_name_patterns, start_year, end_year, type, price
cfd_participants = {
    'entropy': {
        'name_patterns': ['ENTROPY', 'ENTROPY INC'],
        'provinces': ['Alberta'],
        'cities': ['Calgary'],
        'start_year': 2024,  # Agreement signed Dec 2023, implementation 2024
        'end_year': 2038,    # 15-year term: 2024-2038
        'cfd_type': 'CCO',
        'initial_price': 86.50,
        'max_volume': 1000000,  # tCO2e/year
        'actual_volume': 185000,  # Glacier Phase 2
        'status': 'Signed',
        'fid_date': '2023-12-20',
    },
    'gibsonenergy': {
        'name_patterns': ['GIBSON ENERGY', 'GIBSON', 'VARME ENERGY'],
        'provinces': ['Alberta'],
        'cities': ['Edmonton'],
        'start_year': 2025,  # FID expected early 2025, operations later
        'end_year': 2039,    # 15-year term
        'cfd_type': 'CCO',
        'initial_price': 85.00,
        'max_volume': 200000,
        'status': 'Signed (FID pending)',
        'fid_date': '2024-06-11',
    },
    'markhamde': {
        'name_patterns': ['MARKHAM DISTRICT ENERGY', 'MARKHAM DISTRICT', 'MDE'],
        'provinces': ['Ontario'],
        'cities': ['Markham', 'Vaughan'],
        'start_year': 2025,  # Project under development
        'end_year': 2034,    # 10-year term
        'cfd_type': 'Carbon Policy CfD',
        'strike_price': 100.00,
        'potential_reduction': 177400,  # tCO2e
        'status': 'Signed',
        'fid_date': '2024-06-26',
    }
}

logger.info("[SETUP] Configured CfD participants:")
for cfd_id, details in cfd_participants.items():
    logger.info(f"  - {cfd_id.upper()}: {details['start_year']}-{details['end_year']} "
                f"({details['cfd_type']})")

# ============================================================================
# SECTION 2: Load Company Panel
# ============================================================================

logger.info("")
logger.info("[STEP 1] Loading company-year panel...")
try:
    company_panel = pd.read_csv(COMPANY_PANEL_FILE)
    logger.info(f"  Loaded {len(company_panel):,} company-year records")
    logger.info(f"  Unique companies: {company_panel['company_id'].nunique():,}")
except Exception as e:
    logger.error(f"  Failed to load company panel: {e}")
    raise

# ============================================================================
# SECTION 3: Identify CfD Participants
# ============================================================================

logger.info("")
logger.info("[STEP 2] Matching CfD participants...")

# Initialize CfD variables
company_panel['cfd_participant'] = 0
company_panel['cfd_type'] = 'No'
company_panel['cfd_start_year'] = np.nan
company_panel['exposure_cfd_it'] = 0

# Track matches for reporting
matched_companies = []
match_details = []

# Iterate through company names and check for CfD matches
for idx, row in company_panel.iterrows():
    company_name = row['company_name'].upper().strip()
    company_year = row['year']

    for cfd_id, details in cfd_participants.items():
        # Check if any pattern matches
        for pattern in details['name_patterns']:
            if pattern in company_name:
                # Additional validation: check province (if available)
                if pd.notna(row['province']):
                    if row['province'] not in details['provinces']:
                        continue  # Wrong province, skip

                # Mark as CfD participant
                company_panel.at[idx, 'cfd_participant'] = 1
                company_panel.at[idx, 'cfd_type'] = details['cfd_type']
                company_panel.at[idx, 'cfd_start_year'] = details['start_year']

                # Set exposure indicator (1 if year >= start_year)
                if company_year >= details['start_year']:
                    company_panel.at[idx, 'exposure_cfd_it'] = 1

                matched_companies.append(row['company_name'])
                match_details.append({
                    'company_name': row['company_name'],
                    'cfd_id': cfd_id,
                    'cfd_type': details['cfd_type'],
                    'years_in_panel': company_panel[company_panel['company_id'] == row['company_id']].shape[0]
                })
                break  # Found match for this company, stop checking

logger.info(f"  Identified CfD participants:")

# Print matches found
if matched_companies:
    unique_matches = set(matched_companies)
    for company in sorted(unique_matches):
        cfd_years = company_panel[
            (company_panel['company_name'] == company) &
            (company_panel['exposure_cfd_it'] == 1)
        ]['year']
        start_year = company_panel[company_panel['company_name'] == company]['cfd_start_year'].iloc[0]
        cfd_type = company_panel[company_panel['company_name'] == company]['cfd_type'].iloc[0]

        logger.info(f"    - {company}: {cfd_type} (starts {int(start_year)})")
        logger.info(f"      Exposed years in panel: {sorted(cfd_years.tolist()) if len(cfd_years) > 0 else 'None'}")
else:
    logger.warning("  No CfD participants matched in company panel")
    logger.info("  This may indicate companies are not in the GHGRP dataset")

# ============================================================================
# SECTION 4: Data Quality Checks
# ============================================================================

logger.info("")
logger.info("[STEP 3] Data quality checks...")

n_cfd_companies = company_panel[company_panel['cfd_participant'] == 1]['company_id'].nunique()
n_cfd_obs = (company_panel['cfd_participant'] == 1).sum()
n_exposed_obs = (company_panel['exposure_cfd_it'] == 1).sum()

logger.info(f"  CfD participant companies: {n_cfd_companies}")
logger.info(f"  Observations for CfD companies: {n_cfd_obs}")
logger.info(f"  Observations with exposure (year >= start): {n_exposed_obs}")

if n_cfd_obs == 0:
    logger.warning("  No observations for CfD companies found in dataset")
    logger.warning("  Likely reason: CfD counterparties do not yet report to the GHGRP")

# ============================================================================
# SECTION 5: Prepare Output
# ============================================================================

logger.info("")
logger.info("[STEP 4] Preparing CfD exposure dataset...")

# Select relevant columns for output
cfd_output = company_panel[[
    'company_id_raw',
    'company_id',
    'year',
    'company_name',
    'province',
    'cfd_participant',
    'cfd_type',
    'cfd_start_year',
    'exposure_cfd_it',
]].copy()

# Sort by company and year
cfd_output.sort_values(['company_id', 'year'], inplace=True)
cfd_output.reset_index(drop=True, inplace=True)

# Save output
cfd_output.to_csv(OUTPUT_FILE, index=False)
logger.info(f"  Saved to: {OUTPUT_FILE}")

# ============================================================================
# SECTION 6: Generate Metadata
# ============================================================================

logger.info("")
logger.info("[STEP 5] Generating metadata...")

metadata_text = f"""
================================================================================
CfD (Contracts for Difference) EXPOSURE VARIABLES - METADATA
================================================================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SOURCE DATA
-----------
Input file: {COMPANY_PANEL_FILE}
Input records: {len(company_panel):,}
Unique companies: {company_panel['company_id'].nunique():,}

OUTPUT SUMMARY
--------------
Output file: {OUTPUT_FILE}
Records: {len(cfd_output):,}
CfD participant companies found: {n_cfd_companies}
Observations for CfD companies: {n_cfd_obs}
Observations with exposure (year >= start_year): {n_exposed_obs}

VARIABLE DEFINITIONS
---------------------
cfd_participant (0/1):
  - 1 if company is known CfD/CCO participant
  - 0 otherwise
  - Note: Based on name matching to confirmed participants

cfd_type:
  - 'CCO' = Carbon Credit Offtake (Entropy, Gibson/Varme)
  - 'Carbon Policy CfD' = Two-way CfD (Markham District Energy)
  - 'No' = Not a CfD participant

cfd_start_year:
  - Calendar year when CfD exposure begins
  - Based on agreement signing date or FID expectation
  - NaN for non-participants

exposure_cfd_it (0/1):
  - 1 if year >= cfd_start_year AND cfd_participant == 1
  - 0 otherwise
  - This is the main treatment variable for CfD exposure analysis

CONFIRMED CfD PARTICIPANTS
---------------------------

1. ENTROPY INC.
   Location: Calgary, Alberta
   Type: Carbon Credit Offtake (CCO)
   Agreement Date: December 20, 2023
   Start Year: 2024
   Duration: 15 years (2024-2038)
   Price: CAD $86.50/tonne
   Max Volume: 1,000,000 tCO2e/year
   Actual Volume: 185,000 tCO2e/year (Glacier Phase 2, first project)
   Status: Active
   Data Source: Canada.ca official announcement

2. GIBSON ENERGY INC. / VARME ENERGY INC.
   Location: Edmonton, Alberta
   Type: Carbon Credit Offtake (CCO)
   Agreement Date: June 11, 2024
   Start Year: 2025 (expected)
   Duration: 15 years (2025-2039)
   Technology: Waste-to-energy with CO2 capture and storage (CCS)
   Price: CAD $85/tonne
   Max Volume: 200,000 tCO2e/year
   Status: FID (Final Investment Decision) expected early 2025
   Data Source: Canada.ca and Gibson Energy announcement

3. MARKHAM DISTRICT ENERGY INC. (MDE)
   Location: Markham, Ontario
   Type: Carbon Policy CfD (two-way)
   Agreement Date: June 26, 2024
   Start Year: 2025 (expected)
   Duration: 10 years (2025-2034)
   Technology: Wastewater source heat energy transfer (WET system)
   Strike Price: CAD $100/tonne
   Potential CO2 Reduction: 177,400 tCO2e
   Features: Two-way strike: CGF pays if carbon price < $100, MDE pays if > $100
   Status: Active (project under development)
   Data Source: Canada.ca and CGF (Canada Growth Fund)

DATA QUALITY NOTES
-------------------
No CfD participants are found in the GHGRP panel through 2023: the counterparties are new or pre-operational
projects, and agreements were signed in 2023-2024. The variables are therefore all zero in the current panel and
are kept for completeness. Company names from the agreements may also differ from GHGRP legal-entity names.

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
logger.info("CfD EXPOSURE VARIABLE CONSTRUCTION COMPLETE")
logger.info("=" * 80)
logger.info("")

if n_cfd_obs > 0:
    logger.info("CfD participants found in data:")
    logger.info(f"  - Companies: {n_cfd_companies}")
    logger.info(f"  - Total observations: {n_cfd_obs}")
    logger.info(f"  - Exposed observations: {n_exposed_obs}")
else:
    logger.info("No CfD participants currently in GHGRP data (counterparties are new or pre-operational)")

logger.info("")
logger.info(f"  Output file: {OUTPUT_FILE.name}")
logger.info(f"  Metadata: {METADATA_FILE.name}")
logger.info("")
logger.info("=" * 80)
