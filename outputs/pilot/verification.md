# Pilot verification

Verified on October 20, 2026, local America/Los_Angeles date.

Current workbook: `execs_comp_roster.xlsx`, built from the supplied template's column layout. Superseded workbooks are recoverable from Git history. The 16-executive pilot was regenerated from the same original disclosures, with source amounts preserved and USD values converted using the official annual average.

- 59 Python tests passed. Annual FX uses CURRENT YEAR - 1 at local run start. A 2027-date test selects the 2026 annual average and refuses a 2025 fallback. The 2026 pilot therefore uses the official 2025 annual average, 1.3978 CAD per USD, with its official response/hash retained.
- Original Summary Compensation Tables were rendered and visually checked: Interfor PDF page 54, Methanex page 89 and B2Gold page 77. All target-year rows were included: 6, 5 and 5 NEOs respectively. Interfor's two former officers were retained.
- Separate audited consolidated income statements were rendered and visually checked: Interfor PDF page 8, Methanex page 53 and B2Gold page 160. Net income/loss includes NCI where applicable, before the allocation to owners. Source units are respectively CAD millions, USD thousands and USD thousands.
- The workbook's Results and Source data sheets were rendered and inspected, including original figures, conversion formulas, source citations, component review markers and exact footnote text. Long labels were wrapped and column widths adjusted.
- All 128 current-year CAD cells and 25 original USD cells matched Python/source figures. The three ignored columns were verified blank for every record. All 128 prior-year output CAD positions were checked against the original prior-period fields or required blanks. Missing monetary values display blank, while source semantics and review reasons remain available. First/last names and lowercase titles were checked. A USD FX input was doubled and restored; zero and blank inputs were checked separately. Ranks match Python's independently computed ranking.
- The saved XLSX was reopened as OOXML and independently checked for every result amount, cached rank, formula, sheet name, freeze panes and formula-error cells. No formula errors were found. See `workbook_validation.json` and `saved_workbook_validation.json`.
- The managed Windows authoring process returned shutdown status 3221226505 after a completed, saved export. The CLI records this limitation and verifies the actual file before accepting the result. Microsoft Excel application recalculation was not tested.
- 38 component fields remain null: 33 dashes and five absent pension columns. There are also two CAD $1 differences between reported totals and known components for Interfor's Ian M. Fillinger (-1) and Timothy P. Hartnett (+1). The reported totals were retained. No rounding convention was assumed; full reconciliation remains incomplete because source components are missing.
- The original reference CSV and repository copy have the same SHA256. No reference amounts/ranks were used as source evidence.

The saved workbook and JSON are successful collections for the 16 confirmed totals, with explicit unresolved components. New sources and future years still require reviewed source-selection and layout profiles. The real pilot did not use a DEF 14A compensation table; HTML support was tested using synthetic data only.

## Roster and prior-period verification

- Eight current names match the supplied baseline, including Ian M. Fillinger's unique middle-initial variation; eight are new. Brad Boyd and Ryan Nicometo are absent from Methanex's reviewed full FY2025 table and retained as red rows with blank amounts/ranks. No out-of-universe company was marked removed.
- Original 2025 circular tables and footnotes were rendered and visually checked: Interfor PDF page 58, Methanex pages 90–91. Six new executives have original FY2024 values; Mackay and Maloney have no matching original rows and remain blank. Superscript footnotes in the Methanex prior table are kept with their identity row; Gustavo Parra's verified total is CAD 2,598,678.
- The official 2024 annual FX response/hash is retained (1.3698 CAD per USD). The six prior rows already report CAD and are not reconverted. Synthetic USD tests verify distinct current/prior rates, full-dollar unit expansion, zero preservation, missing rows and year rollover to 2027.
- Saved XLSX verification checks every current/prior monetary position, original USD, status, rank and the whole-row red conditional formatting rule. Output renders confirm red rows and prior figures. The current workbook can serve as a future baseline; removed rows are excluded and nondefault baselines are retained by hash before replacement.
