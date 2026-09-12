# Data dictionary

Column definitions for the tracked data files. Monetary values are in Canadian dollars; emissions in tonnes of CO2 equivalent (tCO2e).

## `analysis_ready/analysis_ready_with_oil_controls.csv` (company-year panel, 9,377 rows)

The file read by every estimation script. It extends `analysis_ready_company_year_20251111.csv` (base columns, documented in `analysis_ready/CODEBOOK.md`) with sample flags, sector GDP, deflators and oil-price controls.

### Identifiers and structure

| Column | Description |
|---|---|
| `company_id` | Standardised company identifier |
| `company_name` | Company legal name (GHGRP) |
| `year` | Calendar year, 2004–2023 |
| `province` | Principal province of operation in the year (the province of the modal reporting facility) |
| `naics_code_3digit` | Principal NAICS 3-digit sector in the year |
| `multi_province_dummy` | 1 if the company reports facilities in more than one province |
| `num_facilities` | Number of reporting facilities in the year |
| `company_age` | Years since the company first appears in the GHGRP |
| `year_fe`, `province_fe`, `naics_fe` | String copies of year, province and sector for fixed effects |

### Emissions and intensity

| Column | Description |
|---|---|
| `total_emissions_co2e` | Total GHG emissions of the company's facilities, tCO2e |
| `ln_emissions` | log of total emissions |
| `emissions_squared` | Square of total emissions |
| `high_emitter` | 1 if emissions above the 75th percentile |
| `emissions_growth_pct` | Year-over-year percentage change in emissions |
| `intensity_co2e_per_m_gdp` | Emission intensity of the company's principal NAICS 3-digit sector in its province: sector GHGRP emissions per million dollars of real sector GDP (2015 dollars) |
| `ln_emissions_2018`, `intensity_2018` | 2018 values of log emissions and intensity, carried to all years of the company |

### Green patents

| Column | Description |
|---|---|
| `green_patent_count` | Annual flow of green patents (CPC Y02/Y04S) attributed to the company, fractional counting across sectors |
| `unique_patents` | Number of distinct patents behind the flow |
| `green_patent_stock` | Perpetual-inventory stock of green patents, depreciation 15% |
| `green_patent_intensity` | Stock per tCO2e |
| `has_green_patents` | 1 if the stock is positive |
| `ln_green_patents` | log(1 + stock) |

### Sample flags

| Column | Description |
|---|---|
| `sample_50kt_baseline` | 1 if the company's 2018 emissions are at least 50 kt CO2e (the paper's sample) |
| `sample_any_year_50kt` | 1 if emissions reach 50 kt in any year |
| `sample_all_years_50kt` | 1 if emissions are at least 50 kt in every observed year |

### Policy variables (carried from the base panel; not used in the paper's estimates)

| Column | Description |
|---|---|
| `carbon_price_real_2015` | Provincial carbon price in 2015 dollars per tonne |
| `exposure_price_it` | Carbon-pricing exposure indicator |
| `cfd_participant`, `cfd_type`, `exposure_cfd_it` | Carbon contract-for-difference participation flags |

### Sector GDP and real output

| Column | Description |
|---|---|
| `naics_2digit` | NAICS 2-digit sector |
| `gdp_ind_prov_year` | Nominal GDP of the NAICS 2-digit sector in the province and year, $ million (Statistics Canada 36-10-0402) |
| `emission_share` | Company's share of the emissions of its sector–province cell in the year |
| `gdp_million_statcan` | Sector GDP allocated to the company by `emission_share`, $ million (2-digit allocation) |
| `intensity_statcan` | Emissions per million dollars of `gdp_million_statcan` |
| `naics_3digit_statcan`, `naics_3digit` | NAICS 3-digit code matched to the Statistics Canada industry classification |
| `gdp_3digit_prov_year` | Nominal GDP of the NAICS 3-digit sector in the province and year, $ million |
| `gdp_million_final` | Allocated sector GDP used for the paper (3-digit where available, 2-digit otherwise), $ million |
| `gdp_source` | Which allocation `gdp_million_final` uses |
| `deflator_index` | Sector price deflator, 2015 = 100 |
| `source` | Deflator source: `IPPI` (industrial product price index), `ELECTRIC_PRICE` (electric power selling price index) or `GDP_DEFLATOR` |
| `gdp_defl_rebased` | Deflator rebased to 2015 = 1 |
| `gdp_real_million_v2` | Real allocated sector GDP, 2015 $ million: the implied output Y used in the paper's identity ln E = ln I + ln Y |
| `intensity_real_v2` | Emissions per million dollars of real allocated GDP |

### Oil-price controls

| Column | Description |
|---|---|
| `wti_price_usd` | Annual average WTI crude price, US$ per barrel (EIA) |
| `ln_wti_price` | log of the WTI price |
| `ln_wti_price_lag1` | One-year lag of `ln_wti_price` |
| `wti_price_change` | Year-over-year percentage change in the WTI price |
| `wti_volatility` | Three-year rolling standard deviation of the WTI price |
| `alberta` | 1 if `province` is Alberta |
| `alberta_x_ln_wti` | `alberta` × `ln_wti_price` |

## `analysis_ready/analysis_ready_with_real_output_v2.csv` (9,377 rows)

The same panel without the oil-price block (columns up to `intensity_real_v2`).

## `analysis_ready/analysis_ready_company_year_20251111.csv` (9,358 rows)

The base company-year panel: identifiers, emissions, green patents and policy variables as listed above (no sample flags, sector GDP or oil-price columns). See `analysis_ready/CODEBOOK.md`.

## `processed/4_panels/facility_year_greenpatent_merged_20251022.csv` (facility-year panel, 18,772 rows)

| Column | Description |
|---|---|
| `facility_id`, `facility_name`, `facility_city`, `province`, `province_code`, `latitude`, `longitude` | GHGRP facility identifiers and location |
| `year` | Reporting year |
| `naics_code_6digit`, `naics_code_3digit` | Facility NAICS codes |
| `company_legal_name`, `company_trade_name` | Reporting company |
| `total_emissions_co2e` | Facility emissions, tCO2e |
| `intensity_co2e_per_m_gdp`, `baseline_intensity_2015` | Sector–province emission intensity and its 2015 value |
| `carbon_price_nominal`, `carbon_price_real_2015`, `delta_price_real_2015`, `exposure_price_it` | Provincial carbon price variables |
| `first_year`, `last_year`, `years_active`, `obs_count`, `is_continuous`, `is_entrant`, `is_exiter` | Facility reporting history |
| `green_patent_count`, `unique_patents`, `green_patent_stock`, `green_domains`, `green_patent_intensity`, `green_patents_per_tco2e` | Green patent flow and stock allocated to the facility's sector–province cell |

## `processed/4_panels/company_year_panel_v1_20251111.csv` (9,358 rows)

Company-year aggregation of the facility panel: `company_id_raw`, `company_id`, `year`, `company_name`, `company_trade_name`, `province`, `num_provinces`, `multi_province_dummy`, `naics_code_3digit`, `num_facilities`, `total_emissions_co2e`, `intensity_co2e_per_m_gdp`, `carbon_price_real_2015`, `exposure_price_it`, `green_patent_count`, `unique_patents`, `green_patent_stock`, `green_patent_intensity` (definitions as above).
