from __future__ import annotations

import argparse, csv, json, os
from dataclasses import asdict
from pathlib import Path

from rashomon_tableau.benchmark import build_controlled_cases, load_annotated_cases
from rashomon_tableau.conan_loader import iter_perspectives, load_all_gold, relation_inventory
from rashomon_tableau.evaluation import classify_case, classification_metrics, relation_extraction_metrics
from rashomon_tableau.llm_extractor import OpenAIPropositionExtractor
from rashomon_tableau.ontology import Ontology
from rashomon_tableau.tableau import RelationalTableau


def write_predictions(preds, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "predictions.json").write_text(json.dumps([asdict(p) for p in preds], ensure_ascii=False, indent=2), encoding="utf-8")
    with (out_dir / "predictions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["case_id","gold","predicted","subtype","story","perspective_a","perspective_b","satisfiable_a","satisfiable_b","satisfiable_union","explanation_count"]
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for p in preds:
            d=asdict(p); w.writerow({k:d[k] for k in fields})


def run_llm(args, out_dir: Path):
    extractor = OpenAIPropositionExtractor(args.llm_model, args.llm_max_chars)
    gold_sets=[]; pred_sets=[]; detail=[]
    for item in iter_perspectives(args.conan_root, args.language, args.max_stories):
        if not item.text: continue
        allowed={x.predicate for x in item.propositions}
        pred=extractor.extract(item.text, allowed, item.story, item.perspective)
        gold={(x.subject,x.predicate,x.object) for x in item.propositions}; got={(x.subject,x.predicate,x.object) for x in pred}
        gold_sets.append(gold); pred_sets.append(got)
        detail.append({"story":item.story,"perspective":item.perspective,"gold":sorted(gold),"pred":sorted(got)})
    metrics=relation_extraction_metrics(gold_sets,pred_sets)
    (out_dir/"rq1_llm_extraction.json").write_text(json.dumps({"metrics":metrics,"details":detail},ensure_ascii=False,indent=2),encoding="utf-8")
    return metrics


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--conan-root",default="data/conan"); p.add_argument("--language",default="english")
    p.add_argument("--ontology",default="config/ontology_rules.yaml"); p.add_argument("--benchmark",choices=["controlled","annotated"],default="controlled")
    p.add_argument("--annotation-file",default="data/annotations/contradiction_labels.csv"); p.add_argument("--max-stories",type=int,default=3)
    p.add_argument("--max-cases-per-story",type=int,default=80); p.add_argument("--seed",type=int,default=42); p.add_argument("--out",default="results")
    p.add_argument("--mode",choices=["gold","llm"],default="gold"); p.add_argument("--llm-model",default=os.getenv("OPENAI_MODEL","gpt-5-mini")); p.add_argument("--llm-max-chars",type=int,default=30000)
    args=p.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    ontology=Ontology.from_yaml(args.ontology); reasoner=RelationalTableau(ontology)
    inv=relation_inventory(args.conan_root,args.language,args.max_stories)
    (out/"relation_inventory.json").write_text(json.dumps(inv,ensure_ascii=False,indent=2),encoding="utf-8")
    if args.mode=="llm":
        print("RQ1 relation extraction:",json.dumps(run_llm(args,out),indent=2))
    if args.benchmark=="controlled":
        stories=load_all_gold(args.conan_root,args.language,args.max_stories); cases=build_controlled_cases(stories,ontology,args.seed,args.max_cases_per_story)
        note="CONTROLLED labels are programmatically derived from Conan gold propositions; use annotated mode for natural contradiction claims."
    else:
        cases=load_annotated_cases(args.annotation_file); note="Human annotated contradiction benchmark."
    preds=[classify_case(c,reasoner) for c in cases]; metrics=classification_metrics(preds); metrics["note"]=note
    write_predictions(preds,out); (out/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(metrics,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
