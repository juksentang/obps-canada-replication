#!/usr/bin/env python3
"""Build the LaTeX table fragments (analysis/outputs/manuscript_inputs/tables/tab_*.tex) and analysis/outputs/manuscript_inputs/numbers.json from the estimation outputs
in outputs/tables (scripts 52, 60, 70, 71, 75, 80, 81, 82)."""
import json
import numpy as np, pandas as pd
from paths import TAB, PAPER
T = TAB; SUB = PAPER; TAB = SUB / 'tables'
def texminus(t):
    import re as _re
    return _re.sub(r'(?<![\w$\-])-(?=\d)', '$-$', t)
def sig(p): return '$^{***}$' if p < .01 else '$^{**}$' if p < .05 else '$^{*}$' if p < .10 else ''
def f(x, d=3): return f'{x:.{d}f}'
def cs(coef, se, p, d=3): return f'{coef:.{d}f}{sig(p)} ({se:.{d}f})'
base = pd.read_csv(T / '70_baseline.csv'); pt = pd.read_csv(T / '70_pretrend_tests.csv'); es = pd.read_csv(T / '70_event_study.csv')
cc = pd.read_csv(T / '70_char_controls.csv'); oc = pd.read_csv(T / '70_oil_controls.csv'); dep = pd.read_csv(T / '70_depreciation.csv')
sw = pd.read_csv(T / '70_sample_windows.csv'); seg = pd.read_csv(T / '70_segmented.csv'); het = pd.read_csv(T / '70_mechanism_hetero.csv')
sel = pd.read_csv(T / '70_selection_table.csv'); wf = pd.read_csv(T / '71_true_within_firm_results.csv'); cnt = json.load(open(T / '70_sample_counts.json'))
wb = pd.read_csv(T / '52_wild_bootstrap_results.csv'); power = pd.read_csv(T / '60_power_analysis_n66.csv')
hon = pd.read_csv(T / '82_honestdid_official.csv'); hon = hon[hon.treatment == 'time-varying']  # conditional-least-favourable hybrid sets
OUT3 = ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E']
SHORT = {'green_patent_stock': 'Green patent stock (count)', 'intensity_co2e_per_m_gdp': 'Emission intensity (tCO$_2$e/\\$M)', 'ln_E': 'Log total emissions'}
LAB = {'green_patent_stock': 'Green patent stock (count)', 'intensity_co2e_per_m_gdp': 'Emission intensity (tCO$_2$e per \\$M output)', 'ln_E': 'Log total emissions',
       'ln_I': 'Log sector emission intensity', 'ln_Y': 'Log implied real output'}
DEC = {'green_patent_stock': 2, 'intensity_co2e_per_m_gdp': 1, 'ln_E': 3, 'ln_I': 3, 'ln_Y': 3}
def g(df, y, **k):
    m = df[df.outcome == y]
    for a, b in k.items(): m = m[m[a] == b] if not isinstance(b, str) or not b.startswith('~') else m[m[a].str.contains(b[1:], regex=False)]
    return m.iloc[0]
ALT = {'green_patent_stock': 'green_patent_stock', 'intensity_co2e_per_m_gdp': 'intensity_co2e_per_m_gdp', 'ln_E': 'ln_emissions'}
def wcb(y): return wb[(wb.Sample == '66_strict') & (wb.Method == 'OLS') & (wb.Outcome == ALT[y])].P_Value_Bootstrap.iloc[0]
permdf = pd.read_csv(T / '70_permutation.csv')
def perm(y): return permdf[permdf.outcome == y].perm_p.iloc[0]
def ptp(y, key): return pt[(pt.outcome == y) & (pt.test.str.startswith(key))].p.iloc[0]
def honest_row(y):
    h = hon[hon.outcome == y]; o = h[h.method == 'original'].iloc[0]; r1 = h[(h.method != 'original') & np.isclose(h.Mbar, 1.0)].iloc[0]
    return o.lb, o.ub, r1.lb, r1.ub
num = {}
# ---------------------------------------------------------------- Table: sample / representativeness (transposed: groups as columns)
GROUPS = [('Single-province firms', 'Single-\\\\province'), ('All multi-province firms (101)', 'All multi-\\\\province'), ('Analysis sample: incumbents observed by 2016 (66)', 'Analysis\\\\sample'), ('Excluded post-2016 entrants (35)', 'Excluded\\\\entrants')]
def col(g): return sel[sel.group == g].iloc[0]
stats = [('Firms (2018)', lambda r: f"{int(r.firms_2018)}"), ('Firm-year observations', lambda r: f"{int(r.firm_years):,}"),
         ('Mean emissions, 2018 (kt CO$_2$e)', lambda r: f"{r.mean_emissions_kt:,.0f}"), ('Median emissions, 2018 (kt CO$_2$e)', lambda r: f"{r.median_emissions_kt:,.0f}"),
         ('Share of 2018 GHGRP emissions (\\%)', lambda r: f"{100*r.share_ghgrp_emissions_2018:.1f}"), ('Mean facilities', lambda r: f"{r.mean_facilities:.1f}"),
         ('Mean green patent stock', lambda r: f"{r.mean_patent_stock:.1f}"), ('Any green patents (\\%)', lambda r: f"{100*r.share_with_patents:.0f}"),
         ('EITE sectors (\\%)', lambda r: f"{100*r.share_eite:.0f}"), ('Alberta-based (\\%)', lambda r: f"{100*r.share_alberta:.0f}")]
rows = [name + ' & ' + ' & '.join(fn(col(g)) for g, _ in GROUPS) + ' \\\\' for name, fn in stats]
head = ' & ' + ' & '.join('\\makecell{' + h + '}' for _, h in GROUPS) + ' \\\\'
(TAB / 'tab_sample.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\small
\caption{Sample construction and representativeness, 2018 cross-section}
\label{tab:sample}
\begin{tabular}{lcccc}
\toprule
""" + head + r"""
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: GHGRP reporters with baseline emissions of at least 50 kt CO$_2$e: 271 single-province and 101 multi-province firms, of which 66 incumbents observed by 2016 form the analysis sample and 35 entered after the 2017 threshold change without a usable pre-period. Patent stock: perpetual inventory, 15\% depreciation. EITE sectors: NAICS 211, 212, 311, 321, 322, 324, 325, 327, 331, 332. Principal province: modal province of the firm's reporting facilities.
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- Table: main results
rows = []
for y in OUTCOMES if False else OUT3:
    b = g(base, y); lb0, ub0, lb1, ub1 = honest_row(y); d = DEC[y]
    rows.append(f"{SHORT[y]} & {b.coef:.{d}f}{sig(b.p)} ({b.se:.{d}f}) & {b.p:.2f} & {wcb(y):.2f} & {perm(y):.2f} & {ptp(y,'leads k=-6'):.2f} & [{lb1:.{d}f}, {ub1:.{d}f}] \\\\")
    num[y] = dict(coef=b.coef, se=b.se, p=b.p, ci_lo=b.ci_lo, ci_hi=b.ci_hi, wcb=wcb(y), perm=perm(y), pretrend_p=ptp(y, 'leads k=-6'),
                  pretrend_all_p=ptp(y, 'all pre'), pretrend_1617_p=ptp(y, 'leads 2016'), post_joint_p=ptp(y, 'post'), honest_M0=[lb0, ub0], honest_M1=[lb1, ub1], N=int(b.N))
hnote = ('Honest DiD: conditional--least-favourable hybrid 95\\% sets at $\\bar M=1$ (Rambachan and Roth, 2023; Supplementary Table S5).')
(TAB / 'tab_main.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\small
\caption{Baseline difference-in-differences estimates: differential response of Alberta-based large multi-province firms after the 2019 national price floor, 66 firms, 2004--2023}
\label{tab:main}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lcccccc}
\toprule
 & & \multicolumn{3}{c}{$p$-value} & Pre-trend & Honest DiD \\
\cmidrule(lr){3-5}
Outcome & $\hat\beta$ (SE) & Cluster & Wild boot. & Permut. & joint $p$ & 95\% CS, $\bar M=1$ \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Equation~\ref{eq:did}, one regression per outcome; $N=935$, 66 firms; firm-clustered standard errors in parentheses. Wild bootstrap: Rademacher weights, 1,999 replications. Permutation: 2,000 reassignments across firm--province cells, two-sided. Pre-trend: joint test that the 2013--2017 leads of Equation~\ref{eq:es} are zero. """ + hnote + r""" $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$ (cluster-robust).
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- Table: robustness (controls / oil / windows) for the three outcomes
WINLAB = {'Balanced-ish: firms observed 2016-2023': 'Firms observed 2016--2023', 'Pre-COVID: 2004-2019': 'Pre-COVID: 2004--2019', 'Exclude 2020-2021 (pandemic years)': 'Exclude 2020--2021 (pandemic years)'}
def block(title, df, keycol, keys, d):
    out = [f"\\multicolumn{{4}}{{l}}{{\\textit{{{title}}}}} \\\\"]
    for k in keys:
        cells = []
        for y in OUT3:
            m = df[(df.outcome == y) & (df[keycol] == k)].iloc[0]; cells.append(cs(m.coef, m.se, m.p, DEC[y]))
        lab = WINLAB.get(k, k).replace(' x ', ' $\\times$ ').replace('&', '\\&')
        out.append(f"\\quad {lab} & " + ' & '.join(cells) + ' \\\\')
    return out
rows = []
rows += block('A. Firm-characteristic trends and sector--year shocks', cc, 'spec', cc.spec.unique().tolist(), 3)
rows.append('\\addlinespace')
rows += block('B. Oil-price controls', oc, 'spec', [s for s in oc.spec.unique() if s != 'Baseline'], 3)
rows.append('\\addlinespace')
rows += block('C. Sample windows', sw, 'window', [s for s in sw.window.unique() if not s.startswith('Full')], 3)
(TAB / 'tab_robust.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Robustness of the three main estimates to firm-characteristic trends, sector--year shocks, oil prices and sample windows}
\label{tab:robust}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccc}
\toprule
Specification & Green patents & Intensity & Log emissions \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Alberta $\times$ post-2019 coefficients; firm and year fixed effects; firm-clustered standard errors in parentheses. Panel A adds 2018 firm characteristics $\times$ year effects, NAICS 3-digit $\times$ year effects or province-specific linear trends; panel B adds the log annual WTI price and its Alberta interaction (and lag); panel C restricts the sample window. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- Table: depreciation
rows = []
for delta in (0.10, 0.15, 0.20):
    a = dep[(dep.outcome == 'stock_d') & (dep.delta == delta)].iloc[0]; b = dep[(dep.outcome == 'ln_stock_d') & (dep.delta == delta)].iloc[0]
    rows.append(f"$\\delta={delta:.2f}$ & {cs(a.coef,a.se,a.p,2)} & {a.p:.2f} & {a.pre_mean:.1f} & {cs(b.coef,b.se,b.p,3)} & {b.p:.2f} \\\\")
pub = dep[dep.outcome.str.startswith('green_patent_stock')].iloc[0]
(TAB / 'tab_depreciation.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Sensitivity of the green-patent estimate to the depreciation rate of the patent stock}
\label{tab:depreciation}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccc}
\toprule
 & \multicolumn{3}{c}{Stock in levels} & \multicolumn{2}{c}{log(1 + stock)} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-6}
Depreciation rate & $\hat\beta$ (SE) & $p$ & Pre-period mean (Alberta) & $\hat\beta$ (SE) & $p$ \\
\midrule
""" + '\n'.join(rows) + f"""
\\addlinespace
Published series ($\\delta=0.15$, allocated across provinces) & {cs(pub.coef,pub.se,pub.p,2)} & {pub.p:.2f} & {pub.pre_mean:.1f} & -- & -- \\\\
\\bottomrule
\\end{{tabular}}
\\end{{adjustbox}}
\\par\\vspace{{3pt}}\\begin{{minipage}}{{\\textwidth}}\\footnotesize
Notes: Firm-level stocks rebuilt from annual fractional flows, $S_t=(1-\\delta)S_{{t-1}}+F_t$; the published series allocates the firm stock across provinces by facility NAICS weights, hence the small difference at $\\delta=0.15$. Firm and year fixed effects; firm-clustered standard errors; $N=935$, 66 firms.
\\end{{minipage}}
\\end{{table}}
"""))
# ---------------------------------------------------------------- Table: segmented
rows = []
for y in OUT3:
    s = seg[seg.outcome == y]; d = DEC[y]
    cells = [cs(s[s.period == p].iloc[0].coef, s[s.period == p].iloc[0].se, s[s.period == p].iloc[0].p, d) for p in ['2016-17 announcement', '2018 legislation', '2019+ implementation']]
    jp = s[s.period.str.startswith('joint')].iloc[0].p
    rows.append(f"{LAB[y]} & " + ' & '.join(cells) + f" & {jp:.3f} \\\\")
    num[y]['segmented'] = {p: dict(coef=s[s.period == p].iloc[0].coef, se=s[s.period == p].iloc[0].se, p=s[s.period == p].iloc[0].p) for p in ['2016-17 announcement', '2018 legislation', '2019+ implementation']}; num[y]['segmented_joint_p'] = jp
(TAB / 'tab_segmented.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Policy-stage specification: announcement, legislation and implementation}
\label{tab:segmented}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lcccc}
\toprule
Outcome & Alberta $\times$ 2016--17 & Alberta $\times$ 2018 & Alberta $\times$ 2019--23 & Joint $p$ \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Equation~\ref{eq:stage}, mutually exclusive period indicators, reference period 2004--2015; firm and year fixed effects; firm-clustered standard errors in parentheses; $N=935$, 66 firms. ``Joint $p$'' tests that all three coefficients are zero. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- Table: heterogeneity
rows = []
dims = ['Prior green patents in 2018 (vs. none)', 'EITE sector (vs. non-EITE)', 'Above-median 2018 emissions (vs. below)']; DIMLAB = {dims[0]: 'Prior patents', dims[1]: 'EITE', dims[2]: 'Large'}
for y in OUT3 + ['ln_I']:
    rows.append(f"\\multicolumn{{6}}{{l}}{{\\textit{{{LAB[y]}}}}} \\\\")
    for dm in dims:
        h = het[(het.outcome == y) & (het.dimension == dm)].iloc[0]; d = DEC[y]
        rows.append(f"\\quad {DIMLAB[dm]} & {int(h.n_firms_high)}/{int(h.n_firms_low)} & {cs(h.high_coef,h.high_se,h.high_p,d)} & {cs(h.low_coef,h.low_se,h.low_p,d)} & {h['diff']:.{d}f} & {h.diff_p:.3f} \\\\")
        num.setdefault('hetero', {})[f'{y}|{dm}'] = dict(high=h.high_coef, high_p=h.high_p, low=h.low_coef, low_p=h.low_p, diff=h['diff'], diff_p=h.diff_p, n_high=int(h.n_firms_high), n_low=int(h.n_firms_low))
(TAB / 'tab_hetero.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Heterogeneous responses by prior innovation capacity, trade exposure and size}
\label{tab:hetero}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccc}
\toprule
Outcome / split & Firms (high/low) & With & Without & Difference & $p$ (diff.) \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Equation~\ref{eq:het}: Alberta $\times$ post-2019 interacted with a binary characteristic (``Prior patents'': positive green patent stock in 2018; ``EITE'': sector as in Table~\ref{tab:sample}; ``Large'': above-median 2018 emissions), with the characteristic $\times$ post-2019 control; group effects with firm-clustered standard errors in parentheses; ``$p$ (diff.)'' tests their equality. Firm and year fixed effects; $N=935$ (934 for log sector intensity). $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- Table: decomposition (SI)
rows = []
for y in ['ln_E', 'ln_I', 'ln_Y']:
    b = g(base, y); o = g(oc, y, spec='+ Alberta x ln WTI'); n = g(cc, y, spec='+ NAICS-3 x year FE'); on = oc[(oc.outcome == y) & (oc.spec.str.contains('NAICS'))].iloc[0]; pc = sw[(sw.outcome == y) & (sw.window.str.startswith('Pre-COVID'))].iloc[0]
    rows.append(f"{LAB[y]} & {cs(b.coef,b.se,b.p)} & {cs(o.coef,o.se,o.p)} & {cs(n.coef,n.se,n.p)} & {cs(on.coef,on.se,on.p)} & {cs(pc.coef,pc.se,pc.p)} & {ptp(y,'leads k=-6'):.3f} & {ptp(y,'leads 2016'):.3f} \\\\")
    num[y] = num.get(y, {}); num[y].update(dict(coef=b.coef, se=b.se, p=b.p, oil=dict(coef=o.coef, se=o.se, p=o.p), naics=dict(coef=n.coef, se=n.se, p=n.p), oil_naics=dict(coef=on.coef, se=on.se, p=on.p), precovid=dict(coef=pc.coef, se=pc.se, p=pc.p), pretrend_p=ptp(y, 'leads k=-6'), pretrend_1617_p=ptp(y, 'leads 2016')))
(TAB / 'tab_decomp.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Accounting decomposition $\ln E=\ln I+\ln Y$: firm emissions, sector emission intensity and implied real output}
\label{tab:decomp}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccccc}
\toprule
 & Baseline & + Alberta $\times$ & + NAICS $\times$ & + both & Pre-COVID & \multicolumn{2}{c}{Pre-trend joint $p$} \\
 & & ln WTI & year FE & & ($\leq$2019) & 2013--17 & 2016--17 \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: $E$ is firm emissions; $I$ the emission intensity of the firm's NAICS 3-digit sector in its province (GHGRP sector emissions over real sector GDP, 2015 dollars); $Y=E/I$ is implied real output, so the three coefficients sum exactly within each column. Alberta $\times$ post-2019 coefficients; firm and year fixed effects; firm-clustered standard errors in parentheses; $N=934$. Last two columns: joint tests that the event-study leads are zero. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- Table: true within-firm (facility panel)
rows = []
for _, r in wf.iterrows():
    sp = r.spec.replace(' x year', ' $\\times$ year')
    if r.spec.startswith('Event'): rows.append(f"\\quad {sp} & $F={r.coef:.2f}$ & $p={r.p:.2f}$ & {int(r.N)} & {int(r.firms)} & -- \\\\")
    else: rows.append(f"\\quad {sp} & {cs(r.coef,r.se,r.p)} & {r.p:.3f} & {int(r.N)} & {int(r.firms)} & {int(r.cells)} \\\\")
r1 = rows[:4]; r2 = rows[4:]
(TAB / 'tab_within_firm.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Genuine within-firm comparison: Alberta versus non-Alberta operations of the same firm, company--province--year panel of facility emissions}
\label{tab:withinfirm}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccc}
\toprule
Specification & $\hat\beta$ (SE) & $p$ & $N$ & Firms & Firm--province cells \\
\midrule
\multicolumn{6}{l}{\textit{A. All firms with facilities both inside and outside Alberta}} \\
""" + '\n'.join(r1) + r"""
\addlinespace
\multicolumn{6}{l}{\textit{B. Large incumbents ($\geq$50 kt in 2018, observed by 2016)}} \\
""" + '\n'.join(r2) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Outcome: log emissions of a firm's facilities within each province and year. The third specification of each panel includes firm $\times$ year and firm--province effects, so Alberta $\times$ post-2019 is identified only from firm-years with facilities both inside and outside Alberta. Firm-clustered standard errors. The event-study row is the joint test of the 2013--2017 leads in that specification.
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- Table: event-study coefficients (SI)
def es_rows(df):
    out = []
    for k in sorted(df.k.unique()):
        cells = []
        for y in OUT3 + ['ln_I', 'ln_Y']:
            m = df[(df.outcome == y) & (df.k == k)].iloc[0]; cells.append(cs(m.coef, m.se, m.p, DEC[y]))
        lab = '$\\leq-7$ (2004--12)' if k == -7 else f'{k} ({2019+k})'
        out.append(f"{lab} & " + ' & '.join(cells) + ' \\\\')
        if k == -2: out.append('$-1$ (2018) & \\multicolumn{5}{c}{reference year} \\\\')
    return out
fes = pd.read_csv(T / '80_fixed_event_study.csv'); fpt = pd.read_csv(T / '80_fixed_pretrend.csv')
def fptp(y, key): return fpt[(fpt.outcome == y) & (fpt.test.str.startswith(key))].p.iloc[0]
rows = ['\\multicolumn{6}{l}{\\textit{A. Time-varying principal province (baseline)}} \\\\'] + es_rows(es)
(TAB / 'tab_eventstudy.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\scriptsize
\caption{Event-study coefficients (Equation~\ref{eq:si_es}) for all outcomes under both treatment definitions}
\label{tab:es}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccc}
\toprule
$k$ (year) & Green patents & Intensity & Log emissions & Log sector intensity & Log implied output \\
\midrule
""" + '\n'.join(rows) + r"""
\midrule
Joint $p$, leads 2013--17 & """ + ' & '.join(f"{ptp(y,'leads k=-6'):.3f}" for y in OUT3 + ['ln_I', 'ln_Y']) + r""" \\
Joint $p$, all leads & """ + ' & '.join(f"{ptp(y,'all pre'):.3f}" for y in OUT3 + ['ln_I', 'ln_Y']) + r""" \\
Joint $p$, lags 2019--23 & """ + ' & '.join(f"{ptp(y,'post'):.3f}" for y in OUT3 + ['ln_I', 'ln_Y']) + r""" \\
\midrule
\multicolumn{6}{l}{\textit{B. Fixed 2018 principal province}} \\
""" + '\n'.join(es_rows(fes)) + r"""
\midrule
Joint $p$, leads 2013--17 & """ + ' & '.join(f"{fptp(y,'leads k=-6'):.3f}" for y in OUT3 + ['ln_I', 'ln_Y']) + r""" \\
Joint $p$, lags 2019--23 & """ + ' & '.join(f"{fptp(y,'post'):.3f}" for y in OUT3 + ['ln_I', 'ln_Y']) + r""" \\
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\scriptsize
Notes: Coefficients on Alberta $\times$ year indicators relative to 2018; years up to 2012 are binned. Panel A uses the principal province in each year; panel B the principal province observed in 2018. Firm and year fixed effects; firm-clustered standard errors in parentheses. 2023 patent counts are censored by publication lags (see text). $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.
\end{minipage}
\end{table}
"""))
# ---------------------------------------------------------------- numbers.json
num['counts'] = cnt; num['power'] = power.to_dict('records'); num['permutation'] = permdf.to_dict('records')
num['within_firm'] = wf.to_dict('records'); num['selection'] = sel.to_dict('records')
num['event_study'] = {y: es[es.outcome == y][['k', 'coef', 'se', 'p']].to_dict('records') for y in OUT3 + ['ln_I', 'ln_Y']}
num['depreciation'] = dep.to_dict('records'); num['windows'] = sw.to_dict('records'); num['char_controls'] = cc.to_dict('records'); num['oil'] = oc.to_dict('records')
(SUB / 'numbers.json').write_text(json.dumps(num, indent=1, default=float))
print('Tables written:', sorted(p.name for p in TAB.glob('*.tex')))

# ============================================================================ Round 4 tables (fixed treatment, multi-level inference, official Honest DiD)
def _csv(name):
    p = T / name; return pd.read_csv(p) if p.exists() else None
ft = _csv('80_fixed_treatment.csv'); fp = _csv('80_fixed_pretrend.csv'); inf = _csv('81_inference.csv'); ho = _csv('82_honestdid_official.csv')
OUT3L = {'green_patent_stock': 'Green patent stock', 'intensity_co2e_per_m_gdp': 'Emission intensity (tCO$_2$e/\\$M)', 'ln_E': 'Log total emissions', 'ln_I': 'Log sector intensity', 'ln_Y': 'Log implied output'}
if ft is not None:
    # ---- Table: treatment definitions and switching
    rows = []
    for y in ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E', 'ln_I', 'ln_Y']:
        d = DEC[y]; cells = []
        for sname, tname in [('All 66 firms', 'Time-varying principal province (baseline)'), ('All 66 firms', 'Fixed: principal province in 2018'), ('All 66 firms', 'Fixed: modal province 2014-2018'),
                             ('Non-switchers (no change of principal province 2004-2023)', 'Fixed: principal province in 2018'), ('No switch from 2017 onward', 'Fixed: principal province in 2018')]:
            m = ft[(ft.outcome == y) & (ft['sample'] == sname) & (ft.treatment == tname)].iloc[0]; cells.append(cs(m.coef, m.se, m.p, d))
        pre = fp[(fp.outcome == y) & (fp.test.str.startswith('leads k=-6'))].p.iloc[0]
        rows.append(f"{OUT3L[y]} & " + ' & '.join(cells) + f" & {pre:.2f} \\\\")
    nfo = {k: int(ft[(ft['sample'] == s) & (ft.treatment == 'Fixed: principal province in 2018') & (ft.outcome == 'ln_E')].iloc[0][c]) for k, (s, c) in
           {'all_firms': ('All 66 firms', 'firms'), 'all_treated': ('All 66 firms', 'treated_firms'), 'ns_firms': ('Non-switchers (no change of principal province 2004-2023)', 'firms'), 'ns_treated': ('Non-switchers (no change of principal province 2004-2023)', 'treated_firms'), 'n17_firms': ('No switch from 2017 onward', 'firms'), 'n17_treated': ('No switch from 2017 onward', 'treated_firms')}.items()}
    tvt = int(ft[(ft['sample'] == 'All 66 firms') & (ft.treatment.str.startswith('Time')) & (ft.outcome == 'ln_E')].iloc[0].treated_firms)
    (TAB / 'tab_fixed.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\small
\caption{Fixed-exposure estimates and switching-robust subsamples}
\label{tab:fixed}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccc c}
\toprule
 & \multicolumn{3}{c}{All 66 firms} & \multicolumn{2}{c}{Fixed 2018 exposure, subsamples} & Pre-trend \\
\cmidrule(lr){2-4}\cmidrule(lr){5-6}
Outcome & \makecell{Time-varying\\(baseline; """ + str(tvt) + r""" treated)} & \makecell{Fixed 2018\\(""" + str(nfo['all_treated']) + r""" treated)} & \makecell{Fixed modal\\2014--18 (""" + str(int(ft[(ft['sample'] == 'All 66 firms') & (ft.treatment.str.startswith('Fixed: modal')) & (ft.outcome == 'ln_E')].iloc[0].treated_firms)) + r""" treated)} & \makecell{Never switch\\(""" + str(nfo['ns_firms']) + r""" firms)} & \makecell{No switch\\from 2017 (""" + str(nfo['n17_firms']) + r""" firms)} & \makecell{joint $p$,\\fixed 2018} \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Alberta $\times$ post-2019 coefficients; firm and year fixed effects; firm-clustered standard errors in parentheses. Treatment: principal province in each year (baseline), in 2018, or modal over 2014--2018; subsamples exclude firms whose principal province changes (ever, or from 2017 on). Last column: joint test that the 2013--2017 leads are zero in the fixed-2018 event study. $^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.
\end{minipage}
\end{table}
"""))
if inf is not None:
    # ---- Table: inference at the level of policy variation
    def irow(lab_prefix, tt, y, name, d):
        m = inf[(inf.label.str.startswith(lab_prefix)) & (inf.label.str.contains(tt)) & (inf.outcome == y)].iloc[0]
        pl = f"{m.placebo_p:.2f} ({int(m.placebo_n)})" if not pd.isna(m.get('placebo_p', np.nan)) else '--'
        return f"{name} & {m.coef:.{d}f} & {m.p_firm:.2f} & {m.p_prov_t:.2f} & {m.p_wild_prov:.2f} & {m.p_cell_t:.2f} & {m.p_wild_cell:.2f} & {pl} \\\\"
    rows = []
    for tt, ttl in [('time-varying', 'A. Time-varying principal province (baseline)'), ('fixed-2018', 'B. Fixed 2018 principal province')]:
        rows.append(f"\\multicolumn{{8}}{{l}}{{\\textit{{{ttl}}}}} \\\\")
        for y in ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E']: rows.append(irow('Main effect', tt, y, '\\quad ' + OUT3L[y], DEC[y]))
        rows.append(irow('Oil-sector', tt, 'ln_E', '\\quad Oil-exposed minus other sectors, log emissions', 3))
        rows.append(irow('Oil-sector', tt, 'green_patent_stock', '\\quad Oil-exposed minus other sectors, green patents', 1))
        rows.append(irow('Prior', tt, 'green_patent_stock', '\\quad Prior innovators minus others, green patents', 1))
        rows.append(irow('Prior', tt, 'ln_E', '\\quad Prior innovators minus others, log emissions', 3))
        rows.append(irow('Late', tt, 'intensity_co2e_per_m_gdp', '\\quad 2022--23 minus 2019--21 window, intensity', 1))
        rows.append('\\addlinespace')
    def _g(tt, col): return int(inf[(inf.label.str.startswith('Main')) & (inf.label.str.contains(tt)) & (inf.outcome == 'green_patent_stock')].iloc[0][col])
    G_prov, G_prov_fx, G_cell = _g('time-varying', 'G_prov'), _g('fixed-2018', 'G_prov'), _g('time-varying', 'G_cell')
    def _pl(tt): return list(json.loads(inf[(inf.label.str.startswith('Main')) & (inf.label.str.contains(tt)) & (inf.outcome == 'green_patent_stock')].iloc[0].placebo_json).keys())
    pl_tv, pl_fx = _pl('time-varying'), _pl('fixed-2018')
    def _provlist(l): return ', '.join(l[:-1]) + ' and ' + l[-1]
    # ---- compact main-text inference table: fixed 2018 exposure, headline outcomes + the two narrative contrasts
    def crow(lab_prefix, y, name, d):
        m = inf[(inf.label.str.startswith(lab_prefix)) & (inf.label.str.contains('fixed-2018')) & (inf.outcome == y)].iloc[0]
        return f"{name} & {m.coef:.{d}f} & {m.p_firm:.2f} & {m.p_wild_cell:.2f} & {m.placebo_p:.2f} ({int(m.placebo_n)}) \\\\"
    crows = [crow('Main effect', y, OUT3L[y], DEC[y]) for y in ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E']]
    crows += ['\\addlinespace', crow('Oil-sector', 'ln_E', 'Oil-exposed minus other sectors, log emissions', 3), crow('Prior', 'green_patent_stock', 'Prior innovators minus others, green patents', 1)]
    (TAB / 'tab_inference_main.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\small
\caption{Inference at the level at which the policy varies: fixed 2018 principal province}
\label{tab:inference_main}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lcccc}
\toprule
Estimate & $\hat\beta$ & Firm-cluster $p$ & Cell wild-bootstrap $p$ & Placebo-province $p$ (no. of placebos) \\
\midrule
""" + '\n'.join(crows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Alberta $\times$ post-2019 with treatment fixed at the 2018 principal province; firm and year fixed effects; CR1 estimator with a $t(G-1)$ reference distribution (Section~\ref{sec:inference}). Cell bootstrap: """ + str(G_cell) + r""" NAICS-3 $\times$ province cells, Webb weights, null imposed. Placebo $p=(k+1)/(N+1)$ over $N$ control provinces, floor $1/(N+1)$. Contrasts are differences between group effects. Full set: Supplementary Table S1.
\end{minipage}
\end{table}
"""))
    (TAB / 'tab_inference.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Inference at the level at which the policy varies: headline estimates and heterogeneity contrasts under alternative clustering, wild cluster bootstraps and placebo provinces, both treatment definitions}
\label{tab:inference}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccccc}
\toprule
 & & \multicolumn{3}{c}{Province level} & \multicolumn{2}{c}{Sector--province cell level} & Placebo-province \\
\cmidrule(lr){3-5}\cmidrule(lr){6-7}
Estimate & $\hat\beta$ & Firm-cluster $p$ & Province-cluster $p$ & Province wild-bootstrap $p$ & Cell-cluster $p$ & Cell wild-bootstrap $p$ & $p$ (no. of placebos) \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Firm and year fixed effects; all $p$-values use the CR1 estimator with a $t(G-1)$ reference distribution (Section~4.5 of the main text), so firm-cluster values differ slightly from Table~2 of the main text. Clusters: 66 firms; """ + str(G_prov) + r""" (time-varying) or """ + str(G_prov_fx) + r""" (fixed 2018) provinces; """ + str(G_cell) + r""" NAICS-3 $\times$ province cells. Wild bootstraps impose the null with Webb weights, 2,999 (province) or 999 (cell) replications. Placebo $p=(k+1)/(N+1)$ over the $N$ placebo provinces in parentheses (""" + _provlist(pl_tv) + r"""; """ + _provlist(pl_fx) + r""" under fixed exposure; contrasts use only provinces with firms of both groups), floor $1/(N+1)$. With Alberta the only treated province, province-level values are not reliable guides to size (MacKinnon and Webb, 2017). Contrast rows report the difference between group effects.
\end{minipage}
\end{table}
"""))
if ho is not None:
    rows = []
    for tt, ttl in [('time-varying', 'A. Time-varying principal province'), ('fixed-2018', 'B. Fixed 2018 principal province')]:
        rows.append(f"\\multicolumn{{6}}{{l}}{{\\textit{{{ttl}}}}} \\\\")
        for y in ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E', 'ln_I', 'ln_Y']:
            h = ho[(ho.treatment == tt) & (ho.outcome == y)]; d = DEC[y]; o = h[h.method == 'original'].iloc[0]; cells = [f"[{o.lb:.{d}f}, {o.ub:.{d}f}]"]
            for M in [0.5, 1.0, 1.5, 2.0]:
                r = h[(h.method != 'original') & (np.isclose(h.Mbar, M))].iloc[0]; cells.append(f"[{r.lb:.{d}f}, {r.ub:.{d}f}]")
            rows.append(f"\\quad {OUT3L[y]} & " + ' & '.join(cells) + ' \\\\')
    (TAB / 'tab_honest.tex').write_text(texminus(r"""\begin{table}[htbp]\centering\footnotesize
\caption{Honest DiD (Rambachan and Roth, 2023): 95\% confidence sets for the average 2019--2023 effect under the relative-magnitudes restriction}
\label{tab:honest}
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{lccccc}
\toprule
Outcome & Parallel trends ($\bar M=0$) & $\bar M=0.5$ & $\bar M=1$ & $\bar M=1.5$ & $\bar M=2$ \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\par\vspace{3pt}\begin{minipage}{\textwidth}\footnotesize
Notes: Conditional--least-favourable hybrid sets (Rambachan and Roth, 2023; \texttt{honestdid}) from the 2013--2017 leads and 2019--2023 lags relative to 2018 with their firm-clustered covariance; the target is the equally weighted average of the five post-period coefficients. $\bar M$ bounds the post-period deviation from parallel trends between consecutive years at $\bar M$ times the largest pre-period deviation; $\bar M=0$ is the conventional interval.
\end{minipage}
\end{table}
"""))
    print('additional tables written:', [p.name for p in TAB.glob('tab_*.tex') if p.name in ('tab_fixed.tex', 'tab_inference.tex', 'tab_inference_main.tex', 'tab_honest.tex')])
