"""
Allocate Statistics Canada provincial-industry GDP to firms by their emission share within the
province x NAICS-2 x year cell, and compute the resulting emission intensity.
Inputs : data/analysis_ready/analysis_ready_company_year_latest.csv,
         data/processed/2_standardized/statcan_provincial_industry_gdp_2004_2023.csv
Output : data/analysis_ready/analysis_ready_with_statcan_gdp.csv (adds gdp_million_statcan, intensity_statcan,
         gdp_ind_prov_year, emission_share)
"""


import pandas as pd
import numpy as np
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

print("="*80)
print("BUILDING FIRM-LEVEL OUTPUT VARIABLE FROM STATCAN GDP")
print("="*80)

# Paths
ANALYSIS_READY = DATA / 'analysis_ready' / 'analysis_ready_company_year_latest.csv'
STATCAN_GDP = DATA / 'processed' / '2_standardized' / 'statcan_provincial_industry_gdp_2004_2023.csv'
OUTPUT_FILE = DATA / 'analysis_ready' / 'analysis_ready_with_statcan_gdp.csv'

# Load data
print("\n1. Loading datasets...")
df = pd.read_csv(ANALYSIS_READY)
print(f"   Analysis-ready data: {df.shape}")
print(f"   Columns: {df.columns.tolist()[:10]}...")

gdp_prov_ind = pd.read_csv(STATCAN_GDP)
print(f"   StatCan GDP data: {gdp_prov_ind.shape}")
print(f"   Columns: {gdp_prov_ind.columns.tolist()}")

# Check NAICS format
print(f"\n2. Checking NAICS codes...")
print(f"   Sample NAICS in df: {df['naics_code_3digit'].unique()[:10]}")
print(f"   Sample industries in StatCan: {gdp_prov_ind['naics_industry'].unique()[:10]}")

# Create mapping table of NAICS codes and descriptions
# We'll need to extract NAICS codes from StatCan industry names
print(f"\n3. Extracting NAICS codes from StatCan industry names...")
gdp_prov_ind['naics_code'] = gdp_prov_ind['naics_industry'].str.extract(r'\[([0-9A-Z-]+)\]')
print(f"   Sample extracted codes: {gdp_prov_ind['naics_code'].unique()[:15]}")

# Convert to numeric for matching (drop non-numeric first)
# StatCan uses both 2-digit (like '21') and aggregate codes (like 'T001', 'T002')
gdp_prov_ind['naics_numeric'] = pd.to_numeric(gdp_prov_ind['naics_code'], errors='coerce')

print(f"\n4. Data preparation...")
print(f"   Total rows in df: {len(df)}")
print(f"   Unique provinces in df: {df['province'].nunique()}")
print(f"   Unique years in df: {df['year'].nunique()}")
print(f"   Year range: {df['year'].min()}-{df['year'].max()}")

# Merge GDP data with firm data
# Strategy: Match on year, province, and NAICS code (first 2 digits)
print(f"\n5. Matching firm data to StatCan GDP...")

# First, ensure NAICS in df is numeric and 2-digit
df['naics_2digit'] = (df['naics_code_3digit'] // 10).astype(int)
print(f"   Firm NAICS 2-digit codes: {sorted(df['naics_2digit'].unique())}")

# For StatCan, focus on 2-digit codes (industry level)
gdp_2digit = gdp_prov_ind[gdp_prov_ind['naics_numeric'].notna()].copy()
gdp_2digit = gdp_2digit[gdp_2digit['naics_numeric'] < 100].copy()  # Restrict to 2-digit codes
print(f"   StatCan 2-digit industries: {sorted(gdp_2digit['naics_numeric'].unique())}")

# Rename for merge
gdp_2digit_clean = gdp_2digit[['year', 'province', 'naics_numeric', 'gdp_million']].copy()
gdp_2digit_clean.columns = ['year', 'province', 'naics_2digit', 'gdp_ind_prov_year']

# Merge
df_merged = df.merge(gdp_2digit_clean,
                     on=['year', 'province', 'naics_2digit'],
                     how='left')

print(f"   Merged shape: {df_merged.shape}")
print(f"   Rows with GDP match: {df_merged['gdp_ind_prov_year'].notna().sum()}")
print(f"   Rows without GDP match: {df_merged['gdp_ind_prov_year'].isna().sum()}")

# Calculate emission share within province-industry-year
print(f"\n6. Calculating emission shares...")
# Group by province, industry, year and sum emissions
group_cols = ['year', 'province', 'naics_2digit']
df_merged['emissions_ind_prov_year'] = df_merged.groupby(group_cols)['total_emissions_co2e'].transform('sum')

# Calculate firm's share
df_merged['emission_share'] = (df_merged['total_emissions_co2e'] /
                               df_merged['emissions_ind_prov_year']).fillna(0)

print(f"   Emission share stats:")
print(f"     Mean: {df_merged['emission_share'].mean():.4f}")
print(f"     Median: {df_merged['emission_share'].median():.4f}")
print(f"     Max: {df_merged['emission_share'].max():.4f}")

# Allocate GDP to firm
df_merged['gdp_million_statcan'] = (df_merged['gdp_ind_prov_year'] *
                                    df_merged['emission_share'])

# Handle cases where GDP is missing
# These are firms in industries/provinces/years without StatCan data
print(f"\n7. Handling missing data...")
missing_gdp_count = df_merged['gdp_million_statcan'].isna().sum()
print(f"   Rows with missing GDP allocation: {missing_gdp_count}")

# For these cases, use NaN (we'll handle separately in decomposition analysis)
# Don't forward-fill or interpolate to maintain data integrity

# Calculate intensity using StatCan GDP
df_merged['intensity_statcan'] = (df_merged['total_emissions_co2e'] /
                                  df_merged['gdp_million_statcan']).replace([np.inf, -np.inf], np.nan)

print(f"\n8. Data quality checks...")
print(f"   Rows with valid StatCan GDP: {(df_merged['gdp_million_statcan'] > 0).sum()}")
print(f"   Rows with valid intensity: {df_merged['intensity_statcan'].notna().sum()}")

# Summary statistics
print(f"\n9. Summary statistics for StatCan-based variables...")
print(f"\n   GDP allocation (million CAD):")
print(f"     Mean: {df_merged['gdp_million_statcan'].mean():.1f}")
print(f"     Median: {df_merged['gdp_million_statcan'].median():.1f}")
print(f"     Min: {df_merged['gdp_million_statcan'].min():.1f}")
print(f"     Max: {df_merged['gdp_million_statcan'].max():.1f}")

print(f"\n   Intensity from StatCan (tCO2e/M CAD):")
print(f"     Mean: {df_merged['intensity_statcan'].mean():.1f}")
print(f"     Median: {df_merged['intensity_statcan'].median():.1f}")
print(f"     Min: {df_merged['intensity_statcan'].min():.1f}")
print(f"     Max: {df_merged['intensity_statcan'].max():.1f}")

# Compare with original derived intensity
print(f"\n   Original intensity (E/I derived):")
print(f"     Mean: {df_merged['intensity_co2e_per_m_gdp'].mean():.1f}")
print(f"     Median: {df_merged['intensity_co2e_per_m_gdp'].median():.1f}")

# Correlation check
valid_both = df_merged[(df_merged['intensity_statcan'].notna()) &
                       (df_merged['intensity_co2e_per_m_gdp'].notna())]
if len(valid_both) > 0:
    corr = valid_both['intensity_statcan'].corr(valid_both['intensity_co2e_per_m_gdp'])
    print(f"\n   Correlation (derived vs StatCan intensity): {corr:.4f}")
    print(f"     Based on {len(valid_both)} observations")

# Save output
print(f"\n10. Saving output...")
output_cols = list(df.columns) + ['gdp_million_statcan', 'intensity_statcan',
                                   'gdp_ind_prov_year', 'emission_share']
df_output = df_merged[output_cols].copy()

df_output.to_csv(OUTPUT_FILE, index=False)
print(f"    Saved to: {OUTPUT_FILE}")
print(f"    Shape: {df_output.shape}")
print(f"    File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")

# Sample rows check
print(f"\n11. Sample output rows...")
sample = df_output[
    (df_output['province'] == 'Alberta') &
    (df_output['year'] == 2019) &
    (df_output['gdp_million_statcan'].notna())
].head(5)

if len(sample) > 0:
    print(sample[[
        'company_name', 'year', 'province', 'naics_code_3digit',
        'total_emissions_co2e', 'gdp_million_statcan',
        'intensity_co2e_per_m_gdp', 'intensity_statcan'
    ]].to_string())
else:
    print("   No Alberta 2019 firms with valid StatCan GDP found")

print(f"\n" + "="*80)
print("COMPLETE")
print("="*80)
