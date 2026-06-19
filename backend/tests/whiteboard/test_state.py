import time

from app.agent.whiteboard.state import BoardState


def test_initial_state_is_blank() -> None:
    state = BoardState()

    assert state.user_text == ""
    assert state.is_blank is True
    assert state.refreshed_at is None
    assert state.age_seconds() is None


def test_record_reading_updates_text_and_timestamp() -> None:
    state = BoardState()
    before = time.time()
    state.record_reading("2x + 3 = 9")
    after = time.time()

    assert state.user_text == "Student Card 1:\n2x + 3 = 9"
    assert state.is_blank is False
    assert state.refreshed_at is not None
    assert before <= state.refreshed_at <= after
    age = state.age_seconds()
    assert age is not None and age >= 0


def test_record_empty_marks_blank() -> None:
    state = BoardState()
    state.record_reading("scratch")
    state.record_empty()

    assert state.user_text == ""
    assert state.is_blank is True
    assert state.refreshed_at is not None


def test_records_readings_per_student_card() -> None:
    state = BoardState()

    state.record_reading("x = 2", card_id="student-card-1", card_label="Student Card 1")
    state.record_reading("factor tree", card_id="student-card-2", card_label="Student Card 2")

    assert state.is_blank is False
    assert state.user_text == "Student Card 1:\nx = 2\n\nStudent Card 2:\nfactor tree"


def test_record_empty_clears_only_matching_student_card() -> None:
    state = BoardState()
    state.record_reading("x = 2", card_id="student-card-1", card_label="Student Card 1")
    state.record_reading("factor tree", card_id="student-card-2", card_label="Student Card 2")

    state.record_empty(card_id="student-card-1")

    assert state.user_text == "Student Card 2:\nfactor tree"
    assert state.is_blank is False
