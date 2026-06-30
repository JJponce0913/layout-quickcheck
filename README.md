![LQC logo](logo_100px_width.png)

# Layout QuickCheck

Layout QuickCheck generates randomized web pages and checks browsers for layout
differences. Run all commands below from the repository root.

## 1. Set up

Requirements:

- Python 3
- Firefox
- [geckodriver](https://github.com/mozilla/geckodriver/releases) available on
  `PATH`
- Google Chrome
- [ChromeDriver](https://googlechromelabs.github.io/chrome-for-testing/)
  available on `PATH`

Create a virtual environment and install the project:

```bash
python -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Or activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then install the dependencies:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

Verify that chromedriver and geckodriver are available:

```bash
geckodriver --version
chromedriver --version
```

If a driver is installed but cannot be found through `PATH`, set
`webdriver_path` in each configuration you use to the driver's full path. For
example, use `C:\WebDriver\chromedriver.exe` for Chromium or
`C:\WebDriver\geckodriver.exe` for Firefox. The artifact configurations are in
`config/artifact-configs/`.

## 2. Run an experiment

The six artifact configurations compare two browsers and three processing
modes:

- **Sort:** uses CSS-property weights and automatically minimizes and groups
  detected bugs.
- **No sort:** uses the same CSS-property weights, but `--no-sort` disables bug
  grouping.
- **No weights:** uses equal/default CSS-property selection weights while
  retaining automatic minimization and grouping.

For paper-accurate results, use the `--max-minutes` values shown below. The
runner stops once that total runtime is reached.

### Chromium with weights and sorting

Writes results to `bug_reports/chromium-sort/`.

```bash
python src/lqc_selenium/runner.py --max-minutes 60 --config-file config/artifact-configs/change-chromium.json
```

### Chromium with weights and no sorting

Writes results to `bug_reports/chromium-no-sort/`.

This configuration was not used in the paper evaluation, so it has no
paper-defined duration.

```bash
python src/lqc_selenium/runner.py --config-file config/artifact-configs/change-chromium-no-sort.json --no-sort
```

### Chromium without weights

Writes results to `bug_reports/chromium-no-weights/`.

```bash
python src/lqc_selenium/runner.py --max-minutes 60 --config-file config/artifact-configs/change-chromium-no-weights.json
```

### Firefox with weights and sorting

Writes results to `bug_reports/firefox-sort/`.

```bash
python src/lqc_selenium/runner.py --max-minutes 540 --config-file config/artifact-configs/change-firefox.json
```

### Firefox with weights and no sorting

Writes results to `bug_reports/firefox-no-sort/`.

```bash
python src/lqc_selenium/runner.py --max-minutes 540 --config-file config/artifact-configs/change-firefox-no-sort.json --no-sort
```

### Firefox without weights

Writes results to `bug_reports/firefox-no-weights/`.

```bash
python src/lqc_selenium/runner.py --max-minutes 60 --config-file config/artifact-configs/change-firefox-no-weights.json
```

Run the following command for every available option:

```bash
python src/lqc_selenium/runner.py --help
```

## 3. Generate graphs

Results in these directories:

```text
bug_reports/
├── chromium-no-weights/
├── chromium-no-sort/
├── chromium-sort/
├── firefox-no-sort/
├── firefox-no-weights/
└── firefox-sort/
```

Run the following commands from the repository root in PowerShell. Generated
figures and the results table are written to `generated artifacts/`.

To generate all figures without a time cap and build the RQ1 results table from
the latest snapshot timestamp shared by all four configurations, run:

```bash
make graphs
```

To generate the paper versions, run:

```bash
make graphs-paper
```

This uses the paper's snapshots: 60 minutes for the cumulative RQ1 graph and
results table, and 540 minutes for the Firefox post-processing and bug-group
timelines. The CSS-style and bug-group-size figures also use the Firefox
540-minute snapshot, excluding reports created later.

Or run individual generators with the commands below.

### Cumulative bugs over time by configuration

```powershell
python artifact_generators\figures\cumulative_bugs_over_time_by_config.py `
  "bug_reports\chromium-no-weights" `
  "bug_reports\chromium-sort" `
  "bug_reports\firefox-no-weights" `
  "bug_reports\firefox-sort" `
  --output "generated artifacts\cumulative_bugs_detected_over_time_by_configuration.png" `
  --max-minutes 60
```

### RQ1 bug-discovery results table

```powershell
python artifact_generators\tables\create_rq1_results_table.py `
  "bug_reports\chromium-no-weights" `
  "bug_reports\chromium-sort" `
  "bug_reports\firefox-no-weights" `
  "bug_reports\firefox-sort" `
  --output "generated artifacts\table_3_rq1_results.png"
```

### Post-processing time over time

```powershell
python artifact_generators\figures\post_processing_time_over_time.py `
  "bug_reports\firefox-sort" `
  "bug_reports\firefox-no-sort" `
  --output "generated artifacts\combined_minimization_and_clustering_time_over_time.png"
```

### CSS style elements by report type

```powershell
python artifact_generators\figures\css_style_elements_by_report_type.py `
  "bug_reports\firefox-sort" `
  --output "generated artifacts\firefox_style_elements.png"
```

### Firefox bug-group sizes

```powershell
python artifact_generators\figures\firefox_bug_group_sizes.py `
  "bug_reports\firefox-sort" `
  --output "generated artifacts\firefox_bug_group_sizes.png"
```

### Bug groups and single bugs over time

```powershell
python artifact_generators\figures\bug_groups_and_single_bugs_over_time.py `
  "bug_reports\firefox-sort" `
  --output "generated artifacts\bug_groups_and_single_bugs_over_time.png"
```

Time-series input directories must contain `run_summary_<seconds>s.json`
snapshots. The RQ1 table reads `run_summary_3600s.json` by default; pass
`--highest-common-snapshot` to use the latest timestamp present in all four
input directories. The CSS-style and
bug-group-size generators read the `bug-group-*` and `bug-*` directories in
the supplied Firefox results.

## 4. Other tasks

### Change the configuration

Preset configurations are in `config/`. Copy the closest preset, edit the
copy, and pass it to the runner:

```bash
python src/lqc_selenium/runner.py  --config-file path/to/config.json
```

Configuration controls output paths, browser variants, and CSS-property
weights. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

### Re-run the minimizer

Use a saved run-subject pickle from a bug report:

```bash
python tooling/scripts/run_minify.py --pickle path/to/run_subject.pkl --config config/preset-firefox.config.json
```

Debugging output is written under `bug_reports/debug_minify_runs/`.

### Cluster saved bugs

Cluster bug pickles while using a separate set of known-safe pickles to reject
overly broad rules:

```bash
python tooling/scripts/sort_bug.py --pickles-dir path/to/bugs --pickle-name minified_run_subject.pkl --safe-dir path/to/safe-pickles --output-dir clustered
```

The clustered results are written to `bug_reports/clustered/`.

### Inspect a bug

Each bug-report directory contains:

- `minified_bug.html`: the smallest reproduced test case
- `original_bug.html`: the original generated test case
- `data.json`: browser variants, styles, and detected differences
- `minified_run_subject.pkl`: serialized input for minimization and clustering

Open `minified_bug.html` in a browser. In the developer console, run
`checkForBug()` to repeat the check or `simpleRecreate()` to print the layout
differences.

Additional Selenium instructions are in
[docs/SELENIUM.md](docs/SELENIUM.md). Grizzly instructions are in
[docs/GRIZZLY.md](docs/GRIZZLY.md).

## License

See [MIT-LICENSE](MIT-LICENSE).
