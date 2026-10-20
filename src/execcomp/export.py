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
        mapping=result['run']['template']['mapping']; usd_checked=0
        for row,r in enumerate(result['records'],2):
            for spec in mapping['fields']:
                col=spec['cad'];field=spec['field']
                raw,formula,kind=cells[f'{col}{row}']; expected=r['fields'][field]['cad']
                assert formula is not None,(row,field,'Missing conversion link')
                if expected is None: assert raw in (None,''),(row,field,raw)
                else: assert abs(Decimal(raw)-Decimal(expected))<Decimal('0.00001'),(row,field,raw,expected)
                usd=cells.get(f'{spec["usd"]}{row}',(None,None,None))[0];v=r['fields'][field]
                if v['currency']=='USD' and v['amount'] is not None:
                    assert abs(Decimal(usd)-Decimal(v['amount'])*v['units'])<Decimal('0.00001'),(row,field,'Original USD differs')
                    usd_checked+=1
                else: assert usd in (None,''),(row,field,'USD value inferred from non-USD source')
            for col,key in [('A','first_name'),('B','last_name'),('E','company'),('F','title'),('AJ','symbol')]:
                assert cells.get(f'{col}{row}',(None,None,None))[0]==r[key],(row,key)
            assert r['title']==r['title'].lower(),(row,'Title case')
            for col in mapping['blank_columns']: assert cells.get(f'{col}{row}',(None,None,None))[0] in (None,''),(row,col,'Ignored cell populated')
            assert cells.get(f'AR{row}',(None,None,None))[0]==r['roster_status'],(row,'Roster status')
            prior=r.get('prior_year',{}).get('fields',{}) if r['roster_status']=='new' else {}
            for spec in mapping['fields']:
                v=prior.get(spec['field'],{}); expected=v.get('cad')
                raw=cells.get(f'{spec["prior_cad"]}{row}',(None,None,None))[0]
                if expected is None: assert raw in (None,''),(row,spec['field'],'Unexpected prior CAD')
                else: assert abs(Decimal(raw)-Decimal(expected))<Decimal('0.00001'),(row,spec['field'],'Prior CAD differs')
                raw=cells.get(f'{spec["prior_usd"]}{row}',(None,None,None))[0]
                if v.get('currency')=='USD' and v.get('amount') is not None:
                    assert abs(Decimal(raw)-Decimal(v['amount'])*v['units'])<Decimal('0.00001')
                    if v['cad'] is not None: assert v['fx_period']==str(result['run']['target_year']-1)
                else: assert raw in (None,''),(row,spec['field'],'Unexpected prior USD')
            rank=cells[f'AK{row}'][0]
            assert rank==str(r['rank']) if r['rank'] is not None else rank in (None,''),(row,rank,r['rank'])
        placeholders=result.get('removed_executives',[])+result.get('unverified_executives',[])
        for row,r in enumerate(placeholders,len(result['records'])+2):
            assert cells[f'A{row}'][0]==r['first_name'] and cells[f'B{row}'][0]==r['last_name']
            assert cells[f'AR{row}'][0]==r['roster_status']
            for col in ['AK']+[s[k] for s in mapping['fields'] for k in ['usd','cad','prior_usd','prior_cad']]:
                assert cells.get(f'{col}{row}',(None,None,None))[0] in (None,''),(row,col,'Placeholder compensation/rank')
        rules=tree.findall('.//s:conditionalFormatting/s:cfRule',NS)
        red=next((r for r in rules if r.find('s:formula',NS) is not None and r.find('s:formula',NS).text.lstrip('=')=='$AR2="removed"'),None)
        assert red is not None,'Removal row conditional formatting missing'
        styles=ET.fromstring(archive.read('xl/styles.xml'))
        dxf=styles.findall('s:dxfs/s:dxf',NS)[int(red.get('dxfId'))]
        assert any(c.get('rgb','').upper().endswith('FFC7CE') for c in list(dxf.findall('.//s:fgColor',NS))+list(dxf.findall('.//s:bgColor',NS))),'Removal fill must be red'
        errors=[(addr,value[0]) for addr,value in cells.items() if value[2]=='e']
        assert not errors,errors
        assert tree.find('.//s:pane',NS) is not None,'Frozen headers missing'
        _,source=sheet('xl/worksheets/sheet2.xml')
        for addr,(raw,formula,kind) in source.items():
            assert kind!='e',(addr,raw)
        return {'saved_xlsx_checked':str(Path(path).name),'sheets':titles,'cad_cells_checked':len(result['records'])*8,
            'original_usd_cells_checked':usd_checked,'blank_columns_checked':len(mapping['blank_columns']),
            'prior_cad_cells_checked':len(result['records'])*8,'removed_rows_checked':len(result.get('removed_executives',[])),
            'red_removal_rule':'verified','identity_and_lowercase_titles':'verified','formula_errors':0}
