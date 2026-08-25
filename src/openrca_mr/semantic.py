from __future__ import annotations

from dataclasses import dataclass

from .models import Evidence, Hypothesis, RcaCase


@dataclass(frozen=True)
class SemanticScore:
    support: float
    contradiction: float
    neutral: float


class DebertaEvidenceScorer:
    """NLI scorer for a causal hypothesis against its observed telemetry.

    Gold root-cause/path annotations are never used. The premise is built only
    from evidence attached to the candidate's endpoints and the candidate
    explanation is used as the hypothesis sentence.
    """

    DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str | None = None):
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
        premise = self._premise(case, hypothesis)
        encoded = self.tokenizer(
            premise,
            hypothesis.explanation,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}
        with self.torch.no_grad():
            probs = self.torch.softmax(self.model(**encoded).logits, dim=-1)[0].detach().cpu().tolist()
        return SemanticScore(
            support=float(probs[self.entail]),
            contradiction=float(probs[self.contra]),
            neutral=float(probs[self.neutral]),
        )

    @staticmethod
    def _premise(case: RcaCase, hypothesis: Hypothesis) -> str:
        wanted = set(hypothesis.evidence_ids)
        selected = [e for e in case.evidence if e.evidence_id in wanted]
        return " ".join(_evidence_text(e) for e in selected)


class DeterministicEvidenceScorer:
    """Dependency-free scorer used only for unit tests and smoke tests."""

    def score(self, case: RcaCase, hypothesis: Hypothesis) -> SemanticScore:
        support = max(0.0, min(1.0, hypothesis.abductive_score))
        return SemanticScore(support=support, contradiction=1.0 - support, neutral=0.0)


def apply_semantic_scores(case: RcaCase, hypotheses: list[Hypothesis], scorer) -> list[Hypothesis]:
    for hypothesis in hypotheses:
        score = scorer.score(case, hypothesis)
        hypothesis.semantic_support = score.support
        hypothesis.semantic_contradiction = score.contradiction
    return hypotheses


def _evidence_text(e: Evidence) -> str:
    if e.text:
        return e.text
    state = "abnormal" if e.is_anomalous else "normal"
    ts = f" at {e.timestamp}" if e.timestamp is not None else ""
    return f"{e.node} has {state} {e.kind} signal {e.signal}{ts}; abnormality={e.abnormality:.3f}."
