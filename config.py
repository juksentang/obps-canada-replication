"""Project-wide constants and directory layout for the data pipeline.

Usage:
    from config import PROJECT_DIR, DATA_DIR, ProcessingConfig
"""
from pathlib import Path

# ----------------------------------------------------------------------------- directories
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / 'data'
PIPELINE_DIR = PROJECT_DIR / 'pipeline'
ANALYSIS_DIR = PROJECT_DIR / 'analysis'
PAPER_DIR = PROJECT_DIR / 'paper'
LOGS_DIR = PROJECT_DIR / 'logs'

RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'
ANALYSIS_READY_DIR = DATA_DIR / 'analysis_ready'
RAW_CLEAN_DIR = PROCESSED_DATA_DIR / '1_raw_clean'
STANDARDIZED_DIR = PROCESSED_DATA_DIR / '2_standardized'
VARIABLES_DIR = PROCESSED_DATA_DIR / '3_variables'
PANELS_DIR = PROCESSED_DATA_DIR / '4_panels'
MATRICES_DIR = PROCESSED_DATA_DIR / 'matrices'
METADATA_DIR = DATA_DIR / 'metadata'

GHGRP_RAW_DIR = RAW_DATA_DIR / 'ghgrp'
STATCAN_RAW_DIR = RAW_DATA_DIR / 'statcan'
PATENTS_RAW_DIR = RAW_DATA_DIR / 'patents'
GEOGRAPHIC_RAW_DIR = RAW_DATA_DIR / 'geographic'

# ----------------------------------------------------------------------------- parameters
class ProcessingConfig:
    """Processing parameters and constants."""
    EMISSION_MIN_YEAR = 2004
    EMISSION_MAX_YEAR = 2023
    PATENT_DEPRECIATION_RATE = 0.15   # perpetual-inventory depreciation of the green patent stock
    PATENT_MIN_YEAR = 2000
    PATENT_MAX_YEAR = 2024
    TREATMENT_YEAR = 2019             # first year of the binding national carbon-price floor
    NAICS_DIGIT_LEVEL = 3
    DEFAULT_ENCODING = 'utf-8'
    GHGRP_ENCODING = 'utf-8-sig'

class FileNameConfig:
    """File names used by the pipeline (version stamps are frozen so that names are reproducible)."""
    DATA_VERSION = "20251022"
    VERSION_SUFFIX = f"_{DATA_VERSION}"
    GHGRP_INPUT = "PDGES-GHGRP-GHGEmissionsGES-2004-Present.csv"
    GHGRP_SOURCES = "PDGES-GHGRP-GHGEmissionsSourcesGES-2022-2023.csv"
    GHGRP_CLEANED = f"ghgrp_cleaned_v1{VERSION_SUFFIX}.csv"
    EMISS_FT = f"emiss_ft_v1{VERSION_SUFFIX}.csv"
    INTENSITY_FT = f"intensity_ft_v1{VERSION_SUFFIX}.csv"
    EXPOSURE_PRICE = f"exposure_price_it_v1{VERSION_SUFFIX}.csv"
    FACILITY_PANEL = f"facility_year_panel_v1{VERSION_SUFFIX}.csv"
    GREEN_PATENTS = f"green_patents_identified_v1{VERSION_SUFFIX}.csv"
    ANALYSIS_PANEL = "analysis_ready_with_oil_controls.csv"

class VariableConfig:
    """Variable groups of the analysis-ready panel."""
    ID_VARS = ['company_id', 'company_name', 'year']
    GEO_VARS = ['province', 'naics_code_3digit']
    OUTCOME_VARS = ['total_emissions_co2e', 'intensity_co2e_per_m_gdp', 'green_patent_stock']
    PATENT_VARS = ['green_patent_stock', 'green_patent_count', 'unique_patents']
    CONTROL_VARS = ['company_age', 'num_facilities', 'ln_wti_price', 'ln_wti_price_lag1']

def ensure_directories_exist():
    """Create the processed-data and log directories if they do not exist."""
    for d in (RAW_CLEAN_DIR, STANDARDIZED_DIR, VARIABLES_DIR, PANELS_DIR, MATRICES_DIR, METADATA_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)

if __name__ == '__main__':
    print(f"Project directory: {PROJECT_DIR}")
    print(f"Data directory:    {DATA_DIR}")
    print(f"Years: {ProcessingConfig.EMISSION_MIN_YEAR}-{ProcessingConfig.EMISSION_MAX_YEAR}; "
          f"patent depreciation {ProcessingConfig.PATENT_DEPRECIATION_RATE:.0%}; treatment year {ProcessingConfig.TREATMENT_YEAR}")
