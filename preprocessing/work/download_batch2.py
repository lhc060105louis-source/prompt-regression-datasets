import concurrent.futures,csv,hashlib,json,pathlib,time,urllib.request,zipfile
from download_general import ROOT,DEST,get

CATALOG=ROOT/'outputs/uci_regression_candidates.csv'
def download(row):
    i=row['uci_id'];folder=DEST/'raw'/f'uci_{i}';folder.mkdir(parents=True,exist_ok=True)
    get(f'https://archive.ics.uci.edu/api/dataset?id={i}',folder/'uci_metadata.json')
    api=json.loads((folder/'uci_metadata.json').read_text(encoding='utf-8'))['data']
    url=api['repository_url'];slug=url.rsplit('/',1)[1]
    if i=='925':
        # UCI is an external catalogue entry; use its DOI-matched original release.
        download_url='https://physionet.org/files/face-oral-temp-data/1.0.0/'
        names=['FLIR_groups1and2.csv','ICI_groups1and2.csv','LICENSE.txt','SHA256SUMS.txt','_Table1.pdf','_Table2.pdf']
        extracted=folder/'extracted';extracted.mkdir(exist_ok=True)
        for name in names:get(download_url+name,extracted/name)
        get('https://physionet.org/content/face-oral-temp-data/1.0.0/',folder/'source_page.html')
        files={n:hashlib.sha256((extracted/n).read_bytes()).hexdigest() for n in names}
        sha=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
        size=sum((extracted/n).stat().st_size for n in names)
    else:
        download_url=f'https://archive.ics.uci.edu/static/public/{i}/{slug}.zip';archive=folder/'archive.zip'
        get(download_url,archive)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for name in z.namelist():assert (folder/'extracted'/name).resolve().is_relative_to((folder/'extracted').resolve())
            z.extractall(folder/'extracted')
        sha=hashlib.sha256(archive.read_bytes()).hexdigest();size=archive.stat().st_size
    manifest=dict(row,source_url=url,download_url=download_url,downloaded_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),archive_sha256=sha,archive_bytes=size,metadata_status='ok',batch=2)
    if i=='925':manifest.update(source_release='PhysioNet 1.0.0',file_sha256=files,hash_type='sha256_of_sorted_file_hash_manifest',license_observed='CC0 1.0 (original PhysioNet release)')
    (folder/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(id=int(i),bytes=size,files=[str(p.relative_to(folder/'extracted')) for p in (folder/'extracted').rglob('*') if p.is_file()])
if __name__=='__main__':
    rows=[r for r in csv.DictReader(CATALOG.open(encoding='utf-8-sig')) if r['priority']=='B']
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(download,r):r['uci_id'] for r in rows}
        for future in concurrent.futures.as_completed(futures):
            try:r=future.result()
            except Exception as exc:r={'id':int(futures[future]),'error':str(exc)}
            results.append(r);print(json.dumps(r,ensure_ascii=True),flush=True)
    (DEST/'download_inventory_batch2.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    if any('error' in r for r in results):raise SystemExit(1)
