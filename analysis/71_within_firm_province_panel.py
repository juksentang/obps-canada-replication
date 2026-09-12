#!/usr/bin/env python3
"""Genuine within-firm comparison: facility emissions aggregated to company x province x year,
firm x year FE (Alberta vs non-Alberta operations of the SAME firm in the SAME year).
Only emissions can be measured at the company-province level (patents are firm-level; output is sector-level).
Input: data/processed/4_panels/facility_year_greenpatent_merged_20251022.csv
Outputs: outputs/tables/71_true_within_firm_results.csv, 71_event_study_{all,large}.csv"""
import numpy as np, pandas as pd, statsmodels.api as sm, warnings
from paths import DATA, TAB
warnings.filterwarnings('ignore')
OUT = TAB
f = pd.read_csv(DATA / 'processed/4_panels/facility_year_greenpatent_merged_20251022.csv', low_memory=False)
c = f.dropna(subset=['province', 'company_legal_name'])
cpy = c.groupby(['company_legal_name', 'province', 'year']).agg(E=('total_emissions_co2e', 'sum'), nfac=('facility_id', 'nunique')).reset_index()
cpy = cpy[cpy.E > 0].copy()
cpy['alberta'] = (cpy.province == 'Alberta').astype(int); cpy['post'] = (cpy.year >= 2019).astype(int); cpy['tp'] = cpy.alberta * cpy.post
cpy['ln_E'] = np.log(cpy.E); cpy['cell'] = cpy.company_legal_name + '|' + cpy.province; cpy['fy'] = cpy.company_legal_name + '|' + cpy.year.astype(str)
ab = set(cpy[cpy.alberta == 1].company_legal_name); nab = set(cpy[cpy.alberta == 0].company_legal_name); both = ab & nab
e18 = cpy[cpy.year == 2018].groupby('company_legal_name').E.sum(); fy0 = cpy.groupby('company_legal_name').year.min()
samples = {'All firms with Alberta and non-Alberta facilities': cpy[cpy.company_legal_name.isin(both)],
           'Large incumbents (>=50 kt in 2018, observed by 2016)': cpy[cpy.company_legal_name.isin(both & set(e18[e18 >= 5e4].index) & set(fy0[fy0 <= 2016].index))]}
def fit(w, y, treat, fe, cluster='company_legal_name'):
    X = w[list(treat)].astype(float)
    for g in fe: X = pd.concat([X, pd.get_dummies(w[g].astype(str), prefix=g, drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X); codes, _ = pd.factorize(w[cluster])
    r = sm.OLS(w[y].values, X.values).fit(cov_type='cluster', cov_kwds={'groups': codes}); r.colnames = X.columns.tolist(); return r
rows = []
for sname, w in samples.items():
    w = w.copy()
    fy_both = w.groupby('fy').alberta.nunique(); wb = w[w.fy.map(fy_both) == 2].copy()
    for spec, data, fe in [('Firm FE + year FE', w, ('company_legal_name', 'year')),
                           ('Firm-province FE + year FE', w, ('cell', 'year')),
                           ('Firm x year FE + firm-province FE (true within-firm-year)', wb, ('fy', 'cell'))]:
        r = fit(data, 'ln_E', ('tp',), fe); i = r.colnames.index('tp')
        rows.append(dict(sample=sname, spec=spec, coef=r.params[i], se=r.bse[i], p=r.pvalues[i], N=len(data), firms=data.company_legal_name.nunique(),
                         cells=data.cell.nunique(), firm_years=data.fy.nunique()))
    k = wb.year - 2019; ks = []
    for j in list(range(-6, -1)) + list(range(0, 5)):
        wb[f'k{j}'] = ((k == j) & (wb.alberta == 1)).astype(float); ks.append(f'k{j}')
    wb['kle7'] = ((k <= -7) & (wb.alberta == 1)).astype(float); ks = ['kle7'] + ks
    r = fit(wb, 'ln_E', tuple(ks), ('fy', 'cell')); idx = {n: r.colnames.index(n) for n in ks}
    pre = [f'k{j}' for j in range(-6, -1)]; R = np.zeros((len(pre), len(r.params)))
    for i2, n in enumerate(pre): R[i2, idx[n]] = 1
    t = r.wald_test(R, use_f=True, scalar=True)
    es = pd.DataFrame([dict(sample=sname, k=n, coef=r.params[idx[n]], se=r.bse[idx[n]], p=r.pvalues[idx[n]]) for n in ks])
    es.to_csv(OUT / f'71_event_study_{"all" if sname.startswith("All") else "large"}.csv', index=False)
    rows.append(dict(sample=sname, spec='Event study (firm x year FE): joint test of leads 2013-2017', coef=float(t.statistic), p=float(t.pvalue), N=len(wb), firms=wb.company_legal_name.nunique()))
    print(sname); print(es.round(3).to_string())
res = pd.DataFrame(rows); res.to_csv(OUT / '71_true_within_firm_results.csv', index=False); print(res.round(4).to_string())
