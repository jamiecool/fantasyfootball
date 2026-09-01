import statistics as st
from collections import defaultdict
SEASONS=[2021,2022,2023,2024,2025]; TEAMS={2021:14,2022:12,2023:12,2024:12,2025:12}
NEED={'QB':2.0,'RB':2.5,'WR':3.3,'TE':1.0,'K':1.0,'DEF':1.0}
picks=[]
for y in SEASONS:
    for r in open(f'draft{y}.psv'):
        p=r.rstrip('\n').split('|')
        picks.append(dict(s=y,o=int(p[0]),rd=int(p[1]),pk=int(p[2]),tm=int(p[3]),
            n=p[6],pos=p[7],act=float(p[8]) if p[8] else None,prj=float(p[9]) if p[9] else None))
T={}
for r in open('teams.psv'):
    f=r.rstrip('\n').split('|')
    if f[0]=='season' or f[0]=='2026': continue
    T[(int(f[0]),int(f[1]))]=dict(name=f[2],own=f[4],w=int(f[5]),l=int(f[6]),
        pf=float(f[7]),seed=int(f[8]),fin=int(f[9]))
def need(y,pos): return int(round(NEED[pos]*TEAMS[y]))
for y in SEASONS:
    b=defaultdict(list)
    for p in picks:
        if p['s']==y and p['act'] is not None: b[p['pos']].append(p)
    for pos,l in b.items():
        l.sort(key=lambda x:-x['act'])
        for i,p in enumerate(l,1): p['pr']=i
for p in picks:
    p.setdefault('pr',None)
    p['st']=1 if (p['pr'] and p['pr']<=need(p['s'],p['pos'])) else 0

def corr(a,b):
    if len(a)<3: return float('nan')
    ma,mb=st.mean(a),st.mean(b)
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    den=(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**.5
    return num/den if den else float('nan')

# team-season features
TS={}
for (y,tid),v in T.items():
    ps=[p for p in picks if p['s']==y and p['tm']==tid]
    if not ps: continue
    scored=[p for p in ps if p['act'] is not None]
    f=dict(**v, y=y, tid=tid,
      haul=sum(p['act'] for p in scored),
      hits=sum(p['st'] for p in scored),
      qb3=sum(1 for p in ps if p['pos']=='QB' and p['rd']<=3),
      qb6=sum(1 for p in ps if p['pos']=='QB' and p['rd']<=6),
      qbT=sum(1 for p in ps if p['pos']=='QB'),
      rb6=sum(1 for p in ps if p['pos']=='RB' and p['rd']<=6),
      wr6=sum(1 for p in ps if p['pos']=='WR' and p['rd']<=6),
      te6=sum(1 for p in ps if p['pos']=='TE' and p['rd']<=6),
      kd12=sum(1 for p in ps if p['pos'] in ('K','DEF') and p['rd']<=12),
      early=sum(p['act'] for p in scored if p['rd']<=6),
      late=sum(p['act'] for p in scored if p['rd']>=10),
      top3=sum(sorted([p['act'] for p in scored],reverse=True)[:3]))
    TS[(y,tid)]=f
rows=list(TS.values())
print(f"n = {len(rows)} team-seasons, {len(picks)} picks\n")

print("=== 1. WHAT CORRELATES WITH WINNING ===")
print(f"{'feature':<34}{'vs wins':>9}{'vs points for':>15}{'vs finish':>11}")
for lab,key in [('total points drafted','haul'),('startable picks drafted','hits'),
                ('points from rounds 1-6','early'),('points from rounds 10-18','late'),
                ('top-3 players combined','top3'),
                ('QBs taken in rounds 1-3','qb3'),('QBs taken in rounds 1-6','qb6'),
                ('QBs taken overall','qbT'),
                ('RBs in rounds 1-6','rb6'),('WRs in rounds 1-6','wr6'),('TEs in rounds 1-6','te6'),
                ('K/DEF before round 13','kd12')]:
    v=[r[key] for r in rows]
    print(f"  {lab:<32}{corr(v,[r['w'] for r in rows]):>+9.2f}{corr(v,[r['pf'] for r in rows]):>+15.2f}{corr(v,[-r['fin'] for r in rows]):>+11.2f}")
print("  (finish is sign-flipped so + always means better)")

print("\n=== 2. LUCK vs SKILL ===")
print(f"  points for -> wins            r = {corr([r['pf'] for r in rows],[r['w'] for r in rows]):+.2f}")
print(f"  points for -> final standing  r = {corr([r['pf'] for r in rows],[-r['fin'] for r in rows]):+.2f}")
print(f"  wins       -> final standing  r = {corr([r['w'] for r in rows],[-r['fin'] for r in rows]):+.2f}")
print(f"  draft haul -> points for      r = {corr([r['haul'] for r in rows],[r['pf'] for r in rows]):+.2f}")

print("\n=== 3. QB STRATEGY: how many QBs in the first 3 rounds? ===")
print(f"{'QBs rd1-3':>10}{'n':>5}{'mean wins':>11}{'mean PF':>10}{'mean finish':>13}{'titles':>8}")
g=defaultdict(list)
for r in rows: g[min(r['qb3'],3)].append(r)
for k in sorted(g):
    v=g[k]
    print(f"{k:>10}{len(v):>5}{st.mean(x['w'] for x in v):>11.2f}{st.mean(x['pf'] for x in v):>10.0f}{st.mean(x['fin'] for x in v):>13.2f}{sum(1 for x in v if x['fin']==1):>8}")

print("\n=== 4. WHERE CHAMPIONS DIFFER FROM EVERYONE ELSE ===")
champs=[r for r in rows if r['fin']==1]; podium=[r for r in rows if r['fin']<=3]
rest=[r for r in rows if r['fin']>3]
print(f"{'':<30}{'champions':>11}{'top 3':>9}{'rest':>9}")
for lab,key in [('QBs rounds 1-3','qb3'),('QBs total','qbT'),('RBs rounds 1-6','rb6'),
                ('WRs rounds 1-6','wr6'),('startable picks','hits'),
                ('points drafted','haul'),('points rounds 10-18','late'),
                ('K/DEF before rd 13','kd12')]:
    print(f"  {lab:<28}{st.mean(x[key] for x in champs):>11.1f}{st.mean(x[key] for x in podium):>9.1f}{st.mean(x[key] for x in rest):>9.1f}")
print(f"  {'n':<28}{len(champs):>11}{len(podium):>9}{len(rest):>9}")

print("\n=== 5. MANAGER RECORDS (3+ seasons) ===")
byo=defaultdict(list)
for r in rows: byo[r['own']].append(r)
print(f"{'manager':<22}{'yrs':>4}{'W-L':>9}{'win%':>7}{'PF/yr':>8}{'avg fin':>9}{'titles':>7}{'hits/yr':>9}{'QBrd1-3':>9}")
for o,v in sorted(byo.items(), key=lambda kv:(-len(kv[1]), st.mean(x['fin'] for x in kv[1]))):
    if len(v)<3: continue
    w=sum(x['w'] for x in v); l=sum(x['l'] for x in v)
    print(f"{o:<22}{len(v):>4}{str(w)+'-'+str(l):>9}{w/(w+l)*100:>6.0f}%{st.mean(x['pf'] for x in v):>8.0f}"
          f"{st.mean(x['fin'] for x in v):>9.1f}{sum(1 for x in v if x['fin']==1):>7}{st.mean(x['hits'] for x in v):>9.1f}{st.mean(x['qb3'] for x in v):>9.1f}")

print("\n=== 6. IS DRAFTING SKILL PERSISTENT? (year N vs year N+1, same manager) ===")
pairs=[]
for o,v in byo.items():
    d={x['y']:x for x in v}
    for y in SEASONS[:-1]:
        if y in d and y+1 in d: pairs.append((d[y],d[y+1]))
print(f"  {len(pairs)} manager year-pairs")
for lab,key in [('startable picks','hits'),('points drafted','haul'),('wins','w'),('finish','fin')]:
    print(f"    {lab:<20} year-over-year r = {corr([a[key] for a,b in pairs],[b[key] for a,b in pairs]):+.2f}")

print("\n=== 7. LEAGUE TENDENCIES OVER TIME ===")
print(f"{'season':>7}{'QB rd1-3':>10}{'RB rd1-6':>10}{'WR rd1-6':>10}{'TE rd1-6':>10}{'K/DEF <13':>11}")
for y in SEASONS:
    ps=[p for p in picks if p['s']==y]
    print(f"{y:>7}{sum(1 for p in ps if p['pos']=='QB' and p['rd']<=3):>10}"
          f"{sum(1 for p in ps if p['pos']=='RB' and p['rd']<=6):>10}"
          f"{sum(1 for p in ps if p['pos']=='WR' and p['rd']<=6):>10}"
          f"{sum(1 for p in ps if p['pos']=='TE' and p['rd']<=6):>10}"
          f"{sum(1 for p in ps if p['pos'] in ('K','DEF') and p['rd']<13):>11}")
