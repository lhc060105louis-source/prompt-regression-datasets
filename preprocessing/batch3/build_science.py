"""Build approved S1/S2/S4 candidates. No model fitting; raw downloads are immutable caches."""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, math, pathlib, sys
from functools import reduce
import requests

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / 'raw'
OUT = ROOT / 'candidates'
PINS={'freesolv':'6c7d19b4b565537365ffd22006aa2cd4643200c6',
      'gb1':'dbdd7639187e0b8f22359f404ce4d1d950fcc8a9',
      'flip':'e74069fe09490c6a44a8d7ff8c2811b61f24ec82'}
DATA_HASHES={'freesolv/database.txt':'2d13f095713bc39b85f85dd7b4e5483fbb12fc694bf253bb1d92a4c4d484f260',
             'gb1/result/Mutfit':'fef5c2267d72a2a4520a444aa68ce358492b49fcbeaf222f42a9a3f2a21a4552',
             'jdft2d/matbench_jdft2d.json.gz':'26057dc4524e193e32abffb296ce819b58b6e11d1278cae329a2f97817a4eddf',
             'jdft2d/jdft_2d-7-7-2018.json':'eb0c39185a49ce15ff3bf4ceace6c8d3f4dcf72e055247319c7308d5754c6d82'}

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def get(dataset, filename, url):
    p = RAW / dataset / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        r = requests.get(url, timeout=180); r.raise_for_status()
        p.write_bytes(r.content)
    return {'relativepath': f'{dataset}/{filename}', 'url': url, 'sha256': sha(p), 'bytes': p.stat().st_size}

def download():
    for dataset, repo, branch, names in [
        ('freesolv','MobleyLab/FreeSolv','master',['database.txt','README.md','LICENSE']),
        ('gb1','wchnicholas/ProteinGFourMutants','master',['result/Mutfit','README.md']),
    ]:
        cache = RAW / dataset / 'source_manifest.json'
        if cache.exists():
            print(dataset, 'cached', flush=True); continue
        commit_file = get(dataset, 'commit.json', f'https://api.github.com/repos/{repo}/commits/{PINS[dataset]}')
        commit = json.loads((RAW/dataset/'commit.json').read_text(encoding='utf-8'))['sha']
        assert commit==PINS[dataset]
        files=[commit_file]
        for name in names:
            try: files.append(get(dataset,name,f'https://raw.githubusercontent.com/{repo}/{commit}/{name}'))
            except requests.HTTPError as e:
                if name=='LICENSE' and e.response.status_code==404: continue
                raise
        dump(cache,{'dataset_id':dataset,'repository':repo,'commit':commit,'files':files})
        print(dataset,commit,[(x['relativepath'],x['bytes']) for x in files],flush=True)
    ds='jdft2d'
    files=[get(ds,'matbench_jdft2d.json.gz','https://ml.materialsproject.org/projects/matbench_jdft2d.json.gz'),
           get(ds,'figshare_v1.json','https://api.figshare.com/v2/articles/6815705/versions/1')]
    dump(RAW/ds/'source_manifest.json',{'dataset_id':ds,'source_version':'JARVIS 2D 2018-07-07 v1 / Matbench cached gzip SHA256','files':files})
    print(ds,[(x['relativepath'],x['bytes']) for x in files],flush=True)

def extra_sources():
    p=RAW/'gb1'/'source_manifest.json'; m=json.loads(p.read_text(encoding='utf-8'))
    for name in ['script/Mapper5_NW.py','Fasta/SeqInfo.fa']:
        item=get('gb1',name,f'https://raw.githubusercontent.com/wchnicholas/ProteinGFourMutants/{m["commit"]}/{name}')
        if not any(x['relativepath']==item['relativepath'] for x in m['files']):m['files'].append(item)
    item=get('gb1','FLIP_commit.json',f'https://api.github.com/repos/J-SNACKKB/FLIP/commits/{PINS["flip"]}')
    if not any(x['relativepath']==item['relativepath'] for x in m['files']):m['files'].append(item)
    commit=json.loads((RAW/'gb1/FLIP_commit.json').read_text(encoding='utf-8'))['sha']
    assert commit==PINS['flip']
    item=get('gb1','FLIP_README_license.md',f'https://raw.githubusercontent.com/J-SNACKKB/FLIP/{commit}/splits/gb1/README.md')
    if not any(x['relativepath']==item['relativepath'] for x in m['files']):m['files'].append(item)
    dump(p,m)

def manifest(ds):
    m=json.loads((RAW/ds/'source_manifest.json').read_text(encoding='utf-8'))
    for f in m['files']:
        assert sha(RAW/f['relativepath'])==f['sha256'], f['relativepath']
        if f['relativepath'] in DATA_HASHES:assert f['sha256']==DATA_HASHES[f['relativepath']]
    return m

def write_candidates(ds, rows, meta):
    out=OUT/f'{ds}.jsonl';out.parent.mkdir(parents=True,exist_ok=True)
    seen=set();groups=collections.Counter();labels=[];flags=collections.Counter()
    with out.open('w',encoding='utf-8',newline='\n') as f:
        for r in rows:
            assert isinstance(r['input'],dict) and r['input']
            assert isinstance(r['label'],(float,int)) and math.isfinite(r['label'])
            assert r['source_refs'] and r['split']=='unassigned'
            encoded=json.dumps(r,ensure_ascii=False,allow_nan=False,separators=(',',':'))
            key=json.dumps([r['task_key'],r['input'],r['label']],sort_keys=True,allow_nan=False)
            assert key not in seen, ('duplicate candidate',ds,r['source_refs'])
            seen.add(key);groups[r['group_key']]+=1;labels.append(r['label']);flags.update(r['quality_flags'])
            f.write(encoded+'\n')
    meta['output_candidate_records']=len(labels)
    meta['validation']={'status':'passed','all_source_labels_checked':True,'finite_labels':len(labels),
                        'input_label_duplicate_records':0,'group_count':len(groups),'largest_group':max(groups.values()),
                        'label_min':min(labels),'label_max':max(labels),'zero_labels':labels.count(0),
                        'quality_flag_counts':dict(flags),'candidate_sha256':sha(out),
                        'no_training_executed':True}
    dump(OUT/f'{ds}.meta.json',meta)
    print(ds,meta['validation'],flush=True)

def base_meta(ds, name, source_url, task_key, instruction, target, unit, field_description):
    m=manifest(ds)
    return {'dataset_id':ds,'name':name,'source_url':source_url,
            'version':m.get('commit',m.get('source_version')),'source_files':m['files'],
            'tasks':{task_key:{'instruction':instruction,'target_name':target,'unit':unit,'type':'continuous','field_description':field_description}},
            'field_descriptions':field_description,'invalid_label_examples':0,'excluded_source_rows':0,
            'split_policy':'All records remain unassigned; do not randomly split near-identical source entities.',
            'missing_policy':'No labels are imputed. Only complete supported structures and finite observed source labels are emitted.',
            'precision_policy':'Candidate keeps parsed source numbers. Release formatter caps all numeric values at 12 significant digits.',
            'license':{'name':'CC BY 4.0','url':'https://creativecommons.org/licenses/by/4.0/'},
            'quality_findings':[]}

def build_freesolv():
    vendor=RAW/'freesolv/_vendor'
    if vendor.exists():sys.path.insert(0,str(vendor))
    from rdkit import Chem, rdBase
    from rdkit.Chem.Scaffolds import MurckoScaffold
    ds='freesolv';task='experimental_hydration_free_energy';target='experimental_hydration_free_energy';unit='kcal/mol'
    meta=base_meta(ds,'FreeSolv experimental hydration free energy','https://github.com/MobleyLab/FreeSolv',task,
        'Predict the experimental hydration free energy in water for the molecule represented by the SMILES.',target,unit,
        {'smiles':'RDKit canonical isomeric SMILES; no target-derived properties or experimental uncertainty are input.'})
    meta['license'].update(evidence='README.md License section and LICENSE at the frozen source commit.',
        caveat='Upstream authors license their rights under CC BY 4.0; any original third-party licensing restrictions remain applicable.')
    meta['source_citation']='Mobley DL and Guthrie JP. FreeSolv: a database of experimental and calculated hydration free energies, with input files. J Comput Aided Mol Des (2014). https://doi.org/10.1007/s10822-014-9747-x'
    meta['target_origin']='experimental measurement collected by FreeSolv'
    meta['grouping_rule']='RDKit Bemis-Murcko scaffold without chirality; all acyclic molecules share the empty-scaffold group. Canonical isomeric SMILES identify molecules.'
    meta['split_policy']='Unassigned. Use scaffold groups for held-out chemical families; the 320-member acyclic group makes folds highly imbalanced. Do not claim a balanced scaffold benchmark.'
    meta['excluded_input_columns']=['compound_id','iupac_name','experimental_value','experimental_uncertainty','calculated_value','calculated_uncertainty','experimental_reference','calculated_reference','text_notes']
    meta['rdkit_version']=rdBase.rdkitVersion;rows=[];changed=0;canonical_ids=set();default_uncertainty=0
    lines=(RAW/ds/'database.txt').read_text(encoding='utf-8').splitlines()
    ordinal=0
    for lineno,line in enumerate(lines,1):
        if not line or line.startswith('#'):continue
        ordinal+=1;v=[x.strip() for x in line.split(';')];assert len(v)>=10
        molecule=Chem.MolFromSmiles(v[1]);assert molecule is not None,(lineno,v[1])
        canonical=Chem.MolToSmiles(molecule,isomericSmiles=True);assert canonical not in canonical_ids;canonical_ids.add(canonical)
        changed+=canonical!=v[1];scaffold=MurckoScaffold.MurckoScaffoldSmiles(mol=molecule,includeChirality=False)
        label=float(v[3]);error=float(v[4]);assert math.isfinite(label) and math.isfinite(error)
        isdefault='default' in v[9].lower();default_uncertainty+=isdefault
        flags=['experimental_label']
        if isdefault:flags.append('source_uncertainty_default')
        if not scaffold:flags.append('acyclic_scaffold_group')
        rows.append({'input':{'smiles':canonical},'label':label,'task_key':task,'target_name':target,'unit':unit,'target_type':'continuous',
            'group_key':'scaffold:'+scaffold,'entity_id':v[0],'split':'unassigned','quality_flags':flags,
            'source_refs':[{'file':'database.txt','row':ordinal,'physical_line':lineno,'compound_id':v[0],
                            'experimental_uncertainty_kcal_mol':error,'experimental_reference':v[7],
                            'uncertainty_kind':'source_default' if isdefault else 'source_reported'}]})
    assert len(rows)==642
    meta.update(raw_rows_selected=len(rows),canonical_smiles_changed=changed,source_default_uncertainties=default_uncertainty)
    meta['quality_findings']=['642 finite experimental labels; no molecular identity duplicates after RDKit canonicalization.',
        'Calculated free energy and all uncertainty/reference fields are excluded from input.',
        'Uncertainty values are preserved only as provenance; source defaults are explicitly flagged.',
        'Scaffold grouping is conservative: all acyclic compounds form one large group, and chirality is ignored for grouping.']
    write_candidates(ds,rows,meta)

def build_gb1():
    ds='gb1';task='relative_igg_fc_binding_fitness';target=task;unit='dimensionless'
    meta=base_meta(ds,'Wu 2016 GB1 four-site observed binding fitness','https://github.com/wchnicholas/ProteinGFourMutants',task,
        'Predict the relative IgG-Fc binding fitness in the Wu et al. GB1 four-site assay. The remaining GB1 background is fixed to the assay reference; the reference residues at positions 39, 40, 41, and 54 are V, D, G, and V. Fitness is normalized relative to this reference.',
        target,unit,{'residues_at_positions_39_40_41_54':'Four standard amino-acid one-letter codes in that position order.'})
    meta['license'].update(evidence='Original eLife article copyright and license; FLIP README Data licensing confirms original eLife raw data CC BY 4.0. Only original author Mutfit records, not FLIP derivative records, are used.',
        evidence_urls=['https://pmc.ncbi.nlm.nih.gov/articles/PMC4985287/','https://doi.org/10.7554/eLife.16965.024'])
    meta['source_citation']='Wu NC, Dai L, Olson CA, Lloyd-Smith JO, Sun R. Adaptation in protein fitness landscapes is facilitated by indirect paths. eLife 2016;5:e16965. https://doi.org/10.7554/eLife.16965'
    meta['target_origin']='experimental enrichment-derived relative fitness; single substitutions use author-calibrated prior experimental values'
    meta['grouping_rule']='Exact four-residue variant identity. All samples share one GB1 assay background; identity grouping does not make random splits a cross-protein evaluation.'
    meta['split_policy']='Unassigned. Recommended mutation-depth evaluation: train on Hamming distance <= k from VDGV and test > k (k=1,2,3), deriving depth from input only. These recipes are not official assigned FLIP folds.'
    meta['excluded_input_columns']=['HD','Input','IGG10','IGG20','IGG90','I10fit','I20fitRaw','I90fit','AOfit','I20fit']
    rows=[];reasons=collections.Counter();depths=collections.Counter();n=0;low=0;adjusted=0
    with (RAW/ds/'result/Mutfit').open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f,delimiter='\t')
        assert reader.fieldnames==['mut','HD','Input','IGG10','IGG20','IGG90','I10fit','I20fitRaw','I90fit','AOfit','I20fit']
        for i,r in enumerate(reader,1):
            n+=1;mut=r['mut']
            if len(mut)!=4 or any(c not in 'ACDEFGHIKLMNPQRSTVWY' for c in mut):reasons['nonstandard_four_residue_variant']+=1;continue
            try:label=float(r['I20fit'])
            except ValueError:reasons['missing_observed_I20fit']+=1;continue
            if not math.isfinite(label):reasons['nonfinite_observed_I20fit']+=1;continue
            assert int(r['Input'])>=10
            depth=sum(a!=b for a,b in zip(mut,'VDGV'));assert depth==int(r['HD']);depths[depth]+=1
            flags=['experimental_enrichment_derived_label','single_protein_background']
            if label==0:flags.append('zero_fitness_observed')
            if label<0.01:flags.append('low_fitness_detection_limit_sensitive');low+=1
            if depth==1:flags.append('author_calibrated_prior_experiment');adjusted+=1
            assert label>=0
            rows.append({'input':{'residues_at_positions_39_40_41_54':mut},'label':label,'task_key':task,'target_name':target,'unit':unit,'target_type':'continuous',
                'group_key':'variant:'+mut,'entity_id':mut,'source_refs':[{'file':'result/Mutfit','row':i,'variant':mut,'mutation_depth':depth}],
                'split':'unassigned','quality_flags':flags})
    assert len(rows)==149361 and n==191157
    meta.update(raw_rows_selected=n,excluded_source_rows=sum(reasons.values()),exclusion_reasons=dict(reasons),
                invalid_label_examples=reasons['missing_observed_I20fit']+reasons['nonfinite_observed_I20fit'],
                mutation_depth_counts=dict(depths),low_fitness_count=low,author_calibrated_single_mutants=adjusted,
                possible_standard_variants=160000,unobserved_standard_variants_not_imputed=160000-len(rows))
    meta['quality_findings']=['Exactly 149361 standard four-amino-acid variants have finite observed I20fit and at least 10 input reads.',
        'Missing standard variants are not fabricated or filled from result/regression_missing; that file was not downloaded.',
        'Observed zero fitness is retained. Values below 0.01 are flagged as detection-limit sensitive, without replacing or censoring their numeric labels.',
        'The source uses calibrated earlier experimental single-mutant fitness values; they are measured-derived, not modeled imputations.',
        'Raw counts, alternative fitness values and Hamming distance are excluded from input.']
    write_candidates(ds,rows,meta)

def build_jdft2d():
    ds='jdft2d';task='dft_exfoliation_energy';target=task;unit='meV/atom'
    meta=base_meta(ds,'JARVIS 2D / Matbench jdft2d','https://figshare.com/articles/dataset/jdft_2d-7-7-2018_json/6815705/1',task,
        'Predict the DFT-calculated exfoliation energy per atom for this periodic two-dimensional crystal structure.',target,unit,
        {'lattice_vectors_angstrom':'Three lattice vectors as a 3x3 row matrix in angstrom.',
         'sites':'Ordered atomic sites with element symbols and fractional coordinates relative to the lattice. Coordinates outside [0,1) are valid periodic representations.',
         'periodic':'Periodic boundary conditions along all three lattice directions; the slab cell includes vacuum.'})
    info=json.loads((RAW/ds/'figshare_v1.json').read_text(encoding='utf-8'))
    assert info['license']['name']=='CC BY 4.0'
    meta['license'].update(evidence='Original Figshare article 6815705 version 1 API license field.',evidence_url='https://api.figshare.com/v2/articles/6815705/versions/1')
    meta['source_citation']='Choudhary K et al. (2017), https://doi.org/10.1038/s41598-017-05402-0. JARVIS 2D snapshot jdft_2d-7-7-2018.json v1, https://doi.org/10.6084/m9.figshare.6815705.v1. Matbench structure/exfoliation_en packaging by the Matbench/matminer authors.'
    meta['target_origin']='DFT calculation (not experimental measurement)'
    meta['grouping_rule']='Reduced exact elemental composition, computed from full-occupancy sites. Equivalent crystals with alternative cells/site orders share composition group; this intentionally also groups distinct polymorphs.'
    meta['split_policy']='Unassigned. Use reduced-composition groups for family holdout. These are not official Matbench fivefold assignments and no official benchmark result is claimed.'
    meta['excluded_input_columns']=['exfoliation_en','fin_en','form_enp','all_other_energies','band_gaps','magnetic_and_dielectric_properties','material_ids','Cartesian_xyz','redundant_lattice_parameters','site_velocities']
    mat=json.load(gzip.open(RAW/ds/'matbench_jdft2d.json.gz','rt',encoding='utf-8'))
    orig=json.loads((RAW/ds/'jdft_2d-7-7-2018.json').read_text(encoding='utf-8'))
    assert mat['columns']==['structure','exfoliation_en'] and len(mat['data'])==len(orig)==636
    assert hashlib.md5((RAW/ds/'jdft_2d-7-7-2018.json').read_bytes()).hexdigest()==info['files'][0]['computed_md5']
    rows=[];outside=0;sitescounts=[]
    for i,((s,label),o) in enumerate(zip(mat['data'],orig),1):
        assert label==o['exfoliation_en'];assert s['lattice']['matrix']==o['final_str']['lattice']['matrix']
        assert [(v['abc'],v['species']) for v in s['sites']]==[(v['abc'],v['species']) for v in o['final_str']['sites']]
        assert len(s['lattice']['matrix'])==3 and all(len(v)==3 for v in s['lattice']['matrix'])
        sites=[];counts=collections.Counter();flags=['dft_calculated_label','relaxed_crystal_geometry']
        for site in s['sites']:
            assert len(site['species'])==1 and site['species'][0]['occu']==1
            element=site['species'][0]['element'];coords=site['abc'];assert len(coords)==3 and all(math.isfinite(x) for x in coords)
            sites.append({'element':element,'fractional_coordinates':coords});counts[element]+=1
        factor=reduce(math.gcd,counts.values());composition=';'.join(f'{e}:{n//factor}' for e,n in sorted(counts.items()))
        if any(c<0 or c>=1 for site in sites for c in site['fractional_coordinates']):flags.append('periodic_fractional_coordinates_outside_unit_cell');outside+=1
        sitescounts.append(len(sites))
        rows.append({'input':{'lattice_vectors_angstrom':s['lattice']['matrix'],'sites':sites,'periodic':[True,True,True]},
                     'label':label,'task_key':task,'target_name':target,'unit':unit,'target_type':'continuous',
                     'group_key':'reduced_composition:'+composition,'entity_id':o['jid'],'split':'unassigned','quality_flags':flags,
                     'source_refs':[{'file':'matbench_jdft2d.json.gz','row':i,'source_index':mat['index'][i-1]},
                                    {'file':'jdft_2d-7-7-2018.json','row':i,'jarvis_id':o['jid']} ]})
    meta.update(raw_rows_selected=len(rows),source_geometry_and_target_matches=636,periodic_coordinates_outside_unit_cell=outside,
                site_count_range=[min(sitescounts),max(sitescounts)])
    meta['quality_findings']=['All 636 labels, lattice matrices, species and fractional coordinates match the original licensed Figshare snapshot row by row.',
        'Only lattice, full-occupancy species, fractional coordinates and periodic boundary flags are input; DFT energies used to generate the target are excluded.',
        'Coordinates outside the unit interval are valid periodic representations and are retained; no artificial clipping/wrapping is applied.',
        'Composition groups conservatively prevent polymorph/alternative-cell separation; structure equivalence is not separately claimed.',
        'Labels are calculated DFT values and inputs are relaxed source geometries; this is not an experimental or raw pre-DFT-geometry benchmark.']
    write_candidates(ds,rows,meta)

def validate_source_rows():
    """Independent release-facing row audit; reads candidates back against raw files."""
    results={}
    fraw=[(i,line) for i,line in enumerate((RAW/'freesolv/database.txt').read_text(encoding='utf-8').splitlines(),1) if line and not line.startswith('#')]
    frows=[json.loads(line) for line in (OUT/'freesolv.jsonl').open(encoding='utf-8')]
    assert len(frows)==len(fraw)==642
    for ordinal,(row,(physical,line)) in enumerate(zip(frows,fraw),1):
        values=[x.strip() for x in line.split(';')]
        assert row['label']==float(values[3]) and row['entity_id']==values[0]
        assert set(row['input'])=={'smiles'}
        ref=row['source_refs'][0]
        assert ref['row']==ordinal and ref['physical_line']==physical and ref['experimental_uncertainty_kcal_mol']==float(values[4])
    results['freesolv']={'source_rows_checked':642,'status':'passed'}
    checked=0
    with (RAW/'gb1/result/Mutfit').open(encoding='utf-8',newline='') as raw, (OUT/'gb1.jsonl').open(encoding='utf-8') as candidates:
        for row_number,source in enumerate(csv.DictReader(raw,delimiter='\t'),1):
            if len(source['mut'])!=4 or not set(source['mut'])<=set('ACDEFGHIKLMNPQRSTVWY'):continue
            if source['I20fit']=='NA':continue
            label=float(source['I20fit'])
            if not math.isfinite(label):continue
            row=json.loads(next(candidates));checked+=1
            assert row['input']=={'residues_at_positions_39_40_41_54':source['mut']}
            assert row['label']==label and row['source_refs'][0]['row']==row_number
            assert row['entity_id']==source['mut'] and int(source['Input'])>=10
        assert not next(candidates,None) and checked==149361
    results['gb1']={'source_rows_checked':checked,'status':'passed'}
    originals=json.loads((RAW/'jdft2d/jdft_2d-7-7-2018.json').read_text(encoding='utf-8'))
    candidates=[json.loads(line) for line in (OUT/'jdft2d.jsonl').open(encoding='utf-8')]
    assert len(originals)==len(candidates)==636
    for i,(source,row) in enumerate(zip(originals,candidates),1):
        assert row['label']==source['exfoliation_en'] and row['entity_id']==source['jid']
        assert row['input']['lattice_vectors_angstrom']==source['final_str']['lattice']['matrix']
        assert row['input']['periodic']==[True,True,True]
        assert [(v['element'],v['fractional_coordinates']) for v in row['input']['sites']]==[(v['species'][0]['element'],v['abc']) for v in source['final_str']['sites']]
        assert all(ref['row']==i for ref in row['source_refs'])
        assert set(row['input'])=={'lattice_vectors_angstrom','sites','periodic'}
    results['jdft2d']={'source_rows_checked':636,'status':'passed'}
    for ds,result in results.items():
        p=OUT/f'{ds}.meta.json';meta=json.loads(p.read_text(encoding='utf-8'))
        meta['validation']['independent_readback_source_fidelity']=result;dump(p,meta)
    print('SOURCE_FIDELITY',json.dumps(results),flush=True)
    p=RAW/'jdft2d'/'source_manifest.json';m=json.loads(p.read_text(encoding='utf-8'))
    item=get('jdft2d','jdft_2d-7-7-2018.json','https://ndownloader.figshare.com/files/12394556')
    if not any(x['relativepath']==item['relativepath'] for x in m['files']):m['files'].append(item)
    dump(p,m)

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--download',action='store_true'); p.add_argument('--extra-sources',action='store_true'); p.add_argument('--build',action='store_true'); p.add_argument('--validate',action='store_true'); args=p.parse_args()
    if args.download: download()
    if args.extra_sources: extra_sources()
    if args.build:
        build_freesolv();build_gb1();build_jdft2d()
    if args.validate:validate_source_rows()
