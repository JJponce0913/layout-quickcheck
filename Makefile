.PHONY: setup build graphs graphs-paper nightly

setup:
	pip3 install -r requirements.txt

build:
	(cd web/ui && npm install)
	(cd web/ui && npm run build)
	(cd web/server && pip3 install -r requirements.txt)

graphs: TABLE_SNAPSHOT_ARG = --highest-common-snapshot
graphs-paper: RQ1_MAX_MINUTES_ARG = --max-minutes 60
graphs-paper: FIREFOX_MAX_MINUTES_ARG = --max-minutes 540
graphs-paper: FIREFOX_SNAPSHOT_ARG = --snapshot-seconds 32400

graphs graphs-paper:
	mkdir -p "generated artifacts"
	python artifact_generators/figures/cumulative_bugs_over_time_by_config.py \
	  "bug_reports/chromium-no-weights" \
	  "bug_reports/chromium-sort" \
	  "bug_reports/firefox-no-weights" \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/cumulative_bugs_detected_over_time_by_configuration.png" $(RQ1_MAX_MINUTES_ARG)
	python artifact_generators/tables/create_rq1_results_table.py \
	  "bug_reports/chromium-no-weights" \
	  "bug_reports/chromium-sort" \
	  "bug_reports/firefox-no-weights" \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/table_3_rq1_results.png" $(TABLE_SNAPSHOT_ARG)
	python artifact_generators/figures/post_processing_time_over_time.py \
	  "bug_reports/firefox-sort" \
	  "bug_reports/firefox-no-sort" \
	  --output "generated artifacts/combined_minimization_and_clustering_time_over_time.png" $(FIREFOX_MAX_MINUTES_ARG)
	python artifact_generators/figures/css_style_elements_by_report_type.py \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/firefox_style_elements.png" $(FIREFOX_SNAPSHOT_ARG)
	python artifact_generators/figures/firefox_bug_group_sizes.py \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/firefox_bug_group_sizes.png" $(FIREFOX_SNAPSHOT_ARG)
	python artifact_generators/figures/bug_groups_and_single_bugs_over_time.py \
	  "bug_reports/firefox-sort" \
	  --output "generated artifacts/bug_groups_and_single_bugs_over_time.png" $(FIREFOX_MAX_MINUTES_ARG)

nightly: build
	bash infra/nightly.sh
