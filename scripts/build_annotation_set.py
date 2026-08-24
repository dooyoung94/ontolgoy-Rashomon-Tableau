from __future__ import annotations
import argparse,csv,random
from pathlib import Path
from rashomon_tableau.conan_loader import load_all_gold

def main():
    p=argparse.ArgumentParser(); p.add_argument('--conan-root',default='data/conan'); p.add_argument('--language',default='english'); p.add_argument('--out',default='data/annotations/contradiction_candidates.csv'); p.add_argument('--max-stories',type=int,default=None); p.add_argument('--max-pairs-per-story',type=int,default=100); p.add_argument('--seed',type=int,default=42); a=p.parse_args()
    stories=load_all_gold(a.conan_root,a.language,a.max_stories); rng=random.Random(a.seed); rows=[]
    for story,perspectives in stories.items():
        names=sorted(perspectives); candidates=[]
        for i,pa in enumerate(names):
            for pb in names[i+1:]:
                for fa in perspectives[pa]:
                    for fb in perspectives[pb]:
                        priority=int((fa.subject,fa.object)==(fb.subject,fb.object)); candidates.append((priority,pa,pb,fa,fb))
        rng.shuffle(candidates); candidates.sort(key=lambda x:-x[0])
        for idx,(_,pa,pb,fa,fb) in enumerate(candidates[:a.max_pairs_per_story]):
            rows.append({'case_id':f'{story}::human::{idx}','story':story,'perspective_a':pa,'perspective_b':pb,'label':'','subtype':'','predicate_a':fa.predicate,'subject_a':fa.subject,'object_a':fa.object,'negated_a':0,'predicate_b':fb.predicate,'subject_b':fb.subject,'object_b':fb.object,'negated_b':0,'annotation_note':'label one of: consistent / divergence / contradiction'})
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    if not rows: print('[warn] no rows'); return
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f'[ok] exported {len(rows)} annotation candidates -> {out}')

if __name__=='__main__': main()
