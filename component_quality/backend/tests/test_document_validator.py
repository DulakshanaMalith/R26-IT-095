import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.document_validator import detect_sections, validate_proposal_document


def detected_sections_for(text: str) -> list[str]:
    return detect_sections(text.lower())


def test_abstract_newline_body_detected():
    assert "abstract" in detected_sections_for("Abstract\nThis research investigates proposal quality.")


def test_flattened_abstract_body_detected():
    assert "abstract" in detected_sections_for("Abstract This research investigates proposal quality.")


def test_flattened_abstract_body_starting_with_there_detected():
    assert "abstract" in detected_sections_for("ABSTRACT There are two foundational challenges in proposal quality.")
    assert "abstract" in detected_sections_for("Abstract There is a lack of structured assessment.")


def test_flattened_required_section_headings_detected_generically():
    cases = {
        "introduction": "Introduction This study explains the research context.",
        "methodology": "Methodology The proposed method uses document analysis.",
        "objectives": "Objectives The objectives are to evaluate proposal completeness.",
        "literature_review": "Literature Review Previous studies discuss academic writing.",
        "research_gap": "Research Gap Existing systems miss flattened headings.",
        "evaluation": "Evaluation The evaluation measures detection accuracy.",
    }

    for section, text in cases.items():
        assert section in detected_sections_for(text)


def test_pdf_page_marker_before_abstract_detected():
    assert "abstract" in detected_sections_for("4 | P a g e  ABSTRACT  This paper addresses proposal quality.")


def test_pdf_page_marker_word_before_abstract_detected():
    assert "abstract" in detected_sections_for("4 | Page ABSTRACT This paper addresses proposal quality.")


def test_pdf_page_marker_without_pipe_before_abstract_detected():
    assert "abstract" in detected_sections_for("4 Page ABSTRACT This paper addresses proposal quality.")


def test_pdf_page_marker_before_other_sections_detected():
    assert "methodology" in detected_sections_for("12 | P a g e METHODOLOGY This study uses document analysis.")


def test_numbered_abstract_detected():
    assert "abstract" in detected_sections_for("1. ABSTRACT\nThis research investigates proposal quality.")
    assert "abstract" in detected_sections_for("1 ABSTRACT\nThis research investigates proposal quality.")


def test_colon_abstract_detected():
    assert "abstract" in detected_sections_for("ABSTRACT: This research investigates proposal quality.")


def test_flattened_abstract_detected_when_other_sections_are_present():
    text = (
        "Abstract This research investigates proposal quality. "
        "Introduction This study explains the research context. "
        "Objectives The objectives are to evaluate proposal completeness. "
        "Methodology The proposed method uses document analysis. "
        "Literature Review Previous studies discuss academic writing. "
        "Research Gap Existing systems miss flattened headings. "
        "Evaluation The evaluation measures detection accuracy."
    )

    result = validate_proposal_document(text)

    assert "abstract" in result.detected_sections
    assert "abstract" not in result.missing_sections


def test_flattened_there_abstract_detected_when_other_sections_are_present():
    text = (
        "Abstract There are two foundational challenges in proposal quality. "
        "Introduction This study explains the research context. "
        "Objectives The objectives are to evaluate proposal completeness. "
        "Methodology The proposed method uses document analysis. "
        "Literature Review Previous studies discuss academic writing. "
        "Research Gap Existing systems miss flattened headings. "
        "Evaluation The evaluation measures detection accuracy."
    )

    result = validate_proposal_document(text)

    assert "abstract" in result.detected_sections
    assert "abstract" not in result.missing_sections


def test_abstract_in_normal_prose_is_not_detected_as_section():
    text = "This paragraph discusses the abstract concept of fairness in research evaluation."

    assert "abstract" not in detected_sections_for(text)


def test_abstract_in_additional_normal_prose_is_not_detected_as_section():
    assert "abstract" not in detected_sections_for("We describe an abstract representation of the system.")
    assert "abstract" not in detected_sections_for("Previous studies discuss abstract reasoning.")


def test_methodology_in_normal_prose_is_not_detected_as_section():
    text = "We discuss the methodology used by previous researchers."

    assert "methodology" not in detected_sections_for(text)


def test_real_extracted_pdf_page_marker_structure_detects_abstract():
    text = (
        "... Co-Supervisor\n\n"
        "4 | P a g e  ABSTRACT  This paper addresses a hard problem in contemporary educational institutions..."
    )

    assert "abstract" in detected_sections_for(text)


def test_representative_proposal_with_page_marker_abstract_not_missing_abstract():
    text = (
        "4 | P a g e  ABSTRACT  This paper addresses a hard problem in contemporary educational institutions. "
        "This research study proposes an automated assessment framework with useful feedback. "
        "Introduction This study explains the research context and proposal background with academic evidence. "
        "Objectives The objectives are to evaluate proposal completeness and determine assessment quality. "
        "Research Gap Existing systems lack structured adaptive feedback and clear research guidance. "
        "Methodology This study uses document analysis, survey data, and evaluation procedures. "
        "Literature Review Previous studies provide evidence, framework concepts, and references. "
        "Evaluation The evaluation measures accuracy, validation metrics, and supervisor review outcomes. "
        "References Smith et al. describe related research methods and educational assessment."
    )

    result = validate_proposal_document(text)

    assert "abstract" in result.detected_sections
    assert "abstract" not in result.missing_sections
