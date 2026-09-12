"""
Build industry-level price deflators (2015 = 100) and deflate the allocated sector GDP.
Sources: IPPI (table 18-10-0267-01) for manufacturing NAICS 31-33 at 3-digit detail; electric power selling price
index (18-10-0204-01) for utilities (NAICS 22); GDP implicit price index (36-10-0223-01) for all other industries.
Inputs : data/Industrial Deflator/*.csv, data/analysis_ready/analysis_ready_with_statcan_gdp.csv
Outputs: data/processed/2_standardized/industry_deflator_all.csv,
         data/analysis_ready/analysis_ready_with_real_output.csv (adds deflator_index, gdp_real_million, intensity_real,
         deflator_source)
"""


import pandas as pd
import numpy as np
from pathlib import Path
import re
import warnings

warnings.filterwarnings('ignore')

ROOT = Path(__file__).resolve().parents[1]

print("="*80)
print("BUILDING INDUSTRY-LEVEL PRICE DEFLATORS")
print("="*80)

# Paths
DATA = ROOT / 'data'
DATA_DIR = DATA
DEFLATOR_DIR = DATA_DIR / "Industrial Deflator"
OUTPUT_DIR = DATA_DIR / "processed/2_standardized"
ANALYSIS_DIR = DATA_DIR / "analysis_ready"

# Target base year
BASE_YEAR = 2015

# ============================================================================
# STEP 1: Process IPPI data (Manufacturing, NAICS 31-33)
# ============================================================================
print("\n" + "="*60)
print("STEP 1: Processing IPPI data (Manufacturing)")
print("="*60)

ippi_file = DEFLATOR_DIR / "1810026701-eng.csv"
print(f"Reading: {ippi_file}")

# Read raw data - skip header rows
with open(ippi_file, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Find the header row (contains month names)
header_row_idx = None
for i, line in enumerate(lines):
    if 'NAICS' in line and 'June 2002' in line:
        header_row_idx = i
        break

if header_row_idx is None:
    # Try alternative detection
    for i, line in enumerate(lines):
        if 'June 2002' in line:
            header_row_idx = i
            break

print(f"Header row found at line: {header_row_idx}")

# Read from header row
ippi_raw = pd.read_csv(ippi_file, skiprows=header_row_idx, encoding='utf-8-sig')
print(f"Raw IPPI shape: {ippi_raw.shape}")

# First column contains industry names with NAICS codes
ippi_raw.columns = ['industry'] + list(ippi_raw.columns[1:])

# Extract NAICS codes from industry names
def extract_naics(industry_str):
    """Extract NAICS code from strings like 'Food manufacturing  [311]'"""
    if pd.isna(industry_str):
        return None
    match = re.search(r'\[(\d{3})\]', str(industry_str))
    if match:
        return int(match.group(1))
    # Check for aggregate manufacturing [31-33]
    if '[31-33]' in str(industry_str):
        return 'MFG_TOTAL'
    return None

ippi_raw['naics_3digit'] = ippi_raw['industry'].apply(extract_naics)

# Filter to rows with valid NAICS codes
ippi_valid = ippi_raw[ippi_raw['naics_3digit'].notna()].copy()
print(f"Rows with valid NAICS: {len(ippi_valid)}")
print(f"NAICS codes found: {sorted([x for x in ippi_valid['naics_3digit'].unique() if isinstance(x, int)])}")

# Identify month columns
month_cols = [col for col in ippi_valid.columns if any(month in str(col) for month in
              ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December'])]

print(f"Month columns found: {len(month_cols)}")

# Melt to long format
ippi_long = ippi_valid.melt(
    id_vars=['industry', 'naics_3digit'],
    value_vars=month_cols,
    var_name='month_str',
    value_name='index_value'
)

# Parse month and year
def parse_month_year(month_str):
    """Parse 'January 2004' to (2004, 1)"""
    months = {'January': 1, 'February': 2, 'March': 3, 'April': 4,
              'May': 5, 'June': 6, 'July': 7, 'August': 8,
              'September': 9, 'October': 10, 'November': 11, 'December': 12}
    for month_name, month_num in months.items():
        if month_name in str(month_str):
            year_match = re.search(r'(\d{4})', str(month_str))
            if year_match:
                return int(year_match.group(1)), month_num
    return None, None

ippi_long[['year', 'month']] = ippi_long['month_str'].apply(
    lambda x: pd.Series(parse_month_year(x))
)

# Convert index to numeric
ippi_long['index_value'] = pd.to_numeric(ippi_long['index_value'], errors='coerce')

# Filter valid data
ippi_long = ippi_long[ippi_long['year'].notna() & ippi_long['index_value'].notna()].copy()
ippi_long['year'] = ippi_long['year'].astype(int)

print(f"Year range: {ippi_long['year'].min()} - {ippi_long['year'].max()}")

# Aggregate to annual average
ippi_annual = ippi_long.groupby(['naics_3digit', 'year']).agg({
    'index_value': 'mean',
    'industry': 'first'
}).reset_index()

# Rebase to 2015=100
# Original base is 2020=100
def rebase_index(group, base_year=2015, original_base=2020):
    """Rebase index to new base year"""
    base_value = group[group['year'] == base_year]['index_value'].values
    if len(base_value) > 0:
        group['index_rebased'] = group['index_value'] / base_value[0] * 100
    else:
        # Use original base year if target not available
        orig_base = group[group['year'] == original_base]['index_value'].values
        if len(orig_base) > 0:
            # Calculate base year value by extrapolation
            group['index_rebased'] = group['index_value'] / orig_base[0] * 100
    return group

ippi_rebased = ippi_annual.groupby('naics_3digit').apply(
    lambda x: rebase_index(x, BASE_YEAR, 2020)
).reset_index(drop=True)

# Filter to numeric NAICS only (exclude MFG_TOTAL for now)
ippi_final = ippi_rebased[ippi_rebased['naics_3digit'].apply(lambda x: isinstance(x, int))].copy()
ippi_final['naics_3digit'] = ippi_final['naics_3digit'].astype(int)
ippi_final['source'] = 'IPPI'
ippi_final['naics_2digit'] = (ippi_final['naics_3digit'] // 10).astype(int)

print(f"\nIPPI final shape: {ippi_final.shape}")
print(f"Sample data (NAICS 325, Chemical):")
print(ippi_final[ippi_final['naics_3digit'] == 325][['year', 'index_value', 'index_rebased']].head(10))

# ============================================================================
# STEP 2: Process Electric Power Price Index (NAICS 22)
# ============================================================================
print("\n" + "="*60)
print("STEP 2: Processing Electric Power Price Index")
print("="*60)

elec_file = DEFLATOR_DIR / "1810020401-eng.csv"
print(f"Reading: {elec_file}")

# Read raw data
with open(elec_file, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Find header row
header_row_idx = None
for i, line in enumerate(lines):
    if 'Index' in line and 'May 2002' in line:
        header_row_idx = i
        break

print(f"Header row found at line: {header_row_idx}")

elec_raw = pd.read_csv(elec_file, skiprows=header_row_idx, encoding='utf-8-sig')
print(f"Raw electric data shape: {elec_raw.shape}")

# First column is index type, rest are months
elec_raw.columns = ['index_type'] + list(elec_raw.columns[1:])

# Get national total row
elec_national = elec_raw[elec_raw['index_type'].str.contains('national total', case=False, na=False)].copy()

if len(elec_national) == 0:
    elec_national = elec_raw[elec_raw['index_type'].str.contains('Electric power selling price index', case=False, na=False)].copy()

print(f"Electric national rows: {len(elec_national)}")

# Melt to long format
month_cols_elec = [col for col in elec_national.columns if any(month in str(col) for month in
              ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December'])]

elec_long = elec_national.melt(
    id_vars=['index_type'],
    value_vars=month_cols_elec,
    var_name='month_str',
    value_name='index_value'
)

elec_long[['year', 'month']] = elec_long['month_str'].apply(
    lambda x: pd.Series(parse_month_year(x))
)

elec_long['index_value'] = pd.to_numeric(elec_long['index_value'], errors='coerce')
elec_long = elec_long[elec_long['year'].notna() & elec_long['index_value'].notna()].copy()
elec_long['year'] = elec_long['year'].astype(int)

# Aggregate to annual
elec_annual = elec_long.groupby('year').agg({
    'index_value': 'mean'
}).reset_index()

# Rebase to 2015=100 (original base is 2014=100)
base_value_2015 = elec_annual[elec_annual['year'] == BASE_YEAR]['index_value'].values
if len(base_value_2015) > 0:
    elec_annual['index_rebased'] = elec_annual['index_value'] / base_value_2015[0] * 100
else:
    # Use 2014 as reference
    base_2014 = elec_annual[elec_annual['year'] == 2014]['index_value'].values[0]
    elec_annual['index_rebased'] = elec_annual['index_value'] / base_2014 * 100

elec_annual['naics_2digit'] = 22
elec_annual['naics_3digit'] = 221  # Electric power generation
elec_annual['source'] = 'ELECTRIC_PRICE'
elec_annual['industry'] = 'Electric power generation, transmission and distribution'

print(f"Electric price index year range: {elec_annual['year'].min()} - {elec_annual['year'].max()}")
print(f"Sample data:")
print(elec_annual[['year', 'index_value', 'index_rebased']].head(10))

# ============================================================================
# STEP 3: Process GDP Implicit Price Index (for non-manufacturing industries)
# ============================================================================
print("\n" + "="*60)
print("STEP 3: Processing GDP Implicit Price Index (Fallback)")
print("="*60)

# NOTE: MFP (Multifactor Productivity) is NOT used because:
# - MFP measures efficiency (output per unit of combined inputs)
# - It is NOT a price index and cannot be used as a deflator
# - Using MFP as price deflator would be conceptually incorrect

# Instead, we use GDP Implicit Price Index for non-manufacturing industries
gdp_deflator_file = DEFLATOR_DIR / "Multifactor productivity and related variables in the aggregate business sector and major sub-sectors, by industry/3610022301-eng.csv"
print(f"Reading GDP deflator: {gdp_deflator_file}")

# Read GDP deflator data
with open(gdp_deflator_file, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Find header row (contains years)
header_row_idx = None
for i, line in enumerate(lines):
    if 'Estimates' in line and '2002' in line:
        header_row_idx = i
        break

print(f"Header row found at line: {header_row_idx}")

gdp_defl_raw = pd.read_csv(gdp_deflator_file, skiprows=header_row_idx, encoding='utf-8-sig')
print(f"Raw GDP deflator shape: {gdp_defl_raw.shape}")

# First column is the estimate type
gdp_defl_raw.columns = ['estimate_type'] + list(gdp_defl_raw.columns[1:])

# Get the "Gross domestic product at market prices" row
gdp_row = gdp_defl_raw[gdp_defl_raw['estimate_type'].str.contains('Gross domestic product at market prices', case=False, na=False)].copy()

if len(gdp_row) == 0:
    # Fallback to "Final domestic demand" if GDP row not found
    gdp_row = gdp_defl_raw[gdp_defl_raw['estimate_type'].str.contains('Final domestic demand', case=False, na=False)].copy()

print(f"GDP deflator row found: {len(gdp_row)}")

# Get year columns
year_cols = [col for col in gdp_row.columns if str(col).isdigit()]
print(f"Year columns: {year_cols}")

# Melt to long format
gdp_long = gdp_row.melt(
    id_vars=['estimate_type'],
    value_vars=year_cols,
    var_name='year',
    value_name='index_value'
)

gdp_long['year'] = pd.to_numeric(gdp_long['year'], errors='coerce')
gdp_long['index_value'] = pd.to_numeric(gdp_long['index_value'], errors='coerce')
gdp_long = gdp_long[gdp_long['year'].notna() & gdp_long['index_value'].notna()].copy()
gdp_long['year'] = gdp_long['year'].astype(int)

# Rebase to 2015=100 (original base is 2017=100)
base_value_2015 = gdp_long[gdp_long['year'] == BASE_YEAR]['index_value'].values
if len(base_value_2015) > 0:
    gdp_long['index_rebased'] = gdp_long['index_value'] / base_value_2015[0] * 100
else:
    # Use 2017 as reference
    base_2017 = gdp_long[gdp_long['year'] == 2017]['index_value'].values[0]
    gdp_long['index_rebased'] = gdp_long['index_value'] / base_2017 * 100

gdp_long['industry'] = 'GDP Implicit Price Index (Overall Economy)'
gdp_long['source'] = 'GDP_DEFLATOR'

print(f"GDP deflator year range: {gdp_long['year'].min()} - {gdp_long['year'].max()}")
print(f"Sample data:")
print(gdp_long[['year', 'index_value', 'index_rebased']].head(10))

# ============================================================================
# STEP 4: Combine all deflators
# ============================================================================
print("\n" + "="*60)
print("STEP 4: Combining all deflators")
print("="*60)

# Prepare IPPI data (manufacturing industries)
ippi_out = ippi_final[['naics_3digit', 'naics_2digit', 'year', 'index_rebased', 'source', 'industry']].copy()
ippi_out.columns = ['naics_3digit', 'naics_2digit', 'year', 'deflator_index', 'source', 'industry']

# Prepare electric data (utilities)
elec_out = elec_annual[['naics_3digit', 'naics_2digit', 'year', 'index_rebased', 'source', 'industry']].copy()
elec_out.columns = ['naics_3digit', 'naics_2digit', 'year', 'deflator_index', 'source', 'industry']

# Prepare GDP deflator data (for all other industries as fallback)
# GDP deflator will be used for: Mining (21), Construction (23), Trade (41,44-45),
# Transportation (48-49), Services (51-81), Agriculture (11), etc.
gdp_out = gdp_long[['year', 'index_rebased', 'source', 'industry']].copy()
gdp_out.columns = ['year', 'deflator_index', 'source', 'industry']
# GDP deflator is economy-wide, not industry-specific
gdp_out['naics_3digit'] = None  # Will be used as fallback
gdp_out['naics_2digit'] = None

# Combine IPPI and Electric (industry-specific)
all_deflators = pd.concat([ippi_out, elec_out], ignore_index=True)

# Remove duplicates (prefer IPPI > Electric)
source_priority = {'IPPI': 1, 'ELECTRIC_PRICE': 2}
all_deflators['source_priority'] = all_deflators['source'].map(source_priority).fillna(3)
all_deflators = all_deflators.sort_values(['naics_3digit', 'year', 'source_priority'])
all_deflators = all_deflators.drop_duplicates(subset=['naics_3digit', 'year'], keep='first')
all_deflators = all_deflators.drop('source_priority', axis=1)

print(f"\nCombined deflator shape: {all_deflators.shape}")
print(f"Year range: {all_deflators['year'].min()} - {all_deflators['year'].max()}")
print(f"Sources: {all_deflators['source'].value_counts().to_dict()}")
print(f"\nNAICS 2-digit coverage:")
print(all_deflators.groupby('naics_2digit')['year'].count().sort_index())

# ============================================================================
# STEP 5: Create lookup table for matching
# ============================================================================
print("\n" + "="*60)
print("STEP 5: Creating lookup tables")
print("="*60)

# 3-digit lookup (for manufacturing)
deflator_3digit = all_deflators[all_deflators['naics_3digit'] >= 100].copy()
deflator_3digit = deflator_3digit.pivot_table(
    index='naics_3digit',
    columns='year',
    values='deflator_index'
).reset_index()

# 2-digit lookup (for non-manufacturing)
deflator_2digit = all_deflators.groupby(['naics_2digit', 'year']).agg({
    'deflator_index': 'first',
    'source': 'first'
}).reset_index()

deflator_2digit_pivot = deflator_2digit.pivot_table(
    index='naics_2digit',
    columns='year',
    values='deflator_index'
).reset_index()

# Save intermediate files
output_file_3digit = OUTPUT_DIR / "industry_deflator_naics3.csv"
output_file_2digit = OUTPUT_DIR / "industry_deflator_naics2.csv"
output_file_all = OUTPUT_DIR / "industry_deflator_all.csv"

all_deflators.to_csv(output_file_all, index=False)
print(f"Saved: {output_file_all}")

# ============================================================================
# STEP 6: Match to analysis data and compute real output
# ============================================================================
print("\n" + "="*60)
print("STEP 6: Matching to analysis data")
print("="*60)

# Load analysis data
analysis_file = ANALYSIS_DIR / "analysis_ready_with_statcan_gdp.csv"
df = pd.read_csv(analysis_file)
print(f"Analysis data shape: {df.shape}")
print(f"Year range: {df['year'].min()} - {df['year'].max()}")

# Ensure NAICS columns are numeric
df['naics_3digit'] = pd.to_numeric(df['naics_code_3digit'], errors='coerce').astype('Int64')
if 'naics_2digit' not in df.columns:
    df['naics_2digit'] = (df['naics_3digit'] // 10).astype('Int64')

# Strategy: First try 3-digit match (for manufacturing), then 2-digit match
print("\nMatching deflators...")

# Prepare deflator lookup
deflator_lookup = all_deflators[['naics_3digit', 'naics_2digit', 'year', 'deflator_index', 'source']].copy()

# First merge on 3-digit NAICS
df_merged = df.merge(
    deflator_lookup[['naics_3digit', 'year', 'deflator_index', 'source']],
    on=['naics_3digit', 'year'],
    how='left',
    suffixes=('', '_3digit')
)

# For rows without 3-digit match, try 2-digit
missing_3digit = df_merged['deflator_index'].isna()
print(f"Rows without 3-digit match: {missing_3digit.sum()}")

# Create 2-digit lookup (aggregate)
deflator_2digit_lookup = deflator_lookup.groupby(['naics_2digit', 'year']).agg({
    'deflator_index': 'mean',
    'source': 'first'
}).reset_index()

df_merged = df_merged.merge(
    deflator_2digit_lookup.rename(columns={'deflator_index': 'deflator_index_2digit', 'source': 'source_2digit'}),
    on=['naics_2digit', 'year'],
    how='left'
)

# Use 2-digit if 3-digit is missing
df_merged['deflator_index'] = df_merged['deflator_index'].fillna(df_merged['deflator_index_2digit'])
df_merged['source'] = df_merged['source'].fillna(df_merged['source_2digit'])

# For still missing, use GDP deflator (proper fallback for non-manufacturing)
gdp_deflator_lookup = gdp_out[['year', 'deflator_index']].copy()
gdp_deflator_lookup.columns = ['year', 'gdp_deflator']

df_merged = df_merged.merge(gdp_deflator_lookup, on='year', how='left')
df_merged['deflator_index'] = df_merged['deflator_index'].fillna(df_merged['gdp_deflator'])
df_merged.loc[df_merged['source'].isna(), 'source'] = 'GDP_DEFLATOR'

print(f"\nFinal deflator coverage:")
print(df_merged['source'].value_counts())

# Check for any remaining missing
still_missing = df_merged['deflator_index'].isna()
print(f"\nRows still missing deflator: {still_missing.sum()}")

# ============================================================================
# STEP 7: Compute real output and intensity
# ============================================================================
print("\n" + "="*60)
print("STEP 7: Computing real output and intensity")
print("="*60)

# Real output = Nominal output / (deflator / 100)
# Since deflator is rebased to 2015=100, dividing by (deflator/100) converts to 2015 prices
df_merged['gdp_real_million'] = df_merged['gdp_million_statcan'] / (df_merged['deflator_index'] / 100)

# Real intensity = Emissions / Real output
df_merged['intensity_real'] = df_merged['total_emissions_co2e'] / df_merged['gdp_real_million']

# Handle infinities
df_merged['intensity_real'] = df_merged['intensity_real'].replace([np.inf, -np.inf], np.nan)
df_merged['gdp_real_million'] = df_merged['gdp_real_million'].replace([np.inf, -np.inf], np.nan)

# Summary statistics
print("\nSummary statistics:")
print(f"\n  Original intensity (tCO2e/M CAD nominal):")
print(f"    Mean: {df_merged['intensity_co2e_per_m_gdp'].mean():.2f}")
print(f"    Median: {df_merged['intensity_co2e_per_m_gdp'].median():.2f}")
print(f"    Std: {df_merged['intensity_co2e_per_m_gdp'].std():.2f}")

print(f"\n  Real intensity (tCO2e/M CAD 2015):")
print(f"    Mean: {df_merged['intensity_real'].mean():.2f}")
print(f"    Median: {df_merged['intensity_real'].median():.2f}")
print(f"    Std: {df_merged['intensity_real'].std():.2f}")

print(f"\n  Deflator index (2015=100):")
print(f"    Mean: {df_merged['deflator_index'].mean():.2f}")
print(f"    Min: {df_merged['deflator_index'].min():.2f}")
print(f"    Max: {df_merged['deflator_index'].max():.2f}")

# Correlation between original and real intensity
valid_both = df_merged[df_merged['intensity_real'].notna() & df_merged['intensity_co2e_per_m_gdp'].notna()]
corr = valid_both['intensity_real'].corr(valid_both['intensity_co2e_per_m_gdp'])
print(f"\n  Correlation (original vs real intensity): {corr:.4f}")

# ============================================================================
# STEP 8: Save output
# ============================================================================
print("\n" + "="*60)
print("STEP 8: Saving output")
print("="*60)

# Select output columns
output_cols = list(df.columns) + [
    'deflator_index',
    'gdp_real_million',
    'intensity_real',
    'source'
]

# Remove duplicate columns
output_cols = [col for col in output_cols if col in df_merged.columns]
output_cols = list(dict.fromkeys(output_cols))  # Remove duplicates while preserving order

# Rename source column to be clearer
df_merged = df_merged.rename(columns={'source': 'deflator_source'})
output_cols = [col.replace('source', 'deflator_source') if col == 'source' else col for col in output_cols]

# Get final columns, avoiding duplicates
final_cols = []
for col in output_cols:
    if col not in final_cols:
        final_cols.append(col)
if 'deflator_source' not in final_cols:
    final_cols.append('deflator_source')

df_output = df_merged[final_cols].drop_duplicates()

# Drop helper columns
cols_to_drop = ['deflator_index_2digit', 'source_2digit', 'gdp_deflator']
df_output = df_output.drop(columns=[c for c in cols_to_drop if c in df_output.columns], errors='ignore')

# Save
output_file = ANALYSIS_DIR / "analysis_ready_with_real_output.csv"
df_output.to_csv(output_file, index=False)
print(f"Saved: {output_file}")
print(f"Shape: {df_output.shape}")

# ============================================================================
# STEP 9: Validation report
# ============================================================================
print("\n" + "="*60)
print("VALIDATION REPORT")
print("="*60)

print("\n1. Coverage by NAICS 2-digit:")
coverage = df_output.groupby('naics_2digit').agg({
    'deflator_index': lambda x: x.notna().mean() * 100,
    'intensity_real': lambda x: x.notna().mean() * 100,
    'total_emissions_co2e': 'sum'
}).round(1)
coverage.columns = ['deflator_coverage_%', 'intensity_coverage_%', 'total_emissions']
coverage['emissions_share_%'] = (coverage['total_emissions'] / coverage['total_emissions'].sum() * 100).round(1)
print(coverage.sort_values('emissions_share_%', ascending=False))

print("\n2. Sample comparison (Alberta 2019):")
sample = df_output[
    (df_output['province'] == 'Alberta') &
    (df_output['year'] == 2019)
].head(5)
if len(sample) > 0:
    print(sample[[
        'company_name', 'naics_code_3digit', 'deflator_source',
        'intensity_co2e_per_m_gdp', 'intensity_real', 'deflator_index'
    ]].to_string())

print("\n3. Year-by-year deflator summary:")
yearly_summary = df_output.groupby('year').agg({
    'deflator_index': ['mean', 'std'],
    'intensity_real': 'mean'
}).round(2)
print(yearly_summary.tail(10))

print("\n" + "="*80)
print("COMPLETE")
print("="*80)
