#!/usr/bin/env python3
"""
Build the green-patent panel by NAICS-3 x province x year.

Steps: allocate each identified green patent to NAICS industries by its IPC classes (fractional counting, weights per patent
sum to one); aggregate fractional counts to NAICS x province x filing year; compute perpetual-inventory patent stocks
with a 15% depreciation rate.

Input:  data/processed/green_patents_identified_v1_20251022.csv
Output: data/processed/greenpatent_patent_allocation_v2_<date>.csv
        data/processed/4_panels/greenpatent_naics_prov_year_v2_<date>.csv
        data/metadata/greenpatent_v2_summary_<date>.txt
"""

import pandas as pd
import numpy as np
import logging
import pickle
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
        logging.FileHandler(ROOT / 'logs' / 'greenpatent_v2_construction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_RAW = DATA / 'raw' / 'patents' / 'cipo'
DATA_GREEN = DATA / 'patents' / 'Green'
DATA_PROCESSED = DATA / 'processed'
DATA_OTC = DATA / 'processed' / 'otc'
DATA_METADATA = DATA / 'metadata'

# Constants
DELTA = 0.15  # PIM depreciation rate
MIN_YEAR = 2000
MAX_YEAR = 2024

logger.info("=" * 80)
logger.info("GREEN PATENT PANEL CONSTRUCTION (NAICS x PROVINCE x YEAR)")
logger.info("=" * 80)

# ============================================================================
# LOAD IDENTIFIED GREEN PATENTS
# ============================================================================

logger.info("\n[INPUT] Loading identified green patents...")

try:
    green_patents_file = DATA_PROCESSED / 'green_patents_identified_v1_20251022.csv'

    if not green_patents_file.exists():
        logger.error(f"  Green patents file not found: {green_patents_file}")
        raise FileNotFoundError(f"{green_patents_file}")

    green_patents_v1 = pd.read_csv(green_patents_file)

    logger.info(f"  Loaded {len(green_patents_v1)} green patent records")
    logger.info(f"  Unique green patents: {green_patents_v1['patent_number'].nunique()}")
    logger.info(f"  Green domains: {green_patents_v1['green_domain'].nunique()}")

except Exception as e:
    logger.error(f"  Error loading green patents: {str(e)}")
    raise

# ============================================================================
# STEP 1: IPC -> NAICS PROBABILITY MAPPING
# ============================================================================

logger.info("\n[STEP 1] Creating IPC to NAICS mapping...")

# Each IPC 4-character class is mapped to a small set of representative 6-digit NAICS codes
# (WIPO green-technology to industry correspondence). Fractional counting keeps patent totals conserved.

try:
    ipc_to_naics_distribution = {
        'F03D': [333611, 334413],  # Wind: Turbines, Electronics
        'F03B': [333611, 221114],  # Hydro: Turbines, Hydroelectric utilities
        'H02N': [334413, 333611],  # Solar (non-thermal): Electronics, Equipment
        'F24J': [333414, 238160],  # Solar thermal: Plumbing, HVAC services
        'F24S': [238160, 333414],  # Solar panels: Roofing, Manufacturing
        'C10L': [324191, 492110],  # Biofuels: Petroleum, Transportation fuels
        'C12P': [325414, 312140],  # Bio-production: Chemicals, Beverage
        'H01M': [334413, 333319],  # Batteries: Electronics, Accumulators
        'H02J': [334413, 221122],  # Grid integration: Electronics, Power utilities
        'B60L': [336411, 336412],  # EV propulsion: Auto manufacturing
        'C25B': [325120, 331314],  # Hydrogen: Chemicals, Electrochemistry
        'B01D': [333319, 325120],  # Pollution control: Equipment, Chemicals
        'C02F': [325120, 236330],  # Water treatment: Chemicals, Water utilities
        'E04B': [238160, 236115],  # Building efficiency: Roofing, HVAC
        'E04D': [238160, 336320],  # Thermal insulation: Roofing, Insulation
        'F25B': [333415, 333414],  # Heat pumps: Refrigeration, HVAC
        'B09B': [562119, 562211],  # Waste recycling: Waste handling
        'F28D': [333319, 333415],  # Heat recovery: Equipment, Exchangers

        # Buildings and HVAC
        'F24F': [333415, 238220],  # HVAC efficiency: Refrigeration, HVAC installation
        'F24H': [333414, 238160],  # Solar collectors: Heating equip, Roofing
        'F24D': [238220, 333414],  # Solar heating: HVAC installation, Heating
        'F24C': [333414, 238160],  # Solar cookers: Heating equip, Roofing
        'F24B': [333414, 333319],  # Solar burners: Heating equip, General machinery
        'F24T': [333414, 325314],  # Solar thermal management: Heating equip, Fertilizer/chemicals

        # Power conversion and storage
        'H02K': [335312, 333611],  # Generators/motors: Electric motors, Turbines
        'H02G': [335929, 221122],  # Cable installations: Wiring devices, Power transmission
        'H02M': [335999, 334413],  # Power conversion: Electrical equipment, Semiconductors
        'H02S': [334413, 333319],  # PV power: Semiconductors, General machinery
        'H02P': [335312, 334413],  # Motor control: Electric motors, Semiconductors
        'H02H': [335999, 334413],  # Circuit protection: Electrical equipment, Semiconductors
        'H02B': [335313, 221122],  # Switchgear: Switchgear, Power transmission

        # Solar PV
        'H01L': [334413, 335999],  # PV devices: Semiconductors, Electrical equipment

        # Transportation
        'B60K': [336411, 336412],  # Hybrid drive: Auto manufacturing, Auto body
        'B60W': [336411, 334413],  # Energy management: Auto manufacturing, Semiconductors

        # Renewables
        'F03G': [333611, 221119],  # Wind power: Turbines, Other electric power
        'F03H': [333611, 221119],  # Wind power: Turbines, Other electric power

        # Waste to agriculture
        'C05F': [325314, 562219],  # Organic fertiliser: Fertilizer, Waste services
        'C05G': [325314, 562219],  # Compost: Fertilizer, Waste services
        'C05D': [325314, 325120],  # Inorganic fertiliser: Fertilizer, Basic chemicals
        'C05C': [325314, 325120],  # Nitrogen fertiliser: Fertilizer, Basic chemicals
        'C05B': [325314, 331314],  # Phosphate fertiliser: Fertilizer, Electrochemistry

        # Other
        'H01G': [334413, 335999],  # Supercapacitors: Semiconductors, Electrical equipment
        'F01K': [333319, 221118],  # Combined cycle / waste heat: General machinery, Thermal power
    }

    # Fallback distribution for IPC classes not in the mapping
    default_distribution = [333319, 336411, 325120, 238160, 334413]

    logger.info(f"  Created IPC to NAICS mapping for {len(ipc_to_naics_distribution)} IPC classes")
    logger.info(f"  Default distribution for unmapped IPCs: {len(default_distribution)} NAICS codes")

except Exception as e:
    logger.error(f"  Error creating IPC mapping: {str(e)}")
    raise

# ============================================================================
# STEP 2: ALLOCATE GREEN PATENTS TO NAICS WITH FRACTIONAL COUNTING
# ============================================================================

logger.info("\n[STEP 2] Allocating patents to NAICS with fractional counting...")

patent_naics_allocation = []

try:
    # Group by patent to handle multiple IPC codes per patent
    grouped = green_patents_v1.groupby('patent_number')

    for patent_num, group_df in grouped:
        # Get unique IPC codes for this patent
        unique_ipcs = group_df['ipc_code'].str[:4].unique()
        num_ipcs = len(unique_ipcs)

        # Collect all NAICS codes for this patent from all its IPCs
        all_naics_codes = set()
        for ipc_4digit in unique_ipcs:
            if ipc_4digit in ipc_to_naics_distribution:
                all_naics_codes.update(ipc_to_naics_distribution[ipc_4digit])
            else:
                all_naics_codes.update(default_distribution)

        # Weight per NAICS = 1.0 / total_unique_naics
        # This ensures sum of weights across all NAICS = 1.0 for each patent
        weight_per_naics = 1.0 / len(all_naics_codes) if all_naics_codes else 0

        # Use first row of patent group for province/year info
        first_row = group_df.iloc[0]

        for naics_6digit in all_naics_codes:
            naics_3digit = int(str(naics_6digit)[:3])  # Extract 3-digit NAICS

            patent_naics_allocation.append({
                'patent_number': patent_num,
                'ipc_code': first_row['ipc_code'],  # Use first IPC as reference
                'green_domain': first_row['green_domain'],
                'naics_6digit': naics_6digit,
                'naics_3digit': naics_3digit,
                'party_province_code': first_row['party_province_code'],
                'filing_year': int(first_row['filing_year']),
                'weight': weight_per_naics  # Weight per unique NAICS
            })

    patent_naics_df = pd.DataFrame(patent_naics_allocation)

    logger.info(f"  Allocated {len(patent_naics_df)} patent-NAICS combinations")
    logger.info(f"  Unique NAICS codes: {patent_naics_df['naics_3digit'].nunique()}")

    # Verify weight conservation
    weight_sums = patent_naics_df.groupby('patent_number')['weight'].sum()
    weight_ok = (abs(weight_sums - 1.0) < 0.0001).sum()

    logger.info(f"  Weight conservation check: {weight_ok}/{len(weight_sums)} patents sum to 1.0")

    if weight_ok < len(weight_sums):
        logger.warning(f"  {len(weight_sums) - weight_ok} patents with weight sum != 1.0")

    # Save allocation details
    patent_naics_df.to_csv(
        DATA_PROCESSED / f'greenpatent_patent_allocation_v2_{datetime.now().strftime("%Y%m%d")}.csv',
        index=False
    )
    logger.info(f"  Saved patent allocation details")

except Exception as e:
    logger.error(f"  Error allocating patents to NAICS: {str(e)}")
    raise

# ============================================================================
# STEP 3: AGGREGATE TO NAICS x PROVINCE x YEAR WITH FRACTIONAL COUNTS
# ============================================================================

logger.info("\n[STEP 3] Aggregating to NAICS x Province x Year panel...")

try:
    # Group by (NAICS, Province, Year) and sum fractional weights
    greenpatent_naics_prov_yr = patent_naics_df.groupby(
        ['naics_3digit', 'party_province_code', 'filing_year']
    ).agg({
        'weight': 'sum',  # Sum of fractional weights = fractional patent count
        'patent_number': 'nunique',  # Actual unique patents (for reference)
        'green_domain': lambda x: ', '.join(x.drop_duplicates().head(3))  # Top domains
    }).reset_index()

    greenpatent_naics_prov_yr.columns = [
        'naics_3digit', 'province', 'year',
        'fractional_patent_count', 'unique_patents', 'green_domains'
    ]

    # Ensure fractional_patent_count is float
    greenpatent_naics_prov_yr['fractional_patent_count'] = \
        greenpatent_naics_prov_yr['fractional_patent_count'].astype(float)

    logger.info(f"  Aggregated to {len(greenpatent_naics_prov_yr)} NAICS x Province x Year combinations")
    logger.info(f"  Total fractional patents: {greenpatent_naics_prov_yr['fractional_patent_count'].sum():.2f}")
    logger.info(f"  Total unique patents: {greenpatent_naics_prov_yr['unique_patents'].sum()}")

except Exception as e:
    logger.error(f"  Error aggregating to panel: {str(e)}")
    raise

# ============================================================================
# STEP 4: CALCULATE PIM PATENT STOCKS
# ============================================================================

logger.info("\n[STEP 4] Calculating perpetual inventory method (PIM) patent stocks...")

try:
    # Sort for PIM calculation
    greenpatent_naics_prov_yr = greenpatent_naics_prov_yr.sort_values(
        ['naics_3digit', 'province', 'year']
    ).reset_index(drop=True)

    greenpatent_naics_prov_yr['patent_stock'] = 0.0

    # PIM calculation by NAICS x Province combo
    for naics in greenpatent_naics_prov_yr['naics_3digit'].unique():
        for province in greenpatent_naics_prov_yr['province'].unique():
            mask = (greenpatent_naics_prov_yr['naics_3digit'] == naics) & \
                   (greenpatent_naics_prov_yr['province'] == province)

            if mask.sum() == 0:
                continue

            sub_df = greenpatent_naics_prov_yr[mask].sort_values('year').reset_index(drop=True)

            prev_stock_value = 0.0  # Initialize stock from previous year

            for idx, row in sub_df.iterrows():
                if idx == 0:
                    # First year: stock = flow
                    stock = row['fractional_patent_count']
                else:
                    # PIM: Stock_t = (1 - delta) * Stock_{t-1} + Flow_t
                    # prev_stock_value carries the previous year's stock across iterations
                    stock = (1 - DELTA) * prev_stock_value + row['fractional_patent_count']

                # Update in main dataframe
                main_idx = greenpatent_naics_prov_yr[mask].index[idx]
                greenpatent_naics_prov_yr.loc[main_idx, 'patent_stock'] = stock

                # Update prev_stock_value for next iteration
                prev_stock_value = stock

    logger.info(f"  Calculated patent stocks with delta={DELTA}")
    logger.info(f"  Average patent stock: {greenpatent_naics_prov_yr['patent_stock'].mean():.2f}")
    logger.info(f"  Patent stock range: {greenpatent_naics_prov_yr['patent_stock'].min():.2f} - {greenpatent_naics_prov_yr['patent_stock'].max():.2f}")

except Exception as e:
    logger.error(f"  Error calculating PIM stocks: {str(e)}")
    raise

# ============================================================================
# STEP 5: QUALITY CHECKS AND VALIDATION
# ============================================================================

logger.info("\n[STEP 5] Quality checks and validation...")

try:
    # Check 1: Fractional count distribution
    logger.info(f"  Fractional patent count distribution:")
    logger.info(f"    - Mean: {greenpatent_naics_prov_yr['fractional_patent_count'].mean():.2f}")
    logger.info(f"    - Median: {greenpatent_naics_prov_yr['fractional_patent_count'].median():.2f}")
    logger.info(f"    - Min: {greenpatent_naics_prov_yr['fractional_patent_count'].min():.2f}")
    logger.info(f"    - Max: {greenpatent_naics_prov_yr['fractional_patent_count'].max():.2f}")

    # Check 2: No missing values
    missing_patent_count = greenpatent_naics_prov_yr['fractional_patent_count'].isna().sum()
    missing_stock = greenpatent_naics_prov_yr['patent_stock'].isna().sum()

    logger.info(f"  Missing values:")
    logger.info(f"    - Patent count: {missing_patent_count}")
    logger.info(f"    - Patent stock: {missing_stock}")

    # Check 3: Unique NAICS, Province, Year coverage
    logger.info(f"  Coverage:")
    logger.info(f"    - Unique NAICS: {greenpatent_naics_prov_yr['naics_3digit'].nunique()}")
    logger.info(f"    - Unique Provinces: {greenpatent_naics_prov_yr['province'].nunique()}")
    logger.info(f"    - Year range: {greenpatent_naics_prov_yr['year'].min()} - {greenpatent_naics_prov_yr['year'].max()}")

except Exception as e:
    logger.error(f"  Error in quality checks: {str(e)}")
    raise

# ============================================================================
# STEP 6: SAVE OUTPUTS
# ============================================================================

logger.info("\n[STEP 6] Saving outputs...")

try:
    timestamp = datetime.now().strftime("%Y%m%d")

    # Main output: NAICS x Province x Year panel
    output_file = DATA_PROCESSED / '4_panels' / f'greenpatent_naics_prov_year_v2_{timestamp}.csv'

    # Select and order columns for output
    output_df = greenpatent_naics_prov_yr[[
        'naics_3digit', 'province', 'year',
        'fractional_patent_count', 'unique_patents', 'patent_stock',
        'green_domains'
    ]].copy()

    output_df.columns = [
        'naics_3digit', 'province', 'year',
        'green_patent_count', 'unique_patents', 'green_patent_stock',
        'green_domains'
    ]

    output_df.to_csv(output_file, index=False)
    logger.info(f"  Saved main panel: {output_file.name}")
    logger.info(f"    - File size: {output_file.stat().st_size / 1024:.1f} KB")
    logger.info(f"    - Records: {len(output_df)}")

    # Save summary statistics
    summary_file = DATA_METADATA / f'greenpatent_v2_summary_{timestamp}.txt'

    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("GREEN PATENT PANEL (NAICS x PROVINCE x YEAR) - SUMMARY\n")
        f.write("="*70 + "\n\n")

        f.write("INPUT STATISTICS:\n")
        f.write(f"  Green patents identified: {green_patents_v1['patent_number'].nunique()}\n")
        f.write(f"  Green patent records: {len(green_patents_v1)}\n")
        f.write(f"  Green domains: {green_patents_v1['green_domain'].nunique()}\n\n")

        f.write("FRACTIONAL COUNTING:\n")
        f.write(f"  Patent-NAICS allocations: {len(patent_naics_df)}\n")
        f.write(f"  Unique NAICS codes: {patent_naics_df['naics_3digit'].nunique()}\n")
        f.write(f"  Weight conservation: {weight_ok}/{len(weight_sums)} patents\n\n")

        f.write("OUTPUT PANEL:\n")
        f.write(f"  Dimensions: NAICS x Province x Year\n")
        f.write(f"  Records: {len(output_df)}\n")
        f.write(f"  NAICS codes: {output_df['naics_3digit'].nunique()}\n")
        f.write(f"  Provinces: {output_df['province'].nunique()}\n")
        f.write(f"  Years: {output_df['year'].min():.0f}-{output_df['year'].max():.0f}\n\n")

        f.write("PATENT METRICS:\n")
        f.write(f"  Total fractional patents: {output_df['green_patent_count'].sum():.2f}\n")
        f.write(f"  Avg patent count per cell: {output_df['green_patent_count'].mean():.2f}\n")
        f.write(f"  Avg patent stock per cell: {output_df['green_patent_stock'].mean():.2f}\n")
        f.write(f"  Max patent stock: {output_df['green_patent_stock'].max():.2f}\n\n")

        f.write("METHOD:\n")
        f.write("  Fractional counting: each patent distributed across its mapped industries, weights sum to 1.0\n")
        f.write("  Panel: NAICS x Province x Year, aligned with the facility panel by 3-digit NAICS\n")
        f.write(f"  Patent stock: perpetual inventory method, depreciation {DELTA}\n")

    logger.info(f"  Saved summary: {summary_file.name}")

except Exception as e:
    logger.error(f"  Error saving outputs: {str(e)}")
    raise

# ============================================================================
# FINAL SUMMARY
# ============================================================================

logger.info("\n" + "="*80)
logger.info("GREEN PATENT PANEL CONSTRUCTION COMPLETE")
logger.info("="*80)

logger.info(f"\nResults:")
logger.info(f"  - Green patents: {green_patents_v1['patent_number'].nunique()}")
logger.info(f"  - Patent-industry allocations: {len(patent_naics_df)}")
logger.info(f"  - Output panel: {len(output_df)} NAICS x Province x Year cells")
logger.info(f"  - Average patent stock: {output_df['green_patent_stock'].mean():.2f}")

logger.info(f"\nOutput files:")
logger.info(f"  {output_file}")
logger.info(f"  {summary_file}")

logger.info("="*80)
