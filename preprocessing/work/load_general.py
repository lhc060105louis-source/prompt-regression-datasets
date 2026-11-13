import pathlib, sys, zipfile
HERE=pathlib.Path(__file__).resolve()
ROOT=HERE.parents[2] if HERE.parent.name=='scripts' else HERE.parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'))
import pandas as pd

DEST=ROOT/'构造general数据集'
def base(i): return DEST/'raw'/f'uci_{i}'/'extracted'
def located(i,name): return next(base(i).rglob(name))

def frame(i):
    if i==165:
        d=pd.read_excel(located(i,'Concrete_Data.xls'));d.columns=['cement','blast_furnace_slag','fly_ash','water','superplasticizer','coarse_aggregate','fine_aggregate','age_days','strength_mpa']
    elif i==242:
        d=pd.read_excel(located(i,'ENB2012_data.xlsx')).dropna(how='all');d=d.dropna(axis=1,how='all')
        d.columns=['relative_compactness','surface_area','wall_area','roof_area','overall_height','orientation','glazing_area','glazing_distribution','heating_load','cooling_load']
    elif i==294:
        d=pd.read_excel(located(i,'Folds5x2_pp.xlsx'),sheet_name=0)
    elif i==291:
        d=pd.read_csv(located(i,'airfoil_self_noise.dat'),sep=r'\s+',header=None,names=['frequency_hz','attack_angle_deg','chord_length_m','free_stream_velocity_m_s','displacement_thickness_m','sound_pressure_db'])
    elif i==243:
        d=pd.read_csv(located(i,'yacht_hydrodynamics.data'),sep=r'\s+',header=None,names=['buoyancy_position','prismatic_coefficient','length_displacement_ratio','beam_draught_ratio','length_beam_ratio','froude_number','residuary_resistance'])
    elif i==1:
        d=pd.read_csv(located(i,'abalone.data'),header=None,names=['sex','length_scaled','diameter_scaled','height_scaled','whole_weight_scaled','shucked_weight_scaled','viscera_weight_scaled','shell_weight_scaled','rings'])
    elif i==9:
        d=pd.read_csv(located(i,'auto-mpg.data'),sep=r'\s+',header=None,names=['mpg','cylinders','displacement','horsepower','weight','acceleration','model_year','origin','car_name'],na_values=['?'])
    elif i==477:
        d=pd.read_excel(located(i,'Real estate valuation data set.xlsx'));d.columns=['id','transaction_date','house_age_years','mrt_distance_m','convenience_stores','latitude','longitude','price_per_area']
    elif i==29:
        d=pd.read_csv(located(i,'machine.data'),header=None,names=['vendor','model','cycle_time_ns','memory_min_kb','memory_max_kb','cache_kb','channels_min','channels_max','PRP','ERP'])
    elif i==87:
        d=pd.read_csv(located(i,'servo.data'),header=None,names=['motor','screw','pgain','vgain','response'])
    elif i==464:
        d=pd.read_csv(located(i,'train.csv'))
    elif i==504:
        d=pd.read_csv(located(i,'qsar_fish_toxicity.csv'),sep=';',header=None,names=['CIC0','SM1_Dz_Z','GATS1i','NdsCH','NdssC','MLOGP','LC50'])
    elif i==186:
        parts=[]
        for wine in ['red','white']:
            p=pd.read_csv(located(i,f'winequality-{wine}.csv'),sep=';');p['wine_type']=wine;p['_file']=f'winequality-{wine}.csv';p['_source_row']=range(1,len(p)+1);parts.append(p)
        d=pd.concat(parts,ignore_index=True)
    elif i==320:
        folder=base(i)/'student'
        folder.mkdir(exist_ok=True)
        with zipfile.ZipFile(located(i,'student.zip')) as z:
            for name in z.namelist():
                if not (folder/name).resolve().is_relative_to(folder.resolve()): raise ValueError('Unsafe nested archive')
            z.extractall(folder)
        parts=[]
        for subject in ['mat','por']:
            p=pd.read_csv(folder/f'student-{subject}.csv',sep=';');p['subject']=subject;p['_file']=f'student-{subject}.csv';p['_source_row']=range(1,len(p)+1);parts.append(p)
        d=pd.concat(parts,ignore_index=True)
    elif i==189:
        d=pd.read_csv(located(i,'parkinsons_updrs.data'))
    elif i==597:
        d=pd.read_csv(located(i,'garments_worker_productivity.csv'))
    elif i==275:
        d=pd.read_csv(located(i,'hour.csv'))
    elif i==492:
        d=pd.read_csv(located(i,'Metro_Interstate_Traffic_Volume.csv.gz'),keep_default_na=False)
    else: raise KeyError(i)
    if '_source_row' not in d: d['_source_row']=range(1,len(d)+1)
    return d

if __name__=='__main__':
    import json
    ids=[165,242,294,291,243,1,9,477,29,87,464,504,186,320,189,597,275,492]
    for i in ids:
        d=frame(i);plain=d.drop(columns=[c for c in d if c.startswith('_')])
        info={'id':i,'rows':len(d),'columns':list(plain),'nulls':{k:int(v) for k,v in plain.isna().sum().items() if v},'exact_duplicate_rows':int(plain.duplicated().sum()),'numeric_ranges':{c:[float(plain[c].min()),float(plain[c].max())] for c in plain.select_dtypes('number')},'sample':plain.head(1).to_dict('records')}
        print(json.dumps(info,ensure_ascii=False),flush=True)
