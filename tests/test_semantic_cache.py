from src.llm.semantic_cache import SemanticQueryCache


def test_semantic_cache_in_memory_hit_and_miss():
    cache = SemanticQueryCache(qdrant_client=None, dim=3, threshold=0.9)

    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    cache.upsert(vec_a, {"resp": "A"})
    cache.upsert(vec_b, {"resp": "B"})

    hit = cache.search([0.95, 0.05, 0.0])
    assert hit == {"resp": "A"}

    miss = cache.search([0.0, 0.0, 1.0])
    assert miss is None
