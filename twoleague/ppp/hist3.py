import statistics as st
from collections import defaultdict
exec(open('hist.py').read().split('def corr')[0])
def corr(a,b):
    ma,mb=st.mean(a),st.mean(b)
    n=sum((x-ma)*(y-mb) for x,y in zip(a,b)); d=(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**.5
    return n/d if d else float('nan')
rows=[]
for (y,tid),v in T.items():
    ps=[p for p in picks if p['s']==y and p['tm']==tid]
    if not ps: continue
    rows.append(dict(**v,y=y,tid=tid,ps=ps))

print("=== 15. THE FIVE TEAMS THAT TOOK NO RB IN ROUNDS 1-6 ===")
for r in rows:
    rb=sum(1 for p in r['ps'] if p['pos']=='RB' and p['rd']<=6)
    if rb==0:
        first6=[f"{p['pos']}" for p in sorted(r['ps'],key=lambda x:x['o'])[:6]]
        print(f"  {r['y']} {r['own']:<18} {r['w']}-{r['l']}, finished {r['fin']:>2}   first six picks: {' '.join(first6)}")

print("\n=== 16. FIRST-SIX-ROUND POSITION SHAPE, ranked by mean finish (n>=4) ===")
shape=defaultdict(list)
for r in rows:
    c=defaultdict(int)
    for p in r['ps']:
        if p['rd']<=6: c[p['pos']]+=1
    shape[(c['QB'],c['RB'],c['WR'])].append(r)
out=[]
for k,v in shape.items():
    if len(v)>=4: out.append((st.mean(x['fin'] for x in v),k,v))
for fin,(q,rb,wr),v in sorted(out):
    print(f"  {q}QB {rb}RB {wr}WR  n={len(v):>2}  mean finish {fin:>5.2f}  mean wins {st.mean(x['w'] for x in v):>4.2f}  "
          f"PF {st.mean(x['pf'] for x in v):>5.0f}  titles {sum(1 for x in v if x['fin']==1)}")

print("\n=== 17. DOES A ROUND-1 QUARTERBACK HELP? ===")
g=defaultdict(list)
for r in rows: g[sum(1 for p in r['ps'] if p['pos']=='QB' and p['rd']==1)].append(r)
for k in sorted(g):
    v=g[k]
    print(f"  {k} QB in round 1: n={len(v):>2}  mean wins {st.mean(x['w'] for x in v):.2f}  "
          f"mean finish {st.mean(x['fin'] for x in v):.2f}  PF {st.mean(x['pf'] for x in v):.0f}  titles {sum(1 for x in v if x['fin']==1)}")

print("\n=== 18. WR-HEAVY vs RB-HEAVY STARTS (rounds 1-6) ===")
for lab,test in [('more WR than RB',lambda c:c['WR']>c['RB']),
                 ('equal',lambda c:c['WR']==c['RB']),
                 ('more RB than WR',lambda c:c['RB']>c['WR'])]:
    v=[]
    for r in rows:
        c=defaultdict(int)
        for p in r['ps']:
            if p['rd']<=6: c[p['pos']]+=1
        if test(c): v.append(r)
    print(f"  {lab:<18} n={len(v):>2}  mean wins {st.mean(x['w'] for x in v):.2f}  "
          f"mean finish {st.mean(x['fin'] for x in v):.2f}  PF {st.mean(x['pf'] for x in v):.0f}  titles {sum(1 for x in v if x['fin']==1)}")

print("\n=== 19. HOW OFTEN DOES THE BEST REGULAR-SEASON TEAM WIN IT? ===")
for y in SEASONS:
    yr=[r for r in rows if r['y']==y]
    topseed=min(yr,key=lambda r:r['seed']); champ=min(yr,key=lambda r:r['fin'])
    mostpf=max(yr,key=lambda r:r['pf'])
    print(f"  {y}: 1-seed {topseed['own']:<18} champ {champ['own']:<18} most points {mostpf['own']:<18}"
          f"{'  (1-seed won)' if topseed is champ else ''}{'  (most-points won)' if mostpf is champ else ''}")
seedwin=sum(1 for y in SEASONS if min([r for r in rows if r['y']==y],key=lambda r:r['seed']) is min([r for r in rows if r['y']==y],key=lambda r:r['fin']))
pfwin=sum(1 for y in SEASONS if max([r for r in rows if r['y']==y],key=lambda r:r['pf']) is min([r for r in rows if r['y']==y],key=lambda r:r['fin']))
print(f"  -> 1-seed won {seedwin}/5; most-points team won {pfwin}/5")

print("\n=== 20. CHAMPIONS' DRAFTS IN DETAIL ===")
for r in sorted([x for x in rows if x['fin']==1],key=lambda x:x['y']):
    ps=sorted(r['ps'],key=lambda x:x['o'])[:6]
    print(f"  {r['y']} {r['own']:<18} {r['w']}-{r['l']}  PF {r['pf']:.0f}")
    print(f"       first six: " + ', '.join(f"{p['pos']} {p['n']}" for p in ps))
