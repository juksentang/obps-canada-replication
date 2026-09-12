# Data

This directory holds the derived panels that reproduce every estimate in the paper, the small raw inputs, and the script that downloads the bulk sources. Raw bulk downloads (`data/raw/`) are not tracked.

## Files that reproduce the paper

| File | Rows × cols | Used by | Built by |
|---|---|---|---|
| `analysis_ready/analysis_ready_with_oil_controls.csv` | 9,377 × 55 | all estimation scripts (`analysis/paths.py: PANEL`) | `pipeline/23_add_oil_price_controls.py` |
| `analysis_ready/analysis_ready_with_real_output_v2.csv` | 9,377 × 48 | `analysis/60_power_analysis.py` (sample counts) | see *Known gaps* |
| `analysis_ready/analysis_ready_company_year_20251111.csv` | 9,358 × 28 | base company-year panel (documented in `analysis_ready/CODEBOOK.md`) | `pipeline/16_finalize_analysis_dataset.py` |
| `processed/4_panels/facility_year_greenpatent_merged_20251022.csv` | 18,772 × 32 | `analysis/71_within_firm_province_panel.py` | `pipeline/10_merge_green_patents_facility_panel.py` |
| `processed/4_panels/company_year_panel_v1_20251111.csv` | 9,358 × 18 | input to `pipeline/16_finalize_analysis_dataset.py` | `pipeline/11_construct_company_year_panel.py` |

Column definitions are in `data_dictionary.md` (all five files) and `analysis_ready/CODEBOOK.md` (the base panel, with construction notes).

## Raw inputs included (small)

| Directory | Content | Source and licence |
|---|---|---|
| `ghgrp/` | `PDGES-GHGRP-GHGEmissionsGES-2004-Present.csv` (facility emissions 2004–2023, 11 MB), `PDGES-GHGRP-GHGEmissionsSourcesGES-2022-2023.csv`, the bilingual read-me files | Environment and Climate Change Canada, Greenhouse Gas Reporting Program; Open Government Licence – Canada |
| `CPI/` | Statistics Canada tables 18-10-0004-01 and 18-10-0005-01 (consumer price index) | Statistics Canada Open Licence |
| `Industrial Deflator/` | Tables 18-10-0267-01 (industrial product price index by industry), 18-10-0204-01 (electric power selling price index) and the multifactor-productivity tables 36-10-0208/0211/0217/0223-01 (GDP deflators by industry) | Statistics Canada Open Licence |
| `Industry_GDP/` | Table 36-10-0434-03 (GDP at basic prices by industry, annual average) | Statistics Canada Open Licence |
| `policy/` | HTML snapshots of the ECCC benchmark and OBPS pages and two Department of Finance news releases (institutional background) | Government of Canada; Open Government Licence – Canada |
| `geo/` | Portal page of the 2021 census boundary files (the shapefiles themselves are downloaded by `download.sh`) | Statistics Canada |
| `metadata/` | `cipo_extraction_plan_20251022.json`, the extraction plan read by `pipeline/04_extract_cipo_patents.py` | — |

The annual WTI crude price series (U.S. Energy Information Administration, public domain) is hard-coded in `pipeline/23_add_oil_price_controls.py`.

## Raw inputs not included

Run `bash data/download.sh` from the repository root to fetch them into `data/raw/`:

* CIPO patent researcher datasets (bibliographic data, claims, CPC/IPC classifications; about 20 GB) and the CPC Y-section scheme — CIPO terms of use.
* Statistics Canada bulk tables: 36-10-0402 (GDP by industry and province), 36-10-0478 (supply-use tables), 18-10-0265 and 18-10-0268 (IPPI and RMPI), 36-10-0434 (monthly GDP).
* 2021 census boundary files (provinces and territories).

The pipeline expects them under `data/raw/ghgrp`, `data/raw/statcan/{gdp,sut,price}`, `data/raw/patents/{cipo,cpc}` and `data/raw/geographic`; the GHGRP file included in `data/ghgrp/` must be copied to `data/raw/ghgrp/` to run step 01.

## Rebuilding the panels

`python pipeline/run_all.py` runs the 23 steps in order (about 5 minutes once the raw inputs are in place; step 09 is the slow one). Intermediate outputs are written under `data/processed/` and are not tracked. Output names carry the version stamps used when the paper's panels were built (`_20251022`, `_20251111`) or a `datetime.now()` stamp, exactly as in the original scripts.

### Known gaps

Three intermediate inputs were produced during development by steps whose scripts are not part of this repository, so the pipeline cannot be re-run from raw data end to end without recreating them:

1. `data/processed/green_patents_identified_v1_20251022.csv` — the list of CIPO patents with a CPC Y02/Y04S classification, read by `pipeline/09_construct_green_patents.py` (the identification step, applied to the CIPO classification files extracted by step 04, is described in the paper's data section).
2. `data/processed/3_variables/intensity_ft_final_v1_20251022.csv` — the facility-level intensity file read by steps 07 and 08 (a post-processed version of the output of step 06).
3. `data/analysis_ready/analysis_ready_with_statcan_gdp_v2.csv` and `analysis_ready_with_real_output_v2.csv` — the sector-GDP allocation and real-output files read by step 23. Steps 21 and 22 produce the first versions of these files (`..._with_statcan_gdp.csv`, `..._with_real_output.csv`); the `_v2` files add the NAICS 3-digit GDP allocation (`gdp_3digit_prov_year`, `gdp_million_final`, `gdp_source`, `gdp_defl_rebased`, `gdp_real_million_v2`, `intensity_real_v2`) with the same deflators. The `_v2` real-output panel is tracked so that every estimate reproduces.

In addition, step 15 reads a hand-assembled list of carbon contracts for difference (`cfd_contracts_database_v2_20251023.csv`) and two derived weight matrices that are not tracked; the CfD variables they produce are carried in the panels but are not used in the paper's estimates.

Every number in the paper is produced from the tracked panels by the scripts in `analysis/`; the pipeline is provided to document how those panels were constructed.
