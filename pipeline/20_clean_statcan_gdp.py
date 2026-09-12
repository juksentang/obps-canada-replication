"""
Clean the Statistics Canada provincial-industry GDP table (36-10-0402): keep chained (2017) dollars, 2004-2023,
and the year / province / NAICS industry / GDP columns.
Input : data/raw/statcan/gdp/36100402.csv
Output: data/processed/2_standardized/statcan_provincial_industry_gdp_2004_2023.csv
"""


import pandas as pd
import numpy as np
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

print("="*80)
print("CLEANING STATCAN PROVINCIAL-INDUSTRY GDP DATA")
print("="*80)

RAW_FILE = DATA / 'raw' / 'statcan' / 'gdp' / '36100402.csv'
OUTPUT_DIR = DATA / 'processed' / '2_standardized'
OUTPUT_FILE = OUTPUT_DIR / "statcan_provincial_industry_gdp_2004_2023.csv"

print(f"\nReading raw file: {RAW_FILE}")

# Read the CSV file
start_time = time.time()
df = pd.read_csv(RAW_FILE, dtype={
    'REF_DATE': str,
    'GEO': str,
    'Prices': str,
    'North American Industry Classification System (NAICS)': str,
    'VALUE': float
})
elapsed = time.time() - start_time
print(f"Read complete in {elapsed:.1f} seconds")
print(f"  Shape: {df.shape}")
print(f"  Columns: {df.columns.tolist()}")

# Filter to Chained (2017) dollars
print(f"\nFiltering to Chained (2017) dollars...")
df = df[df['Prices'] == 'Chained (2017) dollars'].copy()
print(f"  Shape after price filter: {df.shape}")

# Filter to 2004-2023 years
print(f"\nFiltering to 2004-2023...")
df['year'] = df['REF_DATE'].astype(int)
df = df[(df['year'] >= 2004) & (df['year'] <= 2023)].copy()
print(f"  Shape after year filter: {df.shape}")

# Check for missing values
print(f"\nData quality check:")
print(f"  Missing VALUE: {df['VALUE'].isna().sum()}")
print(f"  Missing GEO: {df['GEO'].isna().sum()}")

# Drop rows with missing values
df = df.dropna(subset=['VALUE', 'GEO'])
print(f"  Shape after dropping NAs: {df.shape}")

# Rename and select key columns
print(f"\nRenaming columns...")
df_clean = df[[
    'year',
    'GEO',
    'North American Industry Classification System (NAICS)',
    'VALUE'
]].copy()

df_clean.columns = ['year', 'province', 'naics_industry', 'gdp_million']

# Show unique values
print(f"\nUnique provinces ({df_clean['province'].nunique()}):")
print(df_clean['province'].unique())

print(f"\nSample of NAICS industries ({df_clean['naics_industry'].nunique()} unique):")
print(df_clean['naics_industry'].unique()[:20])

# Check for key provinces
key_provinces = ['Alberta', 'Ontario', 'British Columbia', 'Quebec']
for prov in key_provinces:
    count = (df_clean['province'] == prov).sum()
    print(f"  {prov}: {count} rows")

# Save cleaned data
print(f"\nSaving cleaned data to: {OUTPUT_FILE}")
df_clean.to_csv(OUTPUT_FILE, index=False)
print(f"Saved successfully")
print(f"  Shape: {df_clean.shape}")
print(f"  File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")

# Summary statistics
print(f"\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)

print(f"\nYears covered: {df_clean['year'].min()} - {df_clean['year'].max()}")
print(f"Provinces: {df_clean['province'].nunique()}")
print(f"Industries: {df_clean['naics_industry'].nunique()}")

print(f"\nGDP statistics (million CAD):")
print(f"  Mean: {df_clean['gdp_million'].mean():.1f}")
print(f"  Median: {df_clean['gdp_million'].median():.1f}")
print(f"  Min: {df_clean['gdp_million'].min():.1f}")
print(f"  Max: {df_clean['gdp_million'].max():.1f}")

# Check Alberta 2019 data for key industries
print(f"\nAlberta 2019 GDP by sector (sample):")
alberta_2019 = df_clean[(df_clean['province'] == 'Alberta') & (df_clean['year'] == 2019)]
mining = alberta_2019[alberta_2019['naics_industry'].str.contains('Mining|21', regex=True, na=False)]['gdp_million'].sum()
utilities = alberta_2019[alberta_2019['naics_industry'].str.contains('Utilities|22', regex=True, na=False)]['gdp_million'].sum()
manufacturing = alberta_2019[alberta_2019['naics_industry'].str.contains('Manufacturing|31-33', regex=True, na=False)]['gdp_million'].sum()

print(f"  Mining/Oil&Gas: ${mining:,.0f}M")
print(f"  Utilities: ${utilities:,.0f}M")
print(f"  Manufacturing: ${manufacturing:,.0f}M")

print(f"\n" + "="*80)
print("COMPLETE")
print("="*80)
