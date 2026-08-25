from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .models import Literal


@dataclass(frozen=True)
class KGTriple:
    head: str
    relation: str
    tail: str


@dataclass(frozen=True)
class MultiHopExample:
    example_id: str
    head: str
    gold_relation: str
    tail: str
    path: tuple[KGTriple, ...]

    @property
    def hop_count(self) -> int:
        return len(self.path)


@dataclass
class TextMappings:
    entity: dict[str, str]
    relation: dict[str, str]

    def entity_text(self, key: str) -> str:
        return self.entity.get(key, key.replace("_", " ").strip())

    def relation_text(self, key: str) -> str:
        value = self.relation.get(key)
        if value:
            return value
        return key.strip("_").replace("_", " ").strip()


def read_triples(path: str | Path) -> list[KGTriple]:
    triples: list[KGTriple] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split("\t")
        if len(parts) < 3:
            parts = raw.split()
        if len(parts) < 3:
            continue
        triples.append(KGTriple(parts[0], parts[1], parts[2]))
    return triples


def read_text_mapping(path: str | Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if "\t" in raw:
            key, value = raw.split("\t", 1)
        else:
            parts = raw.split(None, 1)
            if len(parts) == 1:
                key, value = parts[0], parts[0]
            else:
                key, value = parts
        out[key.strip()] = value.strip()
    return out


def load_text_mappings(entity2text: str | Path, relation2text: str | Path) -> TextMappings:
    return TextMappings(read_text_mapping(entity2text), read_text_mapping(relation2text))


def relation_vocabulary(*splits: Sequence[KGTriple]) -> list[str]:
    return sorted({triple.relation for split in splits for triple in split})


def build_multihop_examples(
    train: Sequence[KGTriple],
    targets: Sequence[KGTriple],
    *,
    min_hops: int = 2,
    max_hops: int = 4,
    max_examples: int | None = None,
    max_paths_per_target: int = 1,
) -> list[MultiHopExample]:
    """Select target triples whose endpoints remain connected through 2-4 train hops.

    The target relation itself is never inserted into the evidence path. The path is
    discovered only from the train graph, which keeps the benchmark gold relation
    evaluation-only for the relation-completion stage.
    """
    if min_hops < 1 or max_hops < min_hops:
        raise ValueError("invalid hop bounds")

    adjacency: dict[str, list[KGTriple]] = defaultdict(list)
    for triple in train:
        adjacency[triple.head].append(triple)

    examples: list[MultiHopExample] = []
    for target_index, target in enumerate(targets):
        paths = _bounded_directed_paths(
            adjacency,
            target.head,
            target.tail,
            min_hops=min_hops,
            max_hops=max_hops,
            limit=max_paths_per_target,
        )
        for path_index, path in enumerate(paths):
            examples.append(
                MultiHopExample(
                    example_id=f"{target_index}:{path_index}",
                    head=target.head,
                    gold_relation=target.relation,
                    tail=target.tail,
                    path=tuple(path),
                )
            )
            if max_examples is not None and len(examples) >= max_examples:
                return examples
    return examples


def path_as_literals(path: Sequence[KGTriple], *, source: str = "kg_path") -> tuple[Literal, ...]:
    return tuple(
        Literal(triple.relation, triple.head, triple.tail, False, source=source)
        for triple in path
    )


def path_evidence_text(path: Sequence[KGTriple], mappings: TextMappings) -> list[str]:
    return [
        f"{mappings.entity_text(triple.head)} {mappings.relation_text(triple.relation)} {mappings.entity_text(triple.tail)}."
        for triple in path
    ]


def candidate_relation_text(head: str, relation: str, tail: str, mappings: TextMappings) -> str:
    return f"{mappings.entity_text(head)} {mappings.relation_text(relation)} {mappings.entity_text(tail)}."


def _bounded_directed_paths(
    adjacency: dict[str, list[KGTriple]],
    start: str,
    goal: str,
    *,
    min_hops: int,
    max_hops: int,
    limit: int,
) -> list[list[KGTriple]]:
    if start == goal:
        return []
    queue = deque([(start, [], {start})])
    out: list[list[KGTriple]] = []
    while queue and len(out) < limit:
        node, path, visited = queue.popleft()
        if len(path) >= max_hops:
            continue
        for edge in adjacency.get(node, []):
            next_path = [*path, edge]
            next_node = edge.tail
            if next_node == goal and len(next_path) >= min_hops:
                out.append(next_path)
                if len(out) >= limit:
                    break
                continue
            if next_node in visited:
                continue
            queue.append((next_node, next_path, visited | {next_node}))
    return out
