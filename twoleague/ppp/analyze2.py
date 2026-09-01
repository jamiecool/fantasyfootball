import statistics as st
from collections import defaultdict
SEASONS=[2021,2022,2023,2024,2025]; TEAMS={2021:14,2022:12,2023:12,2024:12,2025:12}
WR={2021:2,2022:3,2023:3,2024:3,2025:3}
picks=[]
for y in SEASONS:
    for r in open(f'draft{y}.psv'):
        p=r.rstrip('\n').split('|')
        picks.append(dict(season=y,overall=int(p[0]),rd=int(p[1]),slot=int(p[2]),tm=int(p[3]),pid=p[4],
            name=p[6],pos=p[7],act=float(p[8]) if p[8] else None,proj=float(p[9]) if p[9] else None))
def sn(y,pos): 
    t=TEAMS[y]; return {'QB':2*t,'RB':2*t,'WR':WR[y]*t,'TE':t,'K':t,'DEF':t}[pos]
pr={}
for y in SEASONS:
    b=defaultdict(list)
    for p in picks:
        if p['season']==y and p['act'] is not None: b[p['pos']].append(p)
    for pos,l in b.items():
        l.sort(key=lambda x:-x['act'])
        for i,p in enumerate(l,1): pr[(y,p['pid'])]=i
for p in picks: p['prank']=pr.get((p['season'],p['pid']))

print("=== A. QB SUPPLY CURVE: cumulative QBs drafted by end of round (avg/season) ===")
print(f"{'Rd':>3} {'QBs cum':>8} {'teams':>6} {'QB/team':>8} {'meanQBpts this rd':>18}")
for rd in range(1,19):
    tot=0
    for y in SEASONS: tot+=sum(1 for p in picks if p['season']==y and p['rd']<=rd and p['pos']=='QB')
    cum=tot/5
    g=[p['act'] for p in picks if p['rd']==rd and p['pos']=='QB' and p['act'] is not None]
    m=f"{st.mean(g):.1f} (n={len(g)})" if g else "-"
    print(f"{rd:>3} {cum:>8.1f} {12.4:>6} {cum/12.4:>8.2f} {m:>18}")

print("\n=== B. VALUE OVER REPLACEMENT by position (replacement = last startable rank) ===")
for pos in ['QB','RB','WR','TE','K','DEF']:
    vals=[]
    for y in SEASONS:
        l=sorted([p for p in picks if p['season']==y and p['pos']==pos and p['act'] is not None],key=lambda x:-x['act'])
        n=sn(y,pos)
        if len(l)>n: 
            repl=l[n-1]['act']
            vals.append((y,repl,l[0]['act'],l[min(5,len(l))-1]['act']))
    if vals:
        print(f"  {pos:>3}: replacement pts {st.mean(v[1] for v in vals):6.1f} | top1 {st.mean(v[2] for v in vals):6.1f} | top5 {st.mean(v[3] for v in vals):6.1f} | VOR@top1 {st.mean(v[2]-v[1] for v in vals):+6.1f}")

print("\n=== C. COST OF DRAFTING K / DEF EARLY (before round 13) ===")
early=[p for p in picks if p['pos'] in ('K','DEF') and p['rd']<13 and p['act'] is not None]
late=[p for p in picks if p['pos'] in ('K','DEF') and p['rd']>=13 and p['act'] is not None]
print(f"  K/DEF taken rd<13: n={len(early)} mean {st.mean(p['act'] for p in early):.1f} pts, mean posrank {st.mean(p['prank'] for p in early):.1f}")
print(f"  K/DEF taken rd>=13: n={len(late)} mean {st.mean(p['act'] for p in late):.1f} pts, mean posrank {st.mean(p['prank'] for p in late):.1f}")
skill=[p['act'] for p in picks if p['pos'] not in ('K','DEF') and 7<=p['rd']<=12 and p['act'] is not None]
print(f"  Skill players available rds 7-12 mean {st.mean(skill):.1f} pts -> opportunity cost of an early K/DEF ~{st.mean(skill)-st.mean(p['act'] for p in early):+.1f}")

print("\n=== D. TE: elite vs streamed ===")
for lo,hi in [(1,3),(4,6),(7,9),(10,18)]:
    g=[p for p in picks if p['pos']=='TE' and lo<=p['rd']<=hi and p['act'] is not None]
    if g: print(f"  TE rd {lo}-{hi}: n={len(g):3} mean {st.mean(p['act'] for p in g):6.1f} top-12 rate {sum(1 for p in g if p['prank'] and p['prank']<=12)/len(g)*100:4.0f}%")

print("\n=== E. BIGGEST HITS AND MISSES (actual vs round expectation) ===")
rdmean={}
for rd in range(1,19):
    g=[p['act'] for p in picks if p['rd']==rd and p['act'] is not None]
    rdmean[rd]=st.mean(g)
for p in picks:
    p['vor']=p['act']-rdmean[p['rd']] if p['act'] is not None else None
hits=sorted([p for p in picks if p['vor'] is not None],key=lambda x:-x['vor'])[:10]
miss=sorted([p for p in picks if p['vor'] is not None and p['rd']<=4],key=lambda x:x['vor'])[:8]
print("  Top 10 value picks vs their round:")
for p in hits: print(f"    {p['season']} rd{p['rd']:>2} {p['name']:<24} {p['pos']:>3} {p['act']:>6.1f} ({p['vor']:+.0f} vs rd avg)")
print("  Worst early picks (rds 1-4):")
for p in miss: print(f"    {p['season']} rd{p['rd']:>2} {p['name']:<24} {p['pos']:>3} {p['act']:>6.1f} ({p['vor']:+.0f})")

print("\n=== F. ROUND-BAND SHARE OF TOTAL DRAFTED POINTS (where seasons are won) ===")
tot=sum(p['act'] for p in picks if p['act'] is not None)
for lo,hi in [(1,3),(4,6),(7,9),(10,12),(13,15),(16,18)]:
    s=sum(p['act'] for p in picks if lo<=p['rd']<=hi and p['act'] is not None)
    print(f"  Rd {lo}-{hi}: {s/tot*100:5.1f}% of all drafted points")
