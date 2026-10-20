import csv, re, unicodedata
from collections import OrderedDict

def identity(name):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', name).casefold())

def output_identity(name, position):
    parts=name.strip().rsplit(None,1)
    if len(parts)!=2: return {'first_name':name.strip(),'last_name':None,'title':re.sub(r'\(\d+\)','',position).lower().strip()}
    return {'first_name':parts[0],'last_name':parts[1],'title':re.sub(r'\(\d+\)','',position).lower().strip()}

def match_executive(requested, names):
    matches = [n for n in names if identity(n) == identity(requested)]
    if len(matches) != 1:
        raise ValueError(f'Executive identity requires exact, unique match: {requested}')
    return matches[0]

def load_companies(path):
    groups = OrderedDict()
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not {'company','symbol'} <= set(reader.fieldnames or []):
            raise ValueError('CSV requires company and symbol columns')
        for row in reader:
            if not row['company'].strip() or not row['symbol'].strip():
                raise ValueError('Company and symbol must be populated')
            key = identity(row['company']), row['symbol'].strip().upper()
            group = groups.setdefault(key, dict(row, executives=[], all_executives=False))
            for field in ['ir_url','document','financial_document','profile']:
                if group.get(field) and row.get(field) and group[field] != row[field]:
                    raise ValueError(f'Conflicting {field} for {key}')
                if row.get(field): group[field] = row[field]
            name = row.get('executive','').strip()
            if not name: group['all_executives'] = True
            elif name not in group['executives']: group['executives'].append(name)
    return list(groups.values())
