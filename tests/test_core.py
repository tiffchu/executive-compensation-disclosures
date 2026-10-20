import unittest, sys, tempfile, json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from execcomp.config import ROOT, RunConfig, target_period
from execcomp.inputs import identity, match_executive, load_companies, output_identity
from execcomp.validation import parse_amount, map_label, reconcile, rank_records, FIELDS, combine_annual_columns
from execcomp.currency import cad, select_rate, load_snapshot
from execcomp.extraction import pdf_evidence, extract_compensation
from execcomp.documents import html_tables, acquire

class SelectionTests(unittest.TestCase):
    def test_name_parts_and_lowercase_title(self):
        self.assertEqual(output_identity('Ian M. Fillinger','President & Chief Executive Officer'),{'first_name':'Ian M.','last_name':'Fillinger','title':'president & chief executive officer'})
        self.assertEqual(output_identity('S. Bruce Luxmoore','Executive Vice President (Former)(7)(9)')['first_name'],'S. Bruce')
        self.assertEqual(output_identity('S. Bruce Luxmoore','Executive Vice President (Former)(7)(9)')['title'],'executive vice president (former)')
    def test_local_year_rollover(self):
        self.assertEqual(RunConfig.start(datetime(2026,12,31,23,59)).target_year,2025)
        self.assertEqual(RunConfig.start(datetime(2027,1,1)).target_year,2026)
    def test_actual_end_not_label_or_publication(self):
        self.assertTrue(target_period('2025-09-30',2025))
        self.assertFalse(target_period('2026-01-03',2025))
    def test_identity_exact_and_unique(self):
        self.assertEqual(match_executive(' dean richardson ',['Dean Richardson']),'Dean Richardson')
        with self.assertRaises(ValueError): match_executive('Richardson',['Dean Richardson'])
        with self.assertRaises(ValueError): match_executive('Dean Richardson',['Dean Richardson','Dean Richardson'])
    def test_middle_initial_not_silently_ignored(self):
        with self.assertRaises(ValueError): match_executive('Ian Fillinger',['Ian M. Fillinger'])
    def test_group_same_company_executives(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'input.csv'; p.write_text('company,symbol,executive,document\nAcme,AC,Ada Smith,source.pdf\nAcme,AC,Bo Jones,source.pdf\n')
            groups=load_companies(p)
            self.assertEqual(len(groups),1); self.assertEqual(groups[0]['executives'],['Ada Smith','Bo Jones'])
    def test_no_name_means_all(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'input.csv'; p.write_text('company,symbol,executive\nAcme,AC,\n')
            self.assertTrue(load_companies(p)[0]['all_executives'])
    def test_conflicting_documents_fail(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'input.csv'; p.write_text('company,symbol,document\nAcme,AC,a.pdf\nAcme,AC,b.pdf\n')
            with self.assertRaises(ValueError): load_companies(p)

class AmountTests(unittest.TestCase):
    def test_zero_is_numeric(self): self.assertEqual(parse_amount('$0'),('0','explicit_zero',''))
    def test_na_is_not_zero(self): self.assertEqual(parse_amount('NA')[:2],(None,'not_applicable'))
    def test_blank_is_not_disclosed(self): self.assertEqual(parse_amount('')[:2],(None,'not_disclosed'))
    def test_dash_is_uncertain(self):
        for dash in ['-','—','–']: self.assertEqual(parse_amount(dash)[:2],(None,'uncertain'))
    def test_negative_and_decimal(self): self.assertEqual(parse_amount('($344.4)')[0],'-344.4')
    def test_garbled_or_footnoted_number_not_guessed(self):
        for raw in ['123(1)','approx 12','3 4 9,8 5 3']: self.assertIsNone(parse_amount(raw)[0])
    def test_separate_long_term(self):
        self.assertEqual(map_label('Non-equity Long-Term Incentive Plans'),'long_term_incentive')
        self.assertIsNone(map_label('Non-equity incentive compensation'))
    def test_combined_pension_deferred_ambiguous(self): self.assertIsNone(map_label('Change in pension value and deferred compensation'))
    def test_annual_bonus_mapping(self):
        self.assertEqual(map_label('Bonus'),'annual_incentive')
        self.assertEqual(map_label('Annual Incentive Plans'),'annual_incentive')
    def test_combine_bonus_and_annual_requires_evidence(self):
        columns=[{'source_label':'Bonus','raw':'100','amount':'100'},{'source_label':'Annual Incentive Plans','raw':'50','amount':'50'}]
        self.assertIsNone(combine_annual_columns(columns)['amount'])
        rule={'source_text':'Bonus and annual incentive are separate annual awards','explanation':'Both explicitly annual; sum the two reported columns.'}
        mapped=combine_annual_columns(columns,rule,rule['source_text'])
        self.assertEqual(mapped['amount'],'150'); self.assertIn('100 + 50 = 150',mapped['mapping'])
        self.assertEqual(mapped['original_columns'],columns)
    def test_long_term_cannot_be_folded_into_annual(self):
        columns=[{'source_label':'Bonus','raw':'100','amount':'100'},{'source_label':'Long-term incentives','raw':'50','amount':'50'}]
        self.assertIsNone(combine_annual_columns(columns,{'source_text':'annual','explanation':'x'},'annual')['amount'])

class CurrencyTests(unittest.TestCase):
    def test_future_run_uses_its_previous_calendar_annual_average(self):
        config=RunConfig.start(datetime(2027,1,2))
        fx=select_rate({'observations':[{'d':'2025-01-01','FXAUSDCAD':{'v':'1.3978'}},{'d':'2026-01-01','FXAUSDCAD':{'v':'1.42'}}]},config.target_year)
        self.assertEqual(fx['period'],'2026'); self.assertEqual(fx['rate'],'1.42')
        with self.assertRaises(ValueError): select_rate({'observations':[{'d':'2025-01-01','FXAUSDCAD':{'v':'1.3978'}}]},config.target_year)
    def test_official_snapshot_integrity(self):
        import hashlib
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            path=Path(d)/'fx.json'; path.write_text(json.dumps({'observations':[{'d':'2025-01-01','FXAUSDCAD':{'v':'1.3978'}}]}))
            meta={'url':'https://www.bankofcanada.ca/valet/observations/group/FX_RATES_ANNUAL/json?start_date=2025-01-01&end_date=2025-12-31','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            path.with_suffix('.json.meta.json').write_text(json.dumps(meta))
            self.assertEqual(load_snapshot(path,2025)['rate'],'1.3978')
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'URL/hash'): load_snapshot(path,2025)
    def test_exact_target_annual_average_no_daily_fallback(self):
        payload={'observations':[{'d':'2026-01-01','FXAUSDCAD':{'v':'2'}},{'d':'2024-01-01','FXAUSDCAD':{'v':'1.3698'}},{'d':'2025-01-01','FXAUSDCAD':{'v':'1.3978'}}]}
        fx=select_rate(payload,2025)
        self.assertEqual(fx['rate'],'1.3978'); self.assertEqual(fx['period'],'2025'); self.assertIsNone(fx['date'])
        with self.assertRaises(ValueError): select_rate({'observations':[{'d':'2025-12-31','FXUSDCAD':{'v':'1.3706'}}]},2025)
    def test_no_rate_fails(self):
        with self.assertRaises(ValueError): select_rate({'observations':[]},2025)
    def test_usd_units_and_fx(self): self.assertEqual(cad('144794','USD',1000,{'rate':'1.3978'})[0],'202393053.2000')
    def test_cad_never_double_converted(self): self.assertEqual(cad('3051560','CAD',1,{'rate':'1.3978'})[:3],('3051560','1',False))
    def test_millions(self): self.assertEqual(cad('-344.4','CAD',1000000,None)[0],'-344400000.0')
    def test_missing_currency_rate_or_units(self):
        for args in [('1','EUR',1,None),('1','USD',1,None),('1','CAD',100,None),(None,'CAD',1,None)]: self.assertIsNone(cad(*args)[0])
    def test_same_annual_rate_noncalendar_company(self):
        # Conversion takes calendar target-year rate, never a company fiscal-end argument.
        self.assertEqual(cad('10','USD',1,{'rate':'1.3978'})[0],'13.9780')

class ValidationTests(unittest.TestCase):
    def fields(self,total='7'):
        return {f:{'amount':total if f=='total' else '1'} for f in FIELDS}
    def test_reconcile_matches(self): self.assertEqual(reconcile(self.fields())['status'],'matches')
    def test_reconcile_mismatch_total_unchanged(self):
        f=self.fields('9'); self.assertEqual(reconcile(f)['reported_minus_known'],'2'); self.assertEqual(f['total']['amount'],'9')
    def test_null_is_not_reconciled_zero(self):
        f=self.fields(); f['pension']['amount']=None; self.assertEqual(reconcile(f)['status'],'incomplete')
    def test_documented_rounding_only(self):
        with self.assertRaises(ValueError): reconcile(self.fields(),Decimal('1'))
        self.assertEqual(reconcile(self.fields('8'),Decimal('1'),'Source explicitly rounds each component to whole dollars')['status'],'matches')
    def test_ranking_nulls_ties_zero_negative(self):
        values=['10',None,'10.0','0','-1']
        records=[{'company':'A','executive':str(i),'fields':{'total':{'cad':v}}} for i,v in enumerate(values)]
        ordered=rank_records(records)
        self.assertEqual([r['rank'] for r in ordered],[1,1,3,4,None])
        self.assertEqual(ordered[-1]['fields']['total']['cad'],None)
    def test_html_source_locators(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'proxy.html';p.write_text('<h2>Summary Compensation Table</h2><table><tr><th>Year</th><th>Salary</th></tr><tr><td>2025</td><td>0</td></tr></table>')
            self.assertEqual(html_tables(p)[0]['rows'][1],['2025','0'])

class RealPilotTests(unittest.TestCase):
    def test_template_identity_fields_and_original_amounts(self):
        for r in self.output['records']:
            self.assertEqual(r['title'],r['title'].lower()); self.assertTrue(r['first_name']); self.assertTrue(r['last_name'])
            self.assertEqual(r['first_name']+' '+r['last_name'],r['executive'])
    @classmethod
    def setUpClass(cls): cls.output=json.loads((ROOT/'outputs/pilot/records.json').read_text(encoding='utf-8'))
    def test_three_companies_and_all_neos(self):
        self.assertEqual(len(self.output['records']),16)
        self.assertEqual(len({r['company'] for r in self.output['records']}),3)
    def test_annual_average_applied_to_all_usd_fields(self):
        self.assertEqual(self.output['run']['fx']['basis'],'annual_average')
        for r in self.output['records']:
            for v in r['fields'].values():
                if v['cad'] is not None and v['currency']=='USD':
                    self.assertEqual(v['applied_rate'],'1.3978'); self.assertEqual(v['fx_period'],'2025'); self.assertIsNone(v['fx_date'])
        clive=next(r for r in self.output['records'] if r['executive']=='Clive Johnson')
        self.assertEqual(clive['fields']['total']['cad'],'6764447.6234')
    def test_only_target_year_and_independent_sources(self):
        for r in self.output['records']:
            self.assertEqual(r['fiscal_end'],'2025-12-31')
            self.assertNotEqual(r['fields']['total']['evidence']['filename'],r['fields']['net_income']['evidence']['filename'])
    def test_nulls_have_reason_and_no_cad(self):
        for r in self.output['records']:
            for v in r['fields'].values():
                if v['amount'] is None: self.assertIsNone(v['cad']); self.assertTrue(v['reason'])
    def test_original_csv_unchanged(self):
        import hashlib
        self.assertEqual(hashlib.sha256((ROOT/'data/reference/1792523779.6511.csv').read_bytes()).hexdigest(),'d91f1be5a09c325e093f7d233493c82af13fef8a8541667320f05f0927214b24')
    def test_prior_year_rows_do_not_shift_names(self):
        # Golden values were checked visually against original SCT pages, never reference CSV.
        totals={r['executive']:r['fields']['total']['amount'] for r in self.output['records']}
        self.assertEqual(totals['Michael C. Mackay'],'735870')
        self.assertEqual(totals['Clive Johnson'],'4839353')
        self.assertEqual(totals['Dean Richardson'],'3051560')
    def test_former_officers_retained(self):
        former=[r for r in self.output['records'] if '(Former)' in r['position']]
        self.assertEqual(len(former),2)
    def test_changed_source_hash_fails(self):
        profile=json.loads((ROOT/'config/interfor.json').read_text())
        with self.assertRaisesRegex(ValueError,'hash mismatch'): extract_compensation({'sha256':'wrong'},profile,2025)
    def test_future_run_rejects_old_profile(self):
        profile=json.loads((ROOT/'config/interfor.json').read_text())
        with self.assertRaisesRegex(ValueError,'outside target'): extract_compensation({'sha256':profile['sha256']},profile,2026)
    def test_company_documents_parsed_once_for_two_executives(self):
        from unittest.mock import patch
        from execcomp.pipeline import run
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d)/'companies.csv'
            p.write_text('company,symbol,document,financial_document,executive,profile\nInterfor Corporation,IFP,data/documents/interfor_circular.pdf,data/documents/interfor_financials.pdf,Ian M. Fillinger,interfor\nInterfor Corporation,IFP,data/documents/interfor_circular.pdf,data/documents/interfor_financials.pdf,Michael C. Mackay,interfor\n')
            with patch('execcomp.pipeline.pdf_evidence',wraps=pdf_evidence) as reader:
                result=run(ROOT,p,Path(d)/'out',RunConfig(2025,'test'))
                self.assertEqual(len(result['records']),2)
                self.assertEqual(reader.call_count,2) # one circular and one financial statement

if __name__=='__main__': unittest.main()
