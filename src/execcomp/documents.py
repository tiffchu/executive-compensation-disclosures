"""Conservative retrieval: robots, HTTP failures and authentication never bypassed."""
import hashlib, json, shutil
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from urllib.error import HTTPError
from html.parser import HTMLParser

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.current=[dict(attrs).get('href',''),'']
    def handle_data(self,data):
        if self.current is not None: self.current[1]+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:
            self.links.append(self.current); self.current=None

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables=[]; self.stack=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':
            table={'locator':f'document table index {len(self.tables)+1}','rows':[],'review':'Review rowspan/colspan and nested tables before mapping.'}
            self.tables.append(table); self.stack.append(table)
        elif tag=='tr' and self.stack: self.row=[]; self.stack[-1]['rows'].append(self.row)
        elif tag in ('td','th') and self.row is not None: self.cell=''
    def handle_data(self,data):
        if self.cell is not None: self.cell+=data+' '
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None and self.row is not None:
            self.row.append(' '.join(self.cell.split())); self.cell=None
        elif tag=='tr': self.row=None
        elif tag=='table' and self.stack: self.stack.pop()

AGENT = 'ExecutiveDisclosureResearch/0.1'

def fetch(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https': raise ValueError('Only HTTPS downloads supported')
    robots_url = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    # Failure to establish access policy requires a local supplied file.
    try:
        with urlopen(Request(robots_url, headers={'User-Agent':AGENT}), timeout=30) as response:
            rules = response.read().decode('utf-8', errors='replace')
    except HTTPError as exc:
        if exc.code in (404,410): rules=''
        else: raise PermissionError(f'Cannot establish allowed access: robots HTTP {exc.code}; supply local document') from exc
    robot = RobotFileParser(); robot.parse(rules.splitlines())
    if not robot.can_fetch(AGENT, url): raise PermissionError('robots.txt disallows retrieval; supply local document')
    with urlopen(Request(url, headers={'User-Agent':AGENT}), timeout=60) as response:
        return response.read()

def acquire(location, directory):
    location=str(location)
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    if location.startswith('https://'):
        suffix = '.pdf' if '.pdf' in location.lower() else '.html'
        path = directory / (hashlib.sha256(location.encode()).hexdigest()[:20]+suffix)
        if not path.exists():
            payload = fetch(location)
            if suffix == '.pdf' and not payload.startswith(b'%PDF'): raise ValueError('Server did not return PDF')
            path.write_bytes(payload)
        return path
    path = Path(location)
    if not path.is_file(): raise FileNotFoundError(location)
    if path.resolve().parent == directory.resolve(): return path
    # Preserve local evidence in this repository, avoiding name collisions.
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    dest = directory / (digest[:20]+path.suffix.lower())
    if path.resolve() != dest.resolve() and not dest.exists(): shutil.copyfile(path, dest)
    return dest

def discover(ir_url, year):
    """Return candidates only. Publication year is never proof of period coverage."""
    parser=Links(); parser.feed(fetch(ir_url).decode('utf-8',errors='replace'))
    candidates = []
    for href,title in parser.links:
        url = urljoin(ir_url, href)
        if any(s in (title+' '+url).lower() for s in ['circular','def14a','def-14a','definitive proxy','proxy statement']):
            candidates.append({'url':url,'title':title,'status':'Needs document/period review','target_year':year})
    return candidates

def html_tables(path):
    """Precise locators and untouched cell labels for reviewer-configured HTML adapters."""
    parser=Tables(); parser.feed(Path(path).read_text(encoding='utf-8',errors='replace')); return parser.tables
