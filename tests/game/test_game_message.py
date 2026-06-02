"""GameMessage 経過秒スタンプ。"""
from __future__ import annotations

import unittest

from src.game.game_message import GameMessage, stamp_messages, with_elapsed
from src.sim.systems.world import World


class TestGameMessage(unittest.TestCase):
    def test_with_elapsed_prefix(self):
        world = World("PhaseWaveTest")
        msg = with_elapsed("テスト", world, source="phase")
        self.assertTrue(msg.text.startswith("["))
        self.assertIn("s]", msg.text)
        self.assertIn("テスト", msg.text)
        self.assertIsNotNone(msg.elapsed_seconds)

    def test_stamp_messages_skips_already_stamped(self):
        world = World("PhaseWaveTest")
        msgs = [
            GameMessage(text="a", source="game", elapsed_seconds=1.0),
            GameMessage(text="b", source="game"),
        ]
        out = stamp_messages(msgs, world)
        self.assertEqual(out[0].text, "a")
        self.assertTrue(out[1].text.startswith("["))


if __name__ == "__main__":
    unittest.main()
