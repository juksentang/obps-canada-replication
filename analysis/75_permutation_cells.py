#!/usr/bin/env python3
"""Fisher permutation test: reassign Alberta status across firm-province cells (keeping the number of
Alberta cells fixed), 2,000 draws, two-sided p = share of placebo |beta| >= observed |beta|. Same 66-firm sample and TWFE specification.
Output: outputs/tables/70_permutation.csv"""
import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
from paths import PANEL, TAB
T = TAB
raw = pd.read_csv(PANEL)
d = raw[(raw.sample_50kt_baseline==1)&(raw.multi_province_dummy==1)].copy()
d['first']=d.company_id.map(d.groupby('company_id').year.min()); d=d[d['first']<=2016].copy()
d['province']=d.province.fillna('NA'); d['alberta']=(d.province=='Alberta').astype(int); d['post']=(d.year>=2019).astype(int)
d['ln_E']=np.log(d.total_emissions_co2e); d['ln_Y']=np.log(d.gdp_real_million_v2); d['ln_I']=d.ln_E-d.ln_Y; d['ln_pat']=np.log1p(d.green_patent_stock)
rng=np.random.default_rng(20260907); B=2000
cells=d.groupby(['company_id','province']).alberta.first(); cell_ids={k:i for i,k in enumerate(cells.index)}; n_ab=int(cells.sum())
rows=[]
for y in ['green_patent_stock','intensity_co2e_per_m_gdp','ln_E','ln_I','ln_Y','ln_pat']:
    w=d.dropna(subset=[y]).copy(); F=pd.get_dummies(w.company_id,prefix='f',drop_first=True,dtype=float).values; Y=pd.get_dummies(w.year,prefix='y',drop_first=True,dtype=float).values
    post=w.post.values.astype(float); yv=w[y].values.astype(float); rowcell=np.array([cell_ids[k] for k in zip(w.company_id,w.province)])
    Xb=np.column_stack([F,Y])
    def beta(ab):
        X=np.column_stack([np.ones(len(w)), ab*post, Xb]); return np.linalg.lstsq(X,yv,rcond=None)[0][1]
    b0=beta(w.alberta.values.astype(float)); cnt=0; draws=[]
    for b in range(B):
        perm=np.zeros(len(cells)); perm[rng.choice(len(cells),n_ab,replace=False)]=1; bb=beta(perm[rowcell]); draws.append(bb); cnt+=abs(bb)>=abs(b0)
    p=(cnt+1)/(B+1); rows.append(dict(outcome=y,coef=b0,perm_p=p,B=B,n_cells=len(cells),n_alberta_cells=n_ab,placebo_sd=float(np.std(draws))))
    print(y, round(b0,3), 'perm p =', round(p,3))
res=pd.DataFrame(rows); res.to_csv(T/'70_permutation.csv',index=False); print('written')
