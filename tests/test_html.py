import unittest, tempfile, sys, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from execcomp.config import ROOT
from execcomp.extraction import html_evidence, extract_html_compensation

class HTMLProxyTests(unittest.TestCase):
    def test_reviewed_html_proxy_multiyear_spans_and_locator(self):
        html='''<html><h2>Summary Compensation Table</h2><p>Year ending September 30, 2025. USD.</p>
        <table><tr><th>Name and Position</th><th>Year</th><th>Salary</th><th>Bonus</th><th>Total Compensation</th></tr>
        <tr><td rowspan="2">Ada Example Chief Executive Officer</td><td>2026</td><td>100</td><td>0</td><td>100</td></tr>
        <tr><td>2025</td><td>90</td><td>NA</td><td>90</td></tr></table></html>'''
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            path=Path(d)/'proxy.html';path.write_text(html)
            evidence=html_evidence(path)
            profile={'document_format':'html','sha256':evidence['sha256'],'original_disclosure_reviewed':True,'fiscal_end':'2025-09-30',
              'table_index':1,'header_rows':1,'year_column':1,'row_year_label':'2026','identity_column':0,
              'identity_pattern':r'(?P<name>Ada Example) (?P<position>Chief Executive Officer)','currency':'USD','expected_rows':1,
              'guards':[{'text':'Year ending September 30, 2025'}],'footnote_reference':'Synthetic test fixture only',
              'columns':[{'field':'salary','column':2,'label':'Salary'},{'field':'annual_incentive','column':3,'label':'Bonus'},
                         {'field':'total','column':4,'label':'Total Compensation'}]}
            record=extract_html_compensation(evidence,profile,2025)[0]
            self.assertEqual(record['fields']['salary']['amount'],'100')
            self.assertEqual(record['fields']['annual_incentive']['status'],'explicit_zero')
            self.assertEqual(record['fields']['total']['amount'],'100')
            self.assertIn('tr[2]',record['fields']['total']['locator'])
            self.assertEqual(record['fields']['pension']['amount'],None)
            profile['row_year_label']='2025'
            record=extract_html_compensation(evidence,profile,2025)[0]
            self.assertEqual(record['executive'],'Ada Example')
            self.assertEqual(record['fields']['salary']['amount'],'90')
            self.assertEqual(record['fields']['annual_incentive']['status'],'not_applicable')
            profile['columns'][0]['label']='Wages'
            with self.assertRaisesRegex(ValueError,'header changed'): extract_html_compensation(evidence,profile,2025)

    def test_nested_tables_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            path=Path(d)/'proxy.html';path.write_text('<table><tr><td><table><tr><td>10</td></tr></table></td></tr></table>')
            with self.assertRaisesRegex(ValueError,'Nested'): html_evidence(path)

if __name__=='__main__': unittest.main()
