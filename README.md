# Executive compensation disclosures

Collect original executive compensation disclosures without estimates or generative extraction. The Python pipeline uses reviewed layout profiles, literal PDF word coordinates or HTML cells, and `Decimal` arithmetic. A separate renderer builds the Excel workbook.

## Pilot delivered

`outputs/pilot/` contains the workbook, JSON records, unresolved-item report and saved-workbook verification. The run covers fiscal years ending in **2025**, resolved from the local run date in 2026.

The current workbook is **`execs_comp.xlsx`**, using the supplied `execs_comp_template.xlsx` layout and the annual-average FX policy. Earlier workbooks are retained as historical outputs; the current JSON and run report describe `execs_comp.xlsx`. The template is preserved unchanged in `data/templates/`, pinned by SHA256 in `config/output_template.json` and the run metadata. Its example figures and hardcoded conversion formulas are not factual inputs.

| Company | Executives | Compensation source | Audited income source |
| --- | ---: | --- | --- |
| Interfor | 6, including two former officers | 2026 circular, PDF pages 54–55 | 2025 financial statements, PDF page 8 |
| Methanex | 5 | 2026 circular, PDF pages 89–90 | 2025 annual report, PDF page 53 |
| B2Gold | 5 | 2026 circular, PDF page 77; currency convention page 19 | Original 2025 Form 40-F compilation, PDF page 160 |

The original PDFs and official Bank of Canada response are retained in `data/documents/`, with source URLs and SHA256 sidecars. Page numbers above are **1-based PDF pages**, which differ from printed page numbers. Three SCT pages and all three income statements were rendered and visually reviewed. Figures were read by deterministic code, not transcribed or extracted by a model.

All **16 reported totals** and all three consolidated income figures were collected. **38 component fields** remain null: 33 source dashes with no verified numeric meaning and B2Gold's five absent pension columns. The report also flags **two CAD $1 differences** between Interfor's reported totals and the known components, for Fillinger and Hartnett. No rounding allowance was invented. Reconciliation remains incomplete where any component is nonnumeric.

The official Bank of Canada **2025 annual-average rate is 1.3978 CAD per USD** (series FXAUSDCAD). This replaces the earlier year-end convention at the user's request. It applies to every USD value. Interfor and Methanex SCT figures are already reported in CAD; issuer translations are preserved without converting them twice. Both B2Gold compensation and USD audited income figures use the annual-average rate. The annual series label `2025-01-01` identifies the entire 2025 period; it is not a daily observation date. Methanex income includes NCI, rather than the shareholder-only subtotal used by many summaries.

The reference CSV is unchanged at `data/reference/1792523779.6511.csv`, SHA256 `d91f1be5a09c325e093f7d233493c82af13fef8a8541667320f05f0927214b24`. It was used only to select pilot companies and understand the output layout. Its amounts, ranks and FX convention are not collection evidence.

## Run

Python 3.11+ and pdfplumber 0.11+ are required. In a normal Python environment:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python scripts/run.py run --input inputs/pilot.csv --output outputs/pilot
.venv/Scripts/python -m unittest discover -s tests -v
```

In this Codex workspace, the bundled Python already has pdfplumber:

```powershell
& "$env:USERPROFILE/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" scripts/run.py run
```

Excel authoring uses `@oai/artifact-tool` from the managed Codex runtime. The local ignored `node_modules` junction points to that runtime. To restore the junction in a fresh local checkout, when the managed runtime exists:

```powershell
New-Item -ItemType Junction -Path node_modules -Target "$env:USERPROFILE/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
```

The CLI finds Node on PATH or in the bundled runtime. `EXECOMP_NODE` can supply its executable path. This repository does not modify the bundled dependencies. Outside this environment, configure an available artifact-tool runtime; `--no-excel` runs the Python collector and produces JSON/report without it.

The bundled Windows renderer currently returns status `3221226505` during shutdown after writing the file. The CLI accepts an export only if the renderer's completed-verification marker exists **and** a separate Python reader verifies the saved XLSX cells, formulas, rank caches, sheet names and absence of formula errors. That shutdown limitation is recorded in the run report and verification JSON. No Microsoft Excel application recalculation was claimed. Conversion/rank formulas were recalculated and perturbed in the artifact engine; the saved XLSX was independently inspected.

## Company input CSV

Required columns: `company,symbol`. Optional columns:

| Column | Meaning |
| --- | --- |
| `ir_url` | Issuer investor-relations page, used for candidate discovery |
| `document` | Original circular/definitive proxy HTTPS URL or local file path |
| `financial_document` | Separate original audited consolidated financial statements |
| `executive` | Exact disclosed executive name; blank collects all disclosed NEO rows, including former officers |
| `profile` | Reviewed profile name from `config/<name>.json` |

Paths are relative to the repository root, or absolute. Several executive requests for the same company are grouped. Conflicting documents are rejected. Each selected company document is acquired and parsed once per run; PDF evidence is also cached by source hash. Requested names use exact normalized matching, preserving middle initials; ambiguous or absent matches are reported. No fuzzy identity guess is made.

```csv
company,symbol,ir_url,document,financial_document,executive,profile
Interfor Corporation,IFP,https://interfor.com/investors/reports/,data/documents/interfor_circular.pdf,data/documents/interfor_financials.pdf,Ian M. Fillinger,interfor
Interfor Corporation,IFP,https://interfor.com/investors/reports/,data/documents/interfor_circular.pdf,data/documents/interfor_financials.pdf,Michael C. Mackay,interfor
```

## Discovery and document review

```powershell
python scripts/run.py discover https://interfor.com/investors/reports/ --year 2025
python scripts/run.py inspect-html path/to/original-def14a.html
```

Discovery returns **candidates**, never facts. Check the original issuer or regulator archive, the circular date, actual fiscal year-end, table coverage and any amendment status before creating a profile. The publication year and issuer's fiscal-year label are not a selection rule. Default target is local calendar year minus one, fixed at run start; it is never inferred from the CSV or a document's title.

Retrieval checks robots.txt, makes one request without retries or evasion, and stops on restrictions or failures. Supply a local original document when blocked. Local files work fully offline. No browser automation or access-control bypass is used.

For a new PDF, copy a reviewed profile and set its **actual** `fiscal_end`, original file hash, original-disclosure review, source guards, table page, year-column x-coordinate, table bounds and numeric-column ranges. `row_year_label` can explicitly map a differing issuer year label to the reviewed actual fiscal end. Expected row counts and exact hashes prevent silently using changed tables, amendments or later comparatives. Source dates and periods must be reviewed, not inferred. A nonzero reconciliation tolerance requires an explicit source rounding explanation.

`scripts/configure_pilot.py` can regenerate the three pilot profiles only from the original pinned file hashes. A changed source fails before its hash can be rebound. `scripts/acquire_pilot.py` preserves successful downloads, validates PDF magic and returns a failure status for unsuccessful retrievals.

### Reviewed HTML / SEC DEF 14A profiles

The HTML adapter accepts an original definitive proxy when the reviewed profile sets `document_format: "html"`. It requires `table_index` (1-based document order), `header_rows`, `year_column`, `identity_column`, `identity_pattern` with named `name` and `position` groups, `expected_rows`, actual `fiscal_end`, currency/units, original hash, source text guards and column specifications containing `field`, `column` (zero-based), `label` and optionally `header_row`. The exact original header must match. Rowspan/colspan are expanded while each value keeps its original cell XPath locator. `row_year_label` explicitly handles differing fiscal-year labels. A synthetic multi-year proxy fixture tests this path; no real SEC pilot is claimed.

Combined pension/deferred-compensation headings remain uncertain. Undifferentiated non-equity incentives are never labeled annual. If bonus and annual incentive columns map to the same category, their original labels and amounts are retained separately in JSON. They remain null unless `annual_combination_rule` supplies a reviewed `source_text` actually present in the document and an `explanation`. Only explicitly annual components can then be added; the mapping explanation prints the arithmetic. Long-term incentives cannot be included in that sum.

## Output contract

The `Results` tab follows the supplied template's columns A:AJ, starting with separate first and last names. Titles are lowercase and numeric footnote markers are removed from the display title; original identities/positions remain in JSON and source evidence. Given names and middle initials stay together in First Name, with the last name token in Last Name (for example, `Ian M.` / `Fillinger`, `S. Bruce` / `Luxmoore`). Compound surnames in future inputs require reviewed name handling. Rows are sorted by descending confirmed CAD total. Rank, separate long-term incentive USD/CAD columns, fiscal year-end and review notes follow the template columns. Competition ranks are recomputed within the supplied universe; equal totals share a rank. Missing totals remain unranked at the end. Values retain precision in JSON and Excel; monetary cells display full dollars.

Only the target year is collected. Template prior-year, personal-email, company-net-income and industry cells remain empty. No example data is copied. The original USD columns are populated only for source-reported USD figures, expanded to full dollars using source units. Already reported CAD amounts are not reverse-converted to invent original USD figures. Headers update to the run's target year and prior-year label automatically. Verified net-income data remains in JSON for provenance, but is not exported into the ignored template column.

`Source data` holds literal source cells, original labels, source-unit amounts, currency, unit multipliers, visible conversion formulas, original document dates/periods, PDF pages or HTML locators, hashes, source URLs, FX dates/URLs, mappings and review reasons. Exact source text, including footnotes, is retained at columns AA:AD. Full original documents remain available. The workbook is a run snapshot; re-run after modifying the input universe to refresh sort order.

JSON monetary amounts are decimal strings to avoid binary floating-point loss. Unavailable or uncertain amounts and their CAD values are `null`. Explicit zero, not applicable, not disclosed and uncertain have separate states. Unavailable workbook monetary cells display **blank**, with source meaning and review reasons retained in `Source data` and the run report. Formula cells return an empty string for unavailable values; source inputs are empty cells. Real zero amounts remain numeric zero. No source dash, blank or NA is automatically zero.

Reported totals are copied independently. Award values remain as disclosed. No new option valuation, realized/vested substitution, compensation-actually-paid substitution or annualization is performed. Net income is separately sourced from the audited consolidated income statement, includes NCI, and excludes comprehensive income, adjusted earnings and owners-only subtotals. A missing income figure does not discard compensation.

For USD, use the Bank of Canada FXAUSDCAD annual average for the target calendar year, including non-calendar fiscal issuers. The official response is cached as `data/documents/fx_annual_<year>.json`, with its source URL and hash. A missing response triggers retrieval; a missing target-year annual rate requires manual input, without falling back to a daily rate or another year. Annual period, series label, basis and URLs are recorded explicitly. The old daily snapshot is retained only as historical evidence. Unsupported currencies/rates remain for manual input. CAD is never converted again.

## Modules and validation

`config.py` fixes the run date and target year; `inputs.py` groups requests; `documents.py` separates discovery and respectful acquisition; `extraction.py` reads reviewed source cells; `validation.py` preserves missing-value semantics, maps categories, reconciles and ranks; `currency.py` converts using Decimal; `pipeline.py` writes JSON/report; `export.py` checks the saved workbook; `scripts/export_workbook.mjs` renders and exports Excel.

Run `python -m unittest discover -s tests -v`. The **47 tests** cover fiscal-year rollover and actual end dates, multi-year alignment, exact identity/duplicates and name/title display, company document reuse, category mapping and source-supported arithmetic, zero versus NA/dash/blank, units, exact annual FX selection/snapshot integrity and CAD preservation, reconciliation, ranking, changed-hash rejection, former officers and reviewed HTML spans/locators. A future-date test verifies a 2027 run chooses the 2026 annual average and refuses a 2025 fallback. The rate is never pinned to 2025 or 1.3978 in production logic: each run fixes CURRENT YEAR - 1 from the local start date, selects that year's official annual observation, and retains the response/hash for reproducibility.

Workbook validation checks all 128 current-year CAD cells and 25 original USD cells against Python results, checks ignored/prior-year cells are blank, and verifies split names and lowercase titles. It perturbs/restores a real USD FX input and tests blank-versus-zero recalculation. Both output tabs were visually inspected. `config/output_template.json` is the shared column map used by the builder and saved-file verifier.

## Remaining limits

- Original-document selection and new issuer/year profiles require source review. Search results are not extraction evidence. The three real PDF profiles are deliberately pinned to FY2025 originals.
- Arbitrary PDF/HTML layout recognition, OCR, nested HTML tables and automated original/amendment certification are not implemented. Financial-statement extraction currently uses reviewed PDF line profiles.
- No real SEC DEF 14A issuer was included in the pilot. Its deterministic HTML adapter is covered by synthetic tests.
- Manual values are not filled automatically. Resolve flagged cells against source evidence, retain a review record, update a reviewed adapter when justified, and rerun. Keep verified independent fields.

Everything is contained in this repository. `browser_autowork` is not used or modified.
