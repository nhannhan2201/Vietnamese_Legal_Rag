"""Hand-calculated retrieval metrics; no indexes, model or network required."""

from copy import deepcopy
import unittest

from legal_rag.evaluation.metrics import (
    aggregate_metrics, evaluate_query, is_relevant_chunk,
)


def passage(doc_id="A", start=100, end=200):
    return {"doc_id": doc_id, "start_char": start, "end_char": end}


def hit(chunk_id, doc_id="A", start=50, end=250):
    return {"chunk_id": chunk_id, **passage(doc_id, start, end)}


class EvaluationMetricsTests(unittest.TestCase):
    def test_correct_chunk_at_rank_two_and_missing_second_document(self):
        evidence = [passage(), passage("B")]
        result = evaluate_query([hit("x", "X"), hit("a")], evidence)
        self.assertEqual(result, {"recall@5": 0.5, "hit@5": 1.0, "rr@5": 0.5})

    def test_correct_document_without_evidence_is_not_a_chunk_hit(self):
        self.assertEqual(evaluate_query([hit("a", end=150)], [passage()]),
                         {"recall@5": 1.0, "hit@5": 0.0, "rr@5": 0.0})

    def test_multiple_chunks_and_passages_do_not_inflate_document_recall(self):
        evidence = [passage(), passage(start=500, end=550), passage("B")]
        hits = [hit("a1"), hit("a2", start=400, end=600)]
        self.assertEqual(evaluate_query(hits, evidence)["recall@5"], 0.5)

    def test_equal_boundaries_and_alternative_passage(self):
        evidence = [passage(), passage(start=500, end=550)]
        self.assertTrue(is_relevant_chunk(hit("a", start=500, end=550), evidence))

    def test_offsets_in_another_document_do_not_match(self):
        self.assertFalse(is_relevant_chunk(hit("x", "X"), [passage()]))

    def test_partial_chunks_are_not_merged_into_one_hit(self):
        hits = [hit("a1", start=90, end=150), hit("a2", start=150, end=210)]
        self.assertEqual(evaluate_query(hits, [passage()])["hit@5"], 0.0)

    def test_do_not_refill_after_document_deduplication(self):
        hits = [hit(f"a{i}") for i in range(5)] + [hit("b", "B")]
        scores = evaluate_query(hits, [passage(), passage("B")])
        self.assertEqual(scores["recall@5"], 0.5)

    def test_correct_chunk_outside_top_k_is_not_counted(self):
        hits = [hit(f"x{i}", "X") for i in range(5)] + [hit("a")]
        self.assertEqual(evaluate_query(hits, [passage()]),
                         {"recall@5": 0.0, "hit@5": 0.0, "rr@5": 0.0})

    def test_empty_results_are_zero(self):
        self.assertEqual(evaluate_query([], [passage()]),
                         {"recall@5": 0.0, "hit@5": 0.0, "rr@5": 0.0})

    def test_aggregate_uses_mean_rr_not_inverse_mean_rank(self):
        scores = [evaluate_query([hit("a")], [passage()]),
                  evaluate_query([hit("x", "X"), hit("a")], [passage()]),
                  evaluate_query([], [passage()])]
        result = aggregate_metrics(scores)
        self.assertEqual(result["mrr@5"], 0.5)
        self.assertAlmostEqual(result["recall@5"], 2 / 3)
        self.assertAlmostEqual(result["hit@5"], 2 / 3)

    def test_configurable_k_and_inputs_unchanged(self):
        hits, evidence = [hit("x", "X"), hit("a")], [passage()]
        before = deepcopy((hits, evidence))
        self.assertEqual(evaluate_query(hits, evidence, k=1),
                         {"recall@1": 0.0, "hit@1": 0.0, "rr@1": 0.0})
        self.assertEqual((hits, evidence), before)

    def test_reject_invalid_k(self):
        for k in (0, -1, True, 1.5):
            with self.subTest(k=k), self.assertRaises(ValueError):
                evaluate_query([], [passage()], k=k)

    def test_reject_invalid_evidence_or_offsets(self):
        for evidence in ([], [passage(start=100, end=100)],
                         [passage(start=-1)], [passage(start=True)]):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                evaluate_query([], evidence)

    def test_reject_duplicate_chunk_ids(self):
        with self.assertRaises(ValueError):
            evaluate_query([hit("a"), hit("a")], [passage()])

    def test_reject_invalid_summaries(self):
        for rows in ([], [{}], [{"recall@5": float("nan")}],
                     [{"recall@5": 2.0}], [{"recall@5": True}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                aggregate_metrics(rows)


if __name__ == "__main__":
    unittest.main()
