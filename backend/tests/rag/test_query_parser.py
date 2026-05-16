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
