#!/usr/bin/env bash
# Download the raw inputs of the data pipeline into data/raw/ (run from the repository root: bash data/download.sh).
#   1. GHGRP facility emissions (Environment and Climate Change Canada)      -> data/raw/ghgrp
#   2. Statistics Canada bulk tables (supply-use, price indices, GDP)         -> data/raw/statcan/{sut,price,gdp}
#   3. CIPO patent researcher datasets and the CPC Y scheme                   -> data/raw/patents/{cipo,cpc}
#   4. Policy web pages (HTML snapshots, for reference)                       -> data/policy
#   5. 2021 census boundary files (provinces/territories)                     -> data/raw/geographic
# The CIPO bulk data is about 20 GB. All sources are public; see data/README.md for licences.
set -euo pipefail

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing $1. Please install."; exit 1; }; }
need curl
need wget
mkdir -p data/raw/{ghgrp,statcan/{sut,price,gdp},patents/{cipo,cpc},geographic} data/policy data/logs

LOG="data/logs/download_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
echo "==> Starting downloads into ./data/raw (log: $LOG)"

head_ok () { curl -IsSfL "$1" >/dev/null 2>&1; }
fetch () {
  local url="$1"; local outdir="$2"; local extra="${3:-}"
  mkdir -p "$outdir"
  echo "---- downloading: $url"
  wget -c --retry-connrefused --waitretry=1 --read-timeout=30 --timeout=30 -t 3 --no-check-certificate -P "$outdir" $extra "$url"
}

# ---------- 1) GHGRP facility emissions (directory crawl of CSV/XLSX files) ----------
GHGRP_DIR="https://data-donnees.az.ec.gc.ca/data/substances/monitor/greenhouse-gas-reporting-program-ghgrp-facility-greenhouse-gas-ghg-data/"
echo "==> GHGRP directory crawl (CSV/XLSX)..."
wget -r -np -nd -e robots=off \
     -A ".csv,.CSV,.xlsx,.XLSX" \
     --reject "index.html*,*.md5,*.sha*" \
     --no-check-certificate \
     --directory-prefix=data/raw/ghgrp \
     "$GHGRP_DIR" || true
# key files (retried individually if the crawl missed them)
declare -a GHGRP_KEYS=(
  "PDGES-GHGRP-GHGEmissionsGES-2004-Present.csv"
  "PDGES-GHGRP-GHGEmissionsSourcesGES-2022-2023.csv"
  "Lisez moi-Read me-Emissions.csv"
  "Lisez moi-Read me-Source.csv"
  "Lisezmoi-Readme.csv"
)
for f in "${GHGRP_KEYS[@]}"; do
  u="${GHGRP_DIR}${f}"
  head_ok "$u" && fetch "$u" "data/raw/ghgrp" || echo "skip (not found now): $u"
done

# ---------- 2) Statistics Canada bulk tables (CSV and SDMX zips) ----------
# "Download entire table" links: CSV https://www150.statcan.gc.ca/n1/tbl/csv/<PID>-eng.zip, SDMX .../sdmx/<PID>-SDMX.zip,
# where <PID> is the table number without the trailing -0x (e.g. 36-10-0478-01 -> 36100478).
download_statcan_full () {
  local pid="$1"; local outdir="$2"
  mkdir -p "$outdir"
  local csv_zip="https://www150.statcan.gc.ca/n1/tbl/csv/${pid}-eng.zip"
  local sdmx_zip="https://www150.statcan.gc.ca/n1/tbl/sdmx/${pid}-SDMX.zip"
  for u in "$csv_zip" "$sdmx_zip"; do
    if head_ok "$u"; then fetch "$u" "$outdir"; else echo "not available (yet): $u"; fi
  done
}
echo "==> Statistics Canada supply-use tables (detail, provincial/territorial)"
download_statcan_full "36100478" "data/raw/statcan/sut"     # 36-10-0478-01
echo "==> Statistics Canada price indices (IPPI and RMPI)"
download_statcan_full "18100265" "data/raw/statcan/price"   # 18-10-0265-01 IPPI
download_statcan_full "18100268" "data/raw/statcan/price"   # 18-10-0268-01 RMPI
echo "==> Statistics Canada GDP by industry and province/territory (annual) and monthly national GDP"
download_statcan_full "36100402" "data/raw/statcan/gdp"     # 36-10-0402-0x (annual)
download_statcan_full "36100434" "data/raw/statcan/gdp"     # 36-10-0434-0x (monthly, optional)

# ---------- 3) Patent data ----------
echo "==> CPC scheme (Y and Y04S) for green-technology tagging"
fetch "https://www.uspto.gov/web/patents/classification/cpc/pdf/cpc-Y.pdf" "data/raw/patents/cpc"
fetch "https://www.cooperativepatentclassification.org/sites/default/files/cpc/scheme/Y/scheme-Y04S.pdf" "data/raw/patents/cpc"
echo "==> CIPO patent researcher datasets (all ZIP links on the page)"
CIPO_PAGE="https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/canadian-intellectual-property-statistics/patent-data-bibliographic-and-full-text-csv-and-txt"
curl -fsSLk "$CIPO_PAGE" | \
  grep -Eo 'https?://[^"'\'' ]+\.zip' | sort -u > data/raw/patents/cipo/_cipo_zip_links.txt || true
if [[ -s data/raw/patents/cipo/_cipo_zip_links.txt ]]; then
  while IFS= read -r url; do
    fetch "$url" "data/raw/patents/cipo"
  done < data/raw/patents/cipo/_cipo_zip_links.txt
else
  echo "WARN: no zip links parsed from the CIPO page; retry later or check the page structure."
fi

# ---------- 4) Policy pages (HTML snapshots) ----------
echo "==> Policy pages (HTML snapshots)"
declare -A POLICY_PAGES=(
  ["eccc_benchmark"]="https://www.canada.ca/en/environment-climate-change/services/climate-change/pricing-pollution-how-it-will-work/carbon-pollution-pricing-federal-benchmark-information.html"
  ["eccc_benchmark_update_2023_2030"]="https://www.canada.ca/en/environment-climate-change/services/climate-change/pricing-pollution-how-it-will-work/carbon-pollution-pricing-federal-benchmark-information/federal-benchmark-2023-2030.html"
  ["eccc_obps"]="https://www.canada.ca/en/environment-climate-change/services/climate-change/pricing-pollution-how-it-will-work/output-based-pricing-system.html"
  ["finance_entropy_cfd_2023_12_20"]="https://www.canada.ca/en/department-finance/news/2023/12/deputy-prime-minister-welcomes-the-canada-growth-funds-first-carbon-contract-for-difference.html"
  ["finance_entropy_visit_2024_08_19"]="https://www.canada.ca/en/department-finance/news/2024/08/deputy-prime-minister-visits-entropys-glacier-clean-gas-project-a-recipient-of-the-canada-growth-funds-first-carbon-contract-for-difference.html"
)
for name in "${!POLICY_PAGES[@]}"; do
  curl -fsSL "${POLICY_PAGES[$name]}" -o "data/policy/${name}.html" || echo "WARN: failed ${name}"
done

# ---------- 5) Geography: 2021 census boundary files (provinces/territories) ----------
echo "==> Geography: boundary files (portal page and provinces/territories shapefile)"
fetch "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21" "data/raw/geographic"
for cand in \
  "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files/boundaries/2021/lpr_000b21a_e.zip" \
  "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files/boundaries/2021/lpr_000b21a_f.zip"
do
  head_ok "$cand" && fetch "$cand" "data/raw/geographic" || echo "note: boundary ZIP not directly accessible at $cand (use the portal page)."
done

echo "==> All done."
find data/raw -maxdepth 3 -type f | sed 's/^/ - /'
