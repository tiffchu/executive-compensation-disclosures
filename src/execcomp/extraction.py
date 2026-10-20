"""Layout adapters read literal PDF cells. Unknown files cannot inherit an adapter."""
from pathlib import Path
import hashlib, json, re
import pdfplumber
from .validation import FIELDS, parse_amount, map_label, combine_annual_columns

def pdf_evidence(path, page_numbers, cache_dir):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    cache = Path(cache_dir) / (digest+'.json')
    if cache.exists():
        result = json.loads(cache.read_text(encoding='utf-8'))
        if all(str(p) in result['pages'] for p in page_numbers): return result
    result = {'sha256':digest,'filename':Path(path).name,'pages':{}}
    with pdfplumber.open(path) as pdf:
        for number in sorted(set(page_numbers)):
            page = pdf.pages[number-1]
            result['pages'][str(number)] = {'text':page.extract_text() or '', 'words':page.extract_words(), 'width':page.width,'height':page.height}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result

def joined(words):
    return ' '.join(w['text'] for w in sorted(words,key=lambda w:(round(w['top']/3),w['x0'])))

def normalized(text): return re.sub(r'\s+',' ',text).casefold()

def extract_compensation(evidence, profile, target_year):
    if evidence['sha256'] != profile['sha256']: raise ValueError('Document changed: adapter hash mismatch, review original source again')
    if not profile['original_disclosure_reviewed']: raise ValueError('Original-disclosure selection not reviewed')
    if int(profile['fiscal_end'][:4]) != target_year: raise ValueError('Actual fiscal end is outside target calendar year')
    pages = evidence['pages']
    for guard in profile['guards']:
        if normalized(guard['text']) not in normalized(pages[str(guard['page'])]['text']):
            raise ValueError(f'Source guard failed: page {guard["page"]}, {guard["text"]}')
    p = profile['table_page']; page = pages[str(p)]; words=page['words']
    ymin,ymax = profile['table_y']; year_x = profile['year_x']
    year_token=str(profile.get('row_year_label',target_year))
    anchors = sorted([w for w in words if w['text']==year_token and abs(w['x0']-year_x)<3 and ymin<w['top']<ymax],key=lambda w:w['top'])
    if len(anchors) != profile['expected_rows']: raise ValueError('Unexpected table row count; manual review required')
    records=[]
    for index, anchor in enumerate(anchors):
        top=anchor['top']; bottom=anchors[index+1]['top']-3 if index+1<len(anchors) else ymax
        identity_words=[w for w in words if w['x1']<year_x-3 and top-3<=w['top']<bottom]
        original_identity=joined(identity_words)
        # Position begins at an explicit position word. No fuzzy name guesses.
        match = re.search(r'\b(President|Executive|Senior|Director)\b',original_identity)
        if not match: raise ValueError(f'Cannot separate executive identity: {original_identity}')
        name = re.sub(r'\(\d+\)','',original_identity[:match.start()]).strip(' ,')
        position=original_identity[match.start():]
        fields={}
        for spec in profile['columns']:
            x0,x1=spec['x']
            cell_words=[w for w in words if x0<= (w['x0']+w['x1'])/2 <x1 and abs(w['top']-top)<2]
            raw=''.join(w['text'] for w in sorted(cell_words,key=lambda w:w['x0']))
            amount,status,reason=parse_amount(raw)
            field=spec['field']
            previous=fields.get(field)
            if map_label(spec['label']) != field:
                amount=None; status='uncertain'; reason='Ambiguous source heading/category mapping requires manual review'
            current={'source_label':spec['label'],'raw':raw,'amount':amount,'status':status,'reason':reason,
               'currency':profile['currency'],'units':1,'page':p,'bbox':[x0,top-2,x1,top+12],
               'mapping':spec.get('mapping','Direct mapping from the Summary Compensation Table heading.'),
               'footnote_reference':profile['footnote_reference']}
            if previous:
                if field!='annual_incentive': raise ValueError('Duplicate non-annual target category requires layout review')
                originals=previous.get('original_columns',[previous])+[current]
                fields[field]={**current,**combine_annual_columns(originals,profile.get('annual_combination_rule'),page['text'])}
            else: fields[field]=current
        for field in FIELDS:
            if field not in fields:
                fields[field]={'source_label':None,'raw':None,'amount':None,'status':'not_disclosed',
                    'reason':'No separate column in the Summary Compensation Table','currency':profile['currency'],'units':1,'page':p,
                    'mapping':'No amount inferred from other fields.','footnote_reference':profile['footnote_reference']}
        records.append({'executive':name,'position':position,'original_identity':original_identity,'fields':fields})
    if len({r['executive'] for r in records})!=len(records): raise ValueError('Duplicate executive identities')
    return records

def extract_net_income(evidence, profile):
    if evidence['sha256'] != profile['sha256']: raise ValueError('Financial source hash mismatch')
    page=evidence['pages'][str(profile['page'])]
    for term in profile['guards']:
        if normalized(term) not in normalized(page['text']): raise ValueError(f'Financial guard missing: {term}')
    lines=[line for line in page['text'].splitlines() if re.match(profile['line_pattern'],line)]
    lines=list(dict.fromkeys(lines))
    if len(lines)!=1: raise ValueError('Consolidated income line is not unique')
    matched=re.match(profile['line_pattern'],lines[0])
    raw=matched.group('amount'); amount,status,reason=parse_amount(raw)
    return {'source_label':profile['label'],'raw':raw,'amount':amount,'status':status,'reason':reason,
      'currency':profile['currency'],'units':profile['units'],'page':profile['page'],'mapping':profile['explanation'],
      'original_line':lines[0],'footnote_reference':'Audited consolidated financial statements; see source document auditor report.'}

def html_evidence(path):
    """Expand literal rowspan/colspan while keeping original cell locators."""
    from html.parser import HTMLParser
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True); self.tables=[]; self.table=None; self.row=None; self.cell=None; self.text=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='table':
                if self.table is not None: raise ValueError('Nested HTML tables require a separate reviewed adapter')
                self.table=[]; self.tables.append(self.table)
            elif tag=='tr' and self.table is not None:
                self.row=[]; self.table.append(self.row)
            elif tag in ('td','th') and self.row is not None:
                self.cell={'text':'','rowspan':int(attrs.get('rowspan','1')),'colspan':int(attrs.get('colspan','1'))}
                if self.cell['rowspan']<1 or self.cell['colspan']<1: raise ValueError('Invalid HTML span')
                self.row.append(self.cell)
        def handle_data(self,value):
            self.text.append(value)
            if self.cell is not None: self.cell['text']+=value+' '
        def handle_endtag(self,tag):
            if tag in ('td','th'): self.cell=None
            elif tag=='tr': self.row=None
            elif tag=='table': self.table=None
    reader=Reader(); raw=Path(path).read_bytes(); reader.feed(raw.decode('utf-8-sig'))
    tables=[]
    for number,table in enumerate(reader.tables,1):
        grid={}
        for r,cells in enumerate(table):
            c=0
            for source_column,cell in enumerate(cells):
                while (r,c) in grid: c+=1
                value={'text':' '.join(cell['text'].split()),'locator':f'(//table)[{number}]//tr[{r+1}]/*[self::td or self::th][{source_column+1}]'}
                for rr in range(r,r+cell['rowspan']):
                    for cc in range(c,c+cell['colspan']):
                        if (rr,cc) in grid: raise ValueError('Overlapping HTML spans')
                        grid[rr,cc]=value
                c+=cell['colspan']
        width=max((c for r,c in grid),default=-1)+1
        tables.append([[grid.get((r,c),{'text':'','locator':f'(//table)[{number}]//tr[{r+1}] (missing cell)'}) for c in range(width)] for r in range(len(table))])
    return {'sha256':hashlib.sha256(raw).hexdigest(),'filename':Path(path).name,'text':' '.join(reader.text),'tables':tables}

def extract_html_compensation(evidence, profile, target_year):
    """A reviewed definitive-proxy profile names the exact table and columns."""
    if evidence['sha256']!=profile['sha256']: raise ValueError('Document changed: adapter hash mismatch')
    if not profile['original_disclosure_reviewed']: raise ValueError('Original-disclosure selection not reviewed')
    if int(profile['fiscal_end'][:4])!=target_year: raise ValueError('Actual fiscal end is outside target calendar year')
    for guard in profile['guards']:
        if normalized(guard['text']) not in normalized(evidence['text']): raise ValueError('HTML source guard failed')
    table=evidence['tables'][profile['table_index']-1]; records=[]
    for row in table[profile['header_rows']:]:
        if row[profile['year_column']]['text']!=str(profile.get('row_year_label',target_year)): continue
        raw_identity=row[profile['identity_column']]['text']
        identity_match=re.fullmatch(profile['identity_pattern'],raw_identity)
        if not identity_match: raise ValueError('HTML executive identity needs review')
        fields={}
        for column in profile['columns']:
            field=column['field']; cell=row[column['column']]
            label=table[column.get('header_row',0)][column['column']]['text']
            if normalized(label)!=normalized(column['label']): raise ValueError('HTML header changed; review mapping')
            amount,status,reason=parse_amount(cell['text'])
            if map_label(label)!=field: amount=None;status='uncertain';reason='Ambiguous source heading/category mapping requires manual review'
            previous=fields.get(field)
            current={'source_label':label,'raw':cell['text'],'amount':amount,'status':status,'reason':reason,
                'currency':profile['currency'],'units':profile.get('units',1),'page':None,'locator':cell['locator'],
                'mapping':column.get('mapping','Direct reviewed HTML table column mapping.'),'footnote_reference':profile['footnote_reference']}
            if previous:
                if field!='annual_incentive': raise ValueError('Duplicate non-annual category requires review')
                fields[field]={**current,**combine_annual_columns(previous.get('original_columns',[previous])+[current],profile.get('annual_combination_rule'),evidence['text'])}
            else: fields[field]=current
        for field in FIELDS:
            fields.setdefault(field,{'source_label':None,'raw':None,'amount':None,'status':'not_disclosed','reason':'No separate column in Summary Compensation Table',
                'currency':profile['currency'],'units':profile.get('units',1),'page':None,'locator':f'(//table)[{profile["table_index"]}]',
                'mapping':'No inferred amount.','footnote_reference':profile['footnote_reference']})
        records.append({'executive':identity_match['name'],'position':identity_match['position'],'original_identity':raw_identity,'fields':fields})
    if len(records)!=profile['expected_rows'] or len({r['executive'] for r in records})!=len(records): raise ValueError('Unexpected or duplicate HTML executive rows')
    return records
