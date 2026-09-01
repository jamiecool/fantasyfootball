import json, statistics as st
from collections import defaultdict

SEASONS=[2021,2022,2023,2024,2025]; TEAMS={2021:14,2022:12,2023:12,2024:12,2025:12}
# Starters per team. Superflex is filled by a QB in this league (33 QBs drafted
# for 12 teams in 2025), so QB carries two starting slots, and the single FLEX is
# split across RB/WR/TE by how it has actually been used.
NEED={'QB':2.0,'RB':2.5,'WR':3.3,'TE':1.0,'K':1.0,'DEF':1.0}

picks=[]
for y in SEASONS:
    for r in open(f'draft{y}.psv'):
        p=r.rstrip('\n').split('|')
        picks.append(dict(s=y,o=int(p[0]),rd=int(p[1]),sl=int(p[2]),tm=int(p[3]),pid=p[4],
            n=p[6],pos=p[7],act=float(p[8]) if p[8] else None,prj=float(p[9]) if p[9] else None))

def need(y,pos): return int(round(NEED[pos]*TEAMS[y]))

# positional finish rank among players actually drafted that season
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
    p['fin']=f"{p['pos']}{p['pr']}" if p['pr'] else ''

# ---- realized replacement level, and how far projections overshoot, by position ----
REPL_ACT={}; RATIO={}
for pos in NEED:
    vals=[]
    for y in SEASONS:
        l=sorted([p['act'] for p in picks if p['s']==y and p['pos']==pos and p['act'] is not None],reverse=True)
        i=need(y,pos)-1
        if len(l)>i: vals.append(l[i])
    REPL_ACT[pos]=round(st.mean(vals),1)
    g=[p for p in picks if p['pos']==pos and p['prj'] and p['prj']>5 and p['act'] is not None]
    RATIO[pos]=round(st.mean(p['act'] for p in g)/st.mean(p['prj'] for p in g),3)

# ---- per-round aggregates ----
rdstat=[]
for rd in range(1,19):
    g=[p for p in picks if p['rd']==rd and p['act'] is not None]
    rdstat.append(dict(rd=rd,n=len(g),mean=round(st.mean(p['act'] for p in g),1),
        med=round(st.median(p['act'] for p in g),1),
        st=round(sum(p['st'] for p in g)/len(g)*100)))
rdmean={r['rd']:r['mean'] for r in rdstat}
for p in picks: p['vor']=round(p['act']-rdmean[p['rd']],1) if p['act'] is not None else None

BANDS=[(1,3),(4,6),(7,9),(10,12),(13,15),(16,18)]
posband=[]
for pos in ['QB','RB','WR','TE','K','DEF']:
    row=dict(pos=pos,cells=[])
    for lo,hi in BANDS:
        g=[p for p in picks if lo<=p['rd']<=hi and p['pos']==pos and p['act'] is not None]
        row['cells'].append(dict(band=f'{lo}-{hi}',n=len(g),
            st=round(sum(x['st'] for x in g)/len(g)*100) if g else None,
            mean=round(st.mean(x['act'] for x in g),1) if g else None))
    posband.append(row)

qbedge=[]
for lo,hi in BANDS:
    q=[p['act'] for p in picks if lo<=p['rd']<=hi and p['pos']=='QB' and p['act'] is not None]
    f=[p['act'] for p in picks if lo<=p['rd']<=hi and p['pos'] in ('RB','WR','TE') and p['act'] is not None]
    qbedge.append(dict(band=f'{lo}-{hi}',qb=round(st.mean(q),1),qbn=len(q),
        flex=round(st.mean(f),1),flexn=len(f),edge=round(st.mean(q)-st.mean(f),1)))

poscount=[dict(rd=rd,**{x:sum(1 for p in picks if p['rd']==rd and p['pos']==x)
    for x in ['QB','RB','WR','TE','K','DEF']}) for rd in range(1,19)]
qbcum=[]
tot=0
for rd in range(1,19):
    tot+=sum(1 for p in picks if p['rd']==rd and p['pos']=='QB')
    qbcum.append(round(tot/len(SEASONS),1))

# ---- 2026 board ----
board=[]
for r in open('board2026.psv'):
    f=r.rstrip('\n').split('|')
    board.append(dict(pid=f[0],n=f[1],pos=f[2],tm=f[3],espn=int(f[4]),
        adp=float(f[5]) if f[5] else None,own=float(f[6]) if f[6] else None,
        prj=float(f[7]) if f[7] else 0.0))
byp=defaultdict(list)
for p in board: byp[p['pos']].append(p)
for pos,l in byp.items():
    l.sort(key=lambda x:-x['prj'])
    for i,p in enumerate(l,1): p['prank']=i
# Deflate each projection onto the scale this league's outcomes actually land on,
# then measure against the replacement level those outcomes actually produced.
for p in board:
    p['exp']=round(p['prj']*RATIO.get(p['pos'],0.86),1)
SKILL={'QB','RB','WR','TE'}
skill=[p for p in board if p['pos'] in SKILL]
stream=[p for p in board if p['pos'] not in SKILL]
for p in skill: p['vor']=round(p['exp']-REPL_ACT[p['pos']],1)
for p in stream: p['vor']=None
skill.sort(key=lambda x:-x['vor'])
stream.sort(key=lambda x:(x['pos'],-x['prj']))
espn_order=sorted(skill,key=lambda x:x['espn'])
for i,p in enumerate(espn_order,1): p['espnRank']=i
for i,p in enumerate(skill,1):
    p['rank']=i; p['gap']=p['espnRank']-i
    p['rd']=(i-1)//12+1; p['pk']=(i-1)%12+1
for p in stream:
    p['rank']=None; p['gap']=None; p['rd']=None; p['pk']=None; p['espnRank']=None
board=skill+stream

teams={}
for r in open('teams.psv'):
    f=r.rstrip('\n').split('|')
    if f[0]=='season': continue
    teams.setdefault(f[0],[]).append(dict(id=int(f[1]),name=f[2],ab=f[3],own=f[4],
        w=int(f[5]),l=int(f[6]),pf=float(f[7]),seed=int(f[8]),fin=int(f[9])))
for y in SEASONS:
    haul=defaultdict(float); starters=defaultdict(int)
    for p in picks:
        if p['s']==y and p['act']: haul[p['tm']]+=p['act']; starters[p['tm']]+=p['st']
    for t in teams[str(y)]:
        t['haul']=round(haul[t['id']],1); t['startables']=starters[t['id']]

qb1_3=len([p for p in skill if p['pos']=='QB' and p['rank']<=36])
D2=dict(league=json.load(open('league.json')), seasons=SEASONS, rounds=18,
  replacement=REPL_ACT, ratio=RATIO, need=NEED, qbTop3=qb1_3, qbcum=qbcum,
  board=board, rdstat=rdstat, posband=posband, qbedge=qbedge, poscount=poscount,
  bands=[f'{a}-{b}' for a,b in BANDS],
  draft={str(y):[dict(o=p['o'],rd=p['rd'],pk=p['sl'],tm=p['tm'],n=p['n'],pos=p['pos'],
      act=p['act'],prj=p['prj'],fin=p['fin'],st=p['st'],vor=p['vor'])
      for p in picks if p['s']==y] for y in SEASONS},
  teams=teams)

rb=next(c for c in posband if c['pos']=='RB')['cells']
D2['rules']=[
 dict(id='1',conf='high',area='Superflex',
  rule='The second quarterback is the best value on the board, and this room still underpays for it.',
  why=f"QBs taken in rounds 7-9 returned {qbedge[2]['qb']} points against {qbedge[2]['flex']} for the RB/WR/TE taken alongside them ({qbedge[2]['edge']:+}); in rounds 10-12 the gap is {qbedge[3]['edge']:+}. Six of the ten biggest value picks in five seasons were QBs taken in rounds 6-12 - Mayfield rd 9 (365.8), Stafford rd 6 (350.4), Lawrence rd 8 (338.2), Nix rd 10 (317.2), Love rd 10 (319.1), Goff rd 12 (284.3).",
  n=f"{sum(c['n'] for c in next(x for x in posband if x['pos']=='QB')['cells'])} QB picks vs 587 RB/WR/TE picks, 5 seasons"),
 dict(id='2',conf='high',area='Superflex',
  rule='A quarterback who misses time is replaced by nothing. That is what makes them scarce here.',
  why=f"ESPN projects every starting quarterback to play a full season, so its 24th-best QB for 2026 projects 239.1 points. Across five actual seasons the 24th-best QB scored {REPL_ACT['QB']}. Twenty-four QBs start every week in a superflex league and there is no 25th worth having, so the real floor is {REPL_ACT['QB']} - and measuring against the projected floor instead quietly erases about {round(239.1-REPL_ACT['QB'])} points of value from every quarterback.",
  n='5 seasons of realized outcomes vs ESPN preseason projections'),
 dict(id='3',conf='high',area='Superflex',
  rule="ESPN's own board is built for a one-QB league. Do not draft from it here.",
  why=f"Ranked inside the same {len(skill)}-player pool, quarterbacks sit far later on ESPN than value over replacement says they belong. This board puts {qb1_3} quarterbacks inside the first three rounds; across five seasons the room itself has taken {qbcum[2]} by that point, so the market already knows. ESPN does not.",
  n=f'{len(skill)} skill players, ESPN PPR order vs superflex VOR, same pool'),
 dict(id='4',conf='high',area='Roster shape',
  rule='Never spend a pick on a kicker or defense before round 13.',
  why='K and D/ST were startable 85-100% of the time in every round band from 10 on. The 15 taken before round 13 averaged 133.1 points at position rank 6.6; the 125 taken from round 13 on averaged 118.5 at rank 7.7. One position rank of quality costs a skill player worth roughly 149 points.',
  n='140 K/DEF picks, 5 seasons'),
 dict(id='5',conf='high',area='Running back',
  rule='Running back falls off a cliff after round 9. Take the backs you want before it.',
  why=f"RB startable rate runs {rb[0]['st']}% in rounds 1-3 and {rb[2]['st']}% in 7-9, then collapses to {rb[3]['st']}% in 10-12 and {rb[4]['st']}% in 13-15. Wide receiver follows the same curve one band later. Tight end holds up best late.",
  n=f"{sum(c['n'] for c in rb)} RB picks, 5 seasons"),
 dict(id='6',conf='high',area='Mindset',
  rule='Treat every projection as roughly 15% too high, and rank on the gaps rather than the totals.',
  why=f"Across 933 picks with usable ESPN preseason projections, actual points came in at 0.82-0.90 of projection in every round band through 15. By position the ratio is {RATIO['QB']} for QBs, {RATIO['RB']} for RBs, {RATIO['WR']} for WRs and {RATIO['TE']} for TEs - this board deflates every projection by its own position's factor before ranking.",
  n='933 picks with projections, 4 seasons'),
 dict(id='7',conf='medium',area='Draft slot',
  rule='Your draft slot is not worth worrying about.',
  why='Teams picking 1-4 averaged 6.75 wins and a 7.5 finish; slots 5-8 averaged 7.55 wins and 5.7; slots 9-14 averaged 6.73 wins and 6.9. The spread is inside the noise for 62 team-seasons.',
  n='62 team-seasons, 5 seasons'),
 dict(id='8',conf='high',area='Mindset',
  rule='The draft matters here. It is not all waivers.',
  why='Total points from a team’s drafted players correlate +0.50 with wins and +0.64 with points scored. Rounds 1-3 supply only 26.3% of all drafted points, though - rounds 10-18 supply 36.6%. The draft is won in the middle and late rounds.',
  n='62 team-seasons, 1,116 picks'),
]
json.dump(D2,open('ppp_data.json','w'),separators=(',',':'))
import os
print('bytes',os.path.getsize('ppp_data.json'))
print('\nrealized replacement:',REPL_ACT)
print('proj deflator by pos :',RATIO)
print(f'\nQBs inside rounds 1-3 on the new board: {qb1_3}   (room historically takes {qbcum[2]} by then)')
print('\nNEW ROUND 1:')
for p in skill[:12]: print(f"  {p['rank']:>2}. {p['n']:<24}{p['pos']:>3}  proj {p['prj']:>6.1f} -> exp {p['exp']:>6.1f}  VOR {p['vor']:>+6.1f}")
print('NEW ROUND 2:')
for p in skill[12:24]: print(f"  {p['rank']:>2}. {p['n']:<24}{p['pos']:>3}  proj {p['prj']:>6.1f} -> exp {p['exp']:>6.1f}  VOR {p['vor']:>+6.1f}")
print('NEW ROUND 3:')
for p in skill[24:36]: print(f"  {p['rank']:>2}. {p['n']:<24}{p['pos']:>3}  proj {p['prj']:>6.1f} -> exp {p['exp']:>6.1f}  VOR {p['vor']:>+6.1f}")
