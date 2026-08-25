from __future__ import annotations

from dataclasses import dataclass

from .models import Evidence, Hypothesis, RcaCase


@dataclass(frozen=True)
class SemanticScore:
    support: float
    contradiction: float
    neutral: float


class DebertaEvidenceScorer:
    """NLI-based semantic support scorer over model-visible telemetry only."""

    DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str | None = None, batch_size: int = 16):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install the NLI extra: pip install -e '.[nli]'") from exc

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()
        self.batch_size = batch_size

        labels = {int(k): str(v).lower() for k, v in self.model.config.id2label.items()}
        self.entail = self._label(labels, "entail")
        self.contra = self._label(labels, "contrad")
        self.neutral = self._label(labels, "neutral")

    @staticmethod
    def _label(labels: dict[int, str], needle: str) -> int:
        for idx, label in labels.items():
            if needle in label:
                return idx
        raise RuntimeError(f"Unable to resolve {needle} label from {labels}")

    def score(self, case: RcaCase, hypothesis: Hypothesis) -> SemanticScore:
        return self.score_many(case, [hypothesis])[0]

    def score_many(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[SemanticScore]:
        if not hypotheses:
            return []
        results: list[SemanticScore] = []
        for start in range(0, len(hypotheses), self.batch_size):
            batch = hypotheses[start : start + self.batch_size]
            premises = [self._premise(case, h) for h in batch]
            claims = [self._claim(h) for h in batch]
            encoded = self.tokenizer(
                premises,
                claims,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with self.torch.no_grad():
                probs = self.torch.softmax(self.model(**encoded).logits, dim=-1).detach().cpu().tolist()
            for row in probs:
                results.append(
                    SemanticScore(
                        support=float(row[self.entail]),
                        contradiction=float(row[self.contra]),
                        neutral=float(row[self.neutral]),
                    )
                )
        return results

    @staticmethod
    def _claim(hypothesis: Hypothesis) -> str:
        return (
            f"The abnormal behavior at {hypothesis.edge.source} causally contributed "
            f"to the later abnormal behavior at {hypothesis.edge.target}."
        )

    @staticmethod
    def _premise(case: RcaCase, hypothesis: Hypothesis) -> str:
        wanted = set(hypothesis.evidence_ids)
        selected = [e for e in case.evidence if e.evidence_id in wanted]
        evidence = " ".join(_evidence_text(e) for e in selected)
        return (
            f"Telemetry evidence for a candidate path from {hypothesis.edge.source} "
            f"to {hypothesis.edge.target}: {evidence}"
        )


class DeterministicEvidenceScorer:
    """Dependency-free scorer used only for unit tests and smoke tests."""

    def score(self, case: RcaCase, hypothesis: Hypothesis) -> SemanticScore:
        support = max(0.0, min(1.0, hypothesis.abductive_score))
        return SemanticScore(support=support, contradiction=1.0 - support, neutral=0.0)

    def score_many(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[SemanticScore]:
        return [self.score(case, h) for h in hypotheses]


def apply_semantic_scores(case: RcaCase, hypotheses: list[Hypothesis], scorer) -> list[Hypothesis]:
    if hasattr(scorer, "score_many"):
        scores = scorer.score_many(case, hypotheses)
    else:
        scores = [scorer.score(case, h) for h in hypotheses]
    for hypothesis, score in zip(hypotheses, scores):
        hypothesis.semantic_support = score.support
        hypothesis.semantic_contradiction = score.contradiction
    return hypotheses


def _evidence_text(e: Evidence) -> str:
    state = "abnormal" if e.is_anomalous else "normal"
    ts = f" at time {e.timestamp:.3f}" if e.timestamp is not None else ""
    detail = e.text.strip() if e.text else f"{e.kind} signal {e.signal}"
    return f"[{e.node}] {detail}; state={state}; abnormality={e.abnormality:.3f}{ts}."
