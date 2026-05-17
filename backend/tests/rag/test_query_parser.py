from app.rag.query_parser import parse_retrieval_query


def test_parse_page_and_problem_query() -> None:
    parsed = parse_retrieval_query("help me with problem 8 on page 37")

    assert parsed.page_number == 37
    assert parsed.exercise_number == "8"
    assert parsed.is_structured_lookup is True


def test_parse_exercise_wording() -> None:
    parsed = parse_retrieval_query("Can you explain exercise 12 from p. 41?")

    assert parsed.page_number == 41
    assert parsed.exercise_number == "12"
    assert parsed.is_structured_lookup is True


def test_parse_concept_query_as_semantic() -> None:
    parsed = parse_retrieval_query("What are equivalent fractions?")

    assert parsed.page_number is None
    assert parsed.exercise_number == ""
    assert parsed.is_structured_lookup is False


def test_parse_pg_page_wording() -> None:
    parsed = parse_retrieval_query("show me pg 10")

    assert parsed.page_number == 10
    assert parsed.is_structured_lookup is True


def test_parse_question_wording() -> None:
    parsed = parse_retrieval_query("question 4 is confusing")

    assert parsed.exercise_number == "4"
    assert parsed.is_structured_lookup is True


def test_parse_hash_exercise() -> None:
    parsed = parse_retrieval_query("#8")

    assert parsed.exercise_number == "8"
    assert parsed.is_structured_lookup is True


def test_parse_question_hash_exercise() -> None:
    parsed = parse_retrieval_query("question #8")

    assert parsed.exercise_number == "8"
    assert parsed.is_structured_lookup is True


def test_parse_example_wording() -> None:
    parsed = parse_retrieval_query("example 3")

    assert parsed.example_number == "3"
    assert parsed.is_structured_lookup is True


def test_ignore_hash_after_word_character() -> None:
    parsed = parse_retrieval_query("x#8")

    assert parsed.exercise_number == ""
    assert parsed.is_structured_lookup is False


def test_parse_spelled_out_problem_number() -> None:
    parsed = parse_retrieval_query("Tell me about problem three")

    assert parsed.exercise_number == "3"
    assert parsed.is_structured_lookup is True


def test_parse_spelled_out_question_number() -> None:
    parsed = parse_retrieval_query("what's question number two?")

    assert parsed.exercise_number == "2"
    assert parsed.is_structured_lookup is True


def test_parse_spelled_out_page() -> None:
    parsed = parse_retrieval_query("look at page seven")

    assert parsed.page_number == 7
    assert parsed.is_structured_lookup is True


def test_parse_spelled_out_example() -> None:
    parsed = parse_retrieval_query("explain example five")

    assert parsed.example_number == "5"
    assert parsed.is_structured_lookup is True


def test_parse_question_number_with_digit() -> None:
    # The "number" between "question" and the digit is a common voice pattern;
    # it should still resolve to the exercise number.
    parsed = parse_retrieval_query("question number 4")

    assert parsed.exercise_number == "4"
    assert parsed.is_structured_lookup is True


def test_query_field_preserves_original_phrasing() -> None:
    # Normalisation is for matching only — the original query string is
    # what gets passed to the semantic-search fallback.
    parsed = parse_retrieval_query("problem three")

    assert parsed.query == "problem three"
