"""Tutor-board evaluation — golden cases, scoring, and reports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.agent.whiteboard.messages import (
    AiBoardDiagram,
    AiBoardItem,
    AiBoardPlot,
    AiBoardShape,
    AiBoardText,
)

TutorBoardAxis = Literal["usage", "content", "reference", "card_kind", "grouping"]

_BOARD_REFERENCE_PATTERNS = (
    r"\bon the board\b",
    r"\bthe board\b",
    r"\bour board\b",
    r"\btutor card\b",
    r"\bi put\b",
    r"\bi've put\b",
    r"\bi placed\b",
    r"\blet me put\b",
    r"\blook at the (?:equation|graph|plot|diagram|card|board|tree)\b",
    r"\bsee the (?:equation|graph|plot|diagram|card|tree)\b",
)


class ExpectedItemSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["text", "plot", "shape", "diagram"]
    id: str | None = None
    id_prefix: str | None = None
    markdown_contains: list[str] = Field(default_factory=list)
    expression_contains: list[str] = Field(default_factory=list)
    source_contains: list[str] = Field(default_factory=list)
    svg_contains: list[str] = Field(default_factory=list)
    label_contains: list[str] = Field(default_factory=list)


class ExtractorExpected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emit: bool
    min_items: int = 0
    max_items: int | None = None
    kinds: list[Literal["text", "plot", "shape", "diagram"]] = Field(default_factory=list)
    forbidden_kinds: list[Literal["text", "plot", "shape", "diagram"]] = Field(
        default_factory=list
    )
    items: list[ExpectedItemSpec] = Field(default_factory=list)
    reuse_id: str | None = None
    grouping_action: Literal["append", "create"] | None = None
    forbidden_ids: list[str] = Field(default_factory=list)


class ReferenceExpected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    references_board: bool
    utterance_contains: list[str] = Field(default_factory=list)
    utterance_not_contains: list[str] = Field(default_factory=list)
    reference_patterns: list[str] = Field(default_factory=list)


class ExtractorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentence: str
    last_sentence: str | None = None
    current_items: list[dict[str, Any]] = Field(default_factory=list)


class TutorBoardGoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    axis: TutorBoardAxis
    description: str
    notes: str | None = None
    extractor: ExtractorInput | None = None
    expected_extractor: ExtractorExpected | None = None
    tutor_board: list[dict[str, Any]] = Field(default_factory=list)
    tutor_utterance: str | None = None
    expected_reference: ReferenceExpected | None = None

    @model_validator(mode="after")
    def _validate_axis_payload(self) -> TutorBoardGoldenCase:
        if self.axis == "reference":
            if self.tutor_utterance is None or self.expected_reference is None:
                raise ValueError(
                    f"{self.id}: reference cases need tutor_utterance and expected_reference"
                )
            return self
        if self.extractor is None or self.expected_extractor is None:
            raise ValueError(f"{self.id}: extractor cases need extractor and expected_extractor")
        if self.axis == "grouping" and self.expected_extractor.grouping_action is None:
            raise ValueError(f"{self.id}: grouping cases need expected_extractor.grouping_action")
        return self


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    axis: TutorBoardAxis
    passed: bool
    failures: tuple[str, ...]
    actual_items: tuple[dict[str, Any], ...] = ()
    tutor_utterance: str | None = None


@dataclass(frozen=True)
class AxisSummary:
    axis: TutorBoardAxis
    total: int
    passed: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


@dataclass(frozen=True)
class TutorBoardEvalReport:
    golden_path: str
    extractor_model: str | None
    cases: tuple[CaseScore, ...]

    @property
    def pass_rate(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for case in self.cases if case.passed) / len(self.cases)

    def axis_summaries(self) -> tuple[AxisSummary, ...]:
        by_axis: dict[TutorBoardAxis, list[CaseScore]] = {}
        for case in self.cases:
            by_axis.setdefault(case.axis, []).append(case)
        return tuple(
            AxisSummary(
                axis=axis,
                total=len(scores),
                passed=sum(1 for score in scores if score.passed),
            )
            for axis, scores in sorted(by_axis.items())
        )


def load_tutor_board_cases(path: str | Path) -> list[TutorBoardGoldenCase]:
    cases: list[TutorBoardGoldenCase] = []
    seen: set[str] = set()
    source = Path(path)

    for line_number, line in enumerate(source.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Line {line_number}: expected JSON object")
        try:
            case = TutorBoardGoldenCase.model_validate(row)
        except ValidationError as exc:
            raise ValueError(f"Line {line_number}: {exc}") from exc
        if case.id in seen:
            raise ValueError(f"Duplicate tutor board case id: {case.id}")
        seen.add(case.id)
        cases.append(case)

    if not cases:
        raise ValueError(f"No tutor board cases found in {source}")
    return cases


def parse_board_items(raw_items: list[dict[str, Any]]) -> list[AiBoardItem]:
    parsed: list[AiBoardItem] = []
    for raw in raw_items:
        kind = raw.get("kind")
        if kind == "text":
            parsed.append(AiBoardText.model_validate(raw))
        elif kind == "plot":
            parsed.append(AiBoardPlot.model_validate(raw))
        elif kind == "shape":
            parsed.append(AiBoardShape.model_validate(raw))
        elif kind == "diagram":
            parsed.append(AiBoardDiagram.model_validate(raw))
        else:
            raise ValueError(f"Unknown board item kind: {kind!r}")
    return parsed


def _item_dump(item: AiBoardItem) -> dict[str, Any]:
    return item.model_dump()


def _contains_all(haystack: str, terms: list[str]) -> bool:
    lowered = haystack.lower()
    return all(term.lower() in lowered for term in terms)


def _matches_item_spec(item: AiBoardItem, spec: ExpectedItemSpec) -> bool:
    if item.kind != spec.kind:
        return False
    if spec.id is not None and item.id != spec.id:
        return False
    if spec.id_prefix is not None and not item.id.startswith(spec.id_prefix):
        return False
    if isinstance(item, AiBoardText):
        return _contains_all(item.markdown, spec.markdown_contains)
    if isinstance(item, AiBoardPlot):
        blob = f"{item.expression} {item.label or ''}"
        return _contains_all(blob, spec.expression_contains)
    if isinstance(item, AiBoardDiagram):
        blob = f"{item.source} {item.label or ''}"
        return _contains_all(blob, spec.source_contains)
    if isinstance(item, AiBoardShape):
        return _contains_all(item.svg, spec.svg_contains)
    return False


def _score_grouping_action(
    *,
    action: Literal["append", "create"],
    current_items: list[AiBoardItem],
    actual_items: list[AiBoardItem],
    reuse_id: str | None,
    failures: list[str],
) -> None:
    current_ids = {item.id for item in current_items}
    actual_ids = {item.id for item in actual_items}

    if action == "append":
        new_ids = actual_ids - current_ids
        if new_ids:
            failures.append(
                "grouping append expected an update to an existing card, "
                f"but new id(s) were minted: {sorted(new_ids)}"
            )
        if reuse_id is not None and reuse_id not in actual_ids:
            failures.append(f"grouping append expected reused id {reuse_id!r}")
        return

    reused_ids = actual_ids & current_ids
    if reused_ids:
        failures.append(
            "grouping create expected a fresh card, "
            f"but existing id(s) were reused: {sorted(reused_ids)}"
        )
    if not actual_ids:
        failures.append("grouping create expected at least one new item id")


def score_extractor_case(
    case: TutorBoardGoldenCase,
    actual_items: list[AiBoardItem],
    *,
    current_items: list[AiBoardItem] | None = None,
) -> CaseScore:
    assert case.expected_extractor is not None
    expected = case.expected_extractor
    failures: list[str] = []
    count = len(actual_items)
    board_before = current_items if current_items is not None else []

    if expected.emit and count == 0:
        failures.append("expected tutor board emit but got no items")
    if not expected.emit and count > 0:
        failures.append(f"expected no emit but got {count} item(s)")

    if count < expected.min_items:
        failures.append(f"item count {count} < min_items {expected.min_items}")
    if expected.max_items is not None and count > expected.max_items:
        failures.append(f"item count {count} > max_items {expected.max_items}")

    actual_kinds = [item.kind for item in actual_items]
    if expected.kinds and actual_kinds and any(kind not in expected.kinds for kind in actual_kinds):
        failures.append(f"unexpected kinds {actual_kinds}; allowed={expected.kinds}")
    for forbidden in expected.forbidden_kinds:
        if forbidden in actual_kinds:
            failures.append(f"forbidden kind emitted: {forbidden}")

    if expected.reuse_id is not None:
        if expected.reuse_id not in {item.id for item in actual_items}:
            failures.append(f"expected reused id {expected.reuse_id!r}")

    actual_ids = {item.id for item in actual_items}
    for forbidden_id in expected.forbidden_ids:
        if forbidden_id in actual_ids:
            failures.append(f"forbidden id emitted: {forbidden_id!r}")

    if expected.grouping_action is not None:
        _score_grouping_action(
            action=expected.grouping_action,
            current_items=board_before,
            actual_items=actual_items,
            reuse_id=expected.reuse_id,
            failures=failures,
        )

    for index, spec in enumerate(expected.items):
        if not any(_matches_item_spec(item, spec) for item in actual_items):
            failures.append(f"no actual item matched expected.items[{index}]")

    return CaseScore(
        case_id=case.id,
        axis=case.axis,
        passed=not failures,
        failures=tuple(failures),
        actual_items=tuple(_item_dump(item) for item in actual_items),
    )


def _utterance_references_board(utterance: str, patterns: list[str]) -> bool:
    source = utterance.lower()
    compiled = patterns or list(_BOARD_REFERENCE_PATTERNS)
    return any(re.search(pattern, source, re.I) for pattern in compiled)


def score_reference_case(case: TutorBoardGoldenCase) -> CaseScore:
    assert case.expected_reference is not None
    assert case.tutor_utterance is not None
    expected = case.expected_reference
    utterance = case.tutor_utterance
    failures: list[str] = []

    references = _utterance_references_board(
        utterance,
        expected.reference_patterns,
    )
    if expected.references_board and not references:
        failures.append("expected tutor to reference the board but no reference pattern matched")
    if not expected.references_board and references:
        failures.append("expected tutor not to reference the board but a reference pattern matched")

    for term in expected.utterance_contains:
        if term.lower() not in utterance.lower():
            failures.append(f"utterance missing required phrase: {term!r}")
    for term in expected.utterance_not_contains:
        if term.lower() in utterance.lower():
            failures.append(f"utterance contains forbidden phrase: {term!r}")

    return CaseScore(
        case_id=case.id,
        axis=case.axis,
        passed=not failures,
        failures=tuple(failures),
        tutor_utterance=utterance,
    )


async def evaluate_extractor_cases(
    cases: list[TutorBoardGoldenCase],
    *,
    extractor: Any,
) -> list[CaseScore]:
    scores: list[CaseScore] = []
    for case in cases:
        assert case.extractor is not None
        current = parse_board_items(case.extractor.current_items)
        actual = await extractor.extract(
            sentence=case.extractor.sentence,
            current_items=current,
            last_sentence=case.extractor.last_sentence,
        )
        scores.append(score_extractor_case(case, actual, current_items=current))
    return scores


def evaluate_reference_cases(cases: list[TutorBoardGoldenCase]) -> list[CaseScore]:
    return [score_reference_case(case) for case in cases]


async def evaluate_tutor_board_cases(
    cases: list[TutorBoardGoldenCase],
    *,
    extractor: Any | None,
) -> TutorBoardEvalReport:
    extractor_cases = [case for case in cases if case.axis != "reference"]
    reference_cases = [case for case in cases if case.axis == "reference"]

    scores: list[CaseScore] = []
    if extractor_cases:
        if extractor is None:
            raise ValueError(
                "extractor is required for usage/content/card_kind/grouping cases"
            )
        scores.extend(await evaluate_extractor_cases(extractor_cases, extractor=extractor))
    scores.extend(evaluate_reference_cases(reference_cases))

    by_id = {score.case_id: score for score in scores}
    ordered = tuple(by_id[case.id] for case in cases)
    return TutorBoardEvalReport(
        golden_path="",
        extractor_model=getattr(extractor, "_model", None),
        cases=ordered,
    )


def report_to_dict(
    report: TutorBoardEvalReport,
    *,
    golden_path: str,
    created_at: str = "",
    descriptions: dict[str, str] | None = None,
    target_id: str = "baseline",
    label: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    desc = descriptions or {}
    resolved_label = label or target_id
    return {
        "schema_version": 1,
        "comparison_axis": "tutor_board",
        "target_id": target_id,
        "label": resolved_label,
        "metadata": metadata or {},
        "created_at": created_at,
        "golden_path": golden_path,
        "extractor_model": report.extractor_model,
        "pass_rate": report.pass_rate,
        "axis_summaries": [
            {
                "axis": summary.axis,
                "total": summary.total,
                "passed": summary.passed,
                "pass_rate": summary.pass_rate,
            }
            for summary in report.axis_summaries()
        ],
        "cases": [
            {
                "case_id": case.case_id,
                "axis": case.axis,
                "description": desc.get(case.case_id, ""),
                "passed": case.passed,
                "failures": list(case.failures),
                "actual_items": list(case.actual_items),
                "tutor_utterance": case.tutor_utterance,
            }
            for case in report.cases
        ],
        "failures": [
            {
                "case_id": case.case_id,
                "axis": case.axis,
                "description": desc.get(case.case_id, ""),
                "failures": list(case.failures),
            }
            for case in report.cases
            if not case.passed
        ],
    }


def render_markdown_report(report: TutorBoardEvalReport, *, golden_path: str) -> str:
    passed_count = sum(1 for case in report.cases if case.passed)
    lines = [
        "# Tutor Board Evaluation",
        "",
        f"- Golden set: `{golden_path}`",
        f"- Extractor model: `{report.extractor_model or 'n/a'}`",
        (
            f"- Overall pass rate: **{report.pass_rate:.1%}** "
            f"({passed_count}/{len(report.cases)})"
        ),
        "",
        "## Axis Summary",
        "",
        "| Axis | Passed | Total | Pass rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for summary in report.axis_summaries():
        lines.append(
            f"| {summary.axis} | {summary.passed} | {summary.total} | {summary.pass_rate:.1%} |"
        )

    lines.extend(["", "## Failures", ""])
    failed = [case for case in report.cases if not case.passed]
    if not failed:
        lines.append("_No failures._")
    else:
        for case in failed:
            lines.append(f"### {case.case_id} ({case.axis})")
            for failure in case.failures:
                lines.append(f"- {failure}")
            if case.actual_items:
                dumped = json.dumps(list(case.actual_items), ensure_ascii=False)
                lines.append(f"- actual_items: `{dumped}`")
            if case.tutor_utterance:
                lines.append(f"- tutor_utterance: {case.tutor_utterance!r}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
