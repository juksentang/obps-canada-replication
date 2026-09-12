#!/usr/bin/env python3
"""Does the response vary over the oil-price cycle and by oil-sector exposure?
Post-period split by oil-price regime (2019-2021 vs 2022-2023), oil-exposed vs other sectors, and treatment x demeaned ln WTI.
Outputs: outputs/tables/73_oil_cycle.csv, analysis/outputs/manuscript_inputs/tables/tab_oilcycle.tex; adds 'oil_cycle' and 'wti_by_year' to analysis/outputs/manuscript_inputs/numbers.json"""
import json, numpy as np, pandas as pd, statsmodels.api as sm, warnings
from paths import PANEL, TAB, PAPER
warnings.filterwarnings('ignore')
T = TAB; SUB = PAPER
raw = pd.read_csv(PANEL)
d = raw[(raw.sample_50kt_baseline == 1) & (raw.multi_province_dummy == 1)].copy()
d['first'] = d.company_id.map(d.groupby('company_id').year.min()); d = d[d['first'] <= 2016].copy()
d['alberta'] = (d.province == 'Alberta').astype(int); d['post'] = (d.year >= 2019).astype(int); d['tp'] = d.alberta * d.post
d['ln_E'] = np.log(d.total_emissions_co2e); d['ln_Y'] = np.log(d.gdp_real_million_v2); d['ln_I'] = d.ln_E - d.ln_Y
d['naics'] = d.naics_code_3digit.astype(str); d['oil'] = d.naics.isin(['211', '324', '486']).astype(int)
d['lnwti_c'] = d.ln_wti_price - d.ln_wti_price.mean(); d['tp_x_wti'] = d.tp * d.lnwti_c; d['ab_x_wti'] = d.alberta * d.lnwti_c
d['oil_post'] = d.oil * d.post; d['tp_a'] = d.tp * (d.year <= 2021); d['tp_b'] = d.tp * (d.year >= 2022); d['tp_oil'] = d.tp * d.oil; d['tp_non'] = d.tp * (1 - d.oil)
def fit(w, y, treat, fe=('company_id', 'year')):
    w = w.dropna(subset=[y] + list(treat)); X = w[list(treat)].astype(float)
    for g in fe: X = pd.concat([X, pd.get_dummies(w[g].astype(str), prefix=g, drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X); codes, _ = pd.factorize(w.company_id)
    r = sm.OLS(w[y].values, X.values).fit(cov_type='cluster', cov_kwds={'groups': codes}); r.cols = X.columns.tolist(); r.n = len(w); return r
def diffp(r, a, b):
    R = np.zeros((1, len(r.params))); R[0, r.cols.index(a)] = 1; R[0, r.cols.index(b)] = -1
    return float(r.wald_test(R, use_f=True, scalar=True).pvalue)
OUT = ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E', 'ln_I', 'ln_Y']; rows = []
wti = raw.groupby('year').wti_price_usd.first().round(2).to_dict()   # annual averages; every printed WTI value is formatted from this dict (macro \nWti<year> uses the same)
def W(y): return f"{wti[y]:.0f}"
n_oil, n_non = d[d.oil == 1].company_id.nunique(), d[d.oil == 0].company_id.nunique()
LAB_A, LAB_B = f'2019-2021 (WTI ${W(2020)}-{W(2021)})', f'2022-2023 (WTI ${W(2023)}-{W(2022)})'
LAB_OIL, LAB_NON = f'Oil, gas, refining, pipelines ({n_oil} firms)', f'Other sectors ({n_non} firms)'
for y in OUT:
    r = fit(d, y, ('tp_a', 'tp_b')); i, j = r.cols.index('tp_a'), r.cols.index('tp_b')
    rows.append(dict(outcome=y, block='period', a_coef=r.params[i], a_se=r.bse[i], a_p=r.pvalues[i], b_coef=r.params[j], b_se=r.bse[j], b_p=r.pvalues[j], diff_p=diffp(r, 'tp_a', 'tp_b'), N=r.n,
                     a_label=LAB_A, b_label=LAB_B))
    r = fit(d, y, ('tp_oil', 'tp_non', 'oil_post')); i, j = r.cols.index('tp_oil'), r.cols.index('tp_non')
    rows.append(dict(outcome=y, block='sector', a_coef=r.params[i], a_se=r.bse[i], a_p=r.pvalues[i], b_coef=r.params[j], b_se=r.bse[j], b_p=r.pvalues[j], diff_p=diffp(r, 'tp_oil', 'tp_non'), N=r.n,
                     a_label=LAB_OIL, b_label=LAB_NON))
    r = fit(d, y, ('tp', 'tp_x_wti', 'ab_x_wti')); i, j, k = r.cols.index('tp'), r.cols.index('tp_x_wti'), r.cols.index('ab_x_wti')
    rows.append(dict(outcome=y, block='interaction', a_coef=r.params[i], a_se=r.bse[i], a_p=r.pvalues[i], b_coef=r.params[j], b_se=r.bse[j], b_p=r.pvalues[j], diff_p=np.nan, N=r.n,
                     a_label='Alberta x post', b_label='Alberta x post x (ln WTI - mean)', c_coef=r.params[k], c_se=r.bse[k], c_p=r.pvalues[k]))
res = pd.DataFrame(rows); res.to_csv(T / '73_oil_cycle.csv', index=False)
print(res.round(3).to_string()); print('firms oil:', d[d.oil == 1].company_id.nunique(), 'non:', d[d.oil == 0].company_id.nunique())
# ---- LaTeX table
def texminus(t):
    import re as _re
    return _re.sub(r'(?<![\w$\-])-(?=\d)', '$-$', t)
def sig(p): return '$^{***}$' if p < .01 else '$^{**}$' if p < .05 else '$^{*}$' if p < .10 else ''
LAB = {'green_patent_stock': 'Green patent stock', 'intensity_co2e_per_m_gdp': 'Emission intensity (tCO$_2$e/\\$M)', 'ln_E': 'Log emissions', 'ln_I': 'Log sector intensity', 'ln_Y': 'Log implied output'}
DEC = {'green_patent_stock': 1, 'intensity_co2e_per_m_gdp': 0, 'ln_E': 3, 'ln_I': 3, 'ln_Y': 3}
def cs(c, s, p, dd): return f'{c:.{dd}f}{sig(p)} ({s:.{dd}f})'
lines = ['\\multicolumn{4}{l}{\\textit{A. Post-period split by oil-price regime}} \\\\', f' & 2019--2021 (WTI \\${W(2020)}--{W(2021)}/bbl) & 2022--2023 (WTI \\${W(2023)}--{W(2022)}/bbl) & $p$ (equal) \\\\ \\midrule']
for y in ['ln_E', 'intensity_co2e_per_m_gdp', 'green_patent_stock', 'ln_I']:
    m = res[(res.outcome == y) & (res.block == 'period')].iloc[0]; lines.append(f"{LAB[y]} & {cs(m.a_coef,m.a_se,m.a_p,DEC[y])} & {cs(m.b_coef,m.b_se,m.b_p,DEC[y])} & {m.diff_p:.3f} \\\\")
lines += ['\\addlinespace', '\\multicolumn{4}{l}{\\textit{B. Oil-exposed versus other sectors}} \\\\', f' & {LAB_OIL} & {LAB_NON} & $p$ (equal) \\\\ \\midrule']
for y in ['ln_E', 'intensity_co2e_per_m_gdp', 'green_patent_stock', 'ln_I']:
    m = res[(res.outcome == y) & (res.block == 'sector')].iloc[0]; lines.append(f"{LAB[y]} & {cs(m.a_coef,m.a_se,m.a_p,DEC[y])} & {cs(m.b_coef,m.b_se,m.b_p,DEC[y])} & {m.diff_p:.3f} \\\\")
lines += ['\\addlinespace', '\\multicolumn{4}{l}{\\textit{C. Treatment effect interacted with the oil price}} \\\\', ' & Alberta $\\times$ post-2019 & $\\ldots\\times$ (ln WTI $-$ mean) & Alberta $\\times$ (ln WTI $-$ mean) \\\\ \\midrule']
for y in ['ln_E', 'intensity_co2e_per_m_gdp', 'green_patent_stock', 'ln_I']:
    m = res[(res.outcome == y) & (res.block == 'interaction')].iloc[0]; lines.append(f"{LAB[y]} & {cs(m.a_coef,m.a_se,m.a_p,DEC[y])} & {cs(m.b_coef,m.b_se,m.b_p,DEC[y])} & {cs(m.c_coef,m.c_se,m.c_p,DEC[y])} \\\\")
(SUB / 'tables' / 'tab_oilcycle.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Carbon pricing across the oil-price cycle: differential responses by post-period oil-price regime, by oil-sector exposure, and interacted with the oil price}
\label{tab:oil}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccc}
\toprule
""" + '\n'.join(lines) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: 66 large multi-province firms, 2004--2023, firm and year fixed effects, standard errors clustered by firm in parentheses; $N=935$ (934 for log sector intensity). Panel A splits the post-2019 indicator into 2019--2021 (annual average WTI crude price US\$""" + f'{W(2019)}, {W(2020)} and {W(2021)}' + r""" per barrel) and 2022--2023 (US\$""" + f'{W(2022)} and {W(2023)}' + r"""). Panel B splits it by sector: oil and gas extraction (NAICS 211), petroleum refining (324) and pipeline transportation (486) versus all other sectors, following the firm's principal sector in each year (one firm changes principal sector during the panel and contributes firm-years to both groups, so the firm counts sum to """ + str(n_oil + n_non) + r"""), controlling for a sector-group $\times$ post-2019 indicator so that oil-exposed firms outside Alberta may have their own post-2019 shift. Panel C interacts the treatment indicator with the demeaned log annual WTI price, controlling for the Alberta-specific oil-price response. ``$p$ (equal)'' tests equality of the two coefficients. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.
\end{minipage}
\end{table}
"""))
nj = SUB / 'numbers.json'; num = json.load(open(nj)) if nj.exists() else {}
num['oil_cycle'] = res.to_dict('records'); num['wti_by_year'] = wti
json.dump(num, open(nj, 'w'), indent=1, default=float); print('table + numbers written')
