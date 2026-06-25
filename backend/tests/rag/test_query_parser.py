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


def test_parse_chapter_query() -> None:
    parsed = parse_retrieval_query("summarize chapter 2 on linear algebra")

    assert parsed.chapter_number == 2
    assert parsed.is_structured_lookup is True


def test_parse_spelled_out_chapter() -> None:
    parsed = parse_retrieval_query("what does chapter two cover")

    assert parsed.chapter_number == 2
    assert parsed.is_structured_lookup is True


def test_parse_chapter_two_wording() -> None:
    parsed = parse_retrieval_query("open ch 12")

    assert parsed.chapter_number == 12
    assert parsed.is_structured_lookup is True


def test_parse_section_number() -> None:
    parsed = parse_retrieval_query("summarize section 2.7 on eigendecomposition")

    assert parsed.section_number == "2.7"
    assert parsed.is_structured_lookup is True


def test_parse_figure_number() -> None:
    parsed = parse_retrieval_query("what does figure 2.1 show")

    assert parsed.figure_number == "2.1"
    assert parsed.is_structured_lookup is True


def test_parse_equation_number() -> None:
    parsed = parse_retrieval_query("show equation 2.5")

    assert parsed.equation_number == "2.5"
    assert parsed.is_structured_lookup is True


def test_parse_dotted_example_number() -> None:
    parsed = parse_retrieval_query("explain example 2.12 on PCA")

    assert parsed.example_number == "2.12"
    assert parsed.is_structured_lookup is True
