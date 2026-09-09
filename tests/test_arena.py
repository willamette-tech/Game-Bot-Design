import time
import unittest

from arena import LoadedBot, load_bot_files, run_match
from tournament import SCORING_PRESETS, score_match


def bot(bot_id, function):
    return LoadedBot(bot_id, bot_id.title(), function)


def straight(state):
    return state.direction


class ArenaRuleTests(unittest.TestCase):
    def test_head_on_collision_kills_both(self):
        replay = run_match(
            [bot("a", straight), bot("b", straight)],
            width=5,
            height=5,
            initial_states={"a": (1, 2, "right"), "b": (3, 2, "left")},
        )
        self.assertTrue(all(not item["alive"] for item in replay["frames"][-1]["bots"]))
        self.assertEqual({item["place"] for item in replay["results"]["placements"]}, {1})

    def test_three_way_same_cell_collision_kills_everyone(self):
        replay = run_match(
            [bot("a", straight), bot("b", straight), bot("c", straight)],
            width=5,
            height=5,
            initial_states={"a": (1, 2, "right"), "b": (3, 2, "left"), "c": (2, 1, "down")},
        )
        self.assertEqual(sum(item["alive"] for item in replay["frames"][-1]["bots"]), 0)
        self.assertEqual({item["place"] for item in replay["results"]["placements"]}, {1})

    def test_out_of_bounds_death(self):
        replay = run_match(
            [bot("edge", straight), bot("safe", straight)],
            width=6,
            height=6,
            initial_states={"edge": (0, 0, "left"), "safe": (2, 4, "right")},
        )
        final = {item["id"]: item for item in replay["frames"][-1]["bots"]}
        self.assertFalse(final["edge"]["alive"])
        self.assertTrue(final["safe"]["alive"])

    def test_self_trail_death(self):
        def square(state):
            return {1: "down", 2: "left", 3: "up"}.get(state.tick, "right")

        replay = run_match(
            [bot("square", square), bot("safe", straight)],
            width=8,
            height=8,
            tick_cap=6,
            initial_states={"square": (2, 2, "right"), "safe": (6, 6, "up")},
        )
        final = {item["id"]: item for item in replay["frames"][-1]["bots"]}
        self.assertFalse(final["square"]["alive"])
        self.assertEqual(next(p for p in replay["results"]["placements"] if p["bot_id"] == "square")["death_tick"], 4)


class BotSafetyTests(unittest.TestCase):
    def _fallback_replay(self, bad_move, timeout_ms=100):
        return run_match(
            [bot("bad", bad_move), bot("other", straight)],
            width=8,
            height=8,
            tick_cap=1,
            timeout_ms=timeout_ms,
            initial_states={"bad": (1, 1, "right"), "other": (6, 6, "left")},
        )

    def _assert_fell_back_straight(self, replay, event_type):
        bad = next(item for item in replay["frames"][1]["bots"] if item["id"] == "bad")
        self.assertEqual((bad["x"], bad["y"], bad["direction"]), (2, 1, "right"))
        self.assertEqual(replay["frames"][1]["errors"][0]["type"], event_type)

    def test_exception_is_handled(self):
        def raises(_state):
            raise RuntimeError("broken on purpose")

        self._assert_fell_back_straight(self._fallback_replay(raises), "exception")

    def test_timeout_is_handled(self):
        def sleepy(_state):
            time.sleep(0.1)
            return "down"

        self._assert_fell_back_straight(self._fallback_replay(sleepy, timeout_ms=10), "timeout")

    def test_invalid_return_is_handled(self):
        # A list also proves validation does not try to hash an arbitrary return.
        self._assert_fell_back_straight(self._fallback_replay(lambda _state: ["banana"]), "invalid_return")

    def test_same_seed_reproduces_gameplay_log(self):
        bots = [bot("a", straight), bot("b", straight), bot("c", straight), bot("d", straight)]
        first = run_match(bots, seed=123, tick_cap=20, timestamp="fixed")
        second = run_match(bots, seed=123, tick_cap=20, timestamp="fixed")
        self.assertEqual(first, second)

    def test_bot_cannot_mutate_another_bots_state(self):
        def vandal(state):
            state.grid[6][6] = "fake"
            state.opponents[0].alive = False
            return "right"

        replay = self._fallback_replay(vandal)
        other = next(item for item in replay["frames"][1]["bots"] if item["id"] == "other")
        self.assertTrue(other["alive"])

    def test_explicit_bot_files_can_be_loaded_for_menu_matches(self):
        loaded = load_bot_files(["bots/examples/straight.py", "bots/examples/lookahead.py"])
        self.assertEqual([item.name for item in loaded], ["Straight Shooter", "Two-Step Lookahead"])


if __name__ == "__main__":
    unittest.main()


class TournamentScoringTests(unittest.TestCase):
    placements = [
        {"bot_id": "a", "place": 1, "trail_length": 10},
        {"bot_id": "b", "place": 2, "trail_length": 90},
    ]

    def test_survival_scoring_uses_the_placement_table_only(self):
        awarded = score_match(self.placements, *SCORING_PRESETS["survival"])
        self.assertEqual(awarded, {"a": 3.0, "b": 2.0})

    def test_coverage_scoring_follows_claimed_cells(self):
        awarded = score_match(self.placements, *SCORING_PRESETS["coverage"])
        self.assertAlmostEqual(awarded["a"], 0.5)
        self.assertAlmostEqual(awarded["b"], 4.5)

    def test_presets_are_worth_the_same_pool_when_places_are_distinct(self):
        pool = sum(score_match(self.placements, *SCORING_PRESETS["survival"]).values())
        for preset, weights in SCORING_PRESETS.items():
            with self.subTest(preset=preset):
                self.assertAlmostEqual(sum(score_match(self.placements, *weights).values()), pool)

    def test_a_wiped_out_match_does_not_divide_by_zero(self):
        awarded = score_match([{"bot_id": "a", "place": 1, "trail_length": 0}], 0.0, 1.0)
        self.assertEqual(awarded, {"a": 0.0})
