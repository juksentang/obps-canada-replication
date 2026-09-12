#!/usr/bin/env python3
"""
Stage 1: unzip and standardise the Statistics Canada tables (GDP by industry, IPPI, RMPI, supply-use).
Input : data/raw/statcan/{gdp,price,sut}/*.zip|*.csv
Output: data/processed/2_standardized/statcan_{gdp,ippi,rmpi,sut}_v1_20251022.csv
Log   : data/metadata/statcan_extraction_log_20251022.txt
"""

import zipfile
import pandas as pd
import os
import sys
from datetime import datetime
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
STATCAN_RAW_PATH = str(DATA / 'raw' / 'statcan')
STATCAN_PROCESSED_PATH = str(DATA / 'processed' / '2_standardized')
METADATA_FILE = str(DATA / 'metadata' / 'statcan_extraction_log_20251022.txt')

# Ensure output directory exists
os.makedirs(STATCAN_PROCESSED_PATH, exist_ok=True)
os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)

def log_message(msg, print_also=True):
    """Log message to both console and file"""
    with open(METADATA_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

def extract_zip_files(directory):
    """Extract all ZIP files in a directory"""
    extracted_files = []
    zip_files = glob.glob(os.path.join(directory, "*.zip"))

    for zip_file in zip_files:
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                extract_dir = os.path.dirname(zip_file)
                zip_ref.extractall(extract_dir)
                extracted_files.extend(zip_ref.namelist())
            log_message(f"OK: Extracted: {os.path.basename(zip_file)}")
        except Exception as e:
            log_message(f"FAILED: Error extracting {zip_file}: {str(e)}")

    return extracted_files

def find_csv_file(directory, pattern):
    """Find CSV file matching pattern"""
    csv_files = glob.glob(os.path.join(directory, f"*{pattern}*.csv"))
    if csv_files:
        return csv_files[0]
    return None

def process_gdp_data():
    """Process StatCan GDP data"""
    log_message("\n[GDP Data Processing]")

    # Find and read GDP annual file
    gdp_file = find_csv_file(os.path.join(STATCAN_RAW_PATH, "gdp"), "36100402")

    if not gdp_file:
        log_message("FAILED: GDP annual file not found")
        return None

    try:
        log_message(f"Processing: {os.path.basename(gdp_file)}")

        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(gdp_file, encoding=encoding)
                log_message(f"OK: Loaded with encoding: {encoding}")
                break
            except:
                continue

        log_message(f"  - Original shape: {df.shape}")
        log_message(f"  - Columns: {list(df.columns)[:5]}... (showing first 5)")

        # Save processed version
        output_file = os.path.join(STATCAN_PROCESSED_PATH, "statcan_gdp_v1_20251022.csv")
        df.to_csv(output_file, index=False, encoding='utf-8')
        log_message(f"OK: Saved processed GDP data: {output_file}")

        return df

    except Exception as e:
        log_message(f"FAILED: Error processing GDP: {str(e)}")
        return None

def process_price_data():
    """Process StatCan price indices (IPPI, RMPI)"""
    log_message("\n[Price Index Data Processing]")

    price_files = glob.glob(os.path.join(STATCAN_RAW_PATH, "price", "*18100265*.csv"))
    price_files += glob.glob(os.path.join(STATCAN_RAW_PATH, "price", "*18100268*.csv"))

    if not price_files:
        log_message("FAILED: Price index files not found")
        return []

    processed_dfs = []

    for price_file in price_files:
        try:
            log_message(f"Processing: {os.path.basename(price_file)}")

            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(price_file, encoding=encoding)
                    log_message(f"OK: Loaded with encoding: {encoding}")
                    break
                except:
                    continue

            log_message(f"  - Shape: {df.shape}")

            # Identify index type
            if "18100265" in price_file:
                index_type = "IPPI"  # Industrial Product Price Index
                output_file = os.path.join(STATCAN_PROCESSED_PATH, "statcan_ippi_v1_20251022.csv")
            else:
                index_type = "RMPI"  # Raw Material Price Index
                output_file = os.path.join(STATCAN_PROCESSED_PATH, "statcan_rmpi_v1_20251022.csv")

            df.to_csv(output_file, index=False, encoding='utf-8')
            log_message(f"OK: Saved {index_type}: {output_file}")
            processed_dfs.append(df)

        except Exception as e:
            log_message(f"FAILED: Error processing {os.path.basename(price_file)}: {str(e)}")

    return processed_dfs

def process_sut_data():
    """Process Supply-Use Table (SUT) data"""
    log_message("\n[Supply-Use Table (SUT) Processing]")

    sut_files = glob.glob(os.path.join(STATCAN_RAW_PATH, "sut", "*.csv"))

    if not sut_files:
        log_message("FAILED: SUT files not found")
        return None

    try:
        # Focus on the main SUT file (36100478)
        sut_file = [f for f in sut_files if "36100478" in f]
        if not sut_file:
            sut_file = sut_files[0:1]

        sut_file = sut_file[0] if sut_file else None

        if sut_file:
            log_message(f"Processing: {os.path.basename(sut_file)}")

            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(sut_file, encoding=encoding)
                    log_message(f"OK: Loaded with encoding: {encoding}")
                    break
                except:
                    continue

            log_message(f"  - Shape: {df.shape}")

            output_file = os.path.join(STATCAN_PROCESSED_PATH, "statcan_sut_v1_20251022.csv")
            df.to_csv(output_file, index=False, encoding='utf-8')
            log_message(f"OK: Saved SUT data: {output_file}")

            return df

    except Exception as e:
        log_message(f"FAILED: Error processing SUT: {str(e)}")

    return None

def main():
    # Initialize log file
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(f"StatCan Data Extraction Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting StatCan data extraction and preparation")
    log_message(f"Input directory: {STATCAN_RAW_PATH}")

    # Step 1: Extract ZIP files
    log_message("\n[Step 1] Extracting ZIP files...")
    extract_zip_files(os.path.join(STATCAN_RAW_PATH, "gdp"))
    extract_zip_files(os.path.join(STATCAN_RAW_PATH, "price"))
    extract_zip_files(os.path.join(STATCAN_RAW_PATH, "sut"))

    # Step 2: Process data
    log_message("\n[Step 2] Processing data sources...")

    gdp_data = process_gdp_data()
    price_data = process_price_data()
    sut_data = process_sut_data()

    # Step 3: Summary
    log_message("\n[Step 3] Summary")
    log_message(f"  - GDP data: {'OK: Processed' if gdp_data is not None else 'FAILED: Failed'}")
    log_message(f"  - Price indices: OK: Processed {len(price_data)} files" if price_data else "  - Price indices: FAILED: Failed")
    log_message(f"  - SUT data: {'OK: Processed' if sut_data is not None else 'FAILED: Failed'}")

    log_message("\n" + "="*80)
    log_message("OK: StatCan data extraction COMPLETED")
    log_message(f"Output directory: {STATCAN_PROCESSED_PATH}")
    log_message("="*80)

if __name__ == "__main__":
    main()
