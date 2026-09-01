import random
import unittest

from calcio_balilla.core.tournament import (
    bracket_numbers,
    draw_companions,
    generate_bracket,
    select_byes,
    series_result,
    validate_series_match,
    valid_companion_pairs,
)


class TournamentBracketTests(unittest.TestCase):
    def test_bracket_sizes_four_to_nine(self):
        expected = {
            4: (4, 0, 0), 5: (4, 1, 3), 6: (4, 2, 2),
            7: (4, 3, 1), 8: (8, 0, 0), 9: (8, 1, 7),
        }
        for count, numbers in expected.items():
            with self.subTest(count=count):
                self.assertEqual(bracket_numbers(count), numbers)
                specs = generate_bracket(range(1, count + 1), range(1, count + 1), random.Random(4))
                self.assertEqual(len(specs), count - 1)
                self.assertEqual(sum(s.round_name == "Preliminari" for s in specs), numbers[1])
                self.assertEqual(sum(s.is_final for s in specs), 1)

    def test_byes_use_previous_ranking_then_deterministic_id_fallback(self):
        self.assertEqual(select_byes([7, 2, 5, 9], [5, 7], 3), [5, 7, 2])
        specs = generate_bracket([1, 2, 3, 4, 5, 6], [4, 2, 1], random.Random(1))
        preliminary_players = {p for s in specs if s.round_name == "Preliminari"
                               for p in (s.challenger1_id, s.challenger2_id)}
        self.assertNotIn(4, preliminary_players)
        self.assertNotIn(2, preliminary_players)

    def test_pairing_is_seedable_and_not_rating_balanced(self):
        first = generate_bracket(range(1, 9), (), random.Random(22))
        second = generate_bracket(range(1, 9), (), random.Random(22))
        self.assertEqual(first, second)
        self.assertNotEqual([(s.challenger1_id, s.challenger2_id) for s in first[:4]],
                            [(1, 8), (2, 7), (3, 6), (4, 5)])


class TournamentSeriesTests(unittest.TestCase):
    def test_best_of_three_results(self):
        self.assertEqual(series_result([1, 1], 1, 2), (2, 0, 1))
        self.assertEqual(series_result([1, 2, 1], 1, 2), (2, 1, 1))
        self.assertEqual(series_result([1], 1, 2), (1, 0, None))

    def test_final_best_of_five_results(self):
        self.assertEqual(series_result([1, 1, 1], 1, 2, True), (3, 0, 1))
        self.assertEqual(series_result([1, 2, 1, 2, 1], 1, 2, True), (3, 2, 1))
        self.assertIsNone(series_result([1, 1], 1, 2, True)[2])

    def test_companion_constraints_and_side_switch(self):
        pairs = valid_companion_pairs(1, 2, [1, 2, 3, 4, 5], used1=[3], used2=[4])
        self.assertNotIn((3, 5), pairs)
        self.assertNotIn((5, 4), pairs)
        self.assertIn((4, 3), pairs)  # each companion may switch challenger
        self.assertTrue(all(a != b and a not in (1, 2) and b not in (1, 2) for a, b in pairs))

    def test_draw_fails_without_complete_valid_combination(self):
        with self.assertRaisesRegex(ValueError, "No valid pair"):
            draw_companions(1, 2, [1, 2, 3], rng=random.Random(1))

    def test_manual_match_validation(self):
        self.assertEqual(validate_series_match(1, 2, (1, 8), (2, 9)), (8, 9))
        self.assertEqual(validate_series_match(1, 2, (2, 8), (1, 9)), (9, 8))
        with self.assertRaises(ValueError):
            validate_series_match(1, 2, (1, 2), (8, 9))
        with self.assertRaisesRegex(ValueError, "already played"):
            validate_series_match(1, 2, (1, 8), (2, 9), used1=[8])

    def test_companion_history_resets_between_series(self):
        self.assertIn((3, 4), valid_companion_pairs(1, 5, [1, 3, 4, 5]))


if __name__ == "__main__":
    unittest.main()
