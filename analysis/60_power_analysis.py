#!/usr/bin/env python3
"""Post-hoc power analysis for the 66-firm sample: minimum detectable effects (MDE) at 80% and 90% power, ex-post power and
effective sample size, from the baseline standard errors. The log-outcome inputs are the baseline estimates rounded to three
decimals (as reported in the paper); the patent row uses the published series from outputs/tables/70_baseline.csv.
Input: data/analysis_ready/analysis_ready_with_real_output_v2.csv (sample counts), outputs/tables/70_baseline.csv
Outputs: outputs/tables/60_power_analysis_n66.csv (read by 72_make_tables.py), 60_power_curve_ln_E.csv, 60_power_analysis_latex.tex"""

import pandas as pd
import numpy as np
from scipy import stats
import warnings
from paths import DATA, TAB

warnings.filterwarnings('ignore')

print("=" * 100)
print("POST-HOC POWER ANALYSIS, 66-FIRM SAMPLE")
print("=" * 100)

# ============================================================================
# Configuration
# ============================================================================

DATA_PATH = DATA / 'analysis_ready' / 'analysis_ready_with_real_output_v2.csv'
OUTPUT_DIR = TAB

ALPHA = 0.05  # Significance level (two-tailed)
POWER_TARGET = 0.80  # Conventional power level

# ============================================================================
# Load Data and Apply N=66 Filter
# ============================================================================

print("\n[1] Loading data and applying N=66 filter...")

df_full = pd.read_csv(DATA_PATH)
df_full = df_full[df_full['sample_50kt_baseline'] == 1].copy()
df_wf = df_full[df_full['multi_province_dummy'] == 1].copy()

# Apply N=66 filter (firms observed since 2016 or earlier)
first_year = df_wf.groupby('company_id')['year'].min().reset_index()
first_year.columns = ['company_id', 'first_year_observed']
df_wf = df_wf.merge(first_year, on='company_id', how='left')
df_wf = df_wf[df_wf['first_year_observed'] <= 2016].copy()

# Treatment setup
df_wf['post'] = (df_wf['year'] >= 2019).astype(int)
df_wf['alberta'] = (df_wf['province'] == 'Alberta').astype(int)

n_firms = df_wf['company_id'].nunique()
n_obs = len(df_wf)
n_treated = df_wf[df_wf['alberta'] == 1]['company_id'].nunique()
n_control = df_wf[df_wf['alberta'] == 0]['company_id'].nunique()

print(f"    Total firms: {n_firms}")
print(f"    Treated (Alberta): {n_treated}")
print(f"    Control (Other): {n_control}")
print(f"    Total obs: {n_obs}")

# ============================================================================
# Power Analysis Functions
# ============================================================================

def compute_mde(se, alpha=0.05, power=0.80, two_tailed=True):
    """
    Compute Minimum Detectable Effect (MDE) given standard error.

    MDE = (z_alpha + z_beta) * SE

    For two-tailed test at alpha=0.05, power=0.80:
    MDE = (1.96 + 0.84) * SE = 2.80 * SE
    """
    if two_tailed:
        z_alpha = stats.norm.ppf(1 - alpha / 2)
    else:
        z_alpha = stats.norm.ppf(1 - alpha)

    z_beta = stats.norm.ppf(power)

    mde = (z_alpha + z_beta) * se
    return mde

def compute_power(effect_size, se, alpha=0.05, two_tailed=True):
    """
    Compute statistical power given effect size and standard error.

    Power = Phi(|effect|/SE - z_alpha)
    """
    if two_tailed:
        z_alpha = stats.norm.ppf(1 - alpha / 2)
    else:
        z_alpha = stats.norm.ppf(1 - alpha)

    z_stat = abs(effect_size) / se
    power = stats.norm.cdf(z_stat - z_alpha)

    return power

def compute_effective_n_clusters(n_treated, n_control):
    """
    Compute effective sample size for DiD with clustering.

    For DiD with G treated and H control clusters:
    Effective N ≈ 4 * G * H / (G + H)

    This is much smaller than total clusters when treatment is imbalanced.
    """
    return 4 * n_treated * n_control / (n_treated + n_control)

# ============================================================================
# Extract Standard Errors from Existing Results
# ============================================================================

print("\n[2] Baseline estimates (rounded, as reported)...")

results = {
    'ln_E': {'coef': 0.054, 'se': 0.163, 'pval': 0.74},
    'ln_I': {'coef': -0.346, 'se': 0.197, 'pval': 0.08},
    'ln_Y': {'coef': 0.400, 'se': 0.160, 'pval': 0.015},
}

# Green patent stock: published series, baseline estimate from 70_main_estimates.py
_b = pd.read_csv(OUTPUT_DIR / '70_baseline.csv')
_gp = _b[_b['outcome'] == 'green_patent_stock'].iloc[0]
results['green_patents'] = {'coef': _gp['coef'], 'se': _gp['se'], 'pval': _gp['p']}

# ============================================================================
# Compute MDE for Each Outcome
# ============================================================================

print("\n[3] Computing Minimum Detectable Effects (MDE)...")
print("-" * 80)

mde_results = []

for outcome, res in results.items():
    se = res['se']
    coef = res['coef']
    pval = res['pval']

    # MDE at 80% power
    mde_80 = compute_mde(se, alpha=0.05, power=0.80)

    # MDE at 90% power
    mde_90 = compute_mde(se, alpha=0.05, power=0.90)

    # Current power (ex-post)
    power_current = compute_power(coef, se, alpha=0.05)

    # Effect size (Cohen's d analog for log outcomes)
    # For log outcomes, coefficient directly represents proportional change
    if 'ln_' in outcome:
        pct_change = (np.exp(coef) - 1) * 100
        mde_80_pct = (np.exp(mde_80) - 1) * 100
        mde_90_pct = (np.exp(mde_90) - 1) * 100
    else:
        pct_change = np.nan
        mde_80_pct = np.nan
        mde_90_pct = np.nan

    sig_marker = '***' if pval < 0.01 else ('**' if pval < 0.05 else ('*' if pval < 0.10 else 'ns'))

    print(f"\n{outcome}:")
    print(f"  Observed: β = {coef:.4f}, SE = {se:.4f}, p = {pval:.4f} {sig_marker}")
    print(f"  Ex-post power: {power_current:.1%}")
    print(f"  MDE at 80% power: {mde_80:.4f}")
    print(f"  MDE at 90% power: {mde_90:.4f}")

    if 'ln_' in outcome:
        print(f"  → To detect at 80% power, need effect ≥ {mde_80_pct:+.1f}%")

    mde_results.append({
        'Outcome': outcome,
        'Coefficient': coef,
        'Std_Error': se,
        'P_Value': pval,
        'Significant': sig_marker,
        'Ex_Post_Power': power_current,
        'MDE_80_Power': mde_80,
        'MDE_90_Power': mde_90,
        'MDE_80_Pct_Change': mde_80_pct,
        'Observed_Pct_Change': pct_change
    })

# ============================================================================
# Effective Sample Size Analysis
# ============================================================================

print("\n" + "=" * 100)
print("EFFECTIVE SAMPLE SIZE ANALYSIS")
print("=" * 100)

eff_n = compute_effective_n_clusters(n_treated, n_control)

print(f"""
Sample Composition:
  - Treated firms (Alberta): {n_treated}
  - Control firms (Other provinces): {n_control}
  - Total firms: {n_firms}

Effective Sample Size:
  - For DiD with clustering: {eff_n:.1f}
  - This is the "effective N" for power calculations
  - With severe treatment imbalance ({n_treated}/{n_control}), power is limited

Standard Error Inflation:
  - With G={n_firms} clusters, SEs are ~{np.sqrt(n_obs/n_firms):.1f}x larger than if unclustered
  - This is the "Moulton factor" penalty for clustered data
""")

# ============================================================================
# Power Curves
# ============================================================================

print("\n" + "=" * 100)
print("POWER CURVES FOR DIFFERENT EFFECT SIZES")
print("=" * 100)

# For ln_E
se_ln_E = results['ln_E']['se']
effect_sizes = np.arange(-0.5, 0.55, 0.05)  # -50% to +50% in log points

print(f"\nln(E) Total Emissions (SE = {se_ln_E:.3f}):")
print(f"{'Effect Size':<15} {'% Change':<15} {'Power':<15}")
print("-" * 45)

power_curve_data = []
for effect in effect_sizes:
    pct = (np.exp(effect) - 1) * 100
    power = compute_power(effect, se_ln_E, alpha=0.05)
    print(f"{effect:>8.2f}       {pct:>+8.1f}%       {power:>8.1%}")
    power_curve_data.append({
        'effect_log': effect,
        'effect_pct': pct,
        'power': power
    })

# ============================================================================
# Save Results
# ============================================================================

print("\n" + "=" * 100)
print("SAVING RESULTS")
print("=" * 100)

# Save MDE results
mde_df = pd.DataFrame(mde_results)
output_file = OUTPUT_DIR / '60_power_analysis_n66.csv'
mde_df.to_csv(output_file, index=False)
print(f"Saved: {output_file}")

# Save power curve
power_df = pd.DataFrame(power_curve_data)
power_file = OUTPUT_DIR / '60_power_curve_ln_E.csv'
power_df.to_csv(power_file, index=False)
print(f"Saved: {power_file}")

# ============================================================================
# LaTeX table
# ============================================================================

print("\n" + "=" * 100)
print("LATEX TABLE")
print("=" * 100)

latex_table = r"""
\begin{table}[htbp]
\centering
\caption{Post-hoc Power Analysis (N=66 Robust Sample)}
\label{tab:power_analysis}
\begin{tabular}{lcccccc}
\toprule
& \multicolumn{3}{c}{Observed Results} & \multicolumn{2}{c}{Minimum Detectable Effect} \\
\cmidrule(lr){2-4} \cmidrule(lr){5-6}
Outcome & $\hat{\beta}$ & SE & Ex-post Power & 80\% Power & 90\% Power \\
\midrule
"""

for r in mde_results:
    outcome_label = {
        'ln_E': 'ln(E) Emissions',
        'ln_I': 'ln(I) Intensity',
        'ln_Y': 'ln(Y) Output',
        'green_patents': 'Green Patents'
    }.get(r['Outcome'], r['Outcome'])

    latex_table += f"{outcome_label} & {r['Coefficient']:.3f} & {r['Std_Error']:.3f} & {r['Ex_Post_Power']:.1%} & {r['MDE_80_Power']:.3f} & {r['MDE_90_Power']:.3f} \\\\\n"

latex_table += r"""
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item \textit{Notes:} MDE = Minimum Detectable Effect at specified power level with $\alpha = 0.05$ (two-tailed).
Ex-post power calculated using observed coefficient and standard error.
With only """ + str(n_treated) + r""" treated firms and """ + str(n_control) + r""" control firms,
the effective sample size for DiD estimation is approximately """ + f"{eff_n:.0f}" + r""".
\end{tablenotes}
\end{table}
"""

print(latex_table)

# Save LaTeX
latex_file = OUTPUT_DIR / '60_power_analysis_latex.tex'
with open(latex_file, 'w') as f:
    f.write(latex_table)
print(f"Saved: {latex_file}")

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
