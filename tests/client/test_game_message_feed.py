"""GameMessageFeed の単体テスト。"""
from src.client.game_message_feed import GameMessageFeed
from src.game.game_message import GameMessage


def test_push_keeps_recent_messages_newest_first():
    feed = GameMessageFeed()
    feed.push(
        [
            GameMessage(text="first", source="monitor"),
            GameMessage(text="second", source="progression", priority=5),
        ]
    )
    entries = feed.entries()
    assert len(entries) == 2
    assert entries[0].text == "second"
    assert entries[0].source == "progression"
    assert entries[1].text == "first"


def test_push_deduplicates_same_text():
    feed = GameMessageFeed()
    feed.push_text("hello", source="game")
    feed.push_text("hello", source="progression")
    assert len(feed.entries()) == 1
    assert feed.entries()[0].source == "progression"


def test_max_entries_trim():
    feed = GameMessageFeed()
    feed.MAX_ENTRIES = 3
    for i in range(5):
        feed.push_text(f"msg{i}")
    texts = [e.text for e in feed.entries()]
    assert texts == ["msg4", "msg3", "msg2"]
