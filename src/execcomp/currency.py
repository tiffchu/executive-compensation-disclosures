from datetime import date
from decimal import Decimal
from pathlib import Path
import hashlib, json

def load_snapshot(path, year):
    path=Path(path); raw=path.read_bytes()
    metadata=json.loads(path.with_suffix(path.suffix+'.meta.json').read_text())
    url=f'https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?start_date={year}-01-01&end_date={year}-12-31'
    digest=hashlib.sha256(raw).hexdigest()
    if metadata['url']!=url or metadata['sha256']!=digest:
        raise ValueError('Official FX snapshot URL/hash does not match retained evidence')
    result=select_rate(json.loads(raw),year); result['response_sha256']=digest
    return result

def select_rate(payload, year):
    cutoff = date(year,12,31)
    choices = []
    for item in payload.get('observations',[]):
        observed = date.fromisoformat(item['d'])
        raw = item.get('FXUSDCAD',{}).get('v')
        if raw and observed <= cutoff:
            choices.append((observed, Decimal(raw)))
    if not choices: raise ValueError('No official FXUSDCAD observation on or before cutoff')
    observed, rate = max(choices)
    if rate <= 0: raise ValueError('FX rate must be positive')
    return {'rate':str(rate),'date':observed.isoformat(),'url':f'https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?start_date={year}-01-01&end_date={year}-12-31'}

def cad(amount, currency, units, fx):
    if amount is None: return None, None, False, 'Source value unavailable'
    if units not in (1,1000,1000000): return None,None,False,'Unsupported source units'
    if currency == 'CAD': return str(Decimal(amount)*units), '1', False, ''
    if currency != 'USD': return None,None,False,'Unsupported currency requires manual rate'
    if not fx: return None,None,False,'Official USD rate unavailable'
    return str(Decimal(amount)*units*Decimal(fx['rate'])), fx['rate'], True, ''
