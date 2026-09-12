#!/usr/bin/env python3
"""Honest DiD (Rambachan and Roth 2023) with the reference implementation ('honestdid', conditional/least-favourable hybrid),
relative-magnitudes restriction, for the average 2019-2023 effect; baseline (time-varying) and fixed-2018 treatment; five outcomes.
Output: outputs/tables/82_honestdid_official.csv"""
import numpy as np, pandas as pd, statsmodels.api as sm, warnings
import honestdid as hd
from paths import PANEL, TAB
warnings.filterwarnings('ignore')
T = TAB
raw = pd.read_csv(PANEL)
d = raw[(raw.sample_50kt_baseline == 1) & (raw.multi_province_dummy == 1)].copy()
d['first'] = d.company_id.map(d.groupby('company_id').year.min()); d = d[d['first'] <= 2016].copy(); d['province'] = d.province.fillna('NA')
d['alberta'] = (d.province == 'Alberta').astype(int); d['ln_E'] = np.log(d.total_emissions_co2e); d['ln_Y'] = np.log(d.gdp_real_million_v2); d['ln_I'] = d.ln_E - d.ln_Y
p18 = d[d.year == 2018].set_index('company_id').province; d['ab_fixed'] = (d.company_id.map(p18) == 'Alberta').astype(int)
KS = ['kle7'] + [f'k{k}' for k in range(-6, -1)] + [f'k{k}' for k in range(0, 5)]
def es(w, y, ab):
    w = w.dropna(subset=[y]).copy(); k = w.year - 2019
    w['kle7'] = ((k <= -7) & (w[ab] == 1)).astype(float)
    for j in list(range(-6, -1)) + list(range(0, 5)): w[f'k{j}'] = ((k == j) & (w[ab] == 1)).astype(float)
    X = pd.concat([w[KS].astype(float), pd.get_dummies(w.company_id, prefix='f', drop_first=True, dtype=float), pd.get_dummies(w.year, prefix='y', drop_first=True, dtype=float)], axis=1); X = sm.add_constant(X)
    codes, _ = pd.factorize(w.company_id); r = sm.OLS(w[y].values, X.values).fit(cov_type='cluster', cov_kwds={'groups': codes})
    names = [f'k{k}' for k in range(-6, -1)] + [f'k{k}' for k in range(0, 5)]; ii = [X.columns.tolist().index(n) for n in names]
    return r.params[ii], np.asarray(r.cov_params())[np.ix_(ii, ii)]
rows = []
for ab, tag in [('alberta', 'time-varying'), ('ab_fixed', 'fixed-2018')]:
    for y in ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E', 'ln_I', 'ln_Y']:
        b, S = es(d, y, ab); l = np.repeat(0.2, 5)
        o = hd.constructOriginalCS(betahat=b, sigma=S, numPrePeriods=5, numPostPeriods=5, l_vec=l)
        rows.append(dict(treatment=tag, outcome=y, method='original', Mbar=np.nan, lb=float(o['lb']) if hasattr(o, '__getitem__') else float(o.lb), ub=float(o['ub']) if hasattr(o, '__getitem__') else float(o.ub)))
        rm = hd.createSensitivityResults_relativeMagnitudes(betahat=b, sigma=S, numPrePeriods=5, numPostPeriods=5, Mbarvec=[0.5, 1.0, 1.5, 2.0], l_vec=l, method='C-LF', gridPoints=400)
        rm = pd.DataFrame(rm)
        for _, r in rm.iterrows(): rows.append(dict(treatment=tag, outcome=y, method='relative_magnitudes_C-LF', Mbar=float(r['Mbar']), lb=float(r['lb']), ub=float(r['ub'])))
        print(tag, y, 'orig', rows[-5]['lb'], rows[-5]['ub'], '| RM:', [(round(float(r['Mbar']), 1), round(float(r['lb']), 3), round(float(r['ub']), 3)) for _, r in rm.iterrows()], flush=True)
res = pd.DataFrame(rows); res.to_csv(T / '82_honestdid_official.csv', index=False); print('written')
