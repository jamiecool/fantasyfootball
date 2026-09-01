import statistics as st
from collections import defaultdict
SEASONS=[2021,2022,2023,2024,2025]; TEAMS={2021:14,2022:12,2023:12,2024:12,2025:12}
WRS={2021:2,2022:3,2023:3,2024:3,2025:3}
picks=[]
for y in SEASONS:
    for r in open(f'draft{y}.psv'):
        p=r.rstrip('\n').split('|')
        picks.append(dict(s=y,rd=int(p[1]),pos=p[7],n=p[6],
            act=float(p[8]) if p[8] else None, prj=float(p[9]) if p[9] else None))

print("=== A. Realized replacement level by position (points), by season ===")
# starter counts scaled to team count: QB 2/tm (superflex), RB 2.5/tm, WR 3.3/tm, TE 1/tm
NEED={'QB':2.0,'RB':2.5,'WR':3.3,'TE':1.0}
repl=defaultdict(list); top1=defaultdict(list)
for y in SEASONS:
    for pos,per in NEED.items():
        l=sorted([p['act'] for p in picks if p['s']==y and p['pos']==pos and p['act'] is not None],reverse=True)
        idx=int(round(per*TEAMS[y]))-1
        if len(l)>idx:
            repl[pos].append(l[idx]); top1[pos].append(l[0])
print(f"{'pos':>4} {'realized repl':>14} {'realized top1':>14} {'VOR at top':>11} {'n seasons':>10}")
for pos in ['QB','RB','WR','TE']:
    print(f"{pos:>4} {st.mean(repl[pos]):>14.1f} {st.mean(top1[pos]):>14.1f} {st.mean(top1[pos])-st.mean(repl[pos]):>+11.1f} {len(repl[pos]):>10}")

print("\n=== B. How well ESPN projections track reality, BY POSITION ===")
print(f"{'pos':>4} {'n':>5} {'mean proj':>10} {'mean actual':>12} {'actual/proj':>12}")
for pos in ['QB','RB','WR','TE','K','DEF']:
    g=[p for p in picks if p['pos']==pos and p['prj'] and p['prj']>5 and p['act'] is not None]
    if g:
        mp=st.mean(p['prj'] for p in g); ma=st.mean(p['act'] for p in g)
        print(f"{pos:>4} {len(g):>5} {mp:>10.1f} {ma:>12.1f} {ma/mp:>12.3f}")

print("\n=== C. THE BUG: projection-based replacement vs realized replacement ===")
import json
d=json.load(open('ppp_data.json'))
print("  board used (from 2026 ESPN projections):", d['replacement'])
print("  five seasons of actual outcomes say:   ", {p:round(st.mean(repl[p]),1) for p in ['QB','RB','WR','TE']})
print("""
  ESPN projects every starting QB to play a full season, so its QB24 lands at
  239.1. In reality QBs get hurt and benched: the 24th-best QB actually scored
  %.1f. Using the projected floor instead of the real one strips roughly %.0f
  points of value off every quarterback on the board.""" % (
    st.mean(repl['QB']), 239.1-st.mean(repl['QB'])))

print("\n=== D. What the room actually does (QBs drafted, cumulative by round) ===")
for rd in [1,2,3,4,5]:
    tot=sum(1 for p in picks if p['rd']<=rd and p['pos']=='QB')/5
    print(f"  by end of round {rd}: {tot:.1f} QBs off the board ({tot/12.4:.2f} per team)")
