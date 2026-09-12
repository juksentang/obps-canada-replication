#!/usr/bin/env python3
"""Generate LaTeX macros (analysis/outputs/manuscript_inputs/numbers.tex) from analysis/outputs/manuscript_inputs/numbers.json and the estimation CSVs so that every number in the prose has a source.
Each macro is plain text: \\newcommand{\\nXxx}{0.053}. An index (analysis/outputs/manuscript_inputs/numbers_index.md) lists name -> value -> source."""
import json, re
import pandas as pd, numpy as np
from paths import PANEL, TAB, PAPER
SUB = PAPER; T = TAB
num = json.load(open(SUB / 'numbers.json'))
macros = {}  # name -> (value_string, source)
_DIGIT_WORDS = {'0': 'Zero', '1': 'One', '2': 'Two', '3': 'Three', '4': 'Four', '5': 'Five', '6': 'Six', '7': 'Seven', '8': 'Eight', '9': 'Nine', 'p': 'Point'}
_DIGIT_TOKENS = {'0p5': 'Half', '1p0': 'One', '1p5': 'OneHalf', '2p0': 'Two', '10': 'Ten', '15': 'Fifteen', '17': 'Seventeen', '20': 'Twenty', '80': 'Eighty', '90': 'Ninety',
                 '1617': 'SixteenSeventeen', '20172019': 'SeventeenToNineteen', '2016': 'TwentySixteen', '2017': 'TwentySeventeen', '2018': 'TwentyEighteen',
                 '2019': 'TwentyNineteen', '2020': 'TwentyTwenty', '2021': 'TwentyTwentyOne', '2022': 'TwentyTwentyTwo', '2023': 'TwentyTwentyThree'}
def digit_free(name):
    """LaTeX control words cannot contain digits: spell digit runs out (nWti2019 -> nWtiTwentyNineteen, nHonTvPatM0p5Lb -> nHonTvPatMHalfLb)."""
    return re.sub(r'\d+(?:p\d+)?', lambda m: _DIGIT_TOKENS.get(m.group(0)) or ''.join(_DIGIT_WORDS[ch] for ch in m.group(0)), name)
def add(name, value, source, fmt=None):
    name = digit_free(name)
    if value is None or (isinstance(value, float) and np.isnan(value)): return
    if fmt: s = fmt.format(value)
    elif isinstance(value, (int, np.integer)): s = f'{int(value):,}' if abs(value) >= 10000 else str(int(value))
    elif isinstance(value, float): s = f'{value:.3f}'
    else: s = str(value)
    s = s.replace('-', '$-$') if re.match(r'^-\d', s) else s
    macros[name] = (s, source)
def cap(s): return re.sub(r'[^A-Za-z0-9]', ' ', s).title().replace(' ', '')
OUT = {'green_patent_stock': 'Pat', 'intensity_co2e_per_m_gdp': 'Int', 'ln_E': 'LnE', 'ln_I': 'LnI', 'ln_Y': 'LnY'}
# ---- main estimates (time-varying baseline) from numbers.json
for y, tag in OUT.items():
    m = num.get(y, {})
    for k, fmt in [('coef', '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else ('{:.1f}' if tag == 'Int' else '{:.1f}')), ('se', '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else '{:.1f}'), ('p', '{:.2f}'), ('wcb', '{:.2f}'), ('perm', '{:.2f}'), ('pretrend_p', '{:.2f}'), ('pretrend_1617_p', '{:.2f}'), ('post_joint_p', '{:.3f}')]:
        if k in m: add(f'n{tag}{cap(k)}', m[k], f'numbers.json:{y}.{k}', fmt)
    if 'ci_lo' in m: add(f'n{tag}CiLo', m['ci_lo'], f'numbers.json:{y}.ci_lo', '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else '{:.1f}'); add(f'n{tag}CiHi', m['ci_hi'], f'numbers.json:{y}.ci_hi', '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else '{:.1f}')
    for blk in ['oil', 'naics', 'oil_naics', 'precovid']:
        if blk in m:
            for k, fmt in [('coef', '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else '{:.1f}'), ('se', '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else '{:.1f}'), ('p', '{:.2f}')]: add(f'n{tag}{cap(blk)}{cap(k)}', m[blk][k], f'numbers.json:{y}.{blk}.{k}', fmt)
    if 'segmented' in m:
        for per, v in m['segmented'].items():
            pt = {'2016-17 announcement': 'Ann', '2018 legislation': 'Leg', '2019+ implementation': 'Imp'}[per]
            add(f'n{tag}Seg{pt}Coef', v['coef'], f'numbers.json:{y}.segmented', '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else '{:.1f}'); add(f'n{tag}Seg{pt}P', v['p'], f'numbers.json:{y}.segmented', '{:.3f}')
        add(f'n{tag}SegJointP', m.get('segmented_joint_p'), f'numbers.json:{y}.segmented_joint_p', '{:.3f}')
# derived headline quantities
if 'ln_E' in num:
    add('nLnERuleOutPct', 100 * (1 - np.exp(num['ln_E']['ci_lo'])), 'derived: 100*(1-exp(ci_lo of ln_E))', '{:.0f}')
    add('nLnERuleOutUpPct', 100 * (np.exp(num['ln_E']['ci_hi']) - 1), 'derived: 100*(exp(ci_hi of ln_E)-1)', '{:.0f}')
    add('nLnECoefPct', 100 * (np.exp(num['ln_E']['coef']) - 1), 'derived: 100*(exp(coef of ln_E)-1), plain-language gloss of the log-point estimate', '{:.0f}')
c = num['counts']
for k in ['firms', 'obs', 'obs_with_real_output', 'firm_province_cells', 'alberta_cells', 'firms_with_alberta_obs', 'firms_with_nonalberta_obs', 'firms_with_both', 'firms_alberta_post', 'firms_nonalberta_post', 'naics_count', 'firms_with_prior_patents', 'eite_firms']:
    add(f'nCount{cap(k)}', c[k], f'numbers.json:counts.{k}')
for k in ['pre_mean_patents_alberta', 'pre_mean_intensity_alberta', 'pre_mean_patents_all', 'pre_mean_intensity_all']: add(f'nCount{cap(k)}', c[k], f'numbers.json:counts.{k}', '{:.1f}' if 'patents' in k else '{:,.0f}')
add('nIntPctOfAlbertaPre', 100 * abs(num['intensity_co2e_per_m_gdp']['coef']) / c['pre_mean_intensity_alberta'], 'derived', '{:.0f}')
add('nPatPctOfAlbertaPre', 100 * num['green_patent_stock']['coef'] / c['pre_mean_patents_alberta'], 'derived', '{:.0f}')
sn = c.get('same_naics_share') or {}
for k in ['firms_with_2plus_provinces', 'same_naics']: add(f'nSameNaics{cap(k)}', sn.get(k), 'numbers.json:counts.same_naics_share')
if sn: add('nSameNaicsPct', 100 * sn['share'], 'numbers.json:counts.same_naics_share', '{:.0f}')
# heterogeneity
for key, v in num.get('hetero', {}).items():
    y, dm = key.split('|'); tag = OUT[y]; dt = {'Prior green patents in 2018 (vs. none)': 'Prior', 'EITE sector (vs. non-EITE)': 'Eite', 'Above-median 2018 emissions (vs. below)': 'Size'}[dm]
    f3 = '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else '{:.1f}'
    for k, fmt in [('high', f3), ('low', f3), ('diff', f3), ('high_p', '{:.3f}'), ('low_p', '{:.3f}'), ('diff_p', '{:.3f}')]: add(f'nHet{dt}{tag}{cap(k)}', v[k], f'numbers.json:hetero.{key}.{k}', fmt)
    add(f'nHet{dt}NHigh', v['n_high'], 'numbers.json:hetero'); add(f'nHet{dt}NLow', v['n_low'], 'numbers.json:hetero')
# oil cycle
for r in num.get('oil_cycle', []):
    tag = OUT[r['outcome']]; f3 = '{:.3f}' if tag in ('LnE', 'LnI', 'LnY') else ('{:.0f}' if tag == 'Int' else '{:.1f}')
    bt = {'period': 'Per', 'sector': 'Sec', 'interaction': 'Ixn'}[r['block']]
    for side in ['a', 'b']:
        add(f'nOil{bt}{tag}{side.upper()}Coef', r[side + '_coef'], f'oil_cycle.{r["block"]}.{r["outcome"]}', f3); add(f'nOil{bt}{tag}{side.upper()}Se', r[side + '_se'], 'oil_cycle', f3); add(f'nOil{bt}{tag}{side.upper()}P', r[side + '_p'], 'oil_cycle', '{:.3f}')
    if not (isinstance(r.get('diff_p'), float) and np.isnan(r['diff_p'])): add(f'nOil{bt}{tag}DiffP', r['diff_p'], 'oil_cycle', '{:.3f}')
    if r['block'] == 'interaction': add(f'nOilIxn{tag}CCoef', r['c_coef'], 'oil_cycle', f3); add(f'nOilIxn{tag}CSe', r['c_se'], 'oil_cycle', f3); add(f'nOilIxn{tag}CP', r['c_p'], 'oil_cycle', '{:.3f}')
for yr, v in num.get('wti_by_year', {}).items(): add(f'nWti{yr}', v, 'numbers.json:wti_by_year', '{:.0f}')
# within-firm (facility) check
for r in num.get('within_firm', []):
    if r['spec'].startswith('Firm x year'):
        tag = 'Large' if r['sample'].startswith('Large') else 'All'
        add(f'nWithin{tag}Coef', r['coef'], '71_true_within_firm_results', '{:.3f}'); add(f'nWithin{tag}Se', r['se'], '71', '{:.3f}'); add(f'nWithin{tag}P', r['p'], '71', '{:.2f}'); add(f'nWithin{tag}N', r['N'], '71'); add(f'nWithin{tag}Firms', r['firms'], '71')
# permutation (cell-level)
for r in num.get('permutation', []):
    tag = OUT.get(r['outcome'], 'LnPat' if r['outcome'] == 'ln_pat' else cap(r['outcome'])); add(f'nPerm{tag}P', r['perm_p'], '70_permutation.csv', '{:.2f}'); add('nPermB', r['B'], '70_permutation.csv'); add('nPermCells', r['n_cells'], '70_permutation.csv'); add('nPermAlbertaCells', r['n_alberta_cells'], '70_permutation.csv')
lp = num.get('log_patent_permutation', {}).get('ln_pat')
if lp: add('nLnPatCoef', lp['coef'], 'log_patent_permutation', '{:.3f}'); add('nLnPatClusterP', lp['cluster_p'], 'log_patent_permutation', '{:.2f}')
# power (60_power_analysis via numbers.json:power); MDE = SE * (z_{0.975} + z_{power})
from scipy.stats import norm
add('nMdeMult80', norm.ppf(0.975) + norm.ppf(0.80), 'derived: z_{0.975}+z_{0.80}', '{:.2f}'); add('nMdeMult90', norm.ppf(0.975) + norm.ppf(0.90), 'derived: z_{0.975}+z_{0.90}', '{:.2f}')
PW = {'ln_E': 'LnE', 'ln_I': 'LnI', 'ln_Y': 'LnY', 'green_patents': 'Pat'}
for r in num.get('power', []):
    tag = PW.get(str(r.get('Outcome', r.get('outcome', ''))))
    if tag is None: continue
    fl = '{:.3f}' if tag.startswith('Ln') else '{:.1f}'
    add(f'nMde80{tag}', r['MDE_80_Power'], '60_power_analysis:MDE_80_Power', fl); add(f'nMde90{tag}', r['MDE_90_Power'], '60_power_analysis:MDE_90_Power', fl)
    if tag.startswith('Ln'):
        add(f'nMde80{tag}PctDown', 100 * (1 - np.exp(-r['MDE_80_Power'])), 'derived: 100*(1-exp(-MDE80))', '{:.0f}'); add(f'nMde80{tag}PctUp', 100 * (np.exp(r['MDE_80_Power']) - 1), 'derived: 100*(exp(MDE80)-1)', '{:.0f}')
# the patent MDE is derived from the published series of Table 2 (same specification as the log outcomes above), not from the power script's own re-estimate
if 'green_patent_stock' in num:
    _se = num['green_patent_stock']['se']; _m80 = _se * (norm.ppf(0.975) + norm.ppf(0.80)); _m90 = _se * (norm.ppf(0.975) + norm.ppf(0.90))
    add('nMde80Pat', _m80, 'derived: published patent SE (numbers.json:green_patent_stock.se) x (z_{0.975}+z_{0.80})', '{:.1f}'); add('nMde90Pat', _m90, 'derived: published patent SE x (z_{0.975}+z_{0.90})', '{:.1f}')
    add('nMde80PatPctOfAlbertaPre', 100 * _m80 / c['pre_mean_patents_alberta'], 'derived: 100*MDE80/pre_mean_patents_alberta', '{:.0f}')
# windows / char controls (selected)
for r in num.get('windows', []):
    tag = OUT[r['outcome']]; f3 = '{:.3f}' if tag.startswith('Ln') else '{:.1f}'; wt = {'Exclude 2023 (patent truncation)': 'Ex2023', 'Pre-COVID: 2004-2019': 'PreCovid', 'Exclude 2020-2021 (pandemic years)': 'ExPandemic', 'Balanced-ish: firms observed 2016-2023': 'Balanced', 'Full 2004-2023': 'Full'}[r['window']]
    add(f'nWin{wt}{tag}Coef', r['coef'], 'windows', f3); add(f'nWin{wt}{tag}Se', r['se'], 'windows', f3); add(f'nWin{wt}{tag}P', r['p'], 'windows', '{:.3f}')
for r in num.get('depreciation', []):
    if r['outcome'] in ('stock_d', 'ln_stock_d'):
        tag = ('Dep' if r['outcome'] == 'stock_d' else 'LnDep') + str(int(round(r['delta'] * 100))); add(f'n{tag}Coef', r['coef'], 'depreciation', '{:.1f}' if r['outcome'] == 'stock_d' else '{:.3f}'); add(f'n{tag}P', r['p'], 'depreciation', '{:.2f}')
# fixed treatment / switching / inference / Honest DiD (optional: only if the CSVs exist)
def csv(name): p = T / name; return pd.read_csv(p) if p.exists() else None
ft = csv('80_fixed_treatment.csv')
if ft is not None:
    for _, r in ft.iterrows():
        tag = OUT[r.outcome]; f3 = '{:.3f}' if tag.startswith('Ln') else '{:.1f}'
        st = {'All 66 firms': 'All', 'Non-switchers (no change of principal province 2004-2023)': 'NonSw', 'No switch from 2017 onward': 'NoSw17'}[r['sample']]
        tt = {'Time-varying principal province (baseline)': 'Tv', 'Fixed: principal province in 2018': 'Fx', 'Fixed: modal province 2014-2018': 'Md'}[r.treatment]
        add(f'nFt{tt}{st}{tag}Coef', r.coef, '80_fixed_treatment', f3); add(f'nFt{tt}{st}{tag}Se', r.se, '80', f3); add(f'nFt{tt}{st}{tag}P', r.p, '80', '{:.2f}'); add(f'nFt{tt}{st}{tag}CiLo', r.ci_lo, '80', f3); add(f'nFt{tt}{st}{tag}CiHi', r.ci_hi, '80', f3)
        add(f'nFt{tt}{st}Firms', r.firms, '80'); add(f'nFt{tt}{st}Treated', r.treated_firms, '80'); add(f'nFt{tt}{st}N', r.N, '80')
    sc = json.load(open(T / '80_switching_counts.json'))
    for k in ['switch_events', 'switching_firms', 'firms_switching_2017_on', 'switches_into_alberta', 'switches_out_of_alberta', 'into_alberta_2017_2019', 'alberta_firms_2018', 'non_alberta_firms_2018', 'non_switchers']: add(f'nSw{cap(k)}', sc[k], '80_switching_counts')
    fp = csv('80_fixed_pretrend.csv')
    for _, r in fp.iterrows():
        tag = OUT[r.outcome]; tt = {'leads k=-6..-2 (2013-2017)': 'Leads', 'leads 2016-2017 only': 'Leads1617', 'post-period lags k=0..4': 'Lags'}[r.test]; add(f'nFtFx{tag}{tt}P', r.p, '80_fixed_pretrend', '{:.2f}')
# fixed-2018 event-study coefficients (80_fixed_event_study.csv): individual leads and lags, and the mean of the five post-period coefficients
fes = csv('80_fixed_event_study.csv')
if fes is not None:
    for _, r in fes.iterrows():
        tag = OUT[r.outcome]; f3 = '{:.3f}' if tag.startswith('Ln') else '{:.1f}'; kk = int(r.k); nm = f'Lead{-kk}' if kk < 0 else f'Lag{kk}'
        add(f'nFes{tag}{nm}Coef', r.coef, '80_fixed_event_study', f3); add(f'nFes{tag}{nm}Se', r.se, '80_fixed_event_study', f3); add(f'nFes{tag}{nm}P', r.p, '80_fixed_event_study', '{:.3f}')
    for y, tag in OUT.items():
        m = fes[(fes.outcome == y) & (fes.k >= 0)]; f3 = '{:.3f}' if tag.startswith('Ln') else '{:.1f}'
        add(f'nFes{tag}PostMean', m.coef.mean(), 'derived: mean of the fixed-2018 event-study coefficients k=0..4', f3)
        lp = fes[(fes.outcome == y) & (fes.k >= -6) & (fes.k <= -2)]; add(f'nFes{tag}LeadsMaxP', lp.p.max(), 'derived: largest p among the 2013-2017 leads (fixed 2018)', '{:.3f}'); add(f'nFes{tag}LeadsMinP', lp.p.min(), 'derived: smallest p among the 2013-2017 leads (fixed 2018)', '{:.3f}')
# observed 2023 green-patent flow of the analysis sample (censored by publication lags) and the flow implied by 35-50% publication completeness
_raw = pd.read_csv(PANEL)
_d = _raw[(_raw.sample_50kt_baseline == 1) & (_raw.multi_province_dummy == 1)].copy(); _d['first'] = _d.company_id.map(_d.groupby('company_id').year.min()); _d = _d[_d['first'] <= 2016]
assert _d.company_id.nunique() == c['firms'], 'analysis-sample filter does not reproduce the firm count'
_f23 = float(_d[_d.year == 2023].green_patent_count.sum()); _u23 = int(_d[_d.year == 2023].unique_patents.sum()); _f22 = float(_d[_d.year == 2022].green_patent_count.sum())
add('nPatFlow2023', _f23, 'analysis_ready_with_oil_controls: sum of green_patent_count (fractional flow) over the 66 sample firms, 2023', '{:.0f}'); add('nPatFlow2023Unique', _u23, 'analysis_ready_with_oil_controls: sum of unique_patents, 2023')
add('nPatFlow2022', _f22, 'analysis_ready_with_oil_controls: sum of green_patent_count over the 66 sample firms, 2022', '{:.0f}')
add('nPatFlow2023AtHalf', _f23 / 0.5, 'derived: 2023 flow / 0.50 completeness', '{:.0f}'); add('nPatFlow2023AtThirtyFive', _f23 / 0.35, 'derived: 2023 flow / 0.35 completeness', '{:.0f}')
inf = csv('81_inference.csv')
if inf is not None:
    for _, r in inf.iterrows():
        tag = OUT[r.outcome]; f3 = '{:.3f}' if tag.startswith('Ln') else '{:.1f}'
        lab = r.label; tt = 'Tv' if 'time-varying' in lab else 'Fx'
        kind = 'Main' if lab.startswith('Main') else ('OilDiff' if lab.startswith('Oil') else ('PriorDiff' if lab.startswith('Prior') else 'LateDiff'))
        base = f'nInf{kind}{tt}{tag}'
        add(base + 'Coef', r.coef, '81_inference', f3); add(base + 'PFirm', r.p_firm, '81', '{:.2f}'); add(base + 'PProv', r.p_prov_t, '81', '{:.2f}'); add(base + 'PWildProv', r.p_wild_prov, '81', '{:.2f}'); add(base + 'PCell', r.p_cell_t, '81', '{:.2f}'); add(base + 'PWildCell', r.p_wild_cell, '81', '{:.2f}')
        add(base + 'GProv', r.G_prov, '81'); add(base + 'GCell', r.G_cell, '81')
        if not pd.isna(r.get('placebo_p', np.nan)): add(base + 'PlaceboP', r.placebo_p, '81', '{:.2f}'); add(base + 'PlaceboN', r.placebo_n, '81'); add(base + 'PlaceboMin', r.placebo_min, '81', f3); add(base + 'PlaceboMax', r.placebo_max, '81', f3)
ho = csv('82_honestdid_official.csv')
if ho is not None:
    for _, r in ho.iterrows():
        tag = OUT[r.outcome]; tt = 'Tv' if r.treatment == 'time-varying' else 'Fx'; f3 = '{:.3f}' if tag.startswith('Ln') else '{:.1f}'
        mb = 'Orig' if r.method == 'original' else 'M' + str(r.Mbar).replace('.', 'p')
        add(f'nHon{tt}{tag}{mb}Lb', r.lb, '82_honestdid_official', f3); add(f'nHon{tt}{tag}{mb}Ub', r.ub, '82_honestdid_official', f3)
# sample construction / representativeness (numbers.json:selection = source of tables/tab_sample.tex)
SELG = {'Single-province firms': 'Single', 'All multi-province firms (101)': 'Multi', 'Analysis sample: incumbents observed by 2016 (66)': 'Analysis', 'Excluded post-2016 entrants (35)': 'Entrants'}
for r in num.get('selection', []):
    g = SELG.get(r['group'])
    if g is None: continue
    src = f'numbers.json:selection[{r["group"]}]'
    add(f'nSel{g}Firms', int(r['firms_2018']), src); add(f'nSel{g}FirmYears', int(r['firm_years']), src)
    add(f'nSel{g}MeanEmissionsKt', r['mean_emissions_kt'], src, '{:,.0f}'); add(f'nSel{g}MedianEmissionsKt', r['median_emissions_kt'], src, '{:,.0f}')
    add(f'nSel{g}ShareEmissionsPct', 100 * r['share_ghgrp_emissions_2018'], src, '{:.1f}'); add(f'nSel{g}MeanFacilities', r['mean_facilities'], src, '{:.1f}')
    add(f'nSel{g}MeanPatentStock', r['mean_patent_stock'], src, '{:.1f}'); add(f'nSel{g}ShareWithPatentsPct', 100 * r['share_with_patents'], src, '{:.0f}')
    add(f'nSel{g}ShareEitePct', 100 * r['share_eite'], src, '{:.0f}'); add(f'nSel{g}ShareAlbertaPct', 100 * r['share_alberta'], src, '{:.0f}')
    if g == 'Analysis':  # names used in the prose
        add('nShareEmissionsSample', 100 * r['share_ghgrp_emissions_2018'], src + ' (share of all 2018 GHGRP emissions, analysis sample)', '{:.1f}')
        add('nShareAlbertaPrincipalPre', 100 * r['share_alberta'], src + ' (share with Alberta as principal province, 2018)', '{:.0f}')
# published external constants (not estimated here): numbers_external.json lists name, value, source citation and format
ext = SUB / 'numbers_external.json'
if ext.exists():
    for name, e in json.load(open(ext)).items(): add(name, e['value'], 'external: ' + e['source'], e.get('fmt'))
bad_names = [n for n in macros if not re.fullmatch(r'[A-Za-z]+', n)]
assert not bad_names, f'macro names must be letters only (LaTeX control words): {bad_names}'
# ---- write
lines = ['% AUTO-GENERATED by analysis/78_numbers_tex.py -- do not edit. Source: numbers.json and the estimation CSVs.']
for name, (val, src) in sorted(macros.items()): lines.append(f'\\newcommand{{\\{name}}}{{{val}}}  % {src}')
(SUB / 'numbers.tex').write_text('\n'.join(lines) + '\n')
idx = ['# Number macros (name → value → source)', '', '| macro | value | source |', '|---|---|---|'] + [f'| `\\{n}` | {v} | {s} |' for n, (v, s) in sorted(macros.items())]
(SUB / 'numbers_index.md').write_text('\n'.join(idx) + '\n'); print(len(macros), 'macros written')
