"""Compare identities only. Reference workbook amounts are never source evidence."""
import hashlib, re, zipfile, posixpath
import xml.etree.ElementTree as ET
from pathlib import Path
from .inputs import identity, output_identity

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def company_key(name):
    words=re.findall(r'[\w]+',name.casefold())
    while words and words[-1] in {'corp','corporation','inc','incorporated','ltd','limited','plc'}: words.pop()
    return identity(' '.join(words))

def name_key(name):
    # Only middle initials may be omitted; full middle names remain significant.
    words=name.split()
    return tuple(identity(w) for i,w in enumerate(words) if i in (0,len(words)-1) or len(identity(w))!=1)

def names_match(left,right):
    if name_key(left)!=name_key(right): return False
    initials=lambda name: [identity(w) for w in name.split()[1:-1] if len(identity(w))==1]
    a,b=initials(left),initials(right)
    return not a or not b or a==b

def read_baseline(path):
    path=Path(path)
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        book=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=book.findall('s:sheets/s:sheet',NS)
        selected=next((s for s in sheets if s.get('name')=='Results'),sheets[0])
        rid=selected.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target=next(r.get('Target') for r in rels if r.get('Id')==rid)
        member=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        rows=[]
        for row in ET.fromstring(z.read(member)).findall('s:sheetData/s:row',NS):
            cells={}
            for c in row.findall('s:c',NS):
                v=c.find('s:v',NS); value=v.text if v is not None else ''
                if c.get('t')=='s': value=strings[int(value)]
                elif c.get('t')=='inlineStr': value=''.join(c.find('s:is',NS).itertext())
                cells[re.sub(r'\d','',c.get('r'))]=(value or '').strip()
            if row.get('r')=='1' and [cells.get(c) for c in ['A','B','E']]!=['First Name','Last Name','Company']:
                raise ValueError('Baseline requires template First Name, Last Name and Company columns')
            if row.get('r')=='1' or not all(cells.get(c) for c in ['A','B','E']) or cells.get('AR')=='removed': continue
            name=cells['A']+' '+cells['B']
            rows.append(dict(executive=name,company=cells['E'],symbol=cells.get('AJ',''),
                baseline_row=int(row.get('r')),**output_identity(name,cells.get('F',''))))
    keys=[(company_key(r['company']),identity(r['executive'])) for r in rows]
    if len(keys)!=len(set(keys)): raise ValueError('Duplicate baseline company/executive identities')
    return rows,{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sheet':selected.get('name')}

def classify(records, baseline, companies, verified):
    removed=[]; unverified=[]; excluded=0
    processed={company_key(c['company']) for c in companies}
    # Classify against all rows at once: a collision never certifies a removal.
    for r in records:
        pool=[b for b in baseline if company_key(b['company'])==company_key(r['company'])]
        matches=[b for b in pool if names_match(b['executive'],r['executive'])]
        peers=[x for x in records if company_key(x['company'])==company_key(r['company']) and name_key(x['executive'])==name_key(r['executive'])]
        r['roster_status']='existing' if len(matches)==1 and len(peers)==1 else 'identity review' if matches else 'new'
        if r['roster_status']=='existing': r['baseline_row']=matches[0]['baseline_row']
    for b in baseline:
        key=company_key(b['company'])
        if key not in processed: excluded+=1; continue
        matches=[r for r in records if company_key(r['company'])==key and names_match(r['executive'],b['executive'])]
        if len(matches)==1 and matches[0]['roster_status']=='existing': continue
        if matches:
            status='identity review'; note='Ambiguous name match; removal not certified.'
        elif key in verified:
            status='removed'; note='Absent from the verified full target-year compensation roster; this does not establish employment termination.'
        else:
            status='unverified'; note='Full target-year roster unavailable or not reviewed; removal not certified.'
        (removed if status=='removed' else unverified).append(dict(b,roster_status=status,status=note,rank=None,fiscal_end=None))
    return removed,unverified,excluded
