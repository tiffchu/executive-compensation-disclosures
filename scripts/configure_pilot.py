"""Reviewed layout specifications only. No compensation figures are stored here."""
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PINNED={
 'interfor_circular':'62f51d3625c51cfac54e4777b67a1bfbaa6e39bc401662ebdd3ed347167ab3ab',
 'interfor_financials':'e3daabf8a454e96497ca9fad711edf9a8580acbdef3fe1d574c3528fd97c3415',
 'methanex_circular':'52a00ac52176b80ff10264bb3579ff939ece4db1c590d62a2843d5bf6729e6ce',
 'methanex_financials':'af0ace8269d5a162fca748586c876a97e256619cb5012a8e6d3a4a9f7c2a311d',
 'b2gold_circular':'000bcea1d986585b3d261c785a369eb49859de5dd24837b9d487723021a0214c',
 'b2gold_financials':'8b8899e183155be75bbc51d96361220ced0cd44fd69fb05ee624e7d80d0779c2'}
for stem,digest in PINNED.items():
    if hashlib.sha256((ROOT/'data/documents'/f'{stem}.pdf').read_bytes()).hexdigest()!=digest:
        raise ValueError(f'{stem} differs from the reviewed original. Do not regenerate profiles without reviewing selection and figures.')
COMMON=[('salary','Salary'),('share_awards','Share Based Awards (1)(2)'),('option_awards','Option Based Awards'),('annual_incentive','Non-Equity Incentive Plan Compensation - Annual Incentive Plans(3)'),('long_term_incentive','Non-Equity Incentive Plan Compensation - Long-term Incentive Plans'),('pension','Pension Value(4)'),('other','All Other Compensation(5)'),('total','Total Compensation(6)')]
def make(name,page,yr_x,table_y,edges,currency,count,date,guards,footnotes,columns=None):
    cols=columns or COMMON
    profile={'sha256':hashlib.sha256((ROOT/'data/documents'/f'{name}_circular.pdf').read_bytes()).hexdigest(),
      'original_disclosure_reviewed':True,'full_roster_reviewed':True,'selection_note':'Original 2026 issuer circular for fiscal year ended December 31, 2025, obtained from issuer investor-relations archive; no amendment or later comparative substitution.',
      'document_date':date,'fiscal_end':'2025-12-31','table_page':page,'table_y':table_y,'year_x':yr_x,'currency':currency,'expected_rows':count,
      'guards':guards,'footnote_reference':footnotes,
      'evidence_pages':sorted(set([page]+[g['page'] for g in guards]+([page+1] if name!='b2gold' else []))),
      'columns':[{'field':f,'label':label,'x':[edges[i],edges[i+1]],'mapping':('Annual short-term incentive heading; direct mapping, no long-term amounts combined.' if f=='annual_incentive' else 'Reported table value; no award revaluation or reconstruction.')} for i,(f,label) in enumerate(cols)]}
    (ROOT/'config'/f'{name}.json').write_text(json.dumps(profile,indent=2))

make('interfor',54,124.1,[270,596],[150,195,250,290,335,385,440,500,570],'CAD',6,'2026-03-17',
  [{'page':54,'text':'SUMMARY COMPENSATION TABLE'},{'page':54,'text':'December 31, 2025'},{'page':5,'text':'all dollar amounts are in Canadian dollars'}],
  'PDF pp.54-55, SCT notes (1)-(9). Awards are grant-date fair values. Some US employees already translated to CAD by issuer; do not reconvert.')
make('methanex',89,141.6,[320,542],[165,212,260,308,356,401,449,498,560],'CAD',5,'2026-03-09',
  [{'page':89,'text':'SUMMARY COMPENSATION TABLE'},{'page':89,'text':'are in Canadian dollars'},{'page':90,'text':'year in which they were earned'}],
  'PDF pp.89-90, SCT notes (1)-(7). Grant-date awards retained; issuer-translated CAD values retained. Annual incentive earned in year, not payment year.',
  [('salary','Base Salary(2)'),('share_awards','Share-Based Awards(3)'),('option_awards','Option-Based Awards(4)'),('annual_incentive','Non-Equity Incentive Plan Compensation - Annual Incentive Plans(5)'),('long_term_incentive','Non-Equity Incentive Plan Compensation - Long-Term Incentive Plans'),('pension','Pension Value(6)'),('other','All Other Compensation(7)'),('total','Total Compensation')])
make('b2gold',77,170.6,[215,444],[198,251,310,350,415,455,510,570],'USD',5,'2026-04-13',
  [{'page':77,'text':'Summary Compensation Table'},{'page':77,'text':'year ended December 31, 2025'},{'page':19,'text':'United States dollars'}],
  'PDF p.77, SCT notes (1)-(3); currency convention PDF p.19. Annual cash bonus paid March 2026 for services in FY2025. Share awards copied as reported.',
  [('salary','Salary ($)'),('share_awards','Share-Based Awards ($)(1)'),('option_awards','Option-Based Awards ($)'),('annual_incentive','Annual Incentive Program ($)(2)'),('long_term_incentive','Long-Term Incentive Plans ($)'),('other','All Other Compensation ($)(3)'),('total','Total Compensation ($)')])

for name,page,units,currency,label,pattern,guards,explanation,date in [
 ('interfor',8,1000000,'CAD','Net loss',r'^Net loss \$ (?P<amount>\([\d,.]+\)) \$', ['Consolidated Statements of Earnings','millions of Canadian Dollars','December 31, 2025'], 'Consolidated net loss after tax, before any owners/NCI allocation; not comprehensive income. Source millions expanded to dollars.','2026-02-12'),
 ('methanex',53,1000,'USD','Net income',r'^Net income \$ (?P<amount>[\d,]+) \$', ['Consolidated Statements of Income','thousands of U.S. dollars','2025 2024'], 'Consolidated net income above the allocation to shareholders and non-controlling interests; includes NCI. Source thousands expanded to dollars.','2026-03-05'),
 ('b2gold',160,1000,'USD','Net income (loss)',r'^Net income \(loss\) \$ (?P<amount>[\d,]+) \$', ['CONSOLIDATED STATEMENTS OF OPERATIONS','thousands of United States dollars','2025 2024'], 'Consolidated net income including NCI, before allocation to shareholders. The same total is repeated after the attribution lines. Source thousands expanded to dollars.','2026-02-18')]:
    obj={'sha256':hashlib.sha256((ROOT/'data/documents'/f'{name}_financials.pdf').read_bytes()).hexdigest(),'page':page,'units':units,'currency':currency,'label':label,'line_pattern':pattern,'guards':guards,'explanation':explanation,'document_date':date,'fiscal_end':'2025-12-31'}
    (ROOT/'config'/f'{name}_financials.json').write_text(json.dumps(obj,indent=2))
