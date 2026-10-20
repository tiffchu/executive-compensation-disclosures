"""Collect original prior-period disclosures for newly added names."""
import json, hashlib
from pathlib import Path
from .documents import fetch, acquire
from .currency import annual_rate_url, select_rate, load_snapshot, cad
from .extraction import pdf_evidence, extract_compensation, html_evidence, extract_html_compensation
from .roster import names_match

def annual_snapshot(root, year, path=None):
    path=Path(path or Path(root)/'data/documents'/f'fx_annual_{year}.json')
    if not path.exists():
        url=annual_rate_url(year); raw=fetch(url); select_rate(json.loads(raw),year)
        path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
        path.with_suffix(path.suffix+'.meta.json').write_text(json.dumps({'url':url,'sha256':hashlib.sha256(raw).hexdigest()}))
    return load_snapshot(path,year)

def enrich_prior(records, companies, root, profiles, year, fx, contexts, issues):
    for company in companies:
        new=[r for r in records if r['company']==company['company'] and r.get('roster_status')=='new']
        if not new: continue
        try:
            name=company.get('prior_profile') or company.get('profile','')+'_prior'
            profile=json.loads((profiles/f'{name}.json').read_text())
            location=company.get('prior_document') or profile['document']
            path=acquire(location if location.startswith('https://') else root/location,root/'data/documents')
            if profile.get('document_format')=='html':
                evidence=html_evidence(path); parsed=extract_html_compensation(evidence,profile,year)
                evidence['pages']={'HTML document':{'text':evidence['text']}}
            else:
                evidence=pdf_evidence(path,profile['evidence_pages'],root/'data/extracted/cache')
                parsed=extract_compensation(evidence,profile,year)
            sidecar=path.with_suffix(path.suffix+'.meta.json')
            url=location if location.startswith('https://') else json.loads(sidecar.read_text())['url'] if sidecar.exists() else None
            contexts.append({'id':name,'filename':path.name,'saved_file':str(path.relative_to(root)),'sha256':evidence['sha256'],'url':url,'document_date':profile['document_date'],
                'fiscal_end':profile['fiscal_end'],'selection_note':profile['selection_note'],'page_text':{p:v['text'] for p,v in evidence['pages'].items()}})
            for r in new:
                matches=[p for p in parsed if names_match(p['executive'],r['executive'])]
                if len(matches)!=1:
                    r['prior_year']={'year':year,'fields':{},'reason':'No unique executive row in the reviewed original prior-year disclosure.'}; continue
                prior=matches[0]
                for v in prior['fields'].values():
                    v['evidence']={'document_url':url,'filename':path.name,'sha256':evidence['sha256'],'document_date':profile['document_date'],
                        'fiscal_end':profile['fiscal_end'],'table_heading':'Summary Compensation Table','page':v['page']}
                    converted,rate,usd,reason=cad(v['amount'],v['currency'],v['units'],fx)
                    v.update(cad=converted,applied_rate=rate,converted_from_usd=usd,fx_date=None,
                        fx_url=fx['url'] if usd else None,fx_period=fx['period'] if usd else None,fx_basis=fx['basis'] if usd else None)
                    if reason and not v.get('reason'): v['reason']=reason
                r['prior_year']={'year':year,'fiscal_end':profile['fiscal_end'],'fields':prior['fields'],'source_id':name,'reason':''}
        except (OSError,ValueError,KeyError,IndexError) as exc:
            issues.append({'scope':company['company']+' / prior year','reason':str(exc)})
            for r in new: r['prior_year']={'year':year,'fields':{},'reason':str(exc)}
