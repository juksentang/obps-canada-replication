#!/usr/bin/env python3
"""Treatment defined by the pre-policy (2018) principal province; switching diagnostics; non-switcher subsamples; fixed-treatment event study.
Outputs: outputs/tables/80_fixed_treatment.csv, 80_switching.csv, 80_switching_counts.json, 80_fixed_event_study.csv, 80_fixed_pretrend.csv"""
import numpy as np, pandas as pd, statsmodels.api as sm, warnings, json
from paths import PANEL, TAB
warnings.filterwarnings('ignore')
T = TAB
raw = pd.read_csv(PANEL)
d = raw[(raw.sample_50kt_baseline == 1) & (raw.multi_province_dummy == 1)].copy()
d['first'] = d.company_id.map(d.groupby('company_id').year.min()); d = d[d['first'] <= 2016].copy(); d['province'] = d.province.fillna('NA')
d['alberta'] = (d.province == 'Alberta').astype(int); d['post'] = (d.year >= 2019).astype(int); d['tp'] = d.alberta * d.post
d['ln_E'] = np.log(d.total_emissions_co2e); d['ln_Y'] = np.log(d.gdp_real_million_v2); d['ln_I'] = d.ln_E - d.ln_Y
# fixed exposure: principal province in 2018 (every firm is observed in 2018)
p18 = d[d.year == 2018].set_index('company_id').province; d['prov18'] = d.company_id.map(p18)
d['ab_fixed'] = (d.prov18 == 'Alberta').astype(int); d['tp_fixed'] = d.ab_fixed * d.post
# alternative: modal province over 2014-2018
pm = d[(d.year >= 2014) & (d.year <= 2018)].groupby('company_id').province.agg(lambda s: s.mode().iloc[0]); d['prov_mode'] = d.company_id.map(pm)
d['ab_mode'] = (d.prov_mode == 'Alberta').astype(int); d['tp_mode'] = d.ab_mode * d.post
# switching diagnostics
d = d.sort_values(['company_id', 'year']); d['prev'] = d.groupby('company_id').province.shift()
sw = d[(d.prev.notna()) & (d.prev != d.province)][['company_id', 'year', 'prev', 'province']].copy()
sw['into_alberta'] = (sw.province == 'Alberta').astype(int); sw['out_of_alberta'] = (sw.prev == 'Alberta').astype(int)
sw.to_csv(T / '80_switching.csv', index=False)
switchers = set(sw.company_id); post_switchers = set(sw[sw.year >= 2017].company_id)
def fit(w, y, treat, fe=('company_id', 'year'), cluster='company_id'):
    w = w.dropna(subset=[y] + list(treat)); X = w[list(treat)].astype(float)
    for g in fe: X = pd.concat([X, pd.get_dummies(w[g].astype(str), prefix=g, drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X); codes, _ = pd.factorize(w[cluster])
    r = sm.OLS(w[y].values, X.values).fit(cov_type='cluster', cov_kwds={'groups': codes}); r.cols = X.columns.tolist(); r.n = len(w); r.nf = w.company_id.nunique(); return r
OUT = ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E', 'ln_I', 'ln_Y']; rows = []
samples = {'All 66 firms': d, 'Non-switchers (no change of principal province 2004-2023)': d[~d.company_id.isin(switchers)],
           'No switch from 2017 onward': d[~d.company_id.isin(post_switchers)]}
for y in OUT:
    for sname, w in samples.items():
        for tname, tv in [('Time-varying principal province (baseline)', 'tp'), ('Fixed: principal province in 2018', 'tp_fixed'), ('Fixed: modal province 2014-2018', 'tp_mode')]:
            r = fit(w, y, (tv,)); i = r.cols.index(tv)
            rows.append(dict(outcome=y, sample=sname, treatment=tname, coef=r.params[i], se=r.bse[i], p=r.pvalues[i], ci_lo=r.conf_int()[i][0], ci_hi=r.conf_int()[i][1], N=r.n, firms=r.nf,
                             treated_firms=int(w[w[tv.replace('tp', 'alberta') if tv == 'tp' else tv.replace('tp_', 'ab_')] == 1].company_id.nunique())))
res = pd.DataFrame(rows); res.to_csv(T / '80_fixed_treatment.csv', index=False)
print(res[(res['sample'].str.startswith('All'))].round(3).to_string())
print(res[(res.treatment.str.startswith('Fixed: principal'))].round(3).to_string())
# fixed-treatment event study + pre-trend tests
KS = ['kle7'] + [f'k{k}' for k in range(-6, -1)] + [f'k{k}' for k in range(0, 5)]
w = d.copy(); k = w.year - 2019
w['kle7'] = ((k <= -7) & (w.ab_fixed == 1)).astype(float)
for j in list(range(-6, -1)) + list(range(0, 5)): w[f'k{j}'] = ((k == j) & (w.ab_fixed == 1)).astype(float)
es_rows, pt_rows = [], []
for y in OUT:
    r = fit(w, y, tuple(KS)); idx = {n: r.cols.index(n) for n in KS}
    for n in KS:
        kk = -7 if n == 'kle7' else int(n[1:]); es_rows.append(dict(outcome=y, k=kk, coef=r.params[idx[n]], se=r.bse[idx[n]], p=r.pvalues[idx[n]], ci_lo=r.conf_int()[idx[n]][0], ci_hi=r.conf_int()[idx[n]][1]))
    for names, lab in [([f'k{k}' for k in range(-6, -1)], 'leads k=-6..-2 (2013-2017)'), (['k-3', 'k-2'], 'leads 2016-2017 only'), ([f'k{k}' for k in range(0, 5)], 'post-period lags k=0..4')]:
        R = np.zeros((len(names), len(r.params)))
        for i2, n in enumerate(names): R[i2, idx[n]] = 1
        t = r.wald_test(R, use_f=True, scalar=True); pt_rows.append(dict(outcome=y, test=lab, F=float(t.statistic), p=float(t.pvalue)))
pd.DataFrame(es_rows).to_csv(T / '80_fixed_event_study.csv', index=False); pd.DataFrame(pt_rows).to_csv(T / '80_fixed_pretrend.csv', index=False)
print(pd.DataFrame(pt_rows).round(3).to_string())
counts = dict(switch_events=int(len(sw)), switching_firms=int(len(switchers)), firms_switching_2017_on=int(len(post_switchers)),
              switches_into_alberta=int(sw.into_alberta.sum()), switches_out_of_alberta=int(sw.out_of_alberta.sum()), into_alberta_2017_2019=int(sw[(sw.year.between(2017, 2019)) & (sw.into_alberta == 1)].shape[0]),
              alberta_firms_2018=int((p18 == 'Alberta').sum()), non_alberta_firms_2018=int((p18 != 'Alberta').sum()), switches_by_year=sw.groupby('year').size().to_dict(),
              non_switchers=int(d[~d.company_id.isin(switchers)].company_id.nunique()))
json.dump(counts, open(T / '80_switching_counts.json', 'w'), indent=1, default=int); print(counts)
