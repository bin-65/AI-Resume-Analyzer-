"""Minimal, source-preserving DOCX edits for the resume analyzer."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from typing import Iterable

from docx import Document
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph


class ResumeUpdateError(Exception):
    """Raised when a source-preserving update cannot be made safely."""


SKILLS_HEADINGS = {"skills", "technical skills", "core skills", "key skills", "competencies"}


def _paragraphs_in_cell(cell: _Cell) -> Iterable[Paragraph]:
    for paragraph in cell.paragraphs:
        yield paragraph
    for table in cell.tables:
        yield from _paragraphs_in_table(table)


def _paragraphs_in_table(table: Table) -> Iterable[Paragraph]:
    for row in table.rows:
        for cell in row.cells:
            yield from _paragraphs_in_cell(cell)


def _all_paragraphs(document: Document) -> list[Paragraph]:
    paragraphs = list(document.paragraphs)
    for table in document.tables:
        paragraphs.extend(_paragraphs_in_table(table))
    for section in document.sections:
        paragraphs.extend(section.header.paragraphs + section.footer.paragraphs)
    return paragraphs


def _normalise(value: str) -> str:
    return " ".join(value.lower().replace(":", " ").split())


def _find_skills_paragraph(paragraphs: list[Paragraph]) -> Paragraph | None:
    """Find a paragraph containing the existing inline skills list."""
    for index, paragraph in enumerate(paragraphs):
        text = _normalise(paragraph.text)
        if any(text.startswith(f"{heading} ") for heading in SKILLS_HEADINGS):
            return paragraph
        if text in SKILLS_HEADINGS:
            for candidate in paragraphs[index + 1 :]:
                if candidate.text.strip():
                    return candidate
    return None


def _copy_run_style(source_run, new_run) -> None:
    """Match the existing paragraph style when appending new text."""
    if source_run is not None and source_run._r.rPr is not None:
        new_run._r.insert(0, deepcopy(source_run._r.rPr))


def _unique_new_skills(skills: Iterable[str], paragraph_text: str) -> list[str]:
    existing = _normalise(paragraph_text)
    result: list[str] = []
    for skill in skills:
        clean = str(skill).strip()
        if clean and _normalise(clean) not in existing and clean not in result:
            result.append(clean)
    return result


def update_docx_resume(source_bytes: bytes, skills_to_add: Iterable[str]) -> bytes:
    """Append supported skills without rebuilding or removing original CV content.

    Existing paragraphs, images, fonts, colors, page size, headers, footers, and
    sections are preserved. The only edit is an append to the existing Skills list.
    """
    try:
        document = Document(BytesIO(source_bytes))
    except Exception as error:
        raise ResumeUpdateError("The source DOCX could not be opened.") from error

    skills_paragraph = _find_skills_paragraph(_all_paragraphs(document))
    if skills_paragraph is None:
        raise ResumeUpdateError(
            "A Skills section was not found, so the original resume was not changed."
        )

    additions = _unique_new_skills(skills_to_add, skills_paragraph.text)
    if additions:
        separator = ", " if skills_paragraph.text.strip() else ""
        previous_run = skills_paragraph.runs[-1] if skills_paragraph.runs else None
        run = skills_paragraph.add_run(separator + ", ".join(additions))
        _copy_run_style(previous_run, run)

    output = BytesIO()
    document.save(output)
    return output.getvalue()
