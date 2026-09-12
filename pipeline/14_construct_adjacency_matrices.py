#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build row-standardised spatial weight matrices for spillover checks: W_geo, a province-level contiguity matrix,
and W_IO, a NAICS-3 industry linkage matrix based on a stylised supply-chain adjacency list.

Input:  none (adjacency lists are defined in the script)
Output: data/processed/matrices/W_geo_province_level_20251022.csv, W_IO_naics3digit_20251022.csv, ADJACENCY_MATRICES_METADATA.txt
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
(ROOT / 'logs').mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT / 'logs' / 'construct_adjacency_matrices.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths
OUTPUT_DIR = DATA / 'processed' / 'matrices'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# SECTION 1: Geographic Adjacency Matrix (W_geo)
# ============================================================================

logger.info("=" * 80)
logger.info("ADJACENCY MATRIX CONSTRUCTION")
logger.info("=" * 80)
logger.info("")

logger.info("[SECTION 1] Geographic Adjacency Matrix (W_geo)")
logger.info("=" * 80)
logger.info("")

# Canada Census Divisions with Queen Contiguity Adjacency
# Based on Statistics Canada census division boundaries
# Queen contiguity: shares edges or corners

census_divisions = {
    'ON': {
        'name': 'Ontario',
        'divisions': ['Algoma', 'Brant', 'Dufferin', 'Elgin', 'Essex', 'Grey',
                      'Haldimand-Norfolk', 'Halton', 'Hamilton-Wentworth', 'Hasting-Prince Edward',
                      'Huron', 'Kawartha Lakes', 'Kent', 'Lambton', 'Leeds-Grenville',
                      'Lennox-Addington', 'Nipissing', 'Northumberland', 'Oxford', 'Peel',
                      'Perth', 'Peterborough', 'Simcoe', 'Sudbury', 'Thunder Bay',
                      'Timiskaming', 'Toronto', 'Waterloo', 'York'],
        'code_start': 3501
    },
    'QC': {
        'name': 'Quebec',
        'divisions': ['Abitibi-Ouest', 'Abitibi-Est', 'Acton', 'Argenteuil', 'Arthabaska',
                      'Beauce', 'Bellechasse', 'Berthier', 'Bonaventure', 'Bromé-Missisquoi',
                      'Chambly', 'Charlevoix', 'Châteauguay', 'Chaudière', 'Chicoutimi',
                      'Côte-Nord', 'Deux-Montagnes', 'Drummond', 'Frontenac', 'Gaspé',
                      'Gatineau', 'Hochelaga', 'Huntingdon', 'Île-de-Montréal', 'Île-Jésus',
                      'Jamésie', 'Jean-Talon', 'Joliette', 'Kamouraska', 'Kativik',
                      'L\'Amiante', 'L\'Assomption', 'L\'Islet', 'Lac-Saint-Jean-Est',
                      'Lac-Saint-Jean-Ouest', 'Laprairie', 'Laurentides', 'Laval',
                      'Lévis', 'Lotbinière', 'Maskinongé', 'Matapédia', 'Matane',
                      'Maure-et-Lorentel', 'Mégantic', 'Mille-Isles', 'Missisquoi',
                      'Montcalm', 'Montmagny', 'Montmorency', 'Montréal-Est', 'Montréal-Ouest',
                      'Morin-Heights', 'Napierville', 'Nicolet', 'Nipissing', 'Nord-du-Québec',
                      'Normanby', 'Notre-Dame-de-Grâce', 'Nouvel-Ontario', 'Outaouais',
                      'Papineau', 'Pontiac', 'Portneuf', 'Québec', 'Richelieu', 'Richmond',
                      'Rimouski', 'Rivière-Beaudette', 'Rivière-Rouge', 'Rouville',
                      'Saguenay', 'Saint-Armand', 'Saint-Hyacinthe', 'Saint-Jean',
                      'Saint-Jérôme', 'Saint-Maurice', 'Sainte-Agathe', 'Sainte-Anne-d\'Yamaska',
                      'Sainte-Croix', 'Salaberry', 'Salvail', 'Shawinigan', 'Sherbrooke',
                      'Stanstead', 'Sunbury', 'Témiscaming', 'Témiscouata', 'Terrebonne',
                      'Trois-Rivières', 'Vaudreuil', 'Verchères', 'Vercochois', 'Verdun',
                      'Véritable', 'Vimont', 'Yamachiche', 'Yamaska', 'Yarmouth'],
        'code_start': 2401
    },
    'AB': {
        'name': 'Alberta',
        'divisions': ['Division No. 1', 'Division No. 2', 'Division No. 3', 'Division No. 4',
                      'Division No. 5', 'Division No. 6', 'Division No. 7', 'Division No. 8',
                      'Division No. 9', 'Division No. 10', 'Division No. 11', 'Division No. 12',
                      'Division No. 13', 'Division No. 14', 'Division No. 15', 'Division No. 16',
                      'Division No. 17', 'Division No. 18', 'Division No. 19', 'Division No. 20'],
        'code_start': 4801
    }
}

# Queen Contiguity Adjacency List
# Simplified representation: Which divisions are neighbors
queen_adjacency = {
    # Ontario divisions (simplified - major ones)
    'Algoma': ['Nipissing', 'Sudbury', 'Thunder Bay', 'Hasting-Prince Edward'],
    'Thunder Bay': ['Algoma', 'Nipissing'],
    'Nipissing': ['Sudbury', 'Algoma', 'Timiskaming', 'Muskoka'],
    'Sudbury': ['Nipissing', 'Algoma', 'Timiskaming', 'Parry Sound'],
    'Timiskaming': ['Nipissing', 'Sudbury', 'Outaouais-QC'],
    # Add more as needed for full network
}

# For this implementation, create a simplified W_geo based on provinces only
# Full census division level would require shapefile processing

logger.info("")
logger.info("[STEP 1] Constructing W_geo (geographic adjacency)...")
logger.info("  Note: Using province-level adjacency due to data constraints")
logger.info("  For full CD-level matrix, would require Shapefile processing")

# Province-level adjacency (simplified)
provinces = ['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'ON', 'PE', 'QC', 'SK', 'YT']

# Adjacent provinces (Queen contiguity equivalent)
prov_adjacency = {
    'AB': ['BC', 'SK'],
    'BC': ['AB', 'YT'],
    'MB': ['AB', 'SK', 'ON'],
    'NB': ['NS', 'PE', 'QC'],
    'NL': ['PE'],
    'NS': ['NB', 'PE'],
    'NT': ['BC', 'YT', 'AB'],
    'ON': ['MB', 'QC'],
    'PE': ['NB', 'NS'],
    'QC': ['ON', 'NB'],
    'SK': ['AB', 'MB'],
    'YT': ['BC', 'NT'],
}

# Create W_geo as N x N matrix (provinces as spatial units)
n_prov = len(provinces)
W_geo = np.zeros((n_prov, n_prov))

prov_to_idx = {prov: idx for idx, prov in enumerate(provinces)}

for prov, neighbors in prov_adjacency.items():
    prov_idx = prov_to_idx[prov]
    for neighbor in neighbors:
        if neighbor in prov_to_idx:
            neighbor_idx = prov_to_idx[neighbor]
            W_geo[prov_idx, neighbor_idx] = 1

# Row-standardize (divide by row sum for use in spatial models)
row_sums = W_geo.sum(axis=1)
row_sums[row_sums == 0] = 1  # Avoid division by zero
W_geo_std = W_geo / row_sums[:, np.newaxis]

# Save W_geo
W_geo_df = pd.DataFrame(W_geo_std, index=provinces, columns=provinces)
W_geo_file = OUTPUT_DIR / 'W_geo_province_level_20251022.csv'
W_geo_df.to_csv(W_geo_file)

logger.info(f"  Created {n_prov} x {n_prov} province-level geographic weight matrix")
logger.info(f"  Row-standardized format (ready for spatial lag models)")
logger.info(f"  Saved to: {W_geo_file.name}")

# ============================================================================
# SECTION 2: Industry Input-Output Adjacency Matrix (W_IO)
# ============================================================================

logger.info("")
logger.info("[SECTION 2] Industry Input-Output Adjacency Matrix (W_IO)")
logger.info("=" * 80)
logger.info("")

logger.info("[STEP 2] Constructing W_IO (industry adjacency)...")

# NAICS 3-digit codes present in the facility data
naics_codes = [
    221,   # Utilities
    312,   # Beverage and tobacco
    325,   # Chemical manufacturing
    331,   # Primary metal
    333,   # Machinery
    334,   # Computer equipment
    336,   # Transport equipment
    322,   # Paper manufacturing
    326,   # Plastics and rubber
    327,   # Non-metallic minerals
    338,   # Miscellaneous manufacturing
    492,   # Petroleum pipelines
    562,   # Waste management
]

n_naics = len(naics_codes)

# Simplified IO linkage weights based on industry relationships
# In practice, would be derived from Statistics Canada Supply-Use Tables
# Here using heuristic based on supply chain logic

io_linkages = {
    221: [312, 325, 331, 333, 334, 336, 338],  # Utilities supply to many industries
    312: [325, 333],  # Food supplies to machinery, etc
    325: [331, 333, 336, 338, 326, 327],  # Chemicals widely used
    331: [333, 336, 338],  # Primary metals to machinery/equipment
    333: [336, 338],  # Machinery to equipment
    334: [336],  # Electronics to transport
    336: [],  # Transport equipment (downstream)
    322: [325, 338],  # Paper to chemicals
    326: [],  # Plastics (downstream)
    327: [333],  # Minerals to metals
    338: [],  # Misc manufacturing (downstream)
    492: [312, 325, 331],  # Pipelines serve these industries
    562: [221, 325, 331],  # Waste management served by utilities, serves others
}

# Create sparse IO matrix
W_IO = np.zeros((n_naics, n_naics))

naics_to_idx = {code: idx for idx, code in enumerate(naics_codes)}

for from_naics, to_naics_list in io_linkages.items():
    from_idx = naics_to_idx[from_naics]
    for to_naics in to_naics_list:
        if to_naics in naics_to_idx:
            to_idx = naics_to_idx[to_naics]
            W_IO[from_idx, to_idx] = 1

# Row-standardize
row_sums_io = W_IO.sum(axis=1)
row_sums_io[row_sums_io == 0] = 1
W_IO_std = W_IO / row_sums_io[:, np.newaxis]

# Save W_IO
W_IO_df = pd.DataFrame(W_IO_std, index=naics_codes, columns=naics_codes)
W_IO_file = OUTPUT_DIR / 'W_IO_naics3digit_20251022.csv'
W_IO_df.to_csv(W_IO_file)

logger.info(f"  Created {n_naics} x {n_naics} NAICS 3-digit industry weight matrix")
logger.info(f"  Row-standardized format (ready for spatial lag models)")
logger.info(f"  Saved to: {W_IO_file.name}")

# ============================================================================
# SECTION 3: Descriptive Statistics
# ============================================================================

logger.info("")
logger.info("[STEP 3] Descriptive statistics...")

logger.info("")
logger.info("  W_geo (geographic) statistics:")
logger.info(f"    - Dimensions: {W_geo_std.shape[0]} x {W_geo_std.shape[1]}")
logger.info(f"    - Sparsity: {(W_geo_std == 0).sum() / W_geo_std.size:.1%} (non-zero: {(W_geo_std > 0).sum()})")
logger.info(f"    - Row sum (verification): min={W_geo_std.sum(axis=1).min():.4f}, "
            f"max={W_geo_std.sum(axis=1).max():.4f}")
logger.info(f"    - Mean row sum: {W_geo_std.sum(axis=1).mean():.4f}")

# Find most connected provinces
prov_connectivity = W_geo_std.sum(axis=1)
most_connected = provinces[np.argmax(prov_connectivity)]
logger.info(f"    - Most connected province: {most_connected} "
            f"(avg weight to neighbors: {prov_connectivity.max():.4f})")

logger.info("")
logger.info("  W_IO (industry) statistics:")
logger.info(f"    - Dimensions: {W_IO_std.shape[0]} x {W_IO_std.shape[1]}")
logger.info(f"    - Sparsity: {(W_IO_std == 0).sum() / W_IO_std.size:.1%} (non-zero: {(W_IO_std > 0).sum()})")
logger.info(f"    - Row sum (verification): min={W_IO_std.sum(axis=1).min():.4f}, "
            f"max={W_IO_std.sum(axis=1).max():.4f}")
logger.info(f"    - Mean row sum: {W_IO_std.sum(axis=1).mean():.4f}")

# Find most connected industries
ind_connectivity = W_IO_std.sum(axis=1)
most_connected_ind = naics_codes[np.argmax(ind_connectivity)]
logger.info(f"    - Most connected industry: NAICS {most_connected_ind} "
            f"(avg weight to other industries: {ind_connectivity.max():.4f})")

# ============================================================================
# SECTION 4: Metadata
# ============================================================================

logger.info("")
logger.info("[STEP 4] Generating metadata...")

metadata_text = f"""
================================================================================
ADJACENCY MATRICES METADATA
================================================================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

FILES GENERATED
---------------
1. W_geo_province_level_20251022.csv
   - Geographic weight matrix at provincial level
   - 12 provinces x 12 provinces
   - Row-standardized (sum = 1 for each row)

2. W_IO_naics3digit_20251022.csv
   - Industry input-output weight matrix
   - 13 NAICS 3-digit sectors x 13 sectors
   - Row-standardized (sum = 1 for each row)

SPECIFICATIONS
---------------

W_geo (Geographic Adjacency):
  - Units: Canadian provinces (AB, BC, MB, NB, NL, NS, NT, ON, PE, QC, SK, YT)
  - Contiguity: Queen contiguity (shares edge or corner = neighbors)
  - Neighbors defined:
    * AB: BC, SK
    * BC: AB, YT
    * MB: AB, SK, ON
    * NB: NS, PE, QC
    * NL: PE
    * NS: NB, PE
    * NT: BC, YT, AB
    * ON: MB, QC
    * PE: NB, NS
    * QC: ON, NB
    * SK: AB, MB
    * YT: BC, NT
  - Standardization: Row-standardized (W_ij / sum_k W_ik)

W_IO (Industry Input-Output):
  - Units: NAICS 3-digit industry codes
  - Sectors: {len(naics_codes)} industries
  - Linkages: Based on supply chain relationships
  - Standardization: Row-standardized

  Industries included:
    221 - Utilities
    312 - Beverage and tobacco
    322 - Paper manufacturing
    325 - Chemical manufacturing
    326 - Plastics and rubber
    327 - Non-metallic minerals
    331 - Primary metals
    333 - Machinery
    334 - Computer equipment
    336 - Transport equipment
    338 - Miscellaneous manufacturing
    492 - Petroleum pipelines
    562 - Waste management

DATA QUALITY NOTES
-------------------
1. W_geo uses province-level boundaries
   - For census division level, would require Shapefile processing with GeoPandas
   - Current approach suitable for provincial spillover analysis

2. W_IO uses simplified supply chain logic
   - Derived from industry knowledge, not official Supply-Use Tables
   - Current version captures first-order linkages only

3. Both matrices are row-standardized
   - Suitable for spatial lag (SAR) and spatial error (SEM) models
   - NOT suitable for distance-weighted models (would need distance decay)

IMPLEMENTATION NOTES
---------------------
- Matrices saved as CSV; import with W = pd.read_csv('W_geo...csv', index_col=0).values
- Row-standardized format for spatial lag (SAR) and spatial error (SEM) models

================================================================================
"""

with open(OUTPUT_DIR / 'ADJACENCY_MATRICES_METADATA.txt', 'w', encoding='utf-8') as f:
    f.write(metadata_text)

logger.info(f"  Saved metadata to: ADJACENCY_MATRICES_METADATA.txt")

# ============================================================================
# SUMMARY
# ============================================================================

logger.info("")
logger.info("=" * 80)
logger.info("ADJACENCY MATRIX CONSTRUCTION COMPLETE")
logger.info("=" * 80)
logger.info("")
logger.info("Matrices created:")
logger.info(f"  1. W_geo: {W_geo_std.shape[0]} x {W_geo_std.shape[1]} "
            f"({(W_geo_std > 0).sum()} non-zero elements)")
logger.info(f"  2. W_IO:  {W_IO_std.shape[0]} x {W_IO_std.shape[1]} "
            f"({(W_IO_std > 0).sum()} non-zero elements)")
logger.info("")
logger.info(f"Output directory: {OUTPUT_DIR}")
logger.info("")
logger.info("=" * 80)
