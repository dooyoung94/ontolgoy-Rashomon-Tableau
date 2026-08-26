from __future__ import annotations

from dataclasses import dataclass

from .models import (
    Evidence,
    Hypothesis,
    RcaCase,
    RelationObservation,
    StructuralHypothesis,
)


@dataclass(frozen=True)
class SemanticScore:
    support: float
    contradiction: float
    neutral: float


class DebertaEvidenceScorer:
    """Contrastive NLI scorer for Stage-2 causal vs non-causal semantics."""

    DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        batch_size: int = 16,
    ):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install the NLI extra: pip install -e '.[nli]'") from exc

        self.torch = torch
        self.model_name = model_name
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

    def _contrastive_scores(
        self,
        premises: list[str],
        positive_claims: list[str],
        negative_claims: list[str],
    ) -> list[SemanticScore]:
        if not (len(premises) == len(positive_claims) == len(negative_claims)):
            raise ValueError("premise/claim lengths must match")
        if not premises:
            return []

        results: list[SemanticScore] = []
        for start in range(0, len(premises), self.batch_size):
            p_batch = premises[start : start + self.batch_size]
            pos_batch = positive_claims[start : start + self.batch_size]
            neg_batch = negative_claims[start : start + self.batch_size]
            all_premises: list[str] = []
            all_claims: list[str] = []
            for premise, positive, negative in zip(p_batch, pos_batch, neg_batch):
                all_premises.extend([premise, premise])
                all_claims.extend([positive, negative])

            encoded = self.tokenizer(
                all_premises,
                all_claims,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with self.torch.no_grad():
                probs = (
                    self.torch.softmax(self.model(**encoded).logits, dim=-1)
                    .detach()
                    .cpu()
                    .tolist()
                )

            for i in range(len(p_batch)):
                positive = probs[2 * i]
                negative = probs[2 * i + 1]
                positive_e = float(positive[self.entail])
                negative_e = float(negative[self.entail])
                mass = positive_e + negative_e
                preference = 0.0 if mass <= 1e-12 else (positive_e - negative_e) / mass

                # A tiny entailment difference between two essentially neutral
                # claims must not be amplified into a confident decision.
                reliability = max(0.0, min(1.0, mass / 0.50))
                margin = preference * reliability
                support = 0.5 + 0.5 * margin
                contradiction = 0.5 - 0.5 * margin
                neutral = 1.0 - reliability
                results.append(SemanticScore(support, contradiction, neutral))
        return results

    def score(self, case: RcaCase, hypothesis: Hypothesis) -> SemanticScore:
        return self.score_many(case, [hypothesis])[0]

    def score_many(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[SemanticScore]:
        premises = [self._premise(case, h) for h in hypotheses]
        positives = [self._causal_claim(h) for h in hypotheses]
        negatives = [self._noncausal_claim(h) for h in hypotheses]
        return self._contrastive_scores(premises, positives, negatives)

    @staticmethod
    def _causal_claim(hypothesis: Hypothesis) -> str:
        return (
            f"The incident anomaly at {hypothesis.edge.source} causally propagated "
            f"to {hypothesis.edge.target}."
        )

    @staticmethod
    def _noncausal_claim(hypothesis: Hypothesis) -> str:
        return (
            f"The observed dependency from {hypothesis.edge.source} to {hypothesis.edge.target} "
            f"did not causally propagate the incident anomaly."
        )

    @staticmethod
    def _premise(case: RcaCase, hypothesis: Hypothesis) -> str:
        wanted = set(hypothesis.evidence_ids)
        selected = [e for e in case.evidence if e.evidence_id in wanted]
        evidence = " ".join(_evidence_text(e) for e in selected)
        return (
            f"The telemetry collector observed a dependency from {hypothesis.edge.source} "
            f"to {hypothesis.edge.target}. Incident telemetry for the two endpoints: {evidence}"
        )


class DebertaStructuralRelationScorer(DebertaEvidenceScorer):
    """Stage-1 semantic validator for abducted structural triples.

    It reuses the same DeBERTa NLI backend as the causal scorer but compares a
    structural-relation claim against an explicit non-support claim. This keeps
    Stage 1 and Stage 2 semantically separate while avoiding a second model load
    when the same scorer instance is reused by an experiment driver.
    """

    _RELATION_PHRASE = {
        "calls": "calls",
        "deployed_on": "is deployed on",
        "runs_on": "runs on",
        "uses_database": "uses the database",
        "uses_messaging": "uses the messaging target",
        "has_service": "contains the service",
    }

    def score_structural_many(
        self,
        observations: list[RelationObservation],
        hypotheses: list[StructuralHypothesis],
    ) -> list[SemanticScore]:
        if not hypotheses:
            return []
        by_id = {item.observation_id: item for item in observations}
        premises: list[str] = []
        positives: list[str] = []
        negatives: list[str] = []
        for hypothesis in hypotheses:
            selected = [by_id[x] for x in hypothesis.observation_ids if x in by_id]
            evidence = " ".join(_relation_observation_text(item) for item in selected)
            premise = (
                "Operational telemetry observations for a possible structural relation: "
                + (evidence or "No direct relation evidence was retained.")
            )
            phrase = self._RELATION_PHRASE.get(
                hypothesis.edge.relation,
                f"has relation {hypothesis.edge.relation} with",
            )
            positive = f"{hypothesis.edge.source} {phrase} {hypothesis.edge.target}."
            negative = (
                f"The telemetry does not support that {hypothesis.edge.source} {phrase} "
                f"{hypothesis.edge.target}; the endpoints are only co-observed."
            )
            premises.append(premise)
            positives.append(positive)
            negatives.append(negative)
        return self._contrastive_scores(premises, positives, negatives)


class DeterministicEvidenceScorer:
    """Dependency-free Stage-2 scorer used only for unit/smoke tests."""

    def score(self, case: RcaCase, hypothesis: Hypothesis) -> SemanticScore:
        support = max(0.0, min(1.0, hypothesis.abductive_score))
        return SemanticScore(support=support, contradiction=1.0 - support, neutral=0.0)

    def score_many(self, case: RcaCase, hypotheses: list[Hypothesis]) -> list[SemanticScore]:
        return [self.score(case, h) for h in hypotheses]


class DeterministicStructuralScorer:
    """Dependency-free Stage-1 semantic stub for deterministic tests."""

    def score_structural_many(
        self,
        observations: list[RelationObservation],
        hypotheses: list[StructuralHypothesis],
    ) -> list[SemanticScore]:
        del observations
        return [
            SemanticScore(
                support=max(0.0, min(1.0, h.abductive_support)),
                contradiction=1.0 - max(0.0, min(1.0, h.abductive_support)),
                neutral=0.0,
            )
            for h in hypotheses
        ]


def apply_semantic_scores(case: RcaCase, hypotheses: list[Hypothesis], scorer) -> list[Hypothesis]:
    if hasattr(scorer, "score_many"):
        scores = scorer.score_many(case, hypotheses)
    else:
        scores = [scorer.score(case, h) for h in hypotheses]
    if len(scores) != len(hypotheses):
        raise RuntimeError("semantic scorer returned a mismatched score count")
    for hypothesis, score in zip(hypotheses, scores):
        hypothesis.semantic_support = score.support
        hypothesis.semantic_contradiction = score.contradiction
        hypothesis.semantic_neutral = score.neutral
    return hypotheses


def _evidence_text(e: Evidence) -> str:
    state = "abnormal" if e.is_anomalous else "normal"
    ts = f" at time {e.timestamp:.3f}" if e.timestamp is not None else ""
    detail = e.text.strip() if e.text else f"{e.kind} signal {e.signal}"
    return f"[{e.node}] {detail}; state={state}; abnormality={e.abnormality:.3f}{ts}."


def _relation_observation_text(item: RelationObservation) -> str:
    detail = item.text.strip() or item.evidence_kind
    count = item.metadata.get("observation_count", 1)
    return (
        f"[{item.source} -> {item.target}] {detail} "
        f"evidence_kind={item.evidence_kind}; confidence={item.confidence:.3f}; count={count}."
    )
