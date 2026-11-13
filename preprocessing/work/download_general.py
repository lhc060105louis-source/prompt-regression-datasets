import concurrent.futures, csv, hashlib, json, pathlib, time, urllib.request, zipfile

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2] if HERE.parent.name=='scripts' else HERE.parents[1]
DEST = ROOT / '构造general数据集'
RAW = DEST / 'raw'
RAW.mkdir(parents=True, exist_ok=True)
CATALOG = HERE.parent/'uci_regression_candidates.csv' if HERE.parent.name=='scripts' else ROOT/'outputs/uci_regression_candidates.csv'
rows = [r for r in csv.DictReader(CATALOG.open(encoding='utf-8-sig')) if r['priority']=='A']

def get(url, path):
    if path.exists() and path.stat().st_size > 0:
        return
    error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent':'UCI-regression-data-preparation/1.0'})
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read()
            path.write_bytes(body)
            return
        except Exception as exc:
            error = exc
            time.sleep(attempt+1)
    raise error

def download(row):
    i = row['uci_id']
    slug = row['source_url'].rsplit('/',1)[1]
    if i == '597':
        slug = 'productivity+prediction+of+garment+employees'
        row = dict(row, source_url=f'https://archive.ics.uci.edu/dataset/{i}/{slug}')
    folder = RAW / ('uci_'+i)
    folder.mkdir(exist_ok=True)
    url = f'https://archive.ics.uci.edu/static/public/{i}/{slug}.zip'
    archive = folder/'archive.zip'
    get(url, archive)
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        if bad: raise ValueError(f'Corrupt archive member: {bad}')
        for name in z.namelist():
            p = (folder/'extracted'/name).resolve()
            if not p.is_relative_to((folder/'extracted').resolve()):
                raise ValueError('Unsafe archive path')
        z.extractall(folder/'extracted')
    metadata_status='ok'
    try:
        get(f'https://archive.ics.uci.edu/api/dataset?id={i}', folder/'uci_metadata.json')
        json.loads((folder/'uci_metadata.json').read_text(encoding='utf-8'))
    except Exception as exc:
        metadata_status = str(exc)
    manifest = dict(row, download_url=url, downloaded_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), archive_bytes=archive.stat().st_size, metadata_status=metadata_status)
    (folder/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'id':i,'bytes':archive.stat().st_size,'metadata':metadata_status,'files':[str(p.relative_to(folder/'extracted')) for p in (folder/'extracted').rglob('*') if p.is_file()]}

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(download,row):row['uci_id'] for row in rows}
        results=[]
        for job in concurrent.futures.as_completed(jobs):
            try: result=job.result()
            except Exception as exc: result={'id':jobs[job],'error':str(exc)}
            results.append(result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
    (DEST/'download_inventory.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    if any('error' in r for r in results): raise SystemExit(1)
