#!/usr/bin/env python3
"""Wild cluster bootstrap inference (Cameron, Gelbach and Miller 2008) for the firm-fixed-effects DiD.
For the 66-firm analysis sample and the 101-firm multi-province sample: OLS and emission-weighted WLS with firm and year fixed effects,
firm-clustered SEs, and wild cluster bootstrap p-values (Rademacher weights, 1,999 replications); a continuous-treatment variant
(Alberta x post x standardised 2018 intensity) with 999 replications.
Outputs: outputs/tables/52_wild_bootstrap_results.csv (read by 72_make_tables.py), 52_wild_bootstrap_latex_table.tex,
52_continuous_treatment_results.csv"""

import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
import warnings
from scipy import stats as sp_stats
from paths import PANEL, TAB

warnings.filterwarnings('ignore')

print("="*80)
print("WILD CLUSTER BOOTSTRAP: FIRM-FIXED-EFFECTS DID")
print("="*80)

DATA_PATH = PANEL
OUTPUT_DIR = TAB


# Load data
df = pd.read_csv(DATA_PATH)
df = df[df['sample_50kt_baseline'] == 1].copy()

# Create weight variable: 2018 baseline emissions (for WLS)
# Use ln_emissions_2018 if available, otherwise compute from ln_emissions
if 'ln_emissions_2018' in df.columns:
    # Get 2018 emissions for each firm
    emissions_2018 = df[df['year'] == 2018].groupby('company_id')['ln_emissions_2018'].first()
    df['weight_2018'] = df['company_id'].map(emissions_2018)
    # Exponentiate to get actual emissions (we want to weight by size, not log size)
    df['weight'] = np.exp(df['weight_2018'])
else:
    # Fallback: use emissions in 2018
    emissions_2018 = df[df['year'] == 2018].groupby('company_id')['ln_emissions'].first()
    df['weight_2018'] = df['company_id'].map(emissions_2018)
    df['weight'] = np.exp(df['weight_2018'])

# Normalize weights to have mean = 1 (for interpretability)
df['weight'] = df['weight'] / df['weight'].mean()
print(f"Weights created: mean={df['weight'].mean():.2f}, min={df['weight'].min():.4f}, max={df['weight'].max():.4f}")

# Select only multi-province firms
df_all_multi = df[df['multi_province_dummy'] == 1].copy()
print(f"\nAll multi-province sample: {df_all_multi['company_id'].nunique()} firms")

# 66-firm sample: exclude firms that entered after the 2016 GHGRP threshold change
first_year = df_all_multi.groupby('company_id')['year'].min().reset_index()
first_year.columns = ['company_id', 'first_year_observed']
df_all_multi = df_all_multi.merge(first_year, on='company_id', how='left')

df_strict = df_all_multi[df_all_multi['first_year_observed'] <= 2016].copy()
print(f"Strict sample (excluding post-2016 entrants): {df_strict['company_id'].nunique()} firms")

# Define samples for dual analysis
SAMPLES = {
    '66_strict': {
        'data': df_strict,
        'description': '66 firms (excluding post-2016 GHGRP entrants)'
    },
    '101_full': {
        'data': df_all_multi,
        'description': '101 firms (all multi-province)'
    }
}

outcomes = ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_emissions']
all_results = []


def run_panelols_did(df_sub, outcome):
    """OLS DiD with firm and year fixed effects and firm-clustered standard errors."""

    df_model = df_sub[[outcome, 'company_id', 'year', 'treat_post']].copy()
    df_model = df_model.dropna()

    # Fit OLS with firm and year fixed effects
    formula = f"{outcome} ~ treat_post + C(company_id) + C(year)"
    model = smf.ols(formula, data=df_model).fit(
        cov_type='cluster',
        cov_kwds={'groups': df_model['company_id']}
    )

    return model


def run_ols_did(df_sub, outcome):
    """OLS DiD with firm and year fixed effects and conventional standard errors (for comparison)."""
    formula = f"{outcome} ~ treat_post + C(company_id) + C(year)"
    model = smf.ols(formula, data=df_sub).fit()
    return model


def run_wls_did(df_sub, outcome, weight_col='weight'):
    """WLS DiD with firm and year fixed effects, weighted by 2018 baseline emissions, firm-clustered standard errors."""
    df_model = df_sub[[outcome, 'company_id', 'year', 'treat_post', weight_col]].copy()
    df_model = df_model.dropna()

    # WLS with firm and year fixed effects
    formula = f"{outcome} ~ treat_post + C(company_id) + C(year)"
    model = smf.wls(formula, data=df_model, weights=df_model[weight_col]).fit(
        cov_type='cluster',
        cov_kwds={'groups': df_model['company_id']}
    )

    return model


def wild_cluster_bootstrap_pvalue_wls(df_sub, outcome, weight_col='weight', n_boot=1999, seed=42):
    """
    Run wild cluster bootstrap for WLS to compute robust p-values.

    Uses Rademacher weights and clusters at firm level.
    Returns bootstrap p-value and percentile CI.
    """
    np.random.seed(seed)

    # Prepare data
    df_valid = df_sub[[outcome, 'company_id', 'year', 'treat_post', weight_col]].dropna().copy()

    # Get original WLS estimate with firm + year FE
    formula = f"{outcome} ~ treat_post + C(company_id) + C(year)"
    fit = smf.wls(formula, data=df_valid, weights=df_valid[weight_col]).fit(
        cov_type='cluster',
        cov_kwds={'groups': df_valid['company_id']}
    )
    orig_coef = fit.params['treat_post']
    orig_se = fit.bse['treat_post']
    orig_t = fit.tvalues['treat_post']

    # Compute residuals for bootstrap
    residuals = fit.resid.values
    fitted = fit.fittedvalues.values

    # Get cluster information
    clusters = df_valid['company_id'].values
    unique_clusters = np.unique(clusters)
    n_clusters = len(unique_clusters)

    # Bootstrap loop
    boot_t_stats = []

    for b in range(n_boot):
        # Generate Rademacher weights at cluster level
        cluster_weights = np.random.choice([-1, 1], size=n_clusters)
        weight_map = dict(zip(unique_clusters, cluster_weights))
        obs_weights = np.array([weight_map[c] for c in clusters])

        # Create pseudo-outcome
        y_boot = fitted + obs_weights * residuals

        # Re-estimate
        df_boot = df_valid.copy()
        df_boot[outcome] = y_boot

        try:
            # Re-fit WLS model on bootstrap sample with clustered SE
            boot_fit = smf.wls(formula, data=df_boot, weights=df_boot[weight_col]).fit(
                cov_type='cluster',
                cov_kwds={'groups': df_boot['company_id']}
            )
            boot_t = boot_fit.tvalues['treat_post']
            boot_t_stats.append(boot_t)
        except:
            boot_t_stats.append(np.nan)

    boot_t_stats = np.array(boot_t_stats)
    boot_t_stats = boot_t_stats[~np.isnan(boot_t_stats)]

    if len(boot_t_stats) < 100:
        return np.nan, np.nan, np.nan, orig_coef, orig_se

    # Bootstrap p-value: Pr(|t*| > |t_orig|)
    p_value_boot = np.mean(np.abs(boot_t_stats) > np.abs(orig_t))

    # Percentile CI
    ci_lower = np.percentile(boot_t_stats, 2.5)
    ci_upper = np.percentile(boot_t_stats, 97.5)
    ci_lower_coef = orig_coef - ci_upper * orig_se
    ci_upper_coef = orig_coef - ci_lower * orig_se

    return p_value_boot, ci_lower_coef, ci_upper_coef, orig_coef, orig_se


def wild_cluster_bootstrap_pvalue(df_sub, outcome, n_boot=1999, seed=42):
    """
    Run wild cluster bootstrap to compute robust p-values.

    Uses Rademacher weights and clusters at firm level.
    Returns bootstrap p-value and percentile CI.
    """
    np.random.seed(seed)

    # Prepare data
    df_valid = df_sub[[outcome, 'company_id', 'year', 'treat_post']].dropna().copy()

    # Get original estimate using OLS with firm + year FE
    formula = f"{outcome} ~ treat_post + C(company_id) + C(year)"
    fit = smf.ols(formula, data=df_valid).fit(
        cov_type='cluster',
        cov_kwds={'groups': df_valid['company_id']}
    )
    orig_coef = fit.params['treat_post']
    orig_se = fit.bse['treat_post']
    orig_t = fit.tvalues['treat_post']

    # Compute residuals for bootstrap
    residuals = fit.resid.values
    fitted = fit.fittedvalues.values

    # Get cluster information
    clusters = df_valid['company_id'].values
    unique_clusters = np.unique(clusters)
    n_clusters = len(unique_clusters)

    # Bootstrap loop
    boot_t_stats = []

    for b in range(n_boot):
        # Generate Rademacher weights at cluster level
        cluster_weights = np.random.choice([-1, 1], size=n_clusters)
        weight_map = dict(zip(unique_clusters, cluster_weights))
        obs_weights = np.array([weight_map[c] for c in clusters])

        # Create pseudo-outcome
        y_boot = fitted + obs_weights * residuals

        # Re-estimate
        df_boot = df_valid.copy()
        df_boot[outcome] = y_boot

        try:
            # Re-fit model on bootstrap sample with clustered SE
            boot_fit = smf.ols(formula, data=df_boot).fit(
                cov_type='cluster',
                cov_kwds={'groups': df_boot['company_id']}
            )
            boot_t = boot_fit.tvalues['treat_post']
            boot_t_stats.append(boot_t)
        except:
            boot_t_stats.append(np.nan)

    boot_t_stats = np.array(boot_t_stats)
    boot_t_stats = boot_t_stats[~np.isnan(boot_t_stats)]

    if len(boot_t_stats) < 100:
        return np.nan, np.nan, np.nan, orig_coef, orig_se

    # Bootstrap p-value: Pr(|t*| > |t_orig|)
    p_value_boot = np.mean(np.abs(boot_t_stats) > np.abs(orig_t))

    # Percentile CI
    ci_lower = np.percentile(boot_t_stats, 2.5)
    ci_upper = np.percentile(boot_t_stats, 97.5)
    ci_lower_coef = orig_coef - ci_upper * orig_se
    ci_upper_coef = orig_coef - ci_lower * orig_se

    return p_value_boot, ci_lower_coef, ci_upper_coef, orig_coef, orig_se


print("\n" + "="*80)
print("WILD CLUSTER BOOTSTRAP, BOTH SAMPLES")
print("="*80)

for sample_name, sample_info in SAMPLES.items():
    df_sample = sample_info['data']
    description = sample_info['description']

    print(f"\n{'#'*80}")
    print(f"# SAMPLE: {description}")
    print(f"{'#'*80}")

    # Prepare treatment variables
    df_sample['post'] = (df_sample['year'] >= 2019).astype(int)
    df_sample['alberta'] = (df_sample['province'] == 'Alberta').astype(int)
    df_sample['treat_post'] = df_sample['alberta'] * df_sample['post']

    for outcome in outcomes:
        print(f"\n{'='*80}")
        print(f"Outcome: {outcome} | Sample: {sample_name}")
        print('='*80)

        # Prepare data - include weight column
        df_sub = df_sample[[outcome, 'company_id', 'year', 'province', 'treat_post', 'weight']].copy()
        df_sub = df_sub[df_sub[outcome].notna()].copy()

        # Recreate treatment variable after filtering
        df_sub['post'] = (df_sub['year'] >= 2019).astype(int)
        df_sub['alberta'] = (df_sub['province'] == 'Alberta').astype(int)
        df_sub['treat_post'] = df_sub['alberta'] * df_sub['post']

        n_obs = len(df_sub)
        n_firms = df_sub['company_id'].nunique()
        n_years = df_sub['year'].nunique()

        print(f"Sample size: {n_obs} obs | {n_firms} firms | {n_years} years")

        # ====================================================================
        # Method 1: OLS with firm + year FE and clustered SE
        # ====================================================================
        # Run with clustered SE
        clustered_results = run_panelols_did(df_sub, outcome)
        treat_coef = clustered_results.params['treat_post']
        treat_se_cluster = clustered_results.bse['treat_post']
        treat_t_cluster = clustered_results.tvalues['treat_post']
        treat_pval_cluster = clustered_results.pvalues['treat_post']

        # Run without clustering for comparison
        ols_results = run_ols_did(df_sub, outcome)
        treat_se_ols = ols_results.bse['treat_post']
        treat_pval_ols = ols_results.pvalues['treat_post']

        print(f"\nOLS with Firm + Year FE (Clustered SE at firm level):")
        print(f"  Coefficient: {treat_coef:.4f}")
        print(f"  SE (OLS):    {treat_se_ols:.4f}")
        print(f"  SE (Cluster): {treat_se_cluster:.4f}")
        print(f"  t-stat:      {treat_t_cluster:.4f}")
        print(f"  p-value:     {treat_pval_cluster:.4f}")

        # ====================================================================
        # Method 2: WLS with firm + year FE and clustered SE
        # ====================================================================
        wls_coef = np.nan
        wls_se_cluster = np.nan
        wls_pval_cluster = np.nan
        p_boot_wls = np.nan
        ci_lower_wls = np.nan
        ci_upper_wls = np.nan

        try:
            wls_results = run_wls_did(df_sub, outcome, weight_col='weight')
            wls_coef = wls_results.params['treat_post']
            wls_se_cluster = wls_results.bse['treat_post']
            wls_t_cluster = wls_results.tvalues['treat_post']
            wls_pval_cluster = wls_results.pvalues['treat_post']

            print(f"\nWLS with Firm + Year FE (2018 emissions weights, Clustered SE):")
            print(f"  Coefficient: {wls_coef:.4f}")
            print(f"  SE (Cluster): {wls_se_cluster:.4f}")
            print(f"  t-stat:      {wls_t_cluster:.4f}")
            print(f"  p-value:     {wls_pval_cluster:.4f}")
        except Exception as e:
            print(f"\n  Error in WLS: {str(e)}")

        # ====================================================================
        # Method 3: Wild Cluster Bootstrap (OLS)
        # ====================================================================
        print(f"\nRunning wild cluster bootstrap for OLS (B=1999)...")

        try:
            p_boot, ci_lower, ci_upper, _, _ = wild_cluster_bootstrap_pvalue(
                df_sub, outcome, n_boot=1999, seed=42
            )

            print(f"\nWild Cluster Bootstrap (OLS, B=1999):")
            print(f"  Bootstrap p-val: {p_boot:.4f}")
            print(f"  95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
            print(f"  Significant at 5%? {'YES' if p_boot < 0.05 else 'NO'}")

            # Verify p-value is in valid range
            if p_boot < 0 or p_boot > 1:
                print(f"  WARNING: Invalid p-value detected!")
                p_boot = np.nan

        except Exception as e:
            print(f"\n  Error in OLS bootstrap: {str(e)}")
            p_boot = np.nan
            ci_lower = np.nan
            ci_upper = np.nan

        # ====================================================================
        # Method 4: Wild Cluster Bootstrap (WLS)
        # ====================================================================
        print(f"\nRunning wild cluster bootstrap for WLS (B=1999)...")

        try:
            p_boot_wls, ci_lower_wls, ci_upper_wls, _, _ = wild_cluster_bootstrap_pvalue_wls(
                df_sub, outcome, weight_col='weight', n_boot=1999, seed=42
            )

            print(f"\nWild Cluster Bootstrap (WLS, B=1999):")
            print(f"  Bootstrap p-val: {p_boot_wls:.4f}")
            print(f"  95% CI: [{ci_lower_wls:.4f}, {ci_upper_wls:.4f}]")
            print(f"  Significant at 5%? {'YES' if p_boot_wls < 0.05 else 'NO'}")

            # Verify p-value is in valid range
            if p_boot_wls < 0 or p_boot_wls > 1:
                print(f"  WARNING: Invalid p-value detected!")
                p_boot_wls = np.nan

        except Exception as e:
            print(f"\n  Error in WLS bootstrap: {str(e)}")
            p_boot_wls = np.nan
            ci_lower_wls = np.nan
            ci_upper_wls = np.nan

        # Store OLS results
        all_results.append({
            'Sample': sample_name,
            'Sample_Description': description,
            'Method': 'OLS',
            'Outcome': outcome,
            'N_Obs': n_obs,
            'N_Firms': n_firms,
            'Coefficient': treat_coef,
            'SE_OLS': treat_se_ols,
            'SE_Clustered': treat_se_cluster,
            'T_Stat': treat_t_cluster,
            'P_Value_OLS': treat_pval_ols,
            'P_Value_Clustered': treat_pval_cluster,
            'P_Value_Bootstrap': p_boot,
            'CI_Lower_95': ci_lower,
            'CI_Upper_95': ci_upper,
            'Sig_Clustered': 'Yes' if treat_pval_cluster < 0.05 else 'No',
            'Sig_Bootstrap': 'Yes' if (p_boot is not None and not np.isnan(p_boot) and p_boot < 0.05) else 'No'
        })

        # Store WLS results
        all_results.append({
            'Sample': sample_name,
            'Sample_Description': description,
            'Method': 'WLS',
            'Outcome': outcome,
            'N_Obs': n_obs,
            'N_Firms': n_firms,
            'Coefficient': wls_coef,
            'SE_OLS': np.nan,  # WLS doesn't have non-clustered SE
            'SE_Clustered': wls_se_cluster,
            'T_Stat': wls_coef / wls_se_cluster if not np.isnan(wls_se_cluster) else np.nan,
            'P_Value_OLS': np.nan,
            'P_Value_Clustered': wls_pval_cluster,
            'P_Value_Bootstrap': p_boot_wls,
            'CI_Lower_95': ci_lower_wls,
            'CI_Upper_95': ci_upper_wls,
            'Sig_Clustered': 'Yes' if (not np.isnan(wls_pval_cluster) and wls_pval_cluster < 0.05) else 'No',
            'Sig_Bootstrap': 'Yes' if (p_boot_wls is not None and not np.isnan(p_boot_wls) and p_boot_wls < 0.05) else 'No'
        })

# Save results
results_df = pd.DataFrame(all_results)
results_df.to_csv(OUTPUT_DIR / '52_wild_bootstrap_results.csv', index=False)

print("\n" + "="*80)
print("SUMMARY TABLE: WILD BOOTSTRAP RESULTS (DUAL SAMPLES, OLS vs WLS)")
print("="*80)

# Display summary by sample and method
for sample_name in SAMPLES.keys():
    print(f"\n--- Sample: {sample_name} ---")
    for method in ['OLS', 'WLS']:
        sample_results = results_df[
            (results_df['Sample'] == sample_name) & (results_df['Method'] == method)
        ][['Outcome', 'Coefficient', 'SE_Clustered', 'P_Value_Clustered',
           'P_Value_Bootstrap', 'Sig_Bootstrap']].copy()
        sample_results.columns = ['Outcome', 'Coef', 'SE', 'p (Cluster)', 'p (Boot)', 'Sig?']
        print(f"\n  {method}:")
        print(sample_results.to_string(index=False))

print(f"\nFull results saved to: {OUTPUT_DIR / '52_wild_bootstrap_results.csv'}")

# ============================================================================
# LaTeX table
# ============================================================================

print("\n" + "="*80)
print("LATEX TABLE")
print("="*80)

# Create comparison table for OLS vs WLS
latex_df = results_df[['Sample_Description', 'Method', 'Outcome', 'Coefficient',
                        'SE_Clustered', 'P_Value_Clustered', 'P_Value_Bootstrap']].copy()

# Format outcome names
latex_df['Outcome'] = latex_df['Outcome'].map({
    'green_patent_stock': 'Green Patent Stock',
    'intensity_co2e_per_m_gdp': 'Emission Intensity',
    'ln_emissions': 'Log Emissions'
})

latex_str = r"""
\begin{table}[ht]
\centering
\caption{Wild Cluster Bootstrap Inference: OLS vs WLS (Emission-Weighted)}
\label{tab:wild_bootstrap}
\footnotesize
\begin{tabular}{llcccc}
\toprule
\textbf{Sample} & \textbf{Outcome} & \textbf{Method} & \textbf{Coef.} & \textbf{p (Cluster)} & \textbf{p (Bootstrap)} \\
\midrule
"""

for sample_name in ['66_strict', '101_full']:
    sample_df = latex_df[latex_df['Sample_Description'].str.contains('66' if '66' in sample_name else '101')]
    sample_short = '66 firms' if '66' in sample_name else '101 firms'
    for outcome in ['Green Patent Stock', 'Emission Intensity', 'Log Emissions']:
        for method in ['OLS', 'WLS']:
            row = sample_df[(sample_df['Outcome'] == outcome) & (sample_df['Method'] == method)]
            if len(row) > 0:
                row = row.iloc[0]
                coef = row['Coefficient']
                p_cluster = row['P_Value_Clustered']
                p_boot = row['P_Value_Bootstrap']

                # Format significance
                sig = ''
                if not np.isnan(p_boot) and p_boot < 0.01:
                    sig = '***'
                elif not np.isnan(p_boot) and p_boot < 0.05:
                    sig = '**'
                elif not np.isnan(p_boot) and p_boot < 0.10:
                    sig = '*'

                latex_str += f"{sample_short} & {outcome} & {method} & {coef:.2f}{sig} & {p_cluster:.4f} & {p_boot:.4f} \\\\\n"
    latex_str += r"\midrule" + "\n"

latex_str = latex_str.rstrip(r"\midrule" + "\n")
latex_str += r"""\bottomrule
\end{tabular}
\vspace{0.3em}
\\
\footnotesize
\textit{Notes:} Wild cluster bootstrap uses Rademacher weights with 1,999 replications, clustered at the firm level. WLS weights observations by 2018 baseline emissions to reduce noise from smaller firms. The 66-firm sample excludes companies that entered after the 2016 GHGRP threshold change. The 101-firm sample includes all multi-province firms with baseline emissions $\geq$ 50 kt. All models include firm and year fixed effects. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{table}
"""

with open(OUTPUT_DIR / '52_wild_bootstrap_latex_table.tex', 'w') as f:
    f.write(latex_str)

print(latex_str)
print(f"\nLaTeX table saved to: {OUTPUT_DIR / '52_wild_bootstrap_latex_table.tex'}")
print("="*80)

# ============================================================================
# Validation check: Ensure p-values are valid
# ============================================================================

print("\n" + "="*80)
print("VALIDATION CHECK")
print("="*80)

invalid_p = results_df[
    (results_df['P_Value_Clustered'] < 0) | (results_df['P_Value_Clustered'] > 1) |
    (results_df['P_Value_Bootstrap'] < 0) | (results_df['P_Value_Bootstrap'] > 1)
]

if len(invalid_p) > 0:
    print("WARNING: Invalid p-values detected!")
    print(invalid_p)
else:
    print("All p-values are in valid range [0, 1]")

# Check SE reasonableness
print("\nSE Comparison (should be same order of magnitude):")
for _, row in results_df.iterrows():
    ratio = row['SE_Clustered'] / row['SE_OLS'] if row['SE_OLS'] > 0 else np.nan
    print(f"  {row['Sample']} | {row['Outcome']}: SE_Cluster/SE_OLS = {ratio:.2f}")

print("\n" + "="*80)
print("ANALYSIS COMPLETE (OLS/WLS)")
print("="*80)

# ============================================================================
# Continuous treatment: Alberta x post x standardised 2018 carbon intensity
# ============================================================================

print("\n" + "="*80)
print("CONTINUOUS TREATMENT ANALYSIS")
print("Uses 2018 carbon intensity as treatment intensity (higher = more exposed)")
print("="*80)

continuous_results = []

for sample_name, sample_info in SAMPLES.items():
    df_sample = sample_info['data'].copy()
    description = sample_info['description']

    print(f"\n{'#'*80}")
    print(f"# SAMPLE: {description} - CONTINUOUS TREATMENT")
    print(f"{'#'*80}")

    # Create treatment variables
    df_sample['post'] = (df_sample['year'] >= 2019).astype(int)
    df_sample['alberta'] = (df_sample['province'] == 'Alberta').astype(int)

    # Get 2018 carbon intensity for each firm
    if 'intensity_2018' in df_sample.columns:
        intensity_2018 = df_sample.groupby('company_id')['intensity_2018'].first()
    else:
        # Compute from intensity_co2e_per_m_gdp in 2018
        intensity_2018 = df_sample[df_sample['year'] == 2018].groupby('company_id')['intensity_co2e_per_m_gdp'].first()

    df_sample['intensity_2018_firm'] = df_sample['company_id'].map(intensity_2018)

    # Standardize intensity (mean=0, sd=1) for interpretability
    intensity_mean = df_sample['intensity_2018_firm'].mean()
    intensity_std = df_sample['intensity_2018_firm'].std()
    df_sample['intensity_2018_std'] = (df_sample['intensity_2018_firm'] - intensity_mean) / intensity_std

    # Continuous treatment: Alberta * Post * Intensity
    df_sample['treat_continuous'] = df_sample['alberta'] * df_sample['post'] * df_sample['intensity_2018_std']

    # For comparison, also compute the binary treatment
    df_sample['treat_post'] = df_sample['alberta'] * df_sample['post']

    for outcome in outcomes:
        print(f"\n{'='*80}")
        print(f"Outcome: {outcome} | Continuous Treatment")
        print('='*80)

        # Prepare data
        cols_needed = [outcome, 'company_id', 'year', 'province', 'treat_post',
                       'treat_continuous', 'intensity_2018_std', 'weight']
        df_sub = df_sample[[c for c in cols_needed if c in df_sample.columns]].copy()
        df_sub = df_sub[df_sub[outcome].notna()].copy()

        # Recreate treatment variables
        df_sub['post'] = (df_sub['year'] >= 2019).astype(int)
        df_sub['alberta'] = (df_sub['province'] == 'Alberta').astype(int)

        n_obs = len(df_sub)
        n_firms = df_sub['company_id'].nunique()

        print(f"Sample: {n_obs} obs | {n_firms} firms")
        print(f"Intensity 2018 (std): mean={df_sub['intensity_2018_std'].mean():.3f}, sd={df_sub['intensity_2018_std'].std():.3f}")

        # ====================================================================
        # OLS with Continuous Treatment
        # ====================================================================
        try:
            formula_cont = f"{outcome} ~ treat_continuous + C(company_id) + C(year)"
            model_cont = smf.ols(formula_cont, data=df_sub).fit(
                cov_type='cluster',
                cov_kwds={'groups': df_sub['company_id']}
            )

            cont_coef = model_cont.params['treat_continuous']
            cont_se = model_cont.bse['treat_continuous']
            cont_t = model_cont.tvalues['treat_continuous']
            cont_pval = model_cont.pvalues['treat_continuous']

            print(f"\nOLS with Continuous Treatment (Clustered SE):")
            print(f"  Coefficient: {cont_coef:.4f}")
            print(f"  SE: {cont_se:.4f}")
            print(f"  t-stat: {cont_t:.4f}")
            print(f"  p-value: {cont_pval:.4f}")
            print(f"  Interpretation: 1 SD increase in 2018 intensity -> {cont_coef:.2f} unit change in {outcome}")
        except Exception as e:
            print(f"  Error in continuous treatment OLS: {str(e)}")
            cont_coef = np.nan
            cont_se = np.nan
            cont_pval = np.nan

        # ====================================================================
        # Wild Bootstrap for Continuous Treatment
        # ====================================================================
        p_boot_cont = np.nan
        ci_lower_cont = np.nan
        ci_upper_cont = np.nan

        try:
            np.random.seed(42)
            df_valid = df_sub[[outcome, 'company_id', 'year', 'treat_continuous']].dropna().copy()

            formula_cont = f"{outcome} ~ treat_continuous + C(company_id) + C(year)"
            fit = smf.ols(formula_cont, data=df_valid).fit(
                cov_type='cluster',
                cov_kwds={'groups': df_valid['company_id']}
            )

            orig_t = fit.tvalues['treat_continuous']
            residuals = fit.resid.values
            fitted = fit.fittedvalues.values
            clusters = df_valid['company_id'].values
            unique_clusters = np.unique(clusters)
            n_clusters = len(unique_clusters)

            boot_t_stats = []
            n_boot = 999

            for b in range(n_boot):
                cluster_weights = np.random.choice([-1, 1], size=n_clusters)
                weight_map = dict(zip(unique_clusters, cluster_weights))
                obs_weights = np.array([weight_map[c] for c in clusters])

                y_boot = fitted + obs_weights * residuals
                df_boot = df_valid.copy()
                df_boot[outcome] = y_boot

                try:
                    boot_fit = smf.ols(formula_cont, data=df_boot).fit(
                        cov_type='cluster',
                        cov_kwds={'groups': df_boot['company_id']}
                    )
                    boot_t_stats.append(boot_fit.tvalues['treat_continuous'])
                except:
                    pass

            boot_t_stats = np.array(boot_t_stats)
            boot_t_stats = boot_t_stats[~np.isnan(boot_t_stats)]

            if len(boot_t_stats) >= 100:
                p_boot_cont = np.mean(np.abs(boot_t_stats) > np.abs(orig_t))
                ci_lower_cont = fit.params['treat_continuous'] - np.percentile(boot_t_stats, 97.5) * fit.bse['treat_continuous']
                ci_upper_cont = fit.params['treat_continuous'] - np.percentile(boot_t_stats, 2.5) * fit.bse['treat_continuous']

                print(f"\nWild Bootstrap (B={n_boot}):")
                print(f"  Bootstrap p-val: {p_boot_cont:.4f}")
                print(f"  95% CI: [{ci_lower_cont:.4f}, {ci_upper_cont:.4f}]")
                print(f"  Significant at 5%? {'YES' if p_boot_cont < 0.05 else 'NO'}")
        except Exception as e:
            print(f"  Error in continuous bootstrap: {str(e)}")

        continuous_results.append({
            'Sample': sample_name,
            'Sample_Description': description,
            'Outcome': outcome,
            'Treatment_Type': 'Continuous (2018 Intensity)',
            'N_Obs': n_obs,
            'N_Firms': n_firms,
            'Coefficient': cont_coef,
            'SE_Clustered': cont_se,
            'P_Value_Clustered': cont_pval,
            'P_Value_Bootstrap': p_boot_cont,
            'CI_Lower_95': ci_lower_cont,
            'CI_Upper_95': ci_upper_cont,
        })

# Save continuous treatment results
continuous_df = pd.DataFrame(continuous_results)
continuous_df.to_csv(OUTPUT_DIR / '52_continuous_treatment_results.csv', index=False)

print("\n" + "="*80)
print("CONTINUOUS TREATMENT SUMMARY")
print("="*80)
print(continuous_df[['Sample', 'Outcome', 'Coefficient', 'P_Value_Clustered', 'P_Value_Bootstrap']].to_string(index=False))

print("\n" + "="*80)
print("ALL ANALYSES COMPLETE")
print("="*80)
