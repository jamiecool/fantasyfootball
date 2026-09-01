import csv, statistics as st
from collections import defaultdict

SEASONS=[2021,2022,2023,2024,2025]
TEAMS={2021:14,2022:12,2023:12,2024:12,2025:12}
WRSLOT={2021:2,2022:3,2023:3,2024:3,2025:3}

picks=[]
for y in SEASONS:
    for r in open(f'draft{y}.psv'):
        p=r.rstrip('\n').split('|')
        if p[0]=='overall': continue
        picks.append(dict(season=y,overall=int(p[0]),rd=int(p[1]),slot=int(p[2]),tm=int(p[3]),
            pid=p[4],keeper=p[5],name=p[6],pos=p[7],
            act=float(p[8]) if p[8] else None, proj=float(p[9]) if p[9] else None,
            gp=int(p[10]) if len(p)>10 and p[10] else None))

# starter slots per team by position (superflex counted into QB)
def startable_n(season,pos):
    t=TEAMS[season]
    return {'QB':2*t,'RB':2*t,'WR':WRSLOT[season]*t,'TE':1*t,'K':1*t,'DEF':1*t}[pos]

# positional rank among ALL drafted players that season
posrank={}
for y in SEASONS:
    byp=defaultdict(list)
    for p in picks:
        if p['season']==y and p['act'] is not None: byp[p['pos']].append(p)
    for pos,lst in byp.items():
        lst.sort(key=lambda x:-x['act'])
        for i,p in enumerate(lst,1): posrank[(y,p['pid'])]=i
for p in picks:
    p['prank']=posrank.get((p['season'],p['pid']))
    p['startable']= (p['prank'] is not None and p['prank']<=startable_n(p['season'],p['pos']))

print("=== 1. VALUE BY ROUND (all positions, actual points) ===")
print(f"{'Rd':>3} {'n':>4} {'meanPts':>8} {'median':>7} {'startable%':>10} {'bust<50%med':>12}")
allmed=st.median([p['act'] for p in picks if p['act'] is not None])
for rd in range(1,19):
    g=[p for p in picks if p['rd']==rd and p['act'] is not None]
    if not g: continue
    s=sum(p['startable'] for p in g)/len(g)*100
    print(f"{rd:>3} {len(g):>4} {st.mean(p['act'] for p in g):>8.1f} {st.median(p['act'] for p in g):>7.1f} {s:>9.0f}% {sum(1 for p in g if p['act']<allmed*0.5)/len(g)*100:>11.0f}%")

print("\n=== 2. POSITION TAKEN BY ROUND (counts) ===")
POSL=['QB','RB','WR','TE','K','DEF']
print('Rd  '+' '.join(f'{p:>5}' for p in POSL))
for rd in range(1,19):
    g=[p for p in picks if p['rd']==rd]
    if not g: continue
    c={x:sum(1 for p in g if p['pos']==x) for x in POSL}
    print(f'{rd:>2}  '+' '.join(f'{c[x]:>5}' for x in POSL))

print("\n=== 3. STARTABLE RATE BY POSITION x ROUND BAND ===")
bands=[(1,3),(4,6),(7,9),(10,12),(13,15),(16,18)]
print(f"{'band':>7} "+' '.join(f'{p:>12}' for p in POSL))
for lo,hi in bands:
    row=[]
    for pos in POSL:
        g=[p for p in picks if lo<=p['rd']<=hi and p['pos']==pos and p['act'] is not None]
        row.append(f"{sum(p['startable'] for p in g)/len(g)*100:>4.0f}% (n={len(g):>3})" if g else "     -      ")
    print(f"{lo}-{hi:>2}   "+' '.join(row))

print("\n=== 4. SUPERFLEX: QB vs FLEX-ELIGIBLE value by round band ===")
for lo,hi in bands:
    q=[p['act'] for p in picks if lo<=p['rd']<=hi and p['pos']=='QB' and p['act'] is not None]
    f=[p['act'] for p in picks if lo<=p['rd']<=hi and p['pos'] in ('RB','WR','TE') and p['act'] is not None]
    if q and f:
        print(f"  Rd {lo}-{hi}: QB mean {st.mean(q):6.1f} (n={len(q):3})   RB/WR/TE mean {st.mean(f):6.1f} (n={len(f):3})   QB edge {st.mean(q)-st.mean(f):+6.1f}")

print("\n=== 5. PROJECTION ACCURACY: actual vs ESPN preseason proj (seasons with proj) ===")
pp=[p for p in picks if p['proj'] and p['proj']>5 and p['act'] is not None]
print(f"  n={len(pp)} picks with usable projections")
for lo,hi in bands:
    g=[p for p in pp if lo<=p['rd']<=hi]
    if g:
        ratio=[p['act']/p['proj'] for p in g]
        beat=sum(1 for r in ratio if r>=1)/len(g)*100
        print(f"  Rd {lo}-{hi}: actual/proj mean {st.mean(ratio):.2f}  median {st.median(ratio):.2f}  beat proj {beat:.0f}%  (n={len(g)})")

print("\n=== 6. DRAFT SLOT EFFECT (team's round-1 pick position vs season finish) ===")
tm_slot={}
for p in picks:
    if p['rd']==1: tm_slot[(p['season'],p['tm'])]=p['slot']
teams={}
for r in open('teams.psv'):
    f=r.rstrip('\n').split('|')
    if f[0]=='season' or f[0]=='2026': continue
    teams[(int(f[0]),int(f[1]))]=dict(owner=f[4],w=int(f[5]),pf=float(f[7]),fin=int(f[9]))
rows=[(tm_slot[k],v['w'],v['pf'],v['fin']) for k,v in teams.items() if k in tm_slot]
for band in [(1,4),(5,8),(9,14)]:
    g=[r for r in rows if band[0]<=r[0]<=band[1]]
    if g: print(f"  Slot {band[0]}-{band[1]}: n={len(g):3}  mean wins {st.mean(r[1] for r in g):.2f}  mean PF {st.mean(r[2] for r in g):.0f}  mean finish {st.mean(r[3] for r in g):.1f}")

print("\n=== 7. DRAFT HAUL vs WINS (sum of drafted players' actual pts) ===")
haul=defaultdict(float)
for p in picks:
    if p['act']: haul[(p['season'],p['tm'])]+=p['act']
xs=[];ys=[];zs=[]
for k,v in teams.items():
    if k in haul: xs.append(haul[k]); ys.append(v['w']); zs.append(v['pf'])
def corr(a,b):
    ma,mb=st.mean(a),st.mean(b)
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    den=(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**.5
    return num/den
print(f"  n={len(xs)} team-seasons")
print(f"  corr(draft haul, wins)      = {corr(xs,ys):+.3f}")
print(f"  corr(draft haul, points for)= {corr(xs,zs):+.3f}")
