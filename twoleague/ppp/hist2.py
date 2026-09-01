import statistics as st
from collections import defaultdict
exec(open('hist.py').read().split('def corr')[0])
def corr(a,b):
    ma,mb=st.mean(a),st.mean(b)
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    den=(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**.5
    return num/den if den else float('nan')
rdmean={}
for rd in range(1,19):
    g=[p['act'] for p in picks if p['rd']==rd and p['act'] is not None]
    rdmean[rd]=st.mean(g)
for p in picks: p['vor']=p['act']-rdmean[p['rd']] if p['act'] is not None else None

TS={}
for (y,tid),v in T.items():
    ps=[p for p in picks if p['s']==y and p['tm']==tid]
    if not ps: continue
    sc=[p for p in ps if p['act'] is not None]
    TS[(y,tid)]=dict(**v,y=y,tid=tid,
        vor=sum(p['vor'] for p in sc), haul=sum(p['act'] for p in sc),
        early=sum(p['act'] for p in sc if p['rd']<=6))
rows=list(TS.values())

print("=== 8. DRAFT SKILL vs IN-SEASON SKILL, per manager ===")
print("  'draft rank' = rank of draft value within that season (1 = best drafter that year)")
byo=defaultdict(list)
for y in SEASONS:
    yr=sorted([r for r in rows if r['y']==y], key=lambda r:-r['vor'])
    for i,r in enumerate(yr,1): r['drank']=i
    yr2=sorted([r for r in rows if r['y']==y], key=lambda r:-r['pf'])
    for i,r in enumerate(yr2,1): r['pfrank']=i
for r in rows: byo[r['own']].append(r)
print(f"{'manager':<20}{'yrs':>4}{'draft rank':>12}{'PF rank':>9}{'finish':>8}{'draft->finish':>15}")
for o,v in sorted(byo.items(), key=lambda kv:st.mean(x['fin'] for x in kv[1])):
    if len(v)<3: continue
    d=st.mean(x['drank'] for x in v); f=st.mean(x['fin'] for x in v)
    print(f"{o:<20}{len(v):>4}{d:>12.1f}{st.mean(x['pfrank'] for x in v):>9.1f}{f:>8.1f}{d-f:>+15.1f}")
print("  last column: positive = finishes better than he drafts (gains after the draft)")

print("\n=== 9. HOW MUCH OF FINISH IS SET BY THE DRAFT? ===")
print(f"  draft value -> points for   r = {corr([r['vor'] for r in rows],[r['pf'] for r in rows]):+.2f}")
print(f"  draft value -> wins         r = {corr([r['vor'] for r in rows],[r['w'] for r in rows]):+.2f}")
print(f"  draft value -> finish       r = {corr([r['vor'] for r in rows],[-r['fin'] for r in rows]):+.2f}")
print(f"  points for  -> wins         r = {corr([r['pf'] for r in rows],[r['w'] for r in rows]):+.2f}")

print("\n=== 10. THE LATE-ROUND ILLUSION ===")
for lo,hi in [(1,3),(4,6),(7,9),(10,12),(13,18)]:
    band=[]
    for r in rows:
        ps=[p for p in picks if p['s']==r['y'] and p['tm']==r['tid'] and lo<=p['rd']<=hi and p['act'] is not None]
        band.append(sum(p['act'] for p in ps))
    sd=st.pstdev(band)
    print(f"  rounds {lo}-{hi}: mean {st.mean(band):>6.0f} pts, spread between teams {sd:>5.0f}, "
          f"r with wins {corr(band,[r['w'] for r in rows]):+.2f}")
print("  -> late rounds deliver volume but almost no separation between teams")

print("\n=== 11. POSITION MIX IN THE FIRST SIX ROUNDS vs OUTCOME ===")
buck=defaultdict(list)
for r in rows:
    ps=[p for p in picks if p['s']==r['y'] and p['tm']==r['tid'] and p['rd']<=6]
    rb=sum(1 for p in ps if p['pos']=='RB')
    buck[min(rb,3)].append(r)
print(f"{'RBs in rd1-6':>13}{'n':>5}{'mean wins':>11}{'mean PF':>10}{'mean finish':>13}{'titles':>8}")
for k in sorted(buck):
    v=buck[k]
    print(f"{k if k<3 else '3+':>13}{len(v):>5}{st.mean(x['w'] for x in v):>11.2f}{st.mean(x['pf'] for x in v):>10.0f}"
          f"{st.mean(x['fin'] for x in v):>13.2f}{sum(1 for x in v if x['fin']==1):>8}")

print("\n=== 12. BIGGEST DRAFT-DAY WINS AND LOSSES (team-season draft value) ===")
best=sorted(rows,key=lambda r:-r['vor'])[:6]; worst=sorted(rows,key=lambda r:r['vor'])[:6]
for lab,g in [('best drafts',best),('worst drafts',worst)]:
    print(f"  {lab}:")
    for r in g:
        print(f"    {r['y']} {r['own']:<20}{r['vor']:>+8.0f} pts vs round expectation -> {r['w']}-{r['l']}, finished {r['fin']}")

print("\n=== 13. REPEAT CONTENDERS ===")
for o,v in sorted(byo.items(), key=lambda kv:st.mean(x['fin'] for x in kv[1])):
    if len(v)<3: continue
    fins=sorted(x['fin'] for x in v)
    print(f"  {o:<20} finishes {', '.join(str(x['fin']) for x in sorted(v,key=lambda z:z['y']))}  (best {fins[0]}, worst {fins[-1]})")

print("\n=== 14. WHO TAKES QBs EARLY, AND DOES IT HELP THEM ===")
print(f"{'manager':<20}{'yrs':>4}{'QB rd1-3/yr':>13}{'QB total/yr':>13}{'avg finish':>12}")
for o,v in sorted(byo.items(), key=lambda kv:-st.mean(sum(1 for p in picks if p['s']==x['y'] and p['tm']==x['tid'] and p['pos']=='QB' and p['rd']<=3) for x in kv[1])):
    if len(v)<3: continue
    q3=st.mean(sum(1 for p in picks if p['s']==x['y'] and p['tm']==x['tid'] and p['pos']=='QB' and p['rd']<=3) for x in v)
    qt=st.mean(sum(1 for p in picks if p['s']==x['y'] and p['tm']==x['tid'] and p['pos']=='QB') for x in v)
    print(f"{o:<20}{len(v):>4}{q3:>13.1f}{qt:>13.1f}{st.mean(x['fin'] for x in v):>12.1f}")
