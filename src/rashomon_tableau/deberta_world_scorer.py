from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_DEBERTA_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


@dataclass(frozen=True)
class WorldNliScore:
    support: float
    contradiction: float
    unresolved: float

    def normalized(self) -> "WorldNliScore":
        total = max(1e-12, self.support + self.contradiction + self.unresolved)
        return WorldNliScore(
            support=self.support / total,
            contradiction=self.contradiction / total,
            unresolved=self.unresolved / total,
        )


class DebertaWorldScorer:
    """Discriminative NLI scorer for Rashomon candidate worlds.

    DeBERTa is intentionally *not* used to extract claims or generate worlds.
    It only scores whether a candidate evidence world supports, contradicts, or
    leaves a query unresolved. This isolates the world-ranking contribution.
    """

    def __init__(self, model_name: str = DEFAULT_DEBERTA_MODEL, device: str | None = None):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Install DeBERTa benchmark dependencies: pip install torch transformers sentencepiece"
            ) from exc

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()

        # Resolve labels without relying on one fixed label ordering.
        id2label = {int(k): str(v).lower() for k, v in self.model.config.id2label.items()}
        self.entail_idx = self._find_label(id2label, ("entail",))
        self.contra_idx = self._find_label(id2label, ("contrad",))
        self.neutral_idx = self._find_label(id2label, ("neutral",))

    @staticmethod
    def _find_label(id2label: dict[int, str], needles: tuple[str, ...]) -> int:
        for idx, label in id2label.items():
            if any(needle in label for needle in needles):
                return idx
        raise RuntimeError(f"Unable to resolve NLI label from model labels: {id2label}")

    @staticmethod
    def _query_sentence(query: str) -> str:
        return query.strip()

    @staticmethod
    def _world_text(world_evidence: Iterable[str]) -> str:
        return " ".join(x.strip() for x in world_evidence if x and x.strip())

    def score(self, query: str, world_evidence: Iterable[str]) -> WorldNliScore:
        premise = self._world_text(world_evidence)
        hypothesis = self._query_sentence(query)
        if not premise or not hypothesis:
            return WorldNliScore(0.0, 0.0, 1.0)

        encoded = self.tokenizer(
            premise,
            hypothesis,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}
        with self.torch.no_grad():
            logits = self.model(**encoded).logits[0]
            probs = self.torch.softmax(logits, dim=-1).detach().cpu().tolist()
        return WorldNliScore(
            support=float(probs[self.entail_idx]),
            contradiction=float(probs[self.contra_idx]),
            unresolved=float(probs[self.neutral_idx]),
        ).normalized()
