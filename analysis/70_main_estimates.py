#!/usr/bin/env python3
"""Main difference-in-differences estimates and supporting analyses.
All estimates use the 66-firm analysis sample (multi-province firms observed by 2016 with >= 50 kt baseline emissions),
firm and year fixed effects, standard errors clustered by firm.
Sections: A baseline; B event study and joint lead/lag tests; D firm-characteristic x year controls; E oil-price controls;
F patent-stock depreciation sensitivity; G sample windows; H policy-stage specification; I mechanism heterogeneity;
J representativeness table; K sample counts.
Outputs: outputs/tables/70_*.csv and 70_sample_counts.json"""
import json, warnings
import numpy as np, pandas as pd, statsmodels.api as sm
from paths import PANEL, TAB
warnings.filterwarnings('ignore')
OUT = TAB

# ----------------------------------------------------------------------------- data
raw = pd.read_csv(PANEL)
def robust_sample(df):
    d = df[(df.sample_50kt_baseline == 1) & (df.multi_province_dummy == 1)].copy()
    d['first_year'] = d.company_id.map(d.groupby('company_id').year.min())
    return d[d.first_year <= 2016].copy()

d = robust_sample(raw)
d['post'] = (d.year >= 2019).astype(int)
d['alberta'] = (d.province == 'Alberta').astype(int)
d['tp'] = d.post * d.alberta
d['ln_E'] = np.log(d.total_emissions_co2e)
d['ln_Y'] = np.log(d.gdp_real_million_v2)
d['ln_I'] = d.ln_E - d.ln_Y
d['naics'] = d.naics_code_3digit.astype(str)
d['naics_year'] = d.naics + '_' + d.year.astype(str)
d['t'] = d.year - 2004
# firm-level 2018 characteristics
c18 = d[d.year == 2018].groupby('company_id').agg(size18=('total_emissions_co2e', 'sum'),
                                                   pat18=('green_patent_stock', 'max'),
                                                   nfac18=('num_facilities', 'max'),
                                                   int18=('intensity_co2e_per_m_gdp', 'mean'))
d['ln_size18'] = np.log(d.company_id.map(c18.size18))
d['ln_pat18'] = np.log1p(d.company_id.map(c18.pat18))
d['nfac18'] = d.company_id.map(c18.nfac18)
d['int18'] = d.company_id.map(c18.int18)
d['ln_wti_x_ab'] = d.ln_wti_price * d.alberta
d['ln_wti_lag_x_ab'] = d.ln_wti_price_lag1 * d.alberta
EITE = {'211', '212', '311', '321', '322', '324', '325', '327', '331', '332'}
d['eite'] = d.naics.isin(EITE).astype(int)

OUTCOMES = ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E', 'ln_I', 'ln_Y']
LABELS = {'green_patent_stock': 'Green patent stock', 'intensity_co2e_per_m_gdp': 'Emission intensity (tCO2e/$M)',
          'ln_E': 'ln E (emissions)', 'ln_I': 'ln I (sector intensity)', 'ln_Y': 'ln Y (implied output)'}

# ----------------------------------------------------------------------------- estimator
def fit(dsub, y, treat=('tp',), controls=(), fe=('company_id', 'year'), extra_fe=(), char_x_year=(), cluster='company_id'):
    need = list(treat) + list(controls) + [y, cluster] + list(fe) + list(extra_fe) + list(char_x_year)
    w = dsub.dropna(subset=list(dict.fromkeys(need))).copy()
    X = w[list(treat) + list(controls)].astype(float)
    for f in list(fe) + list(extra_fe):
        X = pd.concat([X, pd.get_dummies(w[f].astype(str), prefix=f, drop_first=True, dtype=float)], axis=1)
    if char_x_year:
        yd = pd.get_dummies(w['year'].astype(str), prefix='yr', drop_first=True, dtype=float)
        for ch in char_x_year:
            X = pd.concat([X, yd.mul(w[ch].astype(float).values, axis=0).add_prefix(ch + '_x_')], axis=1)
    X = sm.add_constant(X)
    codes, _ = pd.factorize(w[cluster])
    res = sm.OLS(w[y].astype(float).values, X.values).fit(cov_type='cluster', cov_kwds={'groups': codes})
    res.colnames = X.columns.tolist(); res.nobs_ = len(w); res.nfirms = w[cluster].nunique(); res.data_ = w
    return res

def row(res, name='tp', **kw):
    i = res.colnames.index(name)
    ci = res.conf_int()[i]
    return dict(coef=res.params[i], se=res.bse[i], p=res.pvalues[i], ci_lo=ci[0], ci_hi=ci[1], N=res.nobs_, firms=res.nfirms, **kw)

def sig(p): return '***' if p < .01 else '**' if p < .05 else '*' if p < .10 else ''

# ----------------------------------------------------------------------------- A. baseline
base = []
for y in OUTCOMES:
    r = fit(d, y); base.append(row(r, outcome=y))
base = pd.DataFrame(base); base['sig'] = base.p.map(sig)
base.to_csv(OUT / '70_baseline.csv', index=False); print('\n[A] Baseline\n', base.round(4).to_string())

# ----------------------------------------------------------------------------- B. event study + pre-trend tests
KS = ['kle7'] + [f'k{k}' for k in range(-6, -1)] + [f'k{k}' for k in range(0, 5)]
def add_es(dsub):
    w = dsub.copy(); k = w.year - 2019
    w['kle7'] = ((k <= -7) & (w.alberta == 1)).astype(float)
    for j in list(range(-6, -1)) + list(range(0, 5)):
        w[f'k{j}'] = ((k == j) & (w.alberta == 1)).astype(float)
    return w
es_rows, pt_rows = [], []
for y in OUTCOMES:
    w = add_es(d); r = fit(w, y, treat=tuple(KS))
    idx = {n: r.colnames.index(n) for n in KS}
    for n in KS:
        kk = -7 if n == 'kle7' else int(n[1:])
        es_rows.append(dict(outcome=y, k=kk, year=2019 + kk if n != 'kle7' else '<=2012', coef=r.params[idx[n]], se=r.bse[idx[n]],
                            p=r.pvalues[idx[n]], ci_lo=r.conf_int()[idx[n]][0], ci_hi=r.conf_int()[idx[n]][1]))
    def wald(names, label):
        R = np.zeros((len(names), len(r.params)))
        for i, n in enumerate(names): R[i, idx[n]] = 1
        t = r.wald_test(R, use_f=True, scalar=True)
        pt_rows.append(dict(outcome=y, test=label, n_restr=len(names), F=float(t.statistic), p=float(t.pvalue)))
    wald(['kle7'] + [f'k{k}' for k in range(-6, -1)], 'all pre-period leads (k<=-7 bin, -6..-2)')
    wald([f'k{k}' for k in range(-6, -1)], 'leads k=-6..-2 (2013-2017)')
    wald(['k-3', 'k-2'], 'leads 2016-2017 only')
    wald([f'k{k}' for k in range(0, 5)], 'post-period lags k=0..4')
es = pd.DataFrame(es_rows); es.to_csv(OUT / '70_event_study.csv', index=False)
pt = pd.DataFrame(pt_rows); pt.to_csv(OUT / '70_pretrend_tests.csv', index=False)
print('\n[B] Pre-trend / post joint tests\n', pt.round(3).to_string())

# ----------------------------------------------------------------------------- D. firm-characteristic controls
specs = [('Baseline (firm + year FE)', {}),
         ('+ 2018 size (ln emissions) x year FE', dict(char_x_year=('ln_size18',))),
         ('+ 2018 patent stock (ln) x year FE', dict(char_x_year=('ln_pat18',))),
         ('+ 2018 facility count x year FE', dict(char_x_year=('nfac18',))),
         ('+ 2018 sector intensity x year FE', dict(char_x_year=('int18',))),
         ('+ NAICS-3 x year FE', dict(extra_fe=('naics_year',))),
         ('+ province linear trends', dict(extra_fe=(), controls=())),  # handled below
         ('+ all firm characteristics x year FE + NAICS x year FE', dict(char_x_year=('ln_size18', 'ln_pat18', 'nfac18'), extra_fe=('naics_year',)))]
prov_tr = pd.get_dummies(d.province, prefix='ptr', drop_first=True, dtype=float).mul(d.t, axis=0)
dtr = pd.concat([d, prov_tr], axis=1)
rows = []
for y in OUTCOMES:
    for name, kw in specs:
        if name.startswith('+ province'):
            r = fit(dtr, y, controls=tuple(prov_tr.columns))
        else:
            r = fit(d, y, **kw)
        rows.append(row(r, outcome=y, spec=name))
cc = pd.DataFrame(rows); cc['sig'] = cc.p.map(sig); cc.to_csv(OUT / '70_char_controls.csv', index=False)
print('\n[D] Firm-characteristic controls\n', cc[['outcome', 'spec', 'coef', 'se', 'p', 'N']].round(3).to_string())

# ----------------------------------------------------------------------------- E. oil-price controls
oil = [('Baseline', ()), ('+ ln WTI', ('ln_wti_price',)), ('+ Alberta x ln WTI', ('ln_wti_x_ab',)),
       ('+ Alberta x ln WTI + Alberta x ln WTI(t-1)', ('ln_wti_x_ab', 'ln_wti_lag_x_ab')),
       ('+ Alberta x ln WTI + NAICS x year FE', ('ln_wti_x_ab',))]
rows = []
for y in OUTCOMES:
    for name, ctr in oil:
        kw = dict(controls=ctr)
        if 'NAICS' in name: kw['extra_fe'] = ('naics_year',)
        rows.append(row(fit(d, y, **kw), outcome=y, spec=name))
oc = pd.DataFrame(rows); oc['sig'] = oc.p.map(sig); oc.to_csv(OUT / '70_oil_controls.csv', index=False)
print('\n[E] Oil-price controls\n', oc[['outcome', 'spec', 'coef', 'se', 'p', 'N']].round(3).to_string())

# ----------------------------------------------------------------------------- F. depreciation-rate sensitivity
def pim_stock(df, delta):
    """Perpetual-inventory patent stock S_t = (1 - delta) S_{t-1} + F_t from annual green patent flows, at the firm level."""
    flows = df.groupby(['company_id', 'year']).green_patent_count.sum().reset_index().sort_values(['company_id', 'year'])
    out = {}
    for cid, g in flows.groupby('company_id'):
        st, prev = 0.0, None
        for yr, fl in zip(g.year, g.green_patent_count.fillna(0)):
            if prev is not None and yr - prev > 1: st *= (1 - delta) ** (yr - prev - 1)
            st = st * (1 - delta) + fl; out[(cid, yr)] = st; prev = yr
    return pd.Series([out[(c, y)] for c, y in zip(df.company_id, df.year)], index=df.index)
rows = []
for delta in (0.10, 0.15, 0.20):
    dd = d.copy(); dd['stock_d'] = pim_stock(dd, delta); dd['ln_stock_d'] = np.log1p(dd.stock_d)
    for y in ('stock_d', 'ln_stock_d'):
        rows.append(row(fit(dd, y), outcome=y, delta=delta, pre_mean=dd[(dd.alberta == 1) & (dd.post == 0)][y].mean()))
rows.append(row(fit(d, 'green_patent_stock'), outcome='green_patent_stock (published series)', delta=0.15,
                pre_mean=d[(d.alberta == 1) & (d.post == 0)].green_patent_stock.mean()))
dep = pd.DataFrame(rows); dep['sig'] = dep.p.map(sig); dep.to_csv(OUT / '70_depreciation.csv', index=False)
print('\n[F] Depreciation sensitivity\n', dep.round(3).to_string())

# ----------------------------------------------------------------------------- G. sample windows
wins = [('Full 2004-2023', d), ('Exclude 2023 (patent truncation)', d[d.year <= 2022]),
        ('Pre-COVID: 2004-2019', d[d.year <= 2019]), ('Exclude 2020-2021 (pandemic years)', d[~d.year.isin([2020, 2021])]),
        ('Balanced-ish: firms observed 2016-2023', d[d.company_id.isin(d[d.year == 2023].company_id.unique())])]
rows = [row(fit(dd, y), outcome=y, window=name) for y in OUTCOMES for name, dd in wins]
sw = pd.DataFrame(rows); sw['sig'] = sw.p.map(sig); sw.to_csv(OUT / '70_sample_windows.csv', index=False)
print('\n[G] Sample windows\n', sw[['outcome', 'window', 'coef', 'se', 'p', 'N', 'firms']].round(3).to_string())

# ----------------------------------------------------------------------------- H. policy-stage specification
ds = d.copy()
ds['ab_1617'] = ((ds.year.isin([2016, 2017])) & (ds.alberta == 1)).astype(float)
ds['ab_18'] = ((ds.year == 2018) & (ds.alberta == 1)).astype(float)
ds['ab_19p'] = ((ds.year >= 2019) & (ds.alberta == 1)).astype(float)
rows = []
for y in OUTCOMES:
    r = fit(ds, y, treat=('ab_1617', 'ab_18', 'ab_19p'))
    for n, lab in [('ab_1617', '2016-17 announcement'), ('ab_18', '2018 legislation'), ('ab_19p', '2019+ implementation')]:
        rows.append(row(r, n, outcome=y, period=lab))
    R = np.zeros((3, len(r.params)))
    for i, n in enumerate(['ab_1617', 'ab_18', 'ab_19p']): R[i, r.colnames.index(n)] = 1
    t = r.wald_test(R, use_f=True, scalar=True)
    rows.append(dict(outcome=y, period='joint F (all three = 0)', coef=float(t.statistic), p=float(t.pvalue), N=r.nobs_, firms=r.nfirms))
seg = pd.DataFrame(rows); seg['sig'] = seg.p.map(sig); seg.to_csv(OUT / '70_segmented.csv', index=False)
print('\n[H] Segmented\n', seg[['outcome', 'period', 'coef', 'se', 'p', 'N']].round(3).to_string())

# ----------------------------------------------------------------------------- I. mechanism-consistent heterogeneity
het_dims = {'eite': 'EITE sector (vs. non-EITE)',
            'large18': 'Above-median 2018 emissions (vs. below)',
            'prior_innov': 'Prior green patents in 2018 (vs. none)'}
d['large18'] = (d.ln_size18 > d.drop_duplicates('company_id').ln_size18.median()).astype(int)
d['prior_innov'] = (d.company_id.map(c18.pat18) > 0).astype(int)
rows = []
for y in OUTCOMES:
    for h, lab in het_dims.items():
        dd = d.copy(); dd['tp_h'] = dd.tp * dd[h]; dd['tp_l'] = dd.tp * (1 - dd[h]); dd['h_post'] = dd[h] * dd.post
        r = fit(dd, y, treat=('tp_l', 'tp_h'), controls=('h_post',))   # group x post control: the control group of each type has its own post-2019 shift
        lo, hi = row(r, 'tp_l'), row(r, 'tp_h')
        R = np.zeros((1, len(r.params))); R[0, r.colnames.index('tp_h')] = 1; R[0, r.colnames.index('tp_l')] = -1
        t = r.wald_test(R, use_f=True, scalar=True)
        n_hi = dd[dd[h] == 1].company_id.nunique()
        rows.append(dict(outcome=y, dimension=lab, n_firms_high=n_hi, n_firms_low=r.nfirms - n_hi,
                         low_coef=lo['coef'], low_se=lo['se'], low_p=lo['p'], high_coef=hi['coef'], high_se=hi['se'], high_p=hi['p'],
                         diff=hi['coef'] - lo['coef'], diff_p=float(t.pvalue), N=r.nobs_))
het = pd.DataFrame(rows); het.to_csv(OUT / '70_mechanism_hetero.csv', index=False)
print('\n[I] Mechanism heterogeneity\n', het.round(3).to_string())

# ----------------------------------------------------------------------------- J. selection / representativeness table
b = raw[raw.sample_50kt_baseline == 1].copy()
b['first_year'] = b.company_id.map(b.groupby('company_id').year.min())
b['naics'] = b.naics_code_3digit.astype(str); b['eite'] = b.naics.isin(EITE).astype(int)
groups = {'Single-province firms': b[b.multi_province_dummy == 0],
          'All multi-province firms (101)': b[b.multi_province_dummy == 1],
          'Analysis sample: incumbents observed by 2016 (66)': b[(b.multi_province_dummy == 1) & (b.first_year <= 2016)],
          'Excluded post-2016 entrants (35)': b[(b.multi_province_dummy == 1) & (b.first_year > 2016)]}
tot18 = raw[raw.year == 2018].total_emissions_co2e.sum()
rows = []
for g, gd in groups.items():
    x = gd[gd.year == 2018]; f = x.groupby('company_id').agg(E=('total_emissions_co2e', 'sum'), fac=('num_facilities', 'max'),
                                                              pat=('green_patent_stock', 'max'), eite=('eite', 'max'), ab=('province', lambda s: (s == 'Alberta').any()))
    rows.append(dict(group=g, firms_2018=len(f), firm_years=len(gd), mean_emissions_kt=f.E.mean() / 1e3, median_emissions_kt=f.E.median() / 1e3,
                     share_ghgrp_emissions_2018=f.E.sum() / tot18, mean_facilities=f.fac.mean(), mean_patent_stock=f.pat.mean(),
                     share_with_patents=(f.pat > 0).mean(), share_eite=f.eite.mean(), share_alberta=f.ab.mean(),
                     obs_per_firm=len(gd) / gd.company_id.nunique()))
sel = pd.DataFrame(rows); sel.to_csv(OUT / '70_selection_table.csv', index=False)
print('\n[J] Selection table\n', sel.round(3).to_string())

# ----------------------------------------------------------------------------- K. exact counts
cnt = dict(firms=int(d.company_id.nunique()), obs=int(len(d)), obs_with_real_output=int(d.gdp_real_million_v2.notna().sum()),
           firm_province_cells=int(d.groupby(['company_id', 'province']).ngroups),
           alberta_cells=int(d[d.alberta == 1].groupby(['company_id', 'province']).ngroups),
           firms_with_alberta_obs=int(d[d.alberta == 1].company_id.nunique()), firms_with_nonalberta_obs=int(d[d.alberta == 0].company_id.nunique()),
           firms_with_both=int(len(set(d[d.alberta == 1].company_id) & set(d[d.alberta == 0].company_id))),
           firms_alberta_post=int(d[(d.alberta == 1) & (d.post == 1)].company_id.nunique()),
           firms_nonalberta_post=int(d[(d.alberta == 0) & (d.post == 1)].company_id.nunique()),
           obs_by_year=d.groupby('year').size().to_dict(), naics_count=int(d.naics.nunique()),
           pre_mean_patents_alberta=float(d[(d.alberta == 1) & (d.post == 0)].green_patent_stock.mean()),
           pre_mean_intensity_alberta=float(d[(d.alberta == 1) & (d.post == 0)].intensity_co2e_per_m_gdp.mean()),
           pre_mean_patents_all=float(d[d.post == 0].green_patent_stock.mean()),
           pre_mean_intensity_all=float(d[d.post == 0].intensity_co2e_per_m_gdp.mean()),
           firms_with_prior_patents=int(c18[c18.pat18 > 0].shape[0]), eite_firms=int(d[d.eite == 1].company_id.nunique()),
           same_naics_share=(lambda g: dict(firms_with_2plus_provinces=int(len(g)), same_naics=int((g == 1).sum()), share=float((g == 1).mean())))(
               (lambda gg: gg[gg.company_id.isin(gg.groupby('company_id').province.nunique().pipe(lambda m: m[m >= 2].index))].groupby('company_id').naics_code_3digit.nunique())(
                   d.assign(province=d.province.fillna('NA')).groupby(['company_id', 'province']).naics_code_3digit.agg(lambda x: x.mode().iloc[0]).reset_index())))
(OUT / '70_sample_counts.json').write_text(json.dumps(cnt, indent=2, default=str)); print('\n[K] counts', cnt)
