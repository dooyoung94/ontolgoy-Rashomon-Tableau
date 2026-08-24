from rashomon_tableau.truth_resolution import SourceClaim
from rashomon_tableau.truth_worlds import candidate_truth_worlds, possible_world_truth_resolution


def test_candidate_worlds_can_combine_partial_claims():
    claims = [
        SourceClaim("book", "s1", frozenset({"a"})),
        SourceClaim("book", "s2", frozenset({"b"})),
        SourceClaim("book", "s3", frozenset({"a", "b"})),
    ]
    worlds = candidate_truth_worlds(claims)
    assert frozenset({"a"}) in worlds
    assert frozenset({"a", "b"}) in worlds


def test_marginal_world_resolution_returns_normalized_worlds():
    claims = [
        SourceClaim("book", "s1", frozenset({"a", "b"})),
        SourceClaim("book", "s2", frozenset({"a"})),
        SourceClaim("book", "s3", frozenset({"a", "b"})),
    ]
    pred, reliability, world_map, _ = possible_world_truth_resolution(claims, mode="marginal", iterations=3)
    assert "book" in pred
    assert set(reliability) == {"s1", "s2", "s3"}
    assert abs(sum(w.posterior for w in world_map["book"]) - 1.0) < 1e-9


def test_uniform_and_marginal_modes_use_same_candidate_space():
    claims = [
        SourceClaim("book", "s1", frozenset({"a"})),
        SourceClaim("book", "s2", frozenset({"a", "b"})),
    ]
    _, _, _, c1 = possible_world_truth_resolution(claims, mode="uniform")
    _, _, _, c2 = possible_world_truth_resolution(claims, mode="marginal", iterations=2)
    assert c1 == c2
