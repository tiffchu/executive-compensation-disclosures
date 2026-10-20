import re
from decimal import Decimal

FIELDS = ['salary','share_awards','option_awards','annual_incentive','long_term_incentive','pension','other','total']

def parse_amount(raw):
    raw = raw.strip()
    if not raw: return None,'not_disclosed','Blank source cell'
    if raw.casefold() in ['na','n/a','not applicable']: return None,'not_applicable','Source explicitly says not applicable'
    if raw in ['-','—','–','�']: return None,'uncertain','Source dash has no verified numeric meaning'
    clean = raw.replace('$','').replace(',','').strip()
    if re.fullmatch(r'\(\d+(?:\.\d+)?\)',clean): clean='-'+clean[1:-1]
    if not re.fullmatch(r'-?\d+(?:\.\d+)?',clean): return None,'uncertain','Unrecognized numeric token'
    return str(Decimal(clean)), 'explicit_zero' if Decimal(clean)==0 else 'reported', ''

def reconcile(fields, tolerance=Decimal('0'), rounding_reason=''):
    components = [fields[f].get('amount') for f in FIELDS[:-1]]
    total = fields['total'].get('amount')
    known = sum((Decimal(v) for v in components if v is not None),Decimal(0))
    difference = Decimal(total)-known if total is not None else None
    if tolerance and not rounding_reason: raise ValueError('Nonzero rounding tolerance requires source explanation')
    complete = total is not None and all(v is not None for v in components)
    return {'status':('matches' if abs(difference)<=tolerance else 'mismatch') if complete else 'incomplete',
            'known_components_sum':str(known),'reported_minus_known':str(difference) if difference is not None else None,
            'tolerance':str(tolerance),'rounding_reason':rounding_reason,
            'note':'Incomplete components remain null; total is copied independently from the source.' if not complete else ''}

def map_label(label):
    key = re.sub(r'[^a-z]', '', label.casefold())
    if 'deferred' in key and 'pension' in key: return None
    if 'longterm' in key and 'incentive' in key: return 'long_term_incentive'
    if 'nonequity' in key and 'annual' not in key: return None
    for needle, field in [('salary','salary'),('sharebased','share_awards'),('optionbased','option_awards'),('bonus','annual_incentive'),('annualincentive','annual_incentive'),('pension','pension'),('allother','other'),('totalcompensation','total')]:
        if needle in key: return field
    return None

def combine_annual_columns(columns, rule=None, source_text=''):
    """Combine only with an explicit source-supported review rule; preserve inputs."""
    mapped={'source_label':' + '.join(c['source_label'] for c in columns),'raw':' + '.join(c['raw'] or '(blank)' for c in columns),
        'amount':None,'status':'uncertain','reason':'Separate bonus/annual incentive amounts need a source-supported combination rule',
        'original_columns':columns,'mapping':'No arithmetic applied without source support.'}
    if not rule or not rule.get('source_text') or rule['source_text'].casefold() not in source_text.casefold(): return mapped
    if any(c['amount'] is None or map_label(c['source_label'])!='annual_incentive' for c in columns): return mapped
    total=sum((Decimal(c['amount']) for c in columns),Decimal(0))
    mapped.update(amount=str(total),status='reported',reason='',mapping=rule['explanation']+' Arithmetic: '+' + '.join(c['amount'] for c in columns)+' = '+str(total)+'.')
    return mapped

def rank_records(records):
    ordered = sorted(records, key=lambda r: (r['fields']['total']['cad'] is None,
        -Decimal(r['fields']['total']['cad'] or '0'), r['company'], r['executive']))
    last = None; current = None
    for i, record in enumerate(ordered,1):
        value = record['fields']['total']['cad']
        if value is None: record['rank']=None; continue
        numeric=Decimal(value)
        if numeric != last: current = i
        record['rank'] = current; last=numeric
    return ordered
