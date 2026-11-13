"""Read the selected official files without dropping or imputing labels."""
import zipfile, pathlib
from load_general import ROOT,DEST,base,located,pd
IDS=[10,265,560,374,501,551,440,332,555,162,925]
AUTO_COLUMNS=['symboling','normalized_losses','make','fuel_type','aspiration','num_doors','body_style','drive_wheels','engine_location','wheel_base','length','width','height','curb_weight','engine_type','num_cylinders','engine_size','fuel_system','bore','stroke','compression_ratio','horsepower','peak_rpm','city_mpg','highway_mpg','price']
RUNS=[f'Run{k} (ms)' for k in range(1,5)]
THERMAL=['T_offset1','Max1R13_1','Max1L13_1','aveAllR13_1','aveAllL13_1','T_RC1','T_RC_Dry1','T_RC_Wet1','T_RC_Max1','T_LC1','T_LC_Dry1','T_LC_Wet1','T_LC_Max1','RCC1','LCC1','canthiMax1','canthi4Max1','T_FHCC1','T_FHRC1','T_FHLC1','T_FHBC1','T_FHTC1','T_FH_Max1','T_FHC_Max1','T_Max1','T_OR1','T_OR_Max1']

def read_file(i,name,**kw):
    d=pd.read_csv(located(i,name),**kw);d['_file']=name;d['_source_row']=range(1,len(d)+1);return d
def raw_frame(i):
    if i==10:d=read_file(i,'imports-85.data',header=None,names=AUTO_COLUMNS,na_values=['?'])
    elif i==265:d=read_file(i,'CASP.csv')
    elif i==560:
        d=read_file(i,'SeoulBikeData.csv',encoding='cp1252')
        d.columns=['date','rented_bike_count','hour','temperature_c','humidity_percent','wind_speed_m_s','visibility_10m','dewpoint_c','solar_radiation_mj_m2','rainfall_mm','snowfall_cm','season','holiday','functioning_day','_file','_source_row']
    elif i==374:d=read_file(i,'energydata_complete.csv')
    elif i==501:
        if not list(base(i).rglob('PRSA_Data_*.csv')):
            with zipfile.ZipFile(located(i,'PRSA2017_Data_20130301-20170228.zip')) as z:
                dest=base(i)/'PRSA2017_Data_20130301-20170228'
                for n in z.namelist():assert (dest/n).resolve().is_relative_to(dest.resolve())
                z.extractall(dest)
        files=sorted(base(i).rglob('PRSA_Data_*.csv'));assert len(files)==12
        d=pd.concat([read_file(i,p.name) for p in files],ignore_index=True)
    elif i==551:d=pd.concat([read_file(i,f'gt_{year}.csv').assign(_year=year) for year in range(2011,2016)],ignore_index=True)
    elif i==440:d=read_file(i,'sgemm_product.csv')
    elif i==332:
        d=read_file(i,'OnlineNewsPopularity.csv',skipinitialspace=True);d.columns=d.columns.str.strip()
    elif i==555:
        if not list(base(i).rglob('apartments_for_rent_classified_100K.csv')):
            import py7zr
            with py7zr.SevenZipFile(located(i,'apartments_for_rent_classified_100K.7z')) as z:
                dest=base(i)/'apartments_for_rent_classified_100K'
                for n in z.getnames():assert (dest/n).resolve().is_relative_to(dest.resolve())
                z.extractall(dest)
        d=read_file(i,'apartments_for_rent_classified_100K.csv',sep=';',encoding='cp1252',na_values=['null'],low_memory=False)
    elif i==162:d=read_file(i,'forestfires.csv')
    elif i==925:
        d=pd.concat([read_file(i,f'{device}_groups1and2.csv',header=2,encoding='utf-8-sig').assign(device=device) for device in ['FLIR','ICI']],ignore_index=True)
        d=d.drop(columns=[c for c in d if c.startswith('Unnamed:')])
    else:raise KeyError(i)
    return d.reset_index(drop=True)

if __name__=='__main__':
    import json
    for i in IDS:
        d=raw_frame(i)
        print(json.dumps({'id':i,'shape':d.shape,'columns':list(d),'missing':{k:int(v) for k,v in d.isna().sum().items() if v},'duplicates':int(d.drop(columns=[c for c in d if c.startswith('_')]).duplicated().sum()),'ranges':{c:[float(d[c].min()),float(d[c].max())] for c in d.select_dtypes('number') if c not in ['_source_row'] and (i not in [925,332] or c in ['aveOralM','aveOralF','shares','n_unique_tokens','n_non_stop_words','n_non_stop_unique_tokens'])}},ensure_ascii=True),flush=True)
