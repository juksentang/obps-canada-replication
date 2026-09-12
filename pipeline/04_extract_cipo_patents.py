#!/usr/bin/env python3
"""
Stage 1: unzip the CIPO patent bulk files (main tables, titles, IPC and CPC classifications first;
abstract, claim and disclosure archives are deferred) and record an extraction plan.
Input : data/raw/patents/cipo/*.zip
Output: extracted CSV/TXT files next to the archives; data/metadata/cipo_extraction_plan_20251022.json
Log   : data/metadata/cipo_extraction_log_20251022.txt
"""

import zipfile
import os
import sys
from datetime import datetime
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CIPO_RAW_PATH = str(DATA / 'raw' / 'patents' / 'cipo')
CIPO_PROCESSED_PATH = str(DATA / 'processed' / '2_standardized')
METADATA_FILE = str(DATA / 'metadata' / 'cipo_extraction_log_20251022.txt')

# Prioritize extraction of these file types
PRIORITY_PATTERNS = [
    "PT_main",         # Main patent data (HIGHEST PRIORITY)
    "PT_title",        # Patent titles
    "PT_IPC",          # IPC classifications
    "PT_CPC",          # CPC classifications
]

# DEFER: These are large but less critical initially
DEFER_PATTERNS = [
    "PT_abstract",     # Patent abstracts
    "PT_claim",        # Patent claims
    "PT_disclosure",   # Patent disclosures
]

# Ensure output directory exists
os.makedirs(CIPO_PROCESSED_PATH, exist_ok=True)
os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)

def log_message(msg, print_also=True):
    """Log message to both console and file"""
    with open(METADATA_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    if print_also:
        print(msg)

def categorize_zip_files():
    """Categorize ZIP files by priority"""
    all_zips = glob.glob(os.path.join(CIPO_RAW_PATH, "*.zip"))

    priority_zips = []
    defer_zips = []

    for zip_file in all_zips:
        basename = os.path.basename(zip_file)
        is_priority = any(pattern in basename for pattern in PRIORITY_PATTERNS)

        if is_priority:
            priority_zips.append(zip_file)
        else:
            defer_zips.append(zip_file)

    return priority_zips, defer_zips

def extract_zip_files(zip_files, category="priority"):
    """Extract ZIP files from a list"""
    log_message(f"\n[Extracting {category.upper()} CIPO files]")

    extracted_count = 0
    error_count = 0
    total_size = 0

    for i, zip_file in enumerate(zip_files, 1):
        basename = os.path.basename(zip_file)
        file_size = os.path.getsize(zip_file) / (1024*1024)  # Convert to MB
        total_size += file_size

        try:
            log_message(f"  [{i}/{len(zip_files)}] Extracting: {basename} ({file_size:.1f} MB)")

            # Extract to the same directory
            extract_dir = os.path.dirname(zip_file)
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            extracted_count += 1

            # Show progress every 10 files
            if i % 10 == 0:
                log_message(f"    Progress: {i}/{len(zip_files)} extracted, ~{total_size:.0f} MB processed")

        except Exception as e:
            log_message(f"  FAILED: Error extracting {basename}: {str(e)}")
            error_count += 1

    log_message(f"OK: Extraction complete: {extracted_count} successful, {error_count} errors")
    log_message(f"  Total files processed: {len(zip_files)}, Total size: {total_size:.0f} MB")

    return extracted_count, error_count

def count_extracted_files():
    """Count extracted files by type"""
    log_message("\n[Counting Extracted Files]")

    file_extensions = ['.csv', '.txt', '.xml', '.json']
    file_counts = {}

    for ext in file_extensions:
        files = glob.glob(os.path.join(CIPO_RAW_PATH, f"**/*{ext}"), recursive=True)
        if files:
            file_counts[ext] = len(files)
            log_message(f"  {ext} files: {len(files)}")

    return file_counts

def find_and_summarize_green_patents():
    """Find Y02/Y04S patent files and create summary"""
    log_message("\n[Green Patent Summary]")

    # Look for CPC classification files
    cpc_files = glob.glob(os.path.join(CIPO_RAW_PATH, "**/*CPC*.csv"), recursive=True)
    cpc_files += glob.glob(os.path.join(CIPO_RAW_PATH, "**/*cpc*.csv"), recursive=True)

    log_message(f"CPC classification files found: {len(cpc_files)}")

    # Create placeholder for green patent processing
    green_patent_summary = {
        'status': 'Pending detailed extraction',
        'target_classes': ['Y02', 'Y04S'],
        'cpc_files_found': len(cpc_files),
        'extraction_priority': 'High - required for the green patent variable'
    }

    return green_patent_summary

def create_extraction_plan():
    """Create and save a detailed extraction plan"""
    log_message("\n[Creating Extraction Plan]")

    plan = {
        'phase': 'Stage 1: CIPO patent data extraction',
        'total_zip_files': len(glob.glob(os.path.join(CIPO_RAW_PATH, "*.zip"))),
        'date_created': datetime.now().isoformat(),
        'priority_approach': {
            '1_extract': PRIORITY_PATTERNS,
            '2_defer': DEFER_PATTERNS,
            'rationale': 'Main patent tables and CPC classifications are needed first for the green patent variable'
        },
        'next_steps': [
            'Extract main patent tables (PT_main_*.zip)',
            'Filter for Y02 and Y04S CPC classifications',
            'Standardize applicant names',
            'Create firm-year panel with patent counts',
            'Link to GHGRP facility-level data'
        ]
    }

    plan_file = str(DATA / 'metadata' / 'cipo_extraction_plan_20251022.json')
    try:
        with open(plan_file, 'w') as f:
            json.dump(plan, f, indent=2)
        log_message(f"OK: Created extraction plan: {plan_file}")
    except Exception as e:
        log_message(f"FAILED: Error creating plan: {str(e)}")

    return plan

def main():
    # Initialize log file
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(f"CIPO Patent Data Extraction Log\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

    log_message("OK: Starting CIPO patent data extraction")
    log_message(f"Input directory: {CIPO_RAW_PATH}")

    # Step 1: Categorize ZIP files
    log_message("\n[Step 1] Categorizing CIPO ZIP files...")
    priority_zips, defer_zips = categorize_zip_files()

    log_message(f"  - Priority files: {len(priority_zips)}")
    log_message(f"    Examples: PT_main, PT_IPC, PT_CPC, PT_title")
    log_message(f"  - Deferred files: {len(defer_zips)}")
    log_message(f"    Examples: PT_abstract, PT_claim, PT_disclosure")

    # Step 2: Extract priority files
    log_message("\n[Step 2] Extracting PRIORITY patent files (main tables + classifications)...")
    log_message("This may take 30-60 minutes depending on disk speed")

    if priority_zips:
        priority_success, priority_errors = extract_zip_files(priority_zips, "priority")
    else:
        log_message("No priority files found to extract")
        priority_success = 0
        priority_errors = 0

    # Step 3: Note deferred extraction
    log_message("\n[Step 3] Deferred file extraction")
    log_message(f"{len(defer_zips)} large files deferred to later phase")
    log_message("  Reason: the green patent variable needs only the main tables and classifications")
    log_message("  Status: Will extract PT_abstract, PT_claim if needed for analysis")

    # Step 4: Count extracted files
    file_counts = count_extracted_files()

    # Step 5: Green patent summary
    green_summary = find_and_summarize_green_patents()

    # Step 6: Create extraction plan
    plan = create_extraction_plan()

    # Final Summary
    log_message("\n[Step 7] Summary")
    log_message(f"  - Total ZIP files: {len(priority_zips) + len(defer_zips)}")
    log_message(f"  - Priority extractions: {priority_success} successful, {priority_errors} errors")
    log_message(f"  - Data files extracted: {sum(file_counts.values()) if file_counts else 'TBD'}")
    log_message(f"  - Green patent classification target: Y02 and Y04S")

    log_message("\n" + "="*80)
    log_message("OK: CIPO data extraction INITIATED")
    log_message(f"Log file: {METADATA_FILE}")
    log_message(f"Extraction plan: {DATA / 'metadata' / 'cipo_extraction_plan_20251022.json'}")
    log_message("="*80)

if __name__ == "__main__":
    main()
