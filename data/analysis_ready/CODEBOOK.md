
# ANALYSIS-READY DATASET CODEBOOK
## Company-year panel (`analysis_ready_company_year_20251111.csv`)


**Dataset**: `data/analysis_ready/analysis_ready_company_year_20251111.csv` (base panel; the extended panels used by the estimation scripts add sector GDP, deflator and oil-price columns, see `data/data_dictionary.md`)

---

## TABLE OF CONTENTS
1. [Dataset Overview](#dataset-overview)
2. [Variable Dictionary](#variable-dictionary)
3. [Data Sources](#data-sources)
4. [Variable Construction](#variable-construction)
5. [Missing Values](#missing-values)
6. [Usage Notes](#usage-notes)

---

## DATASET OVERVIEW

### Dimensions
- **Records**: 9,358
- **Unique companies**: 1,545
- **Time period**: 2004-2023
- **Panel type**: Unbalanced (not all companies appear all years)

### Coverage
- **Provinces**: 13 (all Canadian provinces in data)
- **Industries**: 39 NAICS 3-digit sectors
- **Years with data**: [2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]

---

## VARIABLE DICTIONARY

### IDENTIFIERS

| Variable | Type | Description | Range |
|----------|------|-------------|-------|
| `company_id` | String | Standardized company identifier | - |
| `company_name` | String | Company legal name | - |
| `year` | Integer | Calendar year | 2004-2023 |

### GEOGRAPHIC & STRUCTURAL

| Variable | Type | Description | Range |
|----------|------|-------------|-------|
| `province` | String | Primary province of operations | AB, BC, MB, NB, NL, NS, NT, ON, PE, QC, SK, YT |
| `naics_code_3digit` | String | North American Industry Classification (3-digit) | 221-562 |
| `multi_province_dummy` | Binary | 1 if company operates in multiple provinces | 0, 1 |
| `num_facilities` | Integer | Number of facilities operated by company (in year) | 1-98 |
| `company_age` | Integer | Years since company first appears in data | 0-20 |

### EMISSIONS VARIABLES

**Primary Outcome Variables** (main dependent variables for regression)

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `total_emissions_co2e` | Continuous | tCO2e | Total greenhouse gas emissions (CO2 equivalent) |
| `intensity_co2e_per_m_gdp` | Continuous | tCO2e/M GDP | Emission intensity (normalized by GDP) |
| `emissions_squared` | Continuous | (tCO2e)² | Squared emissions for nonlinear effects |
| `ln_emissions` | Continuous | log(tCO2e) | Natural log of emissions (for elasticity estimation) |

**Emission Indicators**

| Variable | Type | Description |
|----------|------|-------------|
| `high_emitter` | Binary | 1 if company emissions > 75th percentile |
| `emissions_growth_pct` | Continuous | Year-over-year % change in emissions |

### GREEN PATENT VARIABLES

**Patent Stocks** (main innovation indicator)

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `green_patent_stock` | Continuous | Patents | Patent stock (perpetual inventory method, δ=0.15) |
| `green_patent_count` | Continuous | Patents | Number of green patent flows (fractional counting) |
| `unique_patents` | Integer | Patents | Number of unique patent IDs |

**Patent Intensity**

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `green_patent_intensity` | Continuous | Patents/tCO2e | Patent stock per tonne CO2 equivalent |
| `ln_green_patents` | Continuous | log(Patents) | Natural log of patent stock (for elasticity) |
| `ln_patents_per_facility` | Continuous | log(Patents/facility) | Patent intensity per facility |

**Patent Indicators**

| Variable | Type | Description |
|----------|------|-------------|
| `has_green_patents` | Binary | 1 if company has any green patents (stock > 0) |

### POLICY EXPOSURE VARIABLES

**Carbon Price Exposure**

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `carbon_price_real_2015` | Continuous | CAD 2015 $/tonne | Real carbon price (constant 2015 dollars) |
| `exposure_price_it` | Binary | - | Carbon pricing policy exposure indicator |

**CfD (Contracts for Difference) Exposure**

| Variable | Type | Description |
|----------|------|-------------|
| `cfd_participant` | Binary | 1 if company is CfD/CCO participant |
| `cfd_type` | Categorical | Type: 'CCO', 'Carbon Policy CfD', or 'No' |
| `exposure_cfd_it` | Binary | 1 if year >= agreement year (treatment indicator) |

### FIXED EFFECT VARIABLES

| Variable | Type | Description | Usage |
|----------|------|-------------|-------|
| `year_fe` | String | Year indicator | Year fixed effects in regression |
| `province_fe` | String | Province indicator | Province fixed effects in regression |
| `naics_fe` | String | NAICS 3-digit indicator | Industry fixed effects in regression |

---

## DATA SOURCES

| Variable(s) | Source | Coverage | Last Updated |
|-------------|--------|----------|--------------|
| Emissions, intensity, facilities | GHGRP (Environment Canada) | 2004-2023 | 2024 |
| Green patents | CIPO (Canadian Patents) | 2000-2023 | 2024 |
| Carbon price | Federal carbon pricing policy | 2019-2023+ | Ongoing |
| CfD programs | CGF, Ministry of Energy | 2023-2025 | 2024 |

---

## VARIABLE CONSTRUCTION

### Emissions Variables

- **total_emissions_co2e**: Sum of all GHG emissions converted to CO2-equivalent using IPCC GWP values
- **intensity_co2e_per_m_gdp**: Emissions divided by provincial real GDP (millions 2015 CAD)
- **ln_emissions**: log(total_emissions_co2e + 1) to handle zero values

### Green Patent Variables

- **green_patent_stock**: Perpetual inventory model: Stock_t = (1 - δ) × Stock_{t-1} + Flow_t
  - Depreciation rate (δ) = 0.15
  - Flow = fractional count (1.0 per patent, distributed across NAICS sectors)
  - Allocated to companies using facility-level NAICS codes

- **green_patent_count**: Number of green patent grants (fractional counting)
  - Patents with multiple classifications distributed across industries
  - Weights sum to 1.0 per patent (weight conservation)

- **green_patent_intensity**: Stock per unit emissions (patents/tCO2e)

### Exposure Variables

- **exposure_price_it**: = 1 if carbon pricing was active in that year/province
- **exposure_cfd_it**: = 1 if company is CfD participant AND year ≥ agreement year

### Company Age

- First year: Earliest appearance of company in GHGRP data
- Age = current year - first year
- Can be interpreted as proxy for firm maturity

---

## MISSING VALUES

| Variable | N Missing | % Missing | Handling |
|----------|-----------|-----------|----------|
| intensity_co2e_per_m_gdp | 0 | 0.00% | Imputed with median |
| emissions_growth_pct | ~1545 | ~16.5% | First year of company (expected) |
| Other variables | 0 | 0% | Complete |

**Note**: Missingness in green patent variables (set to 0) indicates no green patents reported/attributed.
This is substantively meaningful (absence of innovation) rather than data quality issue.

---

## USAGE NOTES

### For Regression Analysis

**Example: Simple OLS with company and year FE**
```stata
regress ln_emissions exposure_price_it ln_green_patents, absorb(company_id year)
```

**Example: Two-way FE model**
```stata
regress ln_emissions exposure_price_it ln_green_patents i.year i.naics_fe, absorb(company_id)
```

**Example: Heterogeneous effects by emitter size**
```stata
regress ln_emissions c.exposure_price_it##c.high_emitter ln_green_patents, absorb(company_id year)
```

### Panel Structure

- **Unbalanced panel**: Not all companies present all years
  - Total observations: 9,358
  - Avg obs per company: 6.1

- **Time span**: 2004-2023 (20 years)

- **Attrition**: Some companies exit after certain year
  - Use appropriate estimator if attrition is endogenous
  - Consider inverse probability weighting if needed

### Variable Transformations

- **For elasticity estimation**: Use ln_emissions, ln_green_patents
- **For rate-of-change**: Use emissions_growth_pct
- **For threshold effects**: Use high_emitter, has_green_patents dummies
- **For heterogeneity**: Interact with multi_province_dummy, high_emitter, etc.

### Recommended Sample Restrictions

1. **Unbalanced vs balanced**:
   - Unbalanced: Use all data (current)
   - Balanced: Keep only companies with all 20 years (reduces to ~47 companies)

2. **Continuous reporters**:
   - Keep only is_continuous == 1
   - Drops entrants/exiters for stricter specification

3. **Industry restriction**:
   - Some analyses may want to focus on specific NAICS (e.g., energy-intensive industries)

### Quality Flags

- Check for outliers in emissions_squared (nonlinear effects)
- Verify company_age > 0 (no forecasting data)
- Flag if carbon_price_real_2015 > threshold (policy changes)

---

## CITATIONS & REFERENCES

**GHGRP Data**:
Environment and Climate Change Canada. "Greenhouse Gas Reporting Program (GHGRP)."
https://www.canada.ca/en/environment-climate-change/services/climate-change/pricing-pollution-how-it-will-work/industry/facility-greenhouse-gas-emissions.html

**Patent Data**:
Canadian Intellectual Property Office (CIPO). "Canadian Patents Database."
https://www.ic.gc.ca/eic/site/cipointernet-internetopic.nsf/eng/Home

**IPC-NAICS Mapping**:
Based on OECD Technology Concordance tables mapping IPC codes to NAICS sectors.

---



