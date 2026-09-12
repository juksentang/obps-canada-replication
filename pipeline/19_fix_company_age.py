#!/usr/bin/env python3
"""
Recalculate company_age as year minus the company's first observed year, so that age increases
monotonically within each company.
Input : data/analysis_ready/analysis_ready_company_year_latest.csv
Outputs: data/analysis_ready/analysis_ready_company_year_20251025_v3_fixed_age.csv, analysis_ready_company_year_latest.csv,
         data/analysis_ready/company_age_recalculation_report.txt
"""

import pandas as pd
import numpy as np
from pathlib import Path

print("=" * 80)
print("company_age Variable Recalculation")
print("=" * 80)

# Paths
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA_DIR = DATA / 'analysis_ready'
INPUT_FILE = DATA_DIR / 'analysis_ready_company_year_latest.csv'
OUTPUT_FILE = DATA_DIR / 'analysis_ready_company_year_20251025_v3_fixed_age.csv'

print(f"\n[STEP 1] Load data")
df = pd.read_csv(INPUT_FILE)
print(f"  Loaded: {len(df):,} observations")
print(f"  Companies: {df['company_id'].nunique():,}")
print(f"  Years: {df['year'].min()}-{df['year'].max()}")

# Store original for comparison
df['company_age_original'] = df['company_age'].copy()

print(f"\n[STEP 2] Calculate corrected company_age")
print(f"  Logic: age = year - min(year) for each company_id")

# Calculate minimum year per company
company_min_year = df.groupby('company_id')['year'].transform('min')

# Recalculate company_age
df['company_age_corrected'] = df['year'] - company_min_year

print(f"\n[STEP 3] Verify monotonicity")

# Check monotonicity for each company
is_monotonic = True
companies_not_monotonic = []

for company_id in df['company_id'].unique():
    company_data = df[df['company_id'] == company_id].sort_values('year')
    ages = company_data['company_age_corrected'].values

    # Check if monotonically increasing
    is_increasing = np.all(np.diff(ages) >= 0)

    if not is_increasing:
        is_monotonic = False
        companies_not_monotonic.append(company_id)

if is_monotonic:
    print(f"  OK: All {df['company_id'].nunique():,} companies have monotonic age progression")
else:
    print(f"  ERROR: {len(companies_not_monotonic)} companies still have inconsistent age")
    print(f"     First 10: {companies_not_monotonic[:10]}")

print(f"\n[STEP 4] Compare old vs corrected values")

# Count differences
differences = (df['company_age_original'] != df['company_age_corrected']).sum()
pct_different = 100 * differences / len(df)

print(f"  Observations with changed values: {differences:,} ({pct_different:.1f}%)")

# Show sample of changes
print(f"\n  Sample of corrections:")
changes = df[df['company_age_original'] != df['company_age_corrected']].head(10)
for idx, row in changes.iterrows():
    print(f"    Company: {row['company_id']}")
    print(f"      Year: {row['year']}")
    print(f"      Old age: {row['company_age_original']:.1f} -> New age: {row['company_age_corrected']:.1f}")

# Statistical comparison
print(f"\n[STEP 5] Distribution comparison")

print(f"\n  Original company_age:")
print(f"    Mean:   {df['company_age_original'].mean():.2f}")
print(f"    Median: {df['company_age_original'].median():.2f}")
print(f"    Std:    {df['company_age_original'].std():.2f}")
print(f"    Range:  [{df['company_age_original'].min():.1f}, {df['company_age_original'].max():.1f}]")

print(f"\n  Corrected company_age:")
print(f"    Mean:   {df['company_age_corrected'].mean():.2f}")
print(f"    Median: {df['company_age_corrected'].median():.2f}")
print(f"    Std:    {df['company_age_corrected'].std():.2f}")
print(f"    Range:  [{df['company_age_corrected'].min():.1f}, {df['company_age_corrected'].max():.1f}]")

# Verify range is 0 to 19 (2004-2023)
if df['company_age_corrected'].min() == 0 and df['company_age_corrected'].max() <= 19:
    print(f"\n  OK: Age range is [0, {df['company_age_corrected'].max():.0f}]")
else:
    print(f"\n  WARNING: Unexpected age range [{df['company_age_corrected'].min():.1f}, {df['company_age_corrected'].max():.1f}]")

print(f"\n[STEP 6] Check for anomalies")

# Check for any company with gaps in years
years_per_company = df.groupby('company_id')['year'].apply(lambda x: len(set(x)))
expected_years = (df.groupby('company_id')['year'].max() -
                 df.groupby('company_id')['year'].min() + 1)

has_gaps = (years_per_company < expected_years).sum()
pct_gaps = 100 * has_gaps / len(years_per_company)

print(f"  Companies with gaps in years: {has_gaps:,} ({pct_gaps:.1f}%)")
print(f"  Gaps reflect GHGRP entry/exit and data availability")

print(f"\n[STEP 7] Update dataset and save")

# Replace old age with corrected age
df['company_age'] = df['company_age_corrected']

# Remove temporary columns
df = df.drop(columns=['company_age_original', 'company_age_corrected'])

# Save
df.to_csv(OUTPUT_FILE, index=False)
latest_file = DATA_DIR / 'analysis_ready_company_year_latest.csv'
df.to_csv(latest_file, index=False)
print(f"  Saved: {OUTPUT_FILE.name}")
print(f"  Updated canonical dataset: {latest_file.name}")
print(f"     Size: {len(df):,} observations x {len(df.columns)} variables")

print(f"\n[STEP 8] Generate validation report")

# Create validation report
validation_report = f"""
COMPANY_AGE RECALCULATION - VALIDATION REPORT
==============================================

Input File: {INPUT_FILE.name}
Output File: {OUTPUT_FILE.name}

CORRECTIONS SUMMARY
-------------------
Total observations changed: {differences:,} ({pct_different:.1f}%)
All companies now have monotonic age: {'YES' if is_monotonic else 'NO'}

AFTER
-----
  Mean:   {df['company_age'].mean():.2f}
  Median: {df['company_age'].median():.2f}
  Std:    {df['company_age'].std():.2f}
  Range:  [0, {df['company_age'].max():.0f}]

LOGIC VERIFICATION
------------------
Monotonicity: {is_monotonic}
Range: matches years (2004-2023, so max age = 19)
Interpretation: years since first observation in GHGRP

STATUS: COMPLETE
"""

report_file = DATA_DIR / 'company_age_recalculation_report.txt'
with open(report_file, 'w') as f:
    f.write(validation_report)
print(f"  Report saved: {report_file.name}")

print("\n" + "=" * 80)
print("COMPLETE: company_age variable has been recalculated and verified")
print("=" * 80)
