from app.rag.reference_ids import (
    extract_equation_number,
    extract_example_number,
    extract_figure_number,
    parse_section_number,
    parse_section_query,
)


def test_parse_section_number_from_heading() -> None:
    assert parse_section_number("2.7 Eigendecomposition") == "2.7"


def test_parse_section_query() -> None:
    assert parse_section_query("explain section 2.7 on eigenvectors") == "2.7"


def test_extract_figure_number_from_caption() -> None:
    assert extract_figure_number("Figure 2.1 shows the transpose of a matrix.") == "2.1"


def test_extract_equation_number_from_label() -> None:
    assert extract_equation_number("This is equation 2.5 in the chapter.") == "2.5"
    assert extract_equation_number("The identity relation (2.39) defines eigenvectors.") == "2.39"


def test_extract_example_number_from_section_style_heading() -> None:
    assert extract_example_number("2.12 Example: Principal Components Analysis") == "2.12"
    assert extract_example_number("walk through example 3") == "3"
