.PHONY: setup build graphs nightly

setup:
	pip3 install -r requirements.txt

build:
	(cd web/ui && npm install)
	(cd web/ui && npm run build)
	(cd web/server && pip3 install -r requirements.txt)

graphs:
	mkdir -p "generated artifacts"
	python artifact_generators/figures/cumulative_bugs_over_time_by_config.py \
	  "bug_reports/chromium-no-weights" \
	  "bug_reports/chromium-sort" \
	  "bug_reports/firefox-no-weights" \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/cumulative_bugs_detected_over_time_by_configuration.png" \
	  --max-minutes 60
	python artifact_generators/tables/create_rq1_results_table.py \
	  "bug_reports/chromium-no-weights" \
	  "bug_reports/chromium-sort" \
	  "bug_reports/firefox-no-weights" \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/table_3_rq1_results.png"
	python artifact_generators/figures/post_processing_time_over_time.py \
	  "bug_reports/firefox-sort" \
	  "bug_reports/firefox-no-sort" \
	  --output "generated artifacts/combined_minimization_and_clustering_time_over_time.png"
	python artifact_generators/figures/css_style_elements_by_report_type.py \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/firefox_style_elements.png"
	python artifact_generators/figures/firefox_bug_group_sizes.py \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/firefox_bug_group_sizes.png"
	python artifact_generators/figures/bug_groups_and_single_bugs_over_time.py \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/bug_groups_and_single_bugs_over_time.png"

nightly: build
	bash infra/nightly.sh
