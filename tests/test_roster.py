import unittest, json, sys, tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from execcomp.config import ROOT, RunConfig
from execcomp.roster import read_baseline, classify, company_key, names_match
from execcomp.prior import enrich_prior, annual_snapshot
from execcomp.currency import select_rate
from execcomp.extraction import pdf_evidence, extract_compensation

def baseline(name,company='Acme Corp',row=2):
    first,last=name.rsplit(' ',1)
    return dict(executive=name,company=company,first_name=first,last_name=last,title='president',symbol='AC',baseline_row=row)

class RosterTests(unittest.TestCase):
    def test_conflicting_middle_initials_are_not_same_person(self):
        self.assertFalse(names_match('Ada M. Smith','Ada R. Smith'))
        self.assertFalse(names_match('Robert Smith','Rob Smith'))
    def test_unprocessed_or_failed_company_cannot_be_removed(self):
        b=[baseline('Ada Smith'),baseline('Bo Jones','Other Corp',3)]
        removed,unknown,excluded=classify([],b,[{'company':'Acme Corporation'}],set())
        self.assertEqual(removed,[]);self.assertEqual(unknown[0]['roster_status'],'unverified');self.assertEqual(excluded,1)
    def test_verified_missing_is_removed_and_new_is_added(self):
        records=[dict(executive='New Person',company='Acme Corporation')]
        removed,unknown,_=classify(records,[baseline('Ada Smith')],[{'company':'Acme Corporation'}],{company_key('Acme')})
        self.assertEqual(records[0]['roster_status'],'new');self.assertEqual(removed[0]['executive'],'Ada Smith');self.assertEqual(unknown,[])
    def test_unique_extra_middle_initial_is_existing(self):
        records=[dict(executive='Ian M. Fillinger',company='Acme Corporation')]
        removed,unknown,_=classify(records,[baseline('Ian Fillinger')],[{'company':'Acme'}],{company_key('Acme')})
        self.assertEqual(records[0]['roster_status'],'existing');self.assertEqual(removed+unknown,[])
    def test_middle_initial_collision_is_reviewed_not_removed(self):
        records=[dict(executive='Ada Smith',company='Acme')]
        removed,unknown,_=classify(records,[baseline('Ada M. Smith'),baseline('Ada R. Smith',row=3)],[{'company':'Acme'}],{company_key('Acme')})
        self.assertEqual(records[0]['roster_status'],'identity review');self.assertEqual(removed,[]);self.assertEqual(len(unknown),2)
    def test_template_only_identity_fields_are_read(self):
        rows,meta=read_baseline(ROOT/'data/templates/execs_comp_template.xlsx')
        self.assertEqual(len(rows),120);self.assertTrue(meta['sha256'])
        self.assertTrue(all('fields' not in r and 'email' not in r for r in rows))
    def test_saved_output_can_be_next_baseline_without_removed_rows(self):
        rows,_=read_baseline(ROOT/'outputs/pilot/execs_comp_roster.xlsx')
        self.assertEqual(len(rows),16)
        self.assertNotIn('Brad Boyd',[r['executive'] for r in rows])

class PriorYearTests(unittest.TestCase):
    def test_2027_prior_uses_2025_annual_rate_and_original_usd(self):
        config=RunConfig.start(datetime(2027,1,1));year=config.target_year-1
        fx=select_rate({'observations':[{'d':'2025-01-01','FXAUSDCAD':{'v':'1.3978'}},{'d':'2026-01-01','FXAUSDCAD':{'v':'1.42'}}]},year)
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as folder:
            folder=Path(folder)
            (folder/'acme_prior.json').write_text(json.dumps({'document':'original.pdf','evidence_pages':[1],'document_date':'2026-03-01','fiscal_end':'2025-12-31','selection_note':'Original reviewed'}))
            current=[dict(company='Acme',executive='Ada Smith',roster_status='new'),dict(company='Acme',executive='Bo Jones',roster_status='new'),dict(company='Acme',executive='Existing Person',roster_status='existing')]
            fields={name:dict(amount=amount,currency='USD',units=1000,page=1,reason='') for name,amount in [('total','10'),('salary','0'),('other',None)]}
            with patch('execcomp.prior.acquire',return_value=folder/'original.pdf'),patch('execcomp.prior.pdf_evidence',return_value={'sha256':'hash','pages':{'1':{'text':'original'}}}),patch('execcomp.prior.extract_compensation',return_value=[dict(executive='Ada Smith',fields=fields)]) as extract:
                enrich_prior(current,[{'company':'Acme','profile':'acme'}],folder,folder,year,fx,[],[])
            self.assertEqual(extract.call_args.args[2],2025)
            values=current[0]['prior_year']['fields']
            self.assertEqual(values['total']['cad'],'13978.0000');self.assertEqual(values['total']['amount'],'10');self.assertEqual(values['total']['fx_period'],'2025')
            self.assertEqual(values['salary']['cad'],'0.0000');self.assertIsNone(values['other']['cad'])
            self.assertEqual(current[1]['prior_year']['fields'],{});self.assertNotIn('prior_year',current[2])
    def test_missing_prior_original_leaves_blank(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as folder:
            r=[dict(company='Acme',executive='Ada Smith',roster_status='new')];issues=[]
            enrich_prior(r,[{'company':'Acme','profile':'unknown'}],Path(folder),Path(folder),2024,None,[],issues)
            self.assertEqual(r[0]['prior_year']['fields'],{});self.assertEqual(len(issues),1)
    def test_prior_rate_snapshot_rejects_wrong_year(self):
        with self.assertRaises(ValueError): annual_snapshot(ROOT,2025,ROOT/'data/documents/fx_annual_2024.json')
    def test_prior_superscript_identity_does_not_shift_rows(self):
        p=json.loads((ROOT/'config/methanex_prior.json').read_text())
        evidence=pdf_evidence(ROOT/p['document'],p['evidence_pages'],ROOT/'data/extracted/cache')
        rows=extract_compensation(evidence,p,2024)
        self.assertEqual([r['executive'] for r in rows],['Rich Sumner','Dean Richardson','Gustavo Parra','Karine Delbarre','Brad Boyd'])
        self.assertNotIn('Parra',rows[1]['position'])
    def test_pilot_prior_values_from_originals_and_roster_counts(self):
        result=json.loads((ROOT/'outputs/pilot/records.json').read_text(encoding='utf-8'))
        new=[r for r in result['records'] if r['roster_status']=='new']
        self.assertEqual(len(new),8);self.assertEqual(len(result['removed_executives']),2)
        prior={r['executive']:r.get('prior_year',{}).get('fields',{}).get('total',{}).get('cad') for r in new}
        self.assertEqual(prior['Gustavo Parra'],'2598678');self.assertEqual(prior['Karine Delbarre'],'2913704')
        self.assertIsNone(prior['Michael C. Mackay']);self.assertIsNone(prior['Kevin Maloney'])
        self.assertEqual(sum(v is not None for v in prior.values()),6)

if __name__=='__main__': unittest.main()
