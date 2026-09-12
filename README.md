# Does Output Protection Blunt Carbon Pricing? — replication package

Code, derived data and manuscript sources for

> Tang J-S, Gong J, Fu Y, Chen J (2026) *Does Output Protection Blunt Carbon Pricing? Evidence from Large Industrial Emitters under Canada's National Price Floor.* Manuscript.

The paper asks whether large emitters regulated under Alberta's output-based systems (SGER, CCIR, TIER) responded differently from comparable large multi-province firms in other provinces once the Greenhouse Gas Pollution Pricing Act made a rising national carbon-price floor binding in 2019. Outcomes: firm-level greenhouse-gas emissions (GHGRP), firm-level green patent stocks (CIPO, CPC Y02/Y04S) and sector-level emission intensity (GHGRP emissions divided by Statistics Canada real GDP).

## Repository layout

| Path | Content |
|---|---|
| `analysis/` | Estimation and manuscript-generation scripts (see the table below) plus `paths.py` (repository paths) and `figstyle.py` (figure style). Estimation outputs are written to `analysis/outputs/tables/`. |
| `analysis/outputs/manuscript_inputs/` | Generated LaTeX tables (`tables/tab_*.tex`), figures (`figures/fig_*.pdf`) and the number macros (`numbers.json` → `numbers.tex`, indexed in `numbers_index.md`) that the manuscript imports; the manuscript itself is not part of this repository. |
| `data/` | Analysis-ready panels (`data/analysis_ready/`), the facility-level panel (`data/processed/4_panels/`), the small raw inputs and the download script for the bulk sources. See `data/README.md`, `data/data_dictionary.md` and `data/analysis_ready/CODEBOOK.md`. |
| `pipeline/` | Data-construction scripts (`01_…` to `23_…`, run in numerical order by `pipeline/run_all.py`) that build the panels from the raw GHGRP, CIPO and Statistics Canada inputs. Provided for provenance; not needed to reproduce the tables from the shipped panels (see *Data*). |
| `config.py` | Directory layout and constants used by the pipeline. |
| `Makefile` | `make all` regenerates every table, figure and number used in the paper. |

## Reproducing the paper

```bash
pip install -r requirements.txt
make all        # estimation -> tables/figures -> numbers.tex -> PDFs -> numeral audit
```

`make all` runs the steps below in dependency order. Scripts `81` and `82` take roughly 20–40 minutes each; everything else runs in a few minutes. Every script can also be run on its own from any working directory (`python analysis/70_main_estimates.py`); each writes its outputs under `analysis/outputs/`.

| Script | Output |
|---|---|
| `70_main_estimates.py` | Baseline DiD, event studies and joint lead tests, firm-characteristic × year controls, oil-price controls, depreciation and sample-window sensitivity, policy-stage specification, mechanism heterogeneity, representativeness table, sample counts |
| `71_within_firm_province_panel.py` | Company × province × year panel of facility emissions; firm × year fixed-effects check |
| `73_oil_cycle_heterogeneity.py` | Post-period split by oil-price regime; oil-exposed versus other sectors; Table 6 |
| `75_permutation_cells.py` | Fisher permutation over firm–province cells (2,000 draws) |
| `52_wild_bootstrap.py` | Wild cluster bootstrap p-values (Rademacher weights, 1,999 replications) |
| `60_power_analysis.py` | Minimum detectable effects and ex-post power |
| `80_fixed_treatment.py` | Treatment fixed at the 2018 principal province; switching diagnostics; never-switcher subsamples |
| `81_inference_province.py` | Province- and sector–province-cell clustering, wild cluster bootstraps (Webb weights), Conley–Taber placebo provinces |
| `82_honestdid_official.py` | Honest DiD (Rambachan and Roth 2023) relative-magnitudes confidence sets via the `honestdid` reference implementation |

Requirements: Python ≥ 3.10 with the packages in `requirements.txt`; TeX Live (or equivalent) with `pdflatex` and `bibtex` for the manuscript; a LaTeX installation usable by matplotlib (SciencePlots `science` style renders figure text with LaTeX; `amsmath`, `amssymb` and `siunitx` must be installed) for `77_figures.py`. Seeds are fixed (`75`: 20260907; `81`: 20260908; `52`: 42), so the tables and `numbers.json` reproduce exactly. The Makefile runs everything with single-threaded BLAS (`OMP_NUM_THREADS=1`); set the same when running the bootstrap and permutation scripts by hand, otherwise thread oversubscription makes their thousands of small regressions many times slower.

## Data

All inputs are public:

* **Greenhouse Gas Reporting Program** (Environment and Climate Change Canada), facility emissions 2004–2023 — Open Government Licence – Canada. The main GHGRP file is included (`data/ghgrp/`).
* **Canadian Intellectual Property Office** patent bulk data (bibliographic data, claims, classifications) — CIPO terms of use; about 20 GB, downloaded by `data/download.sh`.
* **Statistics Canada** GDP by industry and province, industrial product price indices, electric power selling price index, multifactor-productivity tables (GDP deflator), consumer price index — Statistics Canada Open Licence. The small tables are included; the bulk tables are downloaded by `data/download.sh`.
* **U.S. Energy Information Administration** annual WTI crude prices (hard-coded in `pipeline/23_add_oil_price_controls.py`).

The derived panels needed to reproduce every estimate in the paper are tracked (`data/analysis_ready/analysis_ready_with_oil_controls.csv` is the file read by the estimation scripts; a few MB in total), so the tables can be rebuilt without re-downloading the raw sources. `data/README.md` lists what is and is not included and documents the parts of the pipeline whose intermediate inputs are not reproducible from this repository alone.

## Citation and licence

Code: MIT License (see `LICENSE`). Derived data files retain the licences of their sources listed above. If you use this material, please cite the paper.

Corresponding author: Junhong Chen (chenjunhong@baafs.net.cn). Code and data questions: Juk-Sen Tang (juksen.tang@mail.mcgill.ca).
