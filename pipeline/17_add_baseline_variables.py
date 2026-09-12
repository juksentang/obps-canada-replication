"""
Add 2018 baseline variables and the 50 kt baseline sample indicator to the analysis-ready dataset.
Input : data/analysis_ready/analysis_ready_company_year_20251024.csv
Outputs: data/analysis_ready/analysis_ready_company_year_20251025.csv, data/analysis_ready/baseline_2018_composition.csv
New columns: ln_emissions_2018, intensity_2018, sample_50kt_baseline (1 if 2018 emissions >= 50 kt),
             sample_any_year_50kt, sample_all_years_50kt (alternative sample definitions, for comparison).
"""

import pandas as pd
import numpy as np
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

# Load data
INPUT_FILE = DATA / 'analysis_ready' / 'analysis_ready_company_year_20251024.csv'
OUTPUT_DIR = DATA / 'analysis_ready'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("\n" + "="*80)
print("ADDING BASELINE 2018 VARIABLES TO ANALYSIS-READY DATA")
print("="*80)
print(f"Input: {INPUT_FILE}")
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Read data
df = pd.read_csv(INPUT_FILE)
print(f"\nOriginal data: {len(df)} rows, {len(df.columns)} columns")

# ============================================================================
# Step 1: Extract 2018 baseline data
# ============================================================================

print("\nSTEP 1: Extract 2018 baseline year data")
print("-"*80)

df_2018 = df[df['year'] == 2018][['company_id', 'ln_emissions', 'intensity_co2e_per_m_gdp', 'total_emissions_co2e']].copy()
df_2018.columns = ['company_id', 'ln_emissions_2018', 'intensity_2018', 'total_emissions_2018']

print(f"Firms with 2018 data: {len(df_2018)}")
print(f"\nBaseline Statistics (2018):")
print(f"  Log Emissions (ln_emissions_2018):")
print(f"    Mean: {df_2018['ln_emissions_2018'].mean():.3f}")
print(f"    Std:  {df_2018['ln_emissions_2018'].std():.3f}")
print(f"    Min:  {df_2018['ln_emissions_2018'].min():.3f}")
print(f"    Max:  {df_2018['ln_emissions_2018'].max():.3f}")
print(f"  Intensity (intensity_2018):")
print(f"    Mean: {df_2018['intensity_2018'].mean():.0f}")
print(f"    Std:  {df_2018['intensity_2018'].std():.0f}")

# Define sample based on 2018 baseline
df_2018['sample_50kt_baseline'] = (df_2018['total_emissions_2018'] >= 50000).astype(int)

print(f"\nSample Definition (2018 baseline >= 50kt):")
print(f"  Firms in 50kt+ sample: {df_2018['sample_50kt_baseline'].sum()}")
print(f"  Share: {df_2018['sample_50kt_baseline'].mean():.1%}")

# ============================================================================
# Step 2: Merge baseline variables back to full dataset
# ============================================================================

print("\nSTEP 2: Merge baseline variables to full dataset")
print("-"*80)

df = df.merge(
    df_2018[['company_id', 'ln_emissions_2018', 'intensity_2018', 'sample_50kt_baseline']],
    on='company_id',
    how='left'
)

print(f"After merge: {len(df)} rows, {len(df.columns)} columns")
print(f"\nMissing values in new columns:")
print(f"  ln_emissions_2018: {df['ln_emissions_2018'].isna().sum()}")
print(f"  intensity_2018: {df['intensity_2018'].isna().sum()}")
print(f"  sample_50kt_baseline: {df['sample_50kt_baseline'].isna().sum()}")

# ============================================================================
# Step 3: Diagnostic tables
# ============================================================================

print("\nSTEP 3: Sample diagnostic tables")
print("-"*80)

# Alternative sample definition: any year >= 50kt
df['sample_any_year_50kt'] = 0
firms_any = df[df['total_emissions_co2e'] >= 50000]['company_id'].unique()
df.loc[df['company_id'].isin(firms_any), 'sample_any_year_50kt'] = 1

# All years >= 50kt (strict)
firm_min = df.groupby('company_id')['total_emissions_co2e'].min()
firms_all = firm_min[firm_min >= 50000].index
df['sample_all_years_50kt'] = 0
df.loc[df['company_id'].isin(firms_all), 'sample_all_years_50kt'] = 1

print("\nSample Definition Comparison:")
print(f"{'Method':<35} {'Firms':<8} {'Obs':<8} {'<50kt Obs':<10}")
print("-"*90)

# Any-year method
mask_current = df['sample_any_year_50kt'] == 1
n_obs_current = df[mask_current].shape[0]
n_small_current = len(df[mask_current & (df['total_emissions_co2e'] < 50000)])
print(f"{'Any year >=50kt':<35} {df['sample_any_year_50kt'].sum():<8} {n_obs_current:<8} {n_small_current:<10}")

# Baseline method (used in the analysis)
mask_baseline = df['sample_50kt_baseline'] == 1
n_obs_baseline = df[mask_baseline].shape[0]
n_small_baseline = len(df[mask_baseline & (df['total_emissions_co2e'] < 50000)])
print(f"{'Baseline 2018 >=50kt (analysis)':<35} {df['sample_50kt_baseline'].sum():<8} {n_obs_baseline:<8} {n_small_baseline:<10}")

# All years method
mask_all = df['sample_all_years_50kt'] == 1
n_obs_all = df[mask_all].shape[0]
n_small_all = len(df[mask_all & (df['total_emissions_co2e'] < 50000)])
print(f"{'All years >=50kt (strict)':<35} {df['sample_all_years_50kt'].sum():<8} {n_obs_all:<8} {n_small_all:<10}")

# ============================================================================
# Step 4: Export enhanced dataset
# ============================================================================

print("\nSTEP 4: Export enhanced dataset")
print("-"*80)

output_file = os.path.join(OUTPUT_DIR, 'analysis_ready_company_year_20251025.csv')
df.to_csv(output_file, index=False)
print(f"Saved: {output_file}")
print(f"  Rows: {len(df)}")
print(f"  Columns: {len(df.columns)} (added 4 new columns)")

# Export baseline composition table for reference
baseline_composition = df_2018[[
    'company_id', 'ln_emissions_2018', 'intensity_2018',
    'total_emissions_2018', 'sample_50kt_baseline'
]].copy()
baseline_composition_file = os.path.join(OUTPUT_DIR, 'baseline_2018_composition.csv')
baseline_composition.to_csv(baseline_composition_file, index=False)
print(f"Saved: {baseline_composition_file}")

print(f"\nCompletion time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)
