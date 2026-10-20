# Pilot verification

Verified on October 20, 2026, local America/Los_Angeles date.

Current workbook: `compensation_annual_average.xlsx`. The earlier `compensation.xlsx` remains the historical year-end-rate version. Annual-average results were regenerated from the same original disclosures, with CAD figures preserved and all confirmed USD monetary fields multiplied by 1.3978.

- 44 Python tests passed after switching to the official 2025 annual average of 1.3978 CAD per USD. This includes deterministic PDF multi-year alignment, fiscal-year selection, exact identity matching, document reuse, state distinctions, category mapping, annual FX selection and official snapshot integrity, reconciliation, ranking, pinned-original rejection and a synthetic HTML definitive-proxy path.
- Original Summary Compensation Tables were rendered and visually checked: Interfor PDF page 54, Methanex page 89 and B2Gold page 77. All target-year rows were included: 6, 5 and 5 NEOs respectively. Interfor's two former officers were retained.
- Separate audited consolidated income statements were rendered and visually checked: Interfor PDF page 8, Methanex page 53 and B2Gold page 160. Net income/loss includes NCI where applicable, before the allocation to owners. Source units are respectively CAD millions, USD thousands and USD thousands.
- The workbook's Results and Source data sheets were rendered and inspected, including original figures, conversion formulas, source citations, component review markers and exact footnote text. Long labels were wrapped and column widths adjusted.
- All 144 result monetary cells matched the Python Decimal results. A source FX input was doubled, its dependent conversion checked, and the input restored before final calculation/export. Ranks were checked against Python's independently computed ranking.
- The saved XLSX was reopened as OOXML and independently checked for every result amount, cached rank, formula, sheet name, freeze panes and formula-error cells. No formula errors were found. See `workbook_validation.json` and `saved_workbook_validation.json`.
- The managed Windows authoring process returned shutdown status 3221226505 after a completed, saved export. The CLI records this limitation and verifies the actual file before accepting the result. Microsoft Excel application recalculation was not tested.
- 38 component fields remain null: 33 dashes and five absent pension columns. There are also two CAD $1 differences between reported totals and known components for Interfor's Ian M. Fillinger (-1) and Timothy P. Hartnett (+1). The reported totals were retained. No rounding convention was assumed; full reconciliation remains incomplete because source components are missing.
- The original reference CSV and repository copy have the same SHA256. No reference amounts/ranks were used as source evidence.

The saved workbook and JSON are successful collections for the 16 confirmed totals, with explicit unresolved components. New sources and future years still require reviewed source-selection and layout profiles. The real pilot did not use a DEF 14A compensation table; HTML support was tested using synthetic data only.
