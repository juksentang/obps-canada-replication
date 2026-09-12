#!/usr/bin/env python3
"""Build the four main-text figures (analysis/outputs/manuscript_inputs/figures/fig_*.pdf and .png) from the estimation outputs, using the shared
SciencePlots style with LaTeX text: event study, specification robustness, identity decomposition and the oil-price cycle."""
import json
import numpy as np, pandas as pd
import figstyle as st; st.apply(8)
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from paths import TAB, PAPER
T = TAB; SUB = PAPER; FIG = SUB / 'figures'
BLUE, ORANGE, MUTED, SEC, GRID = st.BLUE, st.ORANGE, st.MUTED, st.SEC, st.GRID
es = pd.read_csv(T / '70_event_study.csv'); pt = pd.read_csv(T / '70_pretrend_tests.csv')
cc = pd.read_csv(T / '70_char_controls.csv'); oc = pd.read_csv(T / '70_oil_controls.csv'); sw = pd.read_csv(T / '70_sample_windows.csv'); base = pd.read_csv(T / '70_baseline.csv')
num = json.load(open(SUB / 'numbers.json')); oil = num['oil_cycle']
def sig(p): return '***' if p < .01 else '**' if p < .05 else '*' if p < .10 else ''
def save(fig, name): fig.savefig(FIG / f'{name}.pdf'); fig.savefig(FIG / f'{name}.png', dpi=200); plt.close(fig); print('written', name)
def ptp(y, key): return pt[(pt.outcome == y) & (pt.test.str.startswith(key))].p.iloc[0]

# ---------------------------------------------------------------- Figure 1: event studies
panels = [('ln_E', 'Log total emissions (firm level)'), ('intensity_co2e_per_m_gdp', 'Emission intensity, tCO2e per $M output (sector level)'), ('green_patent_stock', 'Green patent stock (firm level)')]
fig, axes = plt.subplots(3, 1, figsize=(6.3, 7.4))
for ax, (y, title) in zip(axes, panels):
    e = es[es.outcome == y].copy(); e['kk'] = e.k.astype(int)
    ax.axvspan(-7.5, -1.5, color=BLUE, alpha=0.06, lw=0, zorder=0); ax.axhline(0, color='#b8b7b2', lw=0.6, zorder=1); ax.axvline(-0.5, color='#b8b7b2', lw=0.6, zorder=1)
    for _, r in e.iterrows():
        trunc = (r.kk == 4 and y == 'green_patent_stock'); col = MUTED if trunc else BLUE
        ax.plot([r.kk, r.kk], [r.ci_lo, r.ci_hi], color=col, lw=1.3, ls=(0, (2, 1.5)) if trunc else '-', solid_capstyle='round', zorder=2)
        ax.plot(r.kk, r.coef, 'o', ms=5, mfc='white' if trunc else col, mec=col, mew=1.2, zorder=3)
    ax.plot(-1, 0, 'o', ms=5, mfc='white', mec=BLUE, mew=1.2, zorder=3)
    ax.text(0.015, 0.95, st.tx(f'Leads 2013–2017 jointly zero: $p={ptp(y,"leads k=-6"):.2f}$; leads 2016–2017: $p={ptp(y,"leads 2016"):.2f}$'), transform=ax.transAxes, va='top', ha='left', fontsize=7, color=SEC, bbox=dict(boxstyle='square,pad=0.25', fc='white', ec='none', alpha=0.85))
    if y == 'green_patent_stock': ax.text(4, e[e.kk == 4].ci_hi.iloc[0] + 3, st.tx('2023 censored\n(publication lag)'), ha='center', va='bottom', fontsize=6.5, color=MUTED)
    st.panel_title(ax, 'abc'[panels.index((y, title))], title)
    ax.set_xticks(range(-7, 5)); ax.set_xticklabels([st.tx('≤−7')] + [st.tx(f'{k}') if k != 0 else '0' for k in range(-6, 5)])
    ax.set_xlim(-7.7, 4.7); ax.grid(axis='y', color=GRID, lw=0.5); ax.set_axisbelow(True)
    ax.set_ylabel(st.tx('Coefficient'))
sec = axes[-1].secondary_xaxis('bottom'); sec.set_xticks(range(-7, 5)); sec.set_xticklabels([''] + [str(2019 + k) for k in range(-6, 5)]); sec.tick_params(length=0, pad=14, labelsize=6.5, colors=MUTED); sec.spines['bottom'].set_visible(False)
axes[-1].set_xlabel(st.tx('Years relative to 2019, the first year of the national carbon-price floor (reference year 2018)'), labelpad=22)
fig.tight_layout(h_pad=1.2); save(fig, 'fig_event_study')

# ---------------------------------------------------------------- Figure 2: specification robustness
specs = [('Baseline', cc, 'spec', 'Baseline (firm + year FE)'), ('+ size × year FE', cc, 'spec', '+ 2018 size (ln emissions) x year FE'), ('+ patent stock × year FE', cc, 'spec', '+ 2018 patent stock (ln) x year FE'),
         ('+ facilities × year FE', cc, 'spec', '+ 2018 facility count x year FE'), ('+ NAICS × year FE', cc, 'spec', '+ NAICS-3 x year FE'), ('+ province trends', cc, 'spec', '+ province linear trends'),
         ('+ all characteristics + NAICS × year', cc, 'spec', '+ all firm characteristics x year FE + NAICS x year FE'),
         ('+ Alberta × ln WTI', oc, 'spec', '+ Alberta x ln WTI'), ('+ Alberta × ln WTI (t, t−1)', oc, 'spec', '+ Alberta x ln WTI + Alberta x ln WTI(t-1)'),
         ('Exclude 2023', sw, 'window', 'Exclude 2023 (patent truncation)'), ('Pre-COVID (≤2019)', sw, 'window', 'Pre-COVID: 2004-2019'), ('Exclude 2020–21', sw, 'window', 'Exclude 2020-2021 (pandemic years)')]
fig, axes = plt.subplots(1, 3, figsize=(6.3, 3.6), sharey=True)
for ax, (y, title, unit) in zip(axes, [('green_patent_stock', 'Green patents', 'patents'), ('intensity_co2e_per_m_gdp', 'Emission intensity', 'tCO2e per $M'), ('ln_E', 'Log emissions', 'log points')]):
    ax.axvline(0, color='#b8b7b2', lw=0.6)
    for j, (lab, df, col, key) in enumerate(specs):
        m = df[(df.outcome == y) & (df[col] == key)].iloc[0]; yy = len(specs) - 1 - j
        ax.plot([m.ci_lo, m.ci_hi], [yy, yy], color=BLUE, lw=1.3, solid_capstyle='round'); ax.plot(m.coef, yy, 'o', ms=4.2, color=BLUE, mec='white', mew=0.6)
    ax.set_yticks(range(len(specs))); ax.set_yticklabels([st.tx(s[0]) for s in specs][::-1])
    for yy in (2.5, 4.5): ax.axhline(yy, color=GRID, lw=0.5, ls=(0, (1, 2)))
    st.panel_title(ax, 'abc'[[('green_patent_stock'), ('intensity_co2e_per_m_gdp'), ('ln_E')].index(y)], title); ax.set_xlabel(st.tx(f'Coefficient ({unit})')); ax.grid(axis='x', color=GRID, lw=0.5); ax.set_axisbelow(True)
fig.tight_layout(w_pad=1.0); save(fig, 'fig_specification_robustness')

# ---------------------------------------------------------------- Figure 3: decomposition
spec_rows = [('Baseline', 'base'), ('+ Alberta × ln WTI', 'oil'), ('+ NAICS-3 × year FE', 'naics'), ('+ Alberta × ln WTI\n+ NAICS × year FE', 'oil_naics'), ('Pre-COVID sample (≤2019)', 'precovid')]
def get(y, key):
    if key == 'base': return base[base.outcome == y].iloc[0]
    if key == 'oil': return oc[(oc.outcome == y) & (oc.spec == '+ Alberta x ln WTI')].iloc[0]
    if key == 'naics': return cc[(cc.outcome == y) & (cc.spec == '+ NAICS-3 x year FE')].iloc[0]
    if key == 'oil_naics': return oc[(oc.outcome == y) & (oc.spec.str.contains('NAICS'))].iloc[0]
    if key == 'precovid': return sw[(sw.outcome == y) & (sw.window.str.startswith('Pre-COVID'))].iloc[0]
fig, axes = plt.subplots(1, 3, figsize=(6.3, 2.9), sharey=True)
for ax, (y, title) in zip(axes, [('ln_E', r'$\ln E$ (firm emissions)'), ('ln_I', r'$\ln I$ (sector intensity)'), ('ln_Y', r'$\ln Y$ (implied output)')]):
    ax.axvline(0, color='#b8b7b2', lw=0.6)
    for j, (lab, key) in enumerate(spec_rows):
        r = get(y, key); yy = len(spec_rows) - 1 - j
        ax.plot([r.ci_lo, r.ci_hi], [yy, yy], color=BLUE, lw=1.3, solid_capstyle='round'); ax.plot(r.coef, yy, 'o', ms=4.5, color=BLUE)
        ax.text(r.ci_hi + 0.05, yy, st.tx(f'{r.coef:+.2f}{sig(r.p)}'.replace('-', '−')), va='center', fontsize=6.5, color=SEC)
    ax.set_yticks(range(len(spec_rows))); ax.set_yticklabels([st.tx(s[0]) for s in spec_rows][::-1])
    st.panel_title(ax, 'abc'[['ln_E', 'ln_I', 'ln_Y'].index(y)], title); ax.set_xlim(-1.0, 1.45); ax.set_xlabel(st.tx('Coefficient (log points)')); ax.grid(axis='x', color=GRID, lw=0.5); ax.set_axisbelow(True)
fig.tight_layout(w_pad=1.0); save(fig, 'fig_decomposition')

# ---------------------------------------------------------------- Figure 4: oil-price cycle
_w = {int(k): float(v) for k, v in num['wti_by_year'].items()}; _W = lambda y: f'{_w[y]:.0f}'
_sec = next(x for x in oil if x['block'] == 'sector')
rows = [('period', 'a', f'2019–2021\n(WTI ${_W(2020)}–{_W(2021)}/bbl)', BLUE), ('period', 'b', f'2022–2023\n(WTI ${_W(2023)}–{_W(2022)}/bbl)', BLUE),
        ('sector', 'a', _sec['a_label'].replace('Oil, gas, refining, pipelines', 'Oil, gas, refining,\npipelines'), ORANGE), ('sector', 'b', _sec['b_label'].replace('Other sectors ', 'Other sectors\n'), ORANGE)]
fig, axes = plt.subplots(1, 3, figsize=(6.3, 3.3))
for ax, (y, title, unit, d) in zip(axes, [('ln_E', 'Log emissions', 'log points', 3), ('intensity_co2e_per_m_gdp', 'Emission intensity', 'tCO2e per $M', 0), ('green_patent_stock', 'Green patents', 'patents', 1)]):
    ax.axvline(0, color='#b8b7b2', lw=0.6)
    for j, (blk, side, lab, col) in enumerate(rows):
        r = next(x for x in oil if x['outcome'] == y and x['block'] == blk); c, s, p = r[side + '_coef'], r[side + '_se'], r[side + '_p']; yy = len(rows) - 1 - j
        ax.plot([c - 1.96 * s, c + 1.96 * s], [yy, yy], color=col, lw=1.3, solid_capstyle='round'); ax.plot(c, yy, 'o', ms=4.5, color=col)
        ax.annotate(st.tx(f'{c:+.{d}f}{sig(p)}'.replace('-', '−')), (c + 1.96 * s, yy), xytext=(3, 0), textcoords='offset points', va='center', fontsize=6.5, color=SEC)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([st.tx(r[2]) for r in rows][::-1]); ax.axhline(1.5, color=GRID, lw=0.5, ls=(0, (1, 2)))
    st.panel_title(ax, 'abc'[['ln_E', 'intensity_co2e_per_m_gdp', 'green_patent_stock'].index(y)], title); ax.set_xlabel(st.tx(f'Coefficient ({unit})')); ax.grid(axis='x', color=GRID, lw=0.5); ax.set_axisbelow(True)
    lo, hi = ax.get_xlim(); ax.set_xlim(lo, hi + (hi - lo) * 0.28)
fig.legend(handles=[Line2D([0], [0], marker='o', color=BLUE, lw=1.3, ms=4.5, label=st.tx('Post-period split by oil-price regime')), Line2D([0], [0], marker='o', color=ORANGE, lw=1.3, ms=4.5, label=st.tx('Split by sector (sector × post-2019 control included)'))],
           loc='lower center', ncol=2, bbox_to_anchor=(0.5, 0.0))
fig.tight_layout(rect=(0, 0.08, 1, 1), w_pad=1.0); save(fig, 'fig_oil_cycle')
