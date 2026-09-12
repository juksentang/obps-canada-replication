# Reproduce every table, figure and number in the paper: estimation -> LaTeX tables/figures -> number macros.
#   make all        full run (scripts 81 and 82 take roughly 20-40 minutes each)
#   make estimates  estimation scripts only
# Single-threaded BLAS: the bootstrap and permutation loops fit thousands of small regressions, which run far faster
# (and deterministically across machines) without BLAS thread oversubscription.
export OMP_NUM_THREADS := 1
export OPENBLAS_NUM_THREADS := 1
export MKL_NUM_THREADS := 1
PY  := python3
A   := analysis
T   := $(A)/outputs/tables
EST := $(T)/70_baseline.csv $(T)/71_true_within_firm_results.csv $(T)/70_permutation.csv $(T)/80_fixed_treatment.csv \
       $(T)/81_inference.csv $(T)/82_honestdid_official.csv $(T)/52_wild_bootstrap_results.csv $(T)/60_power_analysis_n66.csv $(T)/73_oil_cycle.csv

.PHONY: all estimates tables figures numbers clean
all: estimates tables figures numbers

estimates: $(EST)
$(T)/70_baseline.csv: $(A)/70_main_estimates.py ; $(PY) $<
$(T)/71_true_within_firm_results.csv: $(A)/71_within_firm_province_panel.py ; $(PY) $<
$(T)/70_permutation.csv: $(A)/75_permutation_cells.py ; $(PY) $<
$(T)/80_fixed_treatment.csv: $(A)/80_fixed_treatment.py ; $(PY) $<
$(T)/81_inference.csv: $(A)/81_inference_province.py ; $(PY) $<
$(T)/82_honestdid_official.csv: $(A)/82_honestdid_official.py ; $(PY) $<
$(T)/52_wild_bootstrap_results.csv: $(A)/52_wild_bootstrap.py ; $(PY) $<
$(T)/60_power_analysis_n66.csv: $(A)/60_power_analysis.py $(T)/70_baseline.csv ; $(PY) $<
$(T)/73_oil_cycle.csv: $(A)/73_oil_cycle_heterogeneity.py ; $(PY) $<

tables: $(EST)
	$(PY) $(A)/72_make_tables.py && $(PY) $(A)/73_oil_cycle_heterogeneity.py
figures: tables
	$(PY) $(A)/77_figures.py
numbers: tables
	$(PY) $(A)/78_numbers_tex.py
clean:
	rm -rf analysis/outputs/manuscript_inputs analysis/outputs/figures
