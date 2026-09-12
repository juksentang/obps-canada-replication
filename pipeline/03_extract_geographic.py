#!/usr/bin/env python3
"""
Stage 1: unzip the provincial boundary shapefiles and write the province code table.
Input : data/raw/geo/*.zip
Output: data/processed/2_standardized/shapefiles/, data/processed/2_standardized/canadian_provinces_metadata.csv
Log   : data/metadata/geographic_extraction_log_20251022.txt
"""

import zipfile
import os
import sys
from datetime import datetime
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
GEO_RAW_PATH = str(DATA / 'raw' / 'geo')
GEO_PROCESSED_PATH = str(DATA / 'processed' / '2_standardized')
METADATA_FILE = str(DATA / 'metadata' / 'geographic_extraction_log_20251022.txt')

# Ensure output directory exists
os.makedirs(GEO_PROCESSED_PATH, exist_ok=True)
os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)

def log_message(msg, print_also=True):
    """Log message to both console and file"""
    with open(METADATA_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

def extract_shapefile_data():
    """Extract Shapefile data from ZIP files"""
    log_message("\n[Shapefile Extraction]")

    zip_files = glob.glob(os.path.join(GEO_RAW_PATH, "*.zip"))

    if not zip_files:
        log_message("FAILED: No ZIP files found in geographic data folder")
        return []

    extracted_info = []

    for zip_file in zip_files:
        try:
            log_message(f"Extracting: {os.path.basename(zip_file)}")

            # Create extraction directory
            extract_dir = os.path.join(GEO_PROCESSED_PATH, "shapefiles")
            os.makedirs(extract_dir, exist_ok=True)

            # Extract files
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                extracted_files = zip_ref.namelist()

                # Extract all files
                zip_ref.extractall(extract_dir)

                # Log extracted files
                shp_files = [f for f in extracted_files if f.endswith('.shp')]
                shx_files = [f for f in extracted_files if f.endswith('.shx')]
                dbf_files = [f for f in extracted_files if f.endswith('.dbf')]

                log_message(f"  - .shp files: {len(shp_files)}")
                log_message(f"  - .shx files: {len(shx_files)}")
                log_message(f"  - .dbf files: {len(dbf_files)}")

                extracted_info.append({
                    'zip_file': os.path.basename(zip_file),
                    'shp_count': len(shp_files),
                    'shx_count': len(shx_files),
                    'dbf_count': len(dbf_files),
                    'total_files': len(extracted_files)
                })

            log_message(f"OK: Extracted {len(extracted_files)} files from {os.path.basename(zip_file)}")

        except Exception as e:
            log_message(f"FAILED: Error extracting {os.path.basename(zip_file)}: {str(e)}")

    return extracted_info

def verify_shapefile_integrity():
    """Verify extracted Shapefile integrity"""
    log_message("\n[Shapefile Integrity Verification]")

    extract_dir = os.path.join(GEO_PROCESSED_PATH, "shapefiles")

    # Count Shapefiles
    shp_files = glob.glob(os.path.join(extract_dir, "**/*.shp"), recursive=True)
    shx_files = glob.glob(os.path.join(extract_dir, "**/*.shx"), recursive=True)
    dbf_files = glob.glob(os.path.join(extract_dir, "**/*.dbf"), recursive=True)

    log_message(f"  - .shp files found: {len(shp_files)}")
    log_message(f"  - .shx files found: {len(shx_files)}")
    log_message(f"  - .dbf files found: {len(dbf_files)}")

    # Check for complete Shapefiles (need .shp, .shx, and .dbf)
    complete = 0
    for shp_file in shp_files:
        base = os.path.splitext(shp_file)[0]
        if os.path.exists(f"{base}.shx") and os.path.exists(f"{base}.dbf"):
            complete += 1
            log_message(f"  OK: Complete: {os.path.basename(shp_file)}")

    log_message(f"OK: Complete Shapefiles: {complete}/{len(shp_files)}")

    return len(shp_files) > 0

def create_province_metadata():
    """Create metadata for Canadian provinces"""
    log_message("\n[Province Metadata Creation]")

    # Standard Canadian provinces and territories
    provinces_data = {
        'Province_Code': ['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'],
        'Province_Name': [
            'Alberta',
            'British Columbia',
            'Manitoba',
            'New Brunswick',
            'Newfoundland and Labrador',
            'Nova Scotia',
            'Northwest Territories',
            'Nunavut',
            'Ontario',
            'Prince Edward Island',
            'Quebec',
            'Saskatchewan',
            'Yukon'
        ]
    }

    try:
        import pandas as pd
        df_provinces = pd.DataFrame(provinces_data)

        metadata_file = os.path.join(GEO_PROCESSED_PATH, "canadian_provinces_metadata.csv")
        df_provinces.to_csv(metadata_file, index=False, encoding='utf-8')
        log_message(f"OK: Created province metadata: {metadata_file}")
        log_message(f"  - Provinces: {len(df_provinces)}")

        return df_provinces

    except Exception as e:
        log_message(f"FAILED: Error creating province metadata: {str(e)}")
        return None

def main():
    # Initialize log file
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Geographic Data Extraction Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting geographic boundary data extraction")
    log_message(f"Input directory: {GEO_RAW_PATH}")

    # Step 1: Extract Shapefiles
    log_message("\n[Step 1] Extracting Shapefiles...")
    extracted_info = extract_shapefile_data()

    # Step 2: Verify integrity
    log_message("\n[Step 2] Verifying Shapefile integrity...")
    is_valid = verify_shapefile_integrity()

    # Step 3: Create province metadata
    log_message("\n[Step 3] Creating province metadata...")
    provinces_df = create_province_metadata()

    # Step 4: Summary
    log_message("\n[Step 4] Summary")
    log_message(f"  - ZIP files extracted: {len(extracted_info)}")
    log_message(f"  - Shapefiles valid: {'OK: Yes' if is_valid else 'FAILED: No'}")
    log_message(f"  - Province metadata: {'OK: Created' if provinces_df is not None else 'FAILED: Failed'}")

    log_message("\n" + "="*80)
    log_message("OK: Geographic data extraction COMPLETED")
    log_message(f"Output directory: {GEO_PROCESSED_PATH}")
    log_message(f"  - Shapefiles: {GEO_PROCESSED_PATH}/shapefiles/")
    log_message(f"  - Metadata: {GEO_PROCESSED_PATH}/canadian_provinces_metadata.csv")
    log_message("="*80)

if __name__ == "__main__":
    main()
