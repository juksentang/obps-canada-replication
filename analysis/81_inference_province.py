#!/usr/bin/env python3
"""Inference that respects the province level of policy variation.
For each estimate: firm-cluster SE (baseline), province-cluster SE with t(G-1), province-level wild cluster bootstrap (Webb weights,
restricted residuals, percentile-t), sector-province-cell clustering for the sector-level intensity outcome, and a Conley-Taber-style
placebo-province distribution (each control province in turn treated as 'treated', Alberta firms dropped). Applied to the headline
outcomes and to the heterogeneity contrasts, under both the time-varying and the fixed-2018 treatment definitions.
Output: outputs/tables/81_inference.csv"""
import numpy as np, pandas as pd, warnings, json
from scipy import stats
from paths import PANEL, TAB
warnings.filterwarnings('ignore')
T = TAB
raw = pd.read_csv(PANEL)
d = raw[(raw.sample_50kt_baseline == 1) & (raw.multi_province_dummy == 1)].copy()
d['first'] = d.company_id.map(d.groupby('company_id').year.min()); d = d[d['first'] <= 2016].copy(); d['province'] = d.province.fillna('NA')
d['alberta'] = (d.province == 'Alberta').astype(int); d['post'] = (d.year >= 2019).astype(int); d['tp'] = d.alberta * d.post
d['ln_E'] = np.log(d.total_emissions_co2e); d['ln_Y'] = np.log(d.gdp_real_million_v2); d['ln_I'] = d.ln_E - d.ln_Y
p18 = d[d.year == 2018].set_index('company_id').province; d['prov18'] = d.company_id.map(p18); d['ab_fixed'] = (d.prov18 == 'Alberta').astype(int); d['tp_fixed'] = d.ab_fixed * d.post
d['naics'] = d.naics_code_3digit.astype(str); d['cell'] = d.naics + '|' + d.province
d['oil'] = d.naics.isin(['211', '324', '486']).astype(int); d['oil_post'] = d.oil * d.post
c18 = d[d.year == 2018].groupby('company_id').green_patent_stock.max(); d['prior'] = (d.company_id.map(c18) > 0).astype(int); d['prior_post'] = d.prior * d.post
d['late'] = (d.year >= 2022).astype(int)
rng = np.random.default_rng(20260908); B = 2999
WEBB = np.array([-np.sqrt(1.5), -1, -np.sqrt(0.5), np.sqrt(0.5), 1, np.sqrt(1.5)])
def design(w, treat_cols, controls=()):
    X = w[list(treat_cols) + list(controls)].astype(float).values
    F = pd.get_dummies(w.company_id, drop_first=True, dtype=float).values; Y = pd.get_dummies(w.year, drop_first=True, dtype=float).values
    return np.column_stack([np.ones(len(w)), X, F, Y])
def fwl(X, y, j):
    """Residualise column j on the other columns; return (beta_j, e_tilde, u_hat)."""
    Z = np.delete(X, j, axis=1); e = X[:, j] - Z @ np.linalg.lstsq(Z, X[:, j], rcond=None)[0]
    b = (e @ y) / (e @ e); u = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]; return b, e, u
def cl_se(e, u, groups):
    """Cluster-robust SE of the FWL coefficient with CR1 small-sample factor."""
    g = pd.factorize(groups)[0]; G = g.max() + 1; N = len(e)
    s = np.bincount(g, weights=e * u); V = (s ** 2).sum() / (e @ e) ** 2 * (G / (G - 1)) * ((N - 1) / (N - 1))
    return np.sqrt(V), G
def wild_boot(X, y, j, groups, B=B):
    """Restricted wild cluster bootstrap (null imposed), Webb weights, percentile-t p-value. Uses the precomputed annihilator of X."""
    g = pd.factorize(groups)[0]; G = g.max() + 1
    b, e, u = fwl(X, y, j); se, _ = cl_se(e, u, g); t0 = b / se
    Z = np.delete(X, j, axis=1); bz = np.linalg.lstsq(Z, y, rcond=None)[0]; yhat0 = Z @ bz; u0 = y - yhat0
    M = np.eye(len(y)) - X @ np.linalg.pinv(X)   # annihilator, once per spec
    ee = e @ e; cnt = 0; fac = G / (G - 1)
    for _ in range(B):
        wgt = WEBB[rng.integers(0, 6, G)][g]; ystar = yhat0 + wgt * u0
        bs = (e @ ystar) / ee; us = M @ ystar
        s = np.bincount(g, weights=e * us, minlength=G); ses = np.sqrt((s ** 2).sum() / ee ** 2 * fac)
        cnt += abs(bs / ses) >= abs(t0)
    return b, se, t0, (cnt + 1) / (B + 1), G
rows = []
def run(label, outcome, w, treat_cols, j_name, controls=(), cluster_prov_col='province', placebo=True):
    w = w.dropna(subset=[outcome]).copy(); X = design(w, treat_cols, controls); y = w[outcome].values.astype(float); j = 1 + list(treat_cols).index(j_name)
    b, e, u = fwl(X, y, j)
    se_f, Gf = cl_se(e, u, w.company_id.values); p_f = 2 * (1 - stats.t.cdf(abs(b / se_f), Gf - 1))
    se_p, Gp = cl_se(e, u, w[cluster_prov_col].values); p_p = 2 * (1 - stats.t.cdf(abs(b / se_p), Gp - 1))
    _, _, _, p_wp, _ = wild_boot(X, y, j, w[cluster_prov_col].values)
    se_c, Gc = cl_se(e, u, w.cell.values); p_c = 2 * (1 - stats.t.cdf(abs(b / se_c), Gc - 1))
    _, _, _, p_wc, _ = wild_boot(X, y, j, w.cell.values, B=999)
    rec = dict(label=label, outcome=outcome, coef=b, se_firm=se_f, p_firm=p_f, G_firm=Gf, se_prov=se_p, p_prov_t=p_p, G_prov=Gp, p_wild_prov=p_wp, se_cell=se_c, p_cell_t=p_c, G_cell=Gc, p_wild_cell=p_wc, N=len(w))
    if placebo:
        # Conley-Taber-style: each control province with >= 4 firms plays 'treated'; Alberta firms/rows removed
        base_col = 'prov18' if cluster_prov_col == 'prov18' else 'province'
        wc = w[w[base_col] != 'Alberta'].copy(); pl = []
        for c in ['Ontario', 'British Columbia', 'Quebec', 'Saskatchewan', 'Manitoba']:
            if wc[wc[base_col] == c].company_id.nunique() < 4: continue
            wc2 = wc.copy(); wc2['_pl'] = ((wc2[base_col] == c) & (wc2.post == 1)).astype(float)
            # rebuild the same contrast structure with the placebo replacing the treatment indicator
            tcols = list(treat_cols); wc2[tcols[j - 1]] = wc2['_pl']
            if len(tcols) > 1:  # contrast designs: recompute sum/diff columns with placebo province
                if 'oil' in label.lower(): wc2['_sum'] = wc2['_pl']; wc2['_diff'] = wc2['_pl'] * wc2.oil
                elif 'prior' in label.lower(): wc2['_sum'] = wc2['_pl']; wc2['_diff'] = wc2['_pl'] * wc2.prior
                elif 'late' in label.lower(): wc2['_sum'] = wc2['_pl']; wc2['_diff'] = wc2['_pl'] * wc2.late
            # a placebo contrast is identified only if the placebo province contains firms of both groups in the post period;
            # otherwise the placebo x group column is collinear and lstsq returns an arbitrary or NaN coefficient
            if len(tcols) > 1:
                grp = 'oil' if 'oil' in label.lower() else ('prior' if 'prior' in label.lower() else 'late')
                if wc2.loc[wc2._pl == 1, grp].nunique() < 2: continue
            Xp = design(wc2, tcols, controls); yp = wc2[outcome].values.astype(float)
            try: bp, _, _ = fwl(Xp, yp, j)
            except Exception: continue
            if np.isfinite(bp): pl.append((c, bp))
        if pl:
            # p = (k+1)/(N+1): Alberta's own estimate is included in the reference set, so the floor is 1/(N+1)
            vals = np.array([v for _, v in pl]); rec.update(placebo_n=len(pl), placebo_p=float((np.sum(np.abs(vals) >= abs(b)) + 1) / (len(vals) + 1)), placebo_min=float(vals.min()), placebo_max=float(vals.max()),
                           placebo_json=json.dumps({c: round(float(v), 4) for c, v in pl}))
    rows.append(rec); print(f"{label:55s} {outcome:24s} b={b:9.3f} p_firm={p_f:.3f} p_prov={p_p:.3f} p_wildprov={p_wp:.3f} p_cell={p_c:.3f} p_wildcell={p_wc:.3f} placebo_p={rec.get('placebo_p', float('nan')):.2f} (n={rec.get('placebo_n', 0)})", flush=True)
for tv, pc, tag in [('tp', 'province', 'time-varying'), ('tp_fixed', 'prov18', 'fixed-2018')]:
    for y in ['green_patent_stock', 'intensity_co2e_per_m_gdp', 'ln_E', 'ln_I', 'ln_Y']:
        run(f'Main effect [{tag}]', y, d, (tv,), tv, cluster_prov_col=pc)
    # heterogeneity contrasts: oil-sector difference (ln_E, patents, intensity); prior-innovator difference (patents, ln_E); late-window difference (intensity, ln_E)
    w = d.copy(); w['_sum'] = w[tv]; w['_diff'] = w[tv] * w.oil
    for y in ['ln_E', 'green_patent_stock', 'intensity_co2e_per_m_gdp']: run(f'Oil-sector minus other sectors [{tag}]', y, w, ('_sum', '_diff'), '_diff', controls=('oil_post',), cluster_prov_col=pc)
    w = d.copy(); w['_sum'] = w[tv]; w['_diff'] = w[tv] * w.prior
    for y in ['green_patent_stock', 'ln_E']: run(f'Prior innovators minus others [{tag}]', y, w, ('_sum', '_diff'), '_diff', controls=('prior_post',), cluster_prov_col=pc)
    w = d.copy(); w['_sum'] = w[tv]; w['_diff'] = w[tv] * w.late
    for y in ['intensity_co2e_per_m_gdp', 'ln_E']: run(f'Late window (2022-23) minus early (2019-21) [{tag}]', y, w, ('_sum', '_diff'), '_diff', controls=(), cluster_prov_col=pc)
res = pd.DataFrame(rows); res.to_csv(T / '81_inference.csv', index=False); print('written', T / '81_inference.csv')
