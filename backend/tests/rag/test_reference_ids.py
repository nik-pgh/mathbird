from app.rag.reference_ids import (
    extract_equation_number,
    extract_example_number,
    extract_figure_number,
    extract_section_number,
    parse_section_number,
    parse_section_query,
)


def test_parse_section_number_from_heading() -> None:
    assert parse_section_number("2.7 Eigendecomposition") == "2.7"


def test_extract_section_number_from_markdown_heading() -> None:
    assert extract_section_number("", "## 2.8 Singular Value Decomposition") == "2.8"
    assert parse_section_number("## 2.8 Singular Value Decomposition") == "2.8"


def test_extract_section_number_prefers_heading_over_later_mentions() -> None:
    haystack = "## 2.8 Singular Value Decomposition\nSee also section 2.7."
    assert extract_section_number(haystack) == "2.8"


def test_parse_section_query() -> None:
    assert parse_section_query("explain section 2.7 on eigenvectors") == "2.7"


def test_extract_figure_number_from_caption() -> None:
    assert extract_figure_number("Figure 2.1 shows the transpose of a matrix.") == "2.1"


def test_extract_equation_number_from_label() -> None:
    assert extract_equation_number("This is equation 2.5 in the chapter.") == "2.5"
    assert extract_equation_number("The identity relation (2.39) defines eigenvectors.") == "2.39"


def test_extract_equation_number_from_latex_tag() -> None:
    tagged = r"$$ \boldsymbol{x} = \boldsymbol{A}^{-1}\boldsymbol{b}. \tag{2.25} $$"
    assert extract_equation_number(tagged) == "2.25"
    assert (
        extract_equation_number(
            "",
            r"$$ \boldsymbol{Ax} = \sum_i x_i \boldsymbol{A}_{:,i}. \tag{2.27} $$",
        )
        == "2.27"
    )


def test_extract_equation_number_prefers_tag_over_cross_reference() -> None:
    haystack = (
        "In order for A^{-1} to exist, equation 2.11 must have exactly one solution.\n"
        r"$$ \boldsymbol{x} = \boldsymbol{A}^{-1}\boldsymbol{b}. \tag{2.25} $$"
    )
    assert extract_equation_number(haystack) == "2.25"


def test_extract_example_number_from_section_style_heading() -> None:
    assert extract_example_number("2.12 Example: Principal Components Analysis") == "2.12"
    assert extract_example_number("walk through example 3") == "3"
