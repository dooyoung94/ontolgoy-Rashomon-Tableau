from __future__ import annotations
from .models import BenchmarkCase

def proposition_to_sentence(predicate,subject,obj,negated=False):
    relation=predicate.replace('_',' '); neg='not ' if negated else ''
    return f'{subject} is {neg}{relation} {obj}.'

class NLIBaseline:
    def __init__(self,model_name='MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli'):
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError('Install optional NLI dependencies: pip install -r requirements-nli.txt') from exc
        self.pipe=pipeline('text-classification',model=model_name,tokenizer=model_name,top_k=None)
    def predict(self,case:BenchmarkCase)->str:
        a,b=case.facts_a[0],case.facts_b[0]
        outputs=self.pipe({'text':proposition_to_sentence(a.predicate,a.subject,a.object,a.negated),'text_pair':proposition_to_sentence(b.predicate,b.subject,b.object,b.negated)})
        if outputs and isinstance(outputs[0],list): outputs=outputs[0]
        scores={str(x['label']).lower():float(x['score']) for x in outputs}; label=max(scores,key=scores.get)
        if 'contrad' in label:return 'contradiction'
        if 'entail' in label:return 'consistent'
        return 'divergence'
