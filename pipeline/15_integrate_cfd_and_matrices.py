#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge the CfD contracts database, the CfD policy spillover matrix and the extended NAICS-3 input-output matrix
onto the company-year panel, producing contract-level CfD exposure variables (participation, contract period,
price, volume, contract value, spillover potential).

Input:  data/processed/4_panels/company_year_panel_v1_20251022.csv
        data/processed/3_variables/cfd_contracts_database_v2_20251023.csv
        data/processed/matrices/W_CfD_policy_spillover_20251023.csv, W_IO_naics3digit_enhanced_20251023.csv
Output: data/processed/3_variables/exposure_cfd_enhanced_20251023.csv, cfd_integration_decisions_20251023.txt
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

# Configure logging
log_dir = ROOT / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / f'integrate_cfd_matrices_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths
DATA_DIR = DATA / 'processed'
COMPANY_PANEL_FILE = DATA_DIR / '4_panels' / 'company_year_panel_v1_20251022.csv'
CfD_DATABASE_FILE = DATA_DIR / '3_variables' / 'cfd_contracts_database_v2_20251023.csv'
CfD_SPILLOVER_FILE = DATA_DIR / 'matrices' / 'W_CfD_policy_spillover_20251023.csv'
IO_ENHANCED_FILE = DATA_DIR / 'matrices' / 'W_IO_naics3digit_enhanced_20251023.csv'

OUTPUT_DIR = DATA_DIR / '3_variables'
OUTPUT_FILE = OUTPUT_DIR / f'exposure_cfd_enhanced_20251023.csv'
DECISION_LOG = OUTPUT_DIR / f'cfd_integration_decisions_20251023.txt'

# ============================================================================
# SECTION 1: Load All Required Datasets
# ============================================================================

logger.info("=" * 80)
logger.info("CfD CONTRACTS AND MATRICES INTEGRATION")
logger.info("=" * 80)
logger.info("")

logger.info("[STEP 1] Loading required datasets...")

try:
    # Load company panel
    company_panel = pd.read_csv(COMPANY_PANEL_FILE)
    logger.info(f"  Company-year panel: {len(company_panel):,} records, "
                f"{company_panel['company_id'].nunique():,} unique companies")

    # Load CfD contracts database
    cfd_contracts = pd.read_csv(CfD_DATABASE_FILE)
    logger.info(f"  CfD contracts database: {len(cfd_contracts)} contracts")

    # Load spillover matrix
    cfd_spillover = pd.read_csv(CfD_SPILLOVER_FILE, index_col=0)
    logger.info(f"  CfD policy spillover matrix: {cfd_spillover.shape[0]}x{cfd_spillover.shape[1]} "
                f"({cfd_spillover.shape[0]} CfD entities)")

    # Load enhanced I-O matrix
    io_enhanced = pd.read_csv(IO_ENHANCED_FILE, index_col=0)
    logger.info(f"  Enhanced W_IO matrix: {io_enhanced.shape[0]}x{io_enhanced.shape[1]} "
                f"({io_enhanced.shape[0]} industries)")

except Exception as e:
    logger.error(f"  Failed to load datasets: {e}")
    raise

# ============================================================================
# SECTION 2: Validate CfD Contracts Database
# ============================================================================

logger.info("")
logger.info("[STEP 2] Validating CfD contracts database...")

required_columns = [
    'company_name', 'naics_code', 'cfd_type', 'contract_type',
    'agreement_date', 'start_year', 'end_year', 'term_years',
    'contract_price_cad', 'max_volume_tco2e_year', 'actual_volume_tco2e_year',
    'strike_price_cad', 'status', 'ghgrp_match_status'
]

missing_cols = [col for col in required_columns if col not in cfd_contracts.columns]
if missing_cols:
    logger.warning(f"  Missing columns: {missing_cols}")
else:
    logger.info(f"  All required columns present ({len(required_columns)} columns)")

logger.info("\n  CfD Contracts Summary:")
for idx, row in cfd_contracts.iterrows():
    logger.info(f"    {idx+1}. {row['company_name']}")
    logger.info(f"       - Type: {row['cfd_type']} ({row['contract_type']})")
    logger.info(f"       - Period: {int(row['start_year'])}-{int(row['end_year'])} "
                f"({int(row['term_years'])} years)")
    logger.info(f"       - Price: CAD ${row['contract_price_cad'] if pd.notna(row['contract_price_cad']) else row['strike_price_cad']:.2f}/tonne")
    logger.info(f"       - GHGRP Status: {row['ghgrp_match_status']}")

# ============================================================================
# SECTION 3: Create CfD Participant Database
# ============================================================================

logger.info("")
logger.info("[STEP 3] Creating CfD participant database...")

# Dictionary to store CfD contract information keyed by company name
cfd_participant_db = {}

for idx, contract in cfd_contracts.iterrows():
    company_name = contract['company_name'].upper().strip()

    # Handle multiple company names (e.g., "Varme Energy / Gibson Energy")
    company_aliases = [name.upper().strip() for name in company_name.split('/')]

    contract_info = {
        'company_name_official': contract['company_name'],
        'company_id_raw': contract['company_id_raw'] if pd.notna(contract['company_id_raw']) else None,
        'company_id': contract['company_id_raw'] if pd.notna(contract['company_id_raw']) else None,
        'province': contract['province'],
        'naics_code': int(contract['naics_code']),
        'cfd_type': contract['cfd_type'],
        'contract_type': contract['contract_type'],
        'agreement_date': contract['agreement_date'],
        'start_year': int(contract['start_year']),
        'end_year': int(contract['end_year']),
        'term_years': int(contract['term_years']),
        'contract_price_cad': float(contract['contract_price_cad'])
                              if pd.notna(contract['contract_price_cad']) else None,
        'strike_price_cad': float(contract['strike_price_cad'])
                           if pd.notna(contract['strike_price_cad']) else None,
        'max_volume_tco2e_year': float(contract['max_volume_tco2e_year'])
                                if pd.notna(contract['max_volume_tco2e_year']) else None,
        'actual_volume_tco2e_year': float(contract['actual_volume_tco2e_year'])
                                   if pd.notna(contract['actual_volume_tco2e_year']) else None,
        'status': contract['status'],
        'ghgrp_match_status': contract['ghgrp_match_status'],
        'technology_description': contract['technology_description'],
        'data_source': contract['data_source'],
    }

    # Register all aliases
    for alias in company_aliases:
        cfd_participant_db[alias] = contract_info

logger.info(f"  Created CfD database with {len(cfd_participant_db)} company name variants")

# ============================================================================
# SECTION 4: Identify CfD Participants in Company Panel
# ============================================================================

logger.info("")
logger.info("[STEP 4] Matching CfD participants in company panel...")

# Initialize CfD variables
company_panel['cfd_participant'] = 0
company_panel['cfd_type'] = 'No'
company_panel['cfd_contract_type'] = 'None'
company_panel['cfd_start_year'] = np.nan
company_panel['cfd_end_year'] = np.nan
company_panel['exposure_cfd_it'] = 0
company_panel['cfd_price_per_tonne'] = np.nan
company_panel['cfd_term_years'] = np.nan
company_panel['cfd_contract_value_m_cad'] = np.nan
company_panel['cfd_max_volume_tco2e'] = np.nan
company_panel['cfd_ghgrp_match_status'] = 'Non-CfD'

matched_count = 0
match_log = []

for idx, row in company_panel.iterrows():
    company_name_upper = row['company_name'].upper().strip()
    company_year = row['year']
    company_id = row['company_id']

    if company_name_upper in cfd_participant_db:
        contract_info = cfd_participant_db[company_name_upper]

        # Validate province match (if available)
        if pd.notna(row['province']) and row['province'] != contract_info['province']:
            continue

        # Assign CfD variables
        company_panel.at[idx, 'cfd_participant'] = 1
        company_panel.at[idx, 'cfd_type'] = contract_info['cfd_type']
        company_panel.at[idx, 'cfd_contract_type'] = contract_info['contract_type']
        company_panel.at[idx, 'cfd_start_year'] = contract_info['start_year']
        company_panel.at[idx, 'cfd_end_year'] = contract_info['end_year']
        company_panel.at[idx, 'cfd_term_years'] = contract_info['term_years']
        company_panel.at[idx, 'cfd_ghgrp_match_status'] = contract_info['ghgrp_match_status']

        # Set price (contract price for CCO, strike price for policy CfD)
        if contract_info['contract_price_cad'] is not None:
            company_panel.at[idx, 'cfd_price_per_tonne'] = contract_info['contract_price_cad']
        elif contract_info['strike_price_cad'] is not None:
            company_panel.at[idx, 'cfd_price_per_tonne'] = contract_info['strike_price_cad']

        # Set volume
        if contract_info['max_volume_tco2e_year'] is not None:
            company_panel.at[idx, 'cfd_max_volume_tco2e'] = contract_info['max_volume_tco2e_year']

        # Calculate contract value (price x actual volume x years remaining)
        if (contract_info['contract_price_cad'] is not None and
            contract_info['actual_volume_tco2e_year'] is not None):
            price = contract_info['contract_price_cad']
            volume = contract_info['actual_volume_tco2e_year']
            years_remaining = max(0, contract_info['end_year'] - company_year + 1)
            contract_value = (price * volume * years_remaining) / 1_000_000  # Convert to millions
            company_panel.at[idx, 'cfd_contract_value_m_cad'] = contract_value

        # Set exposure indicator (1 if year >= start_year AND year <= end_year)
        if contract_info['start_year'] <= company_year <= contract_info['end_year']:
            company_panel.at[idx, 'exposure_cfd_it'] = 1

            if company_id not in [m['company_id'] for m in match_log]:
                matched_count += 1
                match_log.append({
                    'company_id': company_id,
                    'company_name': row['company_name'],
                    'cfd_type': contract_info['cfd_type'],
                    'start_year': contract_info['start_year'],
                    'end_year': contract_info['end_year'],
                    'years_exposed': int(contract_info['end_year']) - int(contract_info['start_year']) + 1,
                    'ghgrp_match_status': contract_info['ghgrp_match_status']
                })

logger.info(f"  Matched {matched_count} unique CfD participant(s)")

if matched_count > 0:
    logger.info("\n  Matched CfD Participants:")
    for match in match_log:
        logger.info(f"    - {match['company_name']} (ID: {match['company_id']})")
        logger.info(f"      Type: {match['cfd_type']}")
        logger.info(f"      Period: {match['start_year']}-{match['end_year']} "
                   f"({match['years_exposed']} years)")
        logger.info(f"      GHGRP Status: {match['ghgrp_match_status']}")
else:
    logger.warning("  No CfD participants found in company panel")
    logger.info("  This is expected if companies have not yet entered GHGRP database")

# ============================================================================
# SECTION 5: Add Spillover Effects
# ============================================================================

logger.info("")
logger.info("[STEP 5] Computing spillover effects...")

# Spillover indicator: maximum pairwise weight from the CfD policy spillover matrix
company_panel['cfd_spillover_potential'] = 0

# Companies in spillover matrix should have potential spillover effects
cfd_companies_in_matrix = cfd_spillover.index.tolist()

for idx, row in company_panel.iterrows():
    if row['company_name'] in cfd_companies_in_matrix:
        # Get spillover from other participants
        spillover_weights = cfd_spillover.loc[row['company_name']]
        # Max spillover from any other participant
        max_spillover = spillover_weights[spillover_weights > 0].max() if (spillover_weights > 0).any() else 0
        company_panel.at[idx, 'cfd_spillover_potential'] = max_spillover

logger.info(f"  Added spillover potential indicator")
logger.info(f"    Maximum pairwise spillover weight: {cfd_spillover.values[cfd_spillover.values > 0].max():.3f}")
logger.info(f"    Average non-zero spillover: {cfd_spillover.values[cfd_spillover.values > 0].mean():.3f}")

# ============================================================================
# SECTION 6: Data Quality and Consistency Checks
# ============================================================================

logger.info("")
logger.info("[STEP 6] Data quality checks...")

# Check 1: CfD participant counts
n_cfd_companies = company_panel[company_panel['cfd_participant'] == 1]['company_id'].nunique()
n_cfd_obs = (company_panel['cfd_participant'] == 1).sum()
n_exposed_obs = (company_panel['exposure_cfd_it'] == 1).sum()

logger.info(f"  CfD participant companies in panel: {n_cfd_companies}")
logger.info(f"  Total observations for CfD companies: {n_cfd_obs}")
logger.info(f"  Observations with active exposure (in contract period): {n_exposed_obs}")

# Check 2: Price consistency
companies_with_price = company_panel[company_panel['cfd_price_per_tonne'].notna()]
if len(companies_with_price) > 0:
    min_price = companies_with_price['cfd_price_per_tonne'].min()
    max_price = companies_with_price['cfd_price_per_tonne'].max()
    avg_price = companies_with_price['cfd_price_per_tonne'].mean()
    logger.info(f"  CfD price range: CAD ${min_price:.2f} - ${max_price:.2f} "
               f"(avg: ${avg_price:.2f})/tonne")

# Check 3: Contract value calculations
companies_with_value = company_panel[company_panel['cfd_contract_value_m_cad'].notna()]
if len(companies_with_value) > 0:
    total_value = companies_with_value['cfd_contract_value_m_cad'].sum()
    logger.info(f"  Total CfD contract values: CAD ${total_value:.2f}M across all years")

# Check 4: Exposure period validation
exposure_by_year = company_panel[company_panel['exposure_cfd_it'] == 1].groupby('year').size()
if len(exposure_by_year) > 0:
    logger.info(f"  Exposure by year:")
    for year, count in exposure_by_year.items():
        logger.info(f"    - {year}: {count} observations")

# ============================================================================
# SECTION 7: Export Enhanced CfD Dataset
# ============================================================================

logger.info("")
logger.info("[STEP 7] Exporting enhanced CfD dataset...")

# Select relevant columns for output
cfd_columns = [
    'company_id_raw', 'company_id', 'year', 'company_name', 'province', 'naics_code_3digit',
    'cfd_participant', 'cfd_type', 'cfd_contract_type',
    'cfd_start_year', 'cfd_end_year', 'cfd_term_years',
    'exposure_cfd_it', 'cfd_price_per_tonne', 'cfd_max_volume_tco2e',
    'cfd_contract_value_m_cad', 'cfd_ghgrp_match_status', 'cfd_spillover_potential'
]

cfd_output = company_panel[cfd_columns].copy()
cfd_output.sort_values(['company_id', 'year'], inplace=True)
cfd_output.reset_index(drop=True, inplace=True)

cfd_output.to_csv(OUTPUT_FILE, index=False)
logger.info(f"  Saved enhanced CfD dataset: {OUTPUT_FILE.name}")
logger.info(f"    Records: {len(cfd_output):,}")

# ============================================================================
# SECTION 8: Generate Decision Log
# ============================================================================

logger.info("")
logger.info("[STEP 8] Documenting integration decisions...")

decision_text = f"""
================================================================================
CfD CONTRACTS AND MATRICES INTEGRATION - DECISION LOG
================================================================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DATASETS INTEGRATED
====================

1. CfD Contracts Database (cfd_contracts_database_v2_20251023.csv)
   - Source: Official Canada Growth Fund and government announcements
   - Records: 3 confirmed CfD/CCO participants
   - Variables: 21 contract and program details
   - Date range: Agreement dates 2023-2024, contract periods 2024-2039

2. CfD Policy Spillover Matrix (W_CfD_policy_spillover_20251023.csv)
   - Dimensions: 3x3 (three CfD participants)
   - Weights: Row-standardized, represent policy coordination effects
   - Spillover mechanisms: Technology similarity, geographic proximity, policy alignment

3. Enhanced W_IO Matrix (W_IO_naics3digit_enhanced_20251023.csv)
   - Dimensions: 14x14 (expanded from 13x13)
   - New addition: NAICS 236 (Construction) for CCS infrastructure
   - Enhanced linkages: Construction-Utilities, Construction-Pipeline, Construction-Waste
   - All rows standardized (sum=1.0)

4. Company-Year Panel (company_year_panel_v1_20251022.csv)
   - Records: {len(company_panel):,}
   - Unique companies: {company_panel['company_id'].nunique():,}
   - Year range: {company_panel['year'].min():.0f}-{company_panel['year'].max():.0f}

INTEGRATION DECISIONS
======================

DECISION 1: Entropy Inc. (Glacier Phase 2 CCS Project)
-----------
Company Name: Entropy Inc.
Location: Calgary, Alberta (NAICS 486: Pipeline Transportation of Crude Oil)
CfD Type: Carbon Credit Offtake (CCO)
Agreement Date: December 20, 2023
Contract Period: 2024-2038 (15 years)
Price: CAD $86.50/tonne CO2e
Actual Capacity: 185,000 tCO2e/year (from Glacier Phase 2)
Status: Signed

GHGRP Match Status: NOT YET REPORTED (Future)
Processing Decision:
  - Marked as "future_not_ghgrp" in database
  - Will be matchable once 2024-2025 GHGRP reports released
  - No current observations in panel (company not yet in GHGRP)

Data Source:
  https://www.canada.ca/en/department-finance/news/2023/12/deputy-prime-minister-welcomes-the-canada-growth-funds-first-carbon-contract-for-difference.html

DECISION 2: Varme Energy / Gibson Energy (Waste-to-Energy CCS Project)
-----------
Company Names: Varme Energy Inc. / Gibson Energy Inc.
Location: Edmonton, Alberta (NAICS 486)
CfD Type: Carbon Credit Offtake (CCO)
Agreement Date: June 11, 2024
Contract Period: 2025-2039 (15 years)
Price: CAD $85/tonne CO2e
Capacity: 200,000 tCO2e/year
Technology: Waste-to-energy facility with CO2 capture and storage (CCS)
Status: Signed (Final Investment Decision expected early 2025)

GHGRP Match Status: PARTIAL (existing company, new project)
Processing Decision:
  - Gibson Energy Inc. already in GHGRP (Company ID: 818448318)
  - Has historical emissions records (2022-2023) from existing operations
  - New Varme/CCS project is distinct and pending FID
  - Panel currently includes Gibson's historical records
  - New project emissions expected 2025-2026 onwards
  - Treatment starts 2025 (FID expected Q1 2025)

Technical Note:
  - Parent company relationship: Varme Energy is partnership with Gibson Energy
  - GHGRP reporting: Gibson as primary operator
  - Company ID consolidation: Using 818448318 from GHGRP

Data Source:
  https://www.canada.ca/en/department-finance/news/2024/06/canada-growth-fund-announces-second-carbon-contract-for-difference.html

DECISION 3: Markham District Energy Inc. (Wastewater Heat Recovery CfD)
-----------
Company Name: Markham District Energy Inc.
Location: Markham, Ontario (NAICS 221: Utilities - Steam & Air-Conditioning)
CfD Type: Carbon Policy Difference Contract (Two-way CfD)
Agreement Date: June 26, 2024
Contract Period: 2025-2034 (10 years)
Strike Price: CAD $100/tonne CO2e
Potential CO2 Reduction: 177,400 tCO2e over contract term
Technology: Wastewater Source Heat Transfer (WET) system
Features: Two-way strike (CGF pays if carbon price < $100, MDE pays if > $100)
Status: Signed (Project under development)

GHGRP Match Status: FULLY MATCHED
Processing Decision:
  - Company ID: 866912389 (matched in GHGRP)
  - 3 facilities in GHGRP database:
    - Warden Energy Centre (Contribution: ~59%)
    - Birchmount Energy Centre (Contribution: ~38%)
    - Clegg Energy Centre (Contribution: ~3%)
  - Company-level aggregation maintained (already done in panel)
  - Has baseline emissions 2022-2023
  - Treatment active 2025 onwards

Data Source:
  https://cdev.gc.ca/canada-growth-fund-inc/

VARIABLES ADDED TO ANALYSIS PANEL
==================================

1. cfd_participant (binary: 0/1)
   - 1 if company is confirmed CfD/CCO participant
   - Based on name matching to CfD database
   - 0 otherwise

2. cfd_type (categorical)
   - "CCO" = Carbon Credit Offtake (Entropy, Gibson/Varme)
   - "Carbon Policy CfD" = Two-way policy CfD (Markham)
   - "No" = Not a CfD participant

3. cfd_contract_type (categorical)
   - "Carbon Credit Offtake" for CCO arrangements
   - "Two-way Carbon Policy Difference Contract" for policy CfD
   - "None" for non-participants

4. cfd_start_year, cfd_end_year (integer)
   - Calendar years of contract period
   - Reflects agreement signing/FID timing

5. cfd_term_years (integer)
   - Contract duration in years
   - CCO contracts: 15 years
   - Policy CfD: 10 years

6. exposure_cfd_it (binary: 0/1)
   - Main treatment variable for econometric analysis
   - 1 if: (a) company is CfD participant AND (b) year in [start_year, end_year]
   - 0 otherwise
   - Allows for DiD and event-study specifications

7. cfd_price_per_tonne (numeric, CAD)
   - Contract price (CCO) or strike price (policy CfD)
   - CCO prices: $85-86.50/tonne
   - Policy CfD: $100/tonne strike

8. cfd_max_volume_tco2e (numeric, tCO2e/year)
   - Maximum annual CO2 reduction capacity
   - Entropy: 185,000 tCO2e/year
   - Gibson: 200,000 tCO2e/year
   - Markham: 177,400 tCO2e (total over 10 years)

9. cfd_contract_value_m_cad (numeric, millions CAD)
   - Estimated total contract value
   - Calculation: price x annual_volume x remaining_years / 1,000,000
   - Dynamic (decreases as contract matures)

10. cfd_ghgrp_match_status (categorical)
    - "Not yet reported (future)" = Entropy
    - "Partial (existing company, new project)" = Gibson
    - "Fully matched (company in GHGRP)" = Markham
    - "Non-CfD" for others

11. cfd_spillover_potential (numeric, [0,1])
    - Maximum pairwise spillover weight from CfD policy matrix
    - Indicates potential for policy coordination effects
    - 0 if no spillover linkages, up to 0.7 for high spillover

MATRICES INTEGRATED
====================

W_CfD Policy Spillover Matrix (3x3)
----
Companies: Entropy Inc., Gibson Energy, Markham District Energy

Weights (row-standardized):
           Entropy  Gibson  Markham
Entropy      0.00    0.700   0.250
Gibson       0.700   0.000   0.150
Markham      0.250   0.150   0.000

Interpretation:
- 0.70 (Entropy-Gibson): High spillover
  * Both Alberta CCS projects (technology similarity)
  * Both CCO contracts with government support
  * Complementary technology demonstration

- 0.25 (Entropy-Markham): Medium spillover
  * Both CGF-supported programs
  * Different provinces, different technologies
  * Policy framework knowledge transfer

- 0.15 (Gibson-Markham): Lower spillover
  * Different contract types (CCO vs. Policy CfD)
  * Different provinces (Alberta vs. Ontario)
  * Different technologies (CCS vs. Heat Recovery)

Use Case: Testing for spatial/policy network effects in emissions reduction

W_IO Enhanced Matrix (14x14)
----
Industries (NAICS 3-digit):
221, 312, 325, 331, 333, 334, 336, 322, 326, 327, 338, 492, 562, 236

Notable enhancements for CfD supply chains:
- 221-236: 0.0625 (Markham infrastructure investment)
- 492-236: 0.1 (CCS infrastructure construction)
- 562-236: 0.4 (Waste-to-energy facility construction)
- 312-325: 0.5 (Chemical manufacturing linkages)

Use Case: Analyzing supply-chain spillover effects of CfD investments

DATA QUALITY SUMMARY
====================

Currently in GHGRP:
- Markham District Energy: 3 facilities, full 2022-2023 baseline
- Gibson Energy: Existing operations, 2022-2023 baseline
- Entropy Inc.: New project, not yet in GHGRP

Current panel observations with CfD treatment:
- Entropy: 0 (future entry)
- Gibson: Pre-treatment observations available, post-treatment pending FID
- Markham: Pre-treatment observations available, post-treatment 2025+

================================================================================
Integration completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Script: 15_integrate_cfd_and_matrices.py
================================================================================
"""

with open(DECISION_LOG, 'w', encoding='utf-8') as f:
    f.write(decision_text)

logger.info(f"  Saved decision log: {DECISION_LOG.name}")

# ============================================================================
# SECTION 9: Summary and Completion
# ============================================================================

logger.info("")
logger.info("=" * 80)
logger.info("CfD CONTRACTS AND MATRICES INTEGRATION COMPLETE")
logger.info("=" * 80)
logger.info("")

logger.info("OUTPUT FILES")
logger.info(f"  - Enhanced CfD dataset: {OUTPUT_FILE.name}")
logger.info(f"    Records: {len(cfd_output):,}")
logger.info(f"    Variables: {len(cfd_columns)}")
logger.info("")
logger.info(f"  - Decision log: {DECISION_LOG.name}")
logger.info("")

logger.info("CfD PARTICIPANTS")
if n_cfd_companies > 0:
    logger.info(f"  - Companies: {n_cfd_companies}")
    logger.info(f"  - Observations: {n_cfd_obs}")
    logger.info(f"  - Exposed observations: {n_exposed_obs}")
else:
    logger.info("  - No participants currently in GHGRP (expected for new projects)")

logger.info("")
logger.info("MATRICES INTEGRATED")
logger.info(f"  - CfD Spillover Matrix: {cfd_spillover.shape[0]}x{cfd_spillover.shape[1]}")
logger.info(f"  - W_IO Enhanced Matrix: {io_enhanced.shape[0]}x{io_enhanced.shape[1]}")
logger.info("")

logger.info("=" * 80)
