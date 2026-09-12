"""
Add annual WTI crude oil price controls to the analysis-ready dataset.
Input : data/analysis_ready/analysis_ready_with_real_output_v2.csv
Output: data/analysis_ready/analysis_ready_with_oil_controls.csv (adds wti_price_usd, ln_wti_price, wti_price_change,
        alberta, alberta_x_ln_wti, ln_wti_price_lag1, wti_volatility)
WTI annual averages (USD/barrel) are the U.S. EIA / FRED series DCOILWTICO, entered as a dictionary below.
"""


import pandas as pd
import numpy as np
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

print("=" * 90)
print("ADD OIL PRICE CONTROLS TO ANALYSIS DATASET")
print("=" * 90)

# ============================================================================
# Configuration
# ============================================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA_DIR = DATA / 'analysis_ready'

# Input file (most recent with real output)
INPUT_FILE = DATA_DIR / 'analysis_ready_with_real_output_v2.csv'

# Output file
OUTPUT_FILE = DATA_DIR / 'analysis_ready_with_oil_controls.csv'

# ============================================================================
# WTI Crude Oil Prices (Annual Average, USD/barrel)
# Source: U.S. EIA, World Bank Commodity Price Data
# ============================================================================

# Historical WTI prices (annual average)
WTI_PRICES = {
    2004: 41.51,
    2005: 56.64,
    2006: 66.05,
    2007: 72.34,
    2008: 99.67,  # Pre-crisis peak
    2009: 61.95,  # Financial crisis
    2010: 79.48,
    2011: 94.88,
    2012: 94.05,
    2013: 97.98,
    2014: 93.17,  # Start of oil price crash
    2015: 48.66,  # Oil price collapse
    2016: 43.29,
    2017: 50.80,
    2018: 65.23,
    2019: 56.99,  # first year of the national carbon-price floor
    2020: 39.68,  # COVID crash
    2021: 68.17,  # Recovery
    2022: 94.53,  # Ukraine war spike
    2023: 77.62,  # Normalization
}

# Create DataFrame
wti_df = pd.DataFrame([
    {'year': year, 'wti_price_usd': price}
    for year, price in WTI_PRICES.items()
])

# Calculate log price
wti_df['ln_wti_price'] = np.log(wti_df['wti_price_usd'])

# Calculate year-over-year change
wti_df = wti_df.sort_values('year')
wti_df['wti_price_change'] = wti_df['wti_price_usd'].pct_change() * 100
wti_df['wti_price_change'] = wti_df['wti_price_change'].fillna(0)

print("\n[1] WTI Oil Price Data:")
print(wti_df.to_string(index=False))

# ============================================================================
# Load and Merge
# ============================================================================

print(f"\n[2] Loading analysis data from: {INPUT_FILE}")
df = pd.read_csv(INPUT_FILE)
print(f"    Loaded {len(df)} observations")

# Merge WTI prices
print("\n[3] Merging WTI oil prices...")
df = df.merge(wti_df, on='year', how='left')

# Check for missing years
missing_years = df[df['wti_price_usd'].isna()]['year'].unique()
if len(missing_years) > 0:
    print(f"    WARNING: Missing WTI prices for years: {missing_years}")
else:
    print("    All years matched successfully")

# ============================================================================
# Additional Oil-Related Controls
# ============================================================================

print("\n[4] Creating additional oil-related controls...")

# Interaction: Alberta x WTI price (to capture differential exposure)
df['alberta'] = (df['province'] == 'Alberta').astype(int)
df['alberta_x_ln_wti'] = df['alberta'] * df['ln_wti_price']

# Lagged oil price (for delayed response)
df = df.sort_values(['company_id', 'year'])
df['ln_wti_price_lag1'] = df.groupby('company_id')['ln_wti_price'].shift(1)

# Oil price volatility (rolling 3-year std dev)
yearly_volatility = wti_df.set_index('year')['wti_price_usd'].rolling(window=3, min_periods=1).std()
yearly_volatility = yearly_volatility.reset_index()
yearly_volatility.columns = ['year', 'wti_volatility']
df = df.merge(yearly_volatility, on='year', how='left')

print("    Created: alberta_x_ln_wti, ln_wti_price_lag1, wti_volatility")

# ============================================================================
# Summary Statistics
# ============================================================================

print("\n[5] Summary of Oil Price Variables:")
print(f"    ln_wti_price:      Mean = {df['ln_wti_price'].mean():.3f}, Std = {df['ln_wti_price'].std():.3f}")
print(f"    wti_price_usd:     Mean = ${df['wti_price_usd'].mean():.2f}, Std = ${df['wti_price_usd'].std():.2f}")
print(f"    wti_volatility:    Mean = {df['wti_volatility'].mean():.2f}")

# Pre vs Post comparison
pre_wti = df[df['year'] < 2019]['wti_price_usd'].mean()
post_wti = df[df['year'] >= 2019]['wti_price_usd'].mean()
print(f"\n    Pre-2019 avg WTI:  ${pre_wti:.2f}")
print(f"    Post-2019 avg WTI: ${post_wti:.2f}")
print(f"    Difference:        ${post_wti - pre_wti:.2f} ({100*(post_wti/pre_wti - 1):.1f}%)")

# ============================================================================
# Save Output
# ============================================================================

print(f"\n[6] Saving to: {OUTPUT_FILE}")
df.to_csv(OUTPUT_FILE, index=False)

print(f"    Saved {len(df)} observations with {len(df.columns)} variables")

# ============================================================================
# Variable Documentation
# ============================================================================

print("\n" + "=" * 90)
print("NEW VARIABLES ADDED:")
print("=" * 90)
print("""
Variable                Description
---------------------   --------------------------------------------------------
wti_price_usd           WTI crude oil price (annual average, USD/barrel)
ln_wti_price            Natural log of WTI price
wti_price_change        Year-over-year percentage change in WTI price
alberta_x_ln_wti        Interaction: Alberta indicator x ln(WTI)
ln_wti_price_lag1       One-year lagged ln(WTI) price
wti_volatility          3-year rolling standard deviation of WTI price
""")

print("\n" + "=" * 90)
print("COMPLETE")
print("=" * 90)
