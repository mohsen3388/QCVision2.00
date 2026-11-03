from visionqc.voice.wake_word_core import WakeWordMatcher


def test_wake_word_and_question_in_one_utterance():
    matcher = WakeWordMatcher("Vision", conversation_timeout=30)
    result = matcher.feed("Vision, what should I check first?", now=100)
    assert result.activated is True
    assert result.question == "what should I check first"


def test_wake_word_arms_follow_up_question():
    matcher = WakeWordMatcher("Vision", conversation_timeout=30)
    first = matcher.feed("Vision", now=100)
    second = matcher.feed("Why did you issue this warning?", now=110)
    assert first.activated and first.question == ""
    assert second.activated
    assert second.question == "Why did you issue this warning?"


def test_normal_factory_speech_is_ignored_without_wake_word():
    matcher = WakeWordMatcher("Vision", conversation_timeout=30)
    result = matcher.feed("The mixer is ready", now=100)
    assert result.activated is False
    assert result.question == ""


def test_conversation_window_expires():
    matcher = WakeWordMatcher("Vision", conversation_timeout=10)
    matcher.feed("Vision", now=100)
    result = matcher.feed("What next?", now=111)
    assert result.activated is False


def test_persian_wake_word_and_question():
    matcher = WakeWordMatcher("Vision", conversation_timeout=30)
    result = matcher.feed("ویژن، اول چه چیزی را بررسی کنم؟", now=100)
    assert result.activated is True
    assert result.question == "اول چه چیزی را بررسی کنم"
