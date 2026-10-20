from datetime import date
from decimal import Decimal
from pathlib import Path
import hashlib, json

ANNUAL_RATE_PAGE='https://www.bankofcanada.ca/rates/exchange/annual-average-exchange-rates/'

def annual_rate_url(year):
    return f'https://www.bankofcanada.ca/valet/observations/group/FX_RATES_ANNUAL/json?start_date={year}-01-01&end_date={year}-12-31'

def load_snapshot(path, year):
    path=Path(path); raw=path.read_bytes()
    metadata=json.loads(path.with_suffix(path.suffix+'.meta.json').read_text())
    url=annual_rate_url(year)
    digest=hashlib.sha256(raw).hexdigest()
    if metadata['url']!=url or metadata['sha256']!=digest:
        raise ValueError('Official FX snapshot URL/hash does not match retained evidence')
    result=select_rate(json.loads(raw),year); result['response_sha256']=digest
    return result

def select_rate(payload, year):
    choices = []
    for item in payload.get('observations',[]):
        observed = date.fromisoformat(item['d'])
        raw = item.get('FXAUSDCAD',{}).get('v')
        if raw and observed.year == year:
            choices.append((observed, Decimal(raw)))
    if len(choices)!=1: raise ValueError('Exactly one official FXAUSDCAD annual average is required for the target year')
    observed, rate = choices[0]
    if rate <= 0: raise ValueError('FX rate must be positive')
    return {'rate':str(rate),'date':None,'observation_label':observed.isoformat(),'period':str(year),
        'basis':'annual_average','series':'FXAUSDCAD','url':ANNUAL_RATE_PAGE,'data_url':annual_rate_url(year)}

def cad(amount, currency, units, fx):
    if amount is None: return None, None, False, 'Source value unavailable'
    if units not in (1,1000,1000000): return None,None,False,'Unsupported source units'
    if currency == 'CAD': return str(Decimal(amount)*units), '1', False, ''
    if currency != 'USD': return None,None,False,'Unsupported currency requires manual rate'
    if not fx: return None,None,False,'Official USD rate unavailable'
    return str(Decimal(amount)*units*Decimal(fx['rate'])), fx['rate'], True, ''
