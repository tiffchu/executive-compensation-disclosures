"""Verify the saved workbook independently of its authoring process."""
from pathlib import Path
import json, zipfile, xml.etree.ElementTree as ET
from decimal import Decimal

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def verify_saved_workbook(path, result):
    with zipfile.ZipFile(path) as archive:
        shared=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared=[''.join(e.itertext()) for e in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        def sheet(name):
            tree=ET.fromstring(archive.read(name)); cells={}
            for cell in tree.findall('.//s:sheetData/s:row/s:c',NS):
                value=cell.find('s:v',NS); raw=value.text if value is not None else None
                if cell.get('t')=='s': raw=shared[int(raw)]
                elif cell.get('t')=='inlineStr': raw=''.join(cell.find('s:is',NS).itertext())
                cells[cell.get('r')]=(raw,cell.find('s:f',NS),cell.get('t'))
            return tree,cells
        tree,cells=sheet('xl/worksheets/sheet1.xml')
        titles=[t.get('name') for t in ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS)]
        assert titles==['Results','Source data'],titles
        fields=['total','salary','net_income','share_awards','option_awards','annual_incentive','long_term_incentive','pension','other']
        for row,r in enumerate(result['records'],7):
            for col,field in zip('EFGHIJKLM',fields):
                raw,formula,kind=cells[f'{col}{row}']; expected=r['fields'][field]['cad']
                assert formula is not None,(row,field,'Missing conversion link')
                if expected is None: assert raw=='Needs manual input',(row,field,raw)
                else: assert abs(Decimal(raw)-Decimal(expected))<Decimal('0.00001'),(row,field,raw,expected)
            rank=cells[f'A{row}'][0]
            assert rank==str(r['rank']) if r['rank'] is not None else rank in (None,''),(row,rank,r['rank'])
        errors=[(addr,value[0]) for addr,value in cells.items() if value[2]=='e']
        assert not errors,errors
        assert tree.find('.//s:pane',NS) is not None,'Frozen headers missing'
        _,source=sheet('xl/worksheets/sheet2.xml')
        for addr,(raw,formula,kind) in source.items():
            assert kind!='e',(addr,raw)
        return {'saved_xlsx_checked':str(Path(path).name),'sheets':titles,'monetary_cells_checked':len(result['records'])*9,'formula_errors':0}
