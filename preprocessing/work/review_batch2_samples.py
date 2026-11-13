import json,random
from load_general import DEST
from build_general import save
folder=next((DEST/'datasets').glob('uci_555_*'))
rng=random.Random(42);sample=[]
for n,line in enumerate((folder/'data.jsonl').open(encoding='utf-8')):
    r=json.loads(line)
    if len(sample)<8:sample.append(r)
    else:
        j=rng.randrange(n+1)
        if j<8:sample[j]=r
save(DEST/'reports/apartment_text_review.json',{'method':'8-record reservoir sample, random.Random(42), manual inspection of prepared text','scope':'Illustrative inspection only, not an estimated error rate','findings':['No visible numeric rent remained in the eight inspected prepared texts; full numeric/money-token scan is in batch2_validation.','One sampled title mentions Morrisville while structured cityname is Manson; raw source retained without speculative geographic corrections.','Source apartment category can include room/shared rental wording; no verified whole-unit rental guarantee.'],'samples':sample})
