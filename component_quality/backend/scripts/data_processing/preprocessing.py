"""Preprocess the Exposia dataset for automated quality assessment research.

The script reads expose submissions, cleans draft/final LaTeX text, extracts
scores, annotations, and comments, then writes modeling-friendly CSV files to
the processed/ directory.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
EXPOSES_DIR = ROOT_DIR / "exposes"
PROCESSED_DIR = ROOT_DIR / "processed"


def read_json(path: Path, default: Any) -> Any:
    """Read JSON from path, returning default when the file is absent or invalid."""
    if not path.exists():
        print(f"Warning: missing JSON file: {path}")
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        print(f"Warning: invalid JSON in {path}: {exc}")
        return default
    except OSError as exc:
        print(f"Warning: could not read {path}: {exc}")
        return default


def read_text_file(path: Path) -> str:
    """Read a text file with a small encoding fallback."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
    except OSError as exc:
        print(f"Warning: could not read {path}: {exc}")
        return ""


def find_latex_file(folder: Path) -> Path | None:
    """Return the main LaTeX file in a submission folder."""
    if not folder.exists():
        print(f"Warning: missing folder: {folder}")
        return None

    preferred = folder / "Expose.tex"
    if preferred.exists():
        return preferred

    tex_files = sorted(
        path
        for path in folder.glob("*.tex")
        if not path.name.lower().endswith((".cfg.tex",))
    )
    if not tex_files:
        print(f"Warning: no LaTeX file found in {folder}")
        return None

    return tex_files[0]


def strip_latex_comments(text: str) -> str:
    """Remove unescaped LaTeX comments while keeping escaped percent signs."""
    cleaned_lines = []
    for line in text.splitlines():
        match = re.search(r"(?<!\\)%", line)
        if match:
            line = line[: match.start()]
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def keep_document_body(text: str) -> str:
    """Keep content between begin/end document when present."""
    begin_match = re.search(r"\\begin\{document\}", text)
    if begin_match:
        text = text[begin_match.end() :]

    end_match = re.search(r"\\end\{document\}", text)
    if end_match:
        text = text[: end_match.start()]

    return text


def clean_latex(raw_text: str) -> str:
    """Convert LaTeX source into plain text suitable for NLP preprocessing."""
    text = strip_latex_comments(raw_text)
    text = keep_document_body(text)

    # Drop environments that generally do not contain prose for assessment.
    text = re.sub(
        r"\\begin\{(?:figure|table|equation|align|lstlisting|verbatim)\*?\}.*?"
        r"\\end\{(?:figure|table|equation|align|lstlisting|verbatim)\*?\}",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove citations, references, URLs, bibliography commands, and includes.
    text = re.sub(r"\\(?:cite|parencite|textcite|autocite|footcite)\*?(?:\[[^\]]*\])*\{[^{}]*\}", " ", text)
    text = re.sub(r"\\(?:ref|autoref|cref|Cref|pageref|label)\*?(?:\[[^\]]*\])*\{[^{}]*\}", " ", text)
    text = re.sub(r"\\(?:url|href)\{[^{}]*\}(?:\{([^{}]*)\})?", r"\1", text)
    text = re.sub(r"\\(?:printbibliography|bibliography|addbibresource)\*?(?:\[[^\]]*\])?\{?[^{}\n]*\}?", " ", text)
    text = re.sub(r"\\(?:input|include)\{[^{}]*\}", " ", text)

    # Preserve section titles and emphasized text while removing command syntax.
    text = re.sub(
        r"\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?"
        r"(?:\[[^\]]*\])?\{([^{}]*)\}",
        r" \1. ",
        text,
    )
    text = re.sub(
        r"\\(?:textbf|textit|emph|underline|enquote|title|author|date)\{([^{}]*)\}",
        r"\1",
        text,
    )

    # Handle common escaped characters and remove remaining commands/braces.
    replacements = {
        r"\&": "&",
        r"\%": "%",
        r"\$": "$",
        r"\#": "#",
        r"\_": "_",
        r"\{": "{",
        r"\}": "}",
        r"~": " ",
        r"``": '"',
        r"''": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"\\.", " ", text)
    text = re.sub(r"[{}]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def load_submission_text(author_dir: Path, submission_type: str) -> str:
    """Load and clean a draft or final LaTeX submission."""
    tex_file = find_latex_file(author_dir / submission_type)
    if tex_file is None:
        return ""
    return clean_latex(read_text_file(tex_file))


def json_for_csv(value: Any) -> str:
    """Serialize nested values for storage in one CSV cell."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def score_total(score_record: dict[str, Any]) -> Any:
    """Extract total score from a score record."""
    scores = score_record.get("scores", {})
    if isinstance(scores, dict):
        return scores.get("total", "")
    return ""


def build_datasets() -> dict[str, int]:
    """Build all requested CSV datasets and return summary statistics."""
    PROCESSED_DIR.mkdir(exist_ok=True)

    reports_rows: list[dict[str, Any]] = []
    annotation_rows: list[dict[str, Any]] = []
    comment_rows: list[dict[str, Any]] = []
    grading_rows: list[dict[str, Any]] = []

    expose_dirs = sorted(path for path in EXPOSES_DIR.iterdir() if path.is_dir()) if EXPOSES_DIR.exists() else []
    if not expose_dirs:
        print(f"Warning: no expose folders found in {EXPOSES_DIR}")

    for author_dir in expose_dirs:
        meta = read_json(author_dir / "meta.json", {})
        author = meta.get("author") or author_dir.name
        topic = meta.get("topic", "")

        draft_text = load_submission_text(author_dir, "draft")
        final_text = load_submission_text(author_dir, "final")

        scores = read_json(author_dir / "scores.json", [])
        if not isinstance(scores, list):
            print(f"Warning: expected list in {author_dir / 'scores.json'}")
            scores = []

        draft_scores = [record for record in scores if record.get("type") == "draft"]
        final_scores = [record for record in scores if record.get("type") == "final"]

        reports_rows.append(
            {
                "author": author,
                "topic": topic,
                "draft_text": draft_text,
                "final_text": final_text,
                "draft_scores": json_for_csv(draft_scores),
                "final_scores": json_for_csv(final_scores),
            }
        )

        for score_record in scores:
            submission_type = score_record.get("type", "")
            if submission_type not in {"draft", "final"}:
                continue

            grading_rows.append(
                {
                    "author": author,
                    "submission_type": submission_type,
                    "text": draft_text if submission_type == "draft" else final_text,
                    "criteria_json": json_for_csv(score_record.get("criteria", {})),
                    "total_score": score_total(score_record),
                }
            )

        annotations = read_json(author_dir / "annotations.json", [])
        if not isinstance(annotations, list):
            print(f"Warning: expected list in {author_dir / 'annotations.json'}")
            annotations = []

        for annotation in annotations:
            annotation_rows.append(
                {
                    "author": author,
                    "annotation_id": annotation.get("id", ""),
                    "review": annotation.get("review", ""),
                    "role": annotation.get("role", ""),
                    "tag": annotation.get("tag", ""),
                    "annotated_text": annotation.get("text", ""),
                }
            )

        comments = read_json(author_dir / "comments.json", [])
        if not isinstance(comments, list):
            print(f"Warning: expected list in {author_dir / 'comments.json'}")
            comments = []

        for comment in comments:
            comment_rows.append(
                {
                    "author": author,
                    "comment_id": comment.get("id", ""),
                    "annotation_id": comment.get("annotationId", ""),
                    "review": comment.get("review", ""),
                    "role": comment.get("role", ""),
                    "comment_text": comment.get("text", ""),
                    "tags": json_for_csv(comment.get("tags", [])),
                }
            )

    write_csv(
        PROCESSED_DIR / "exposia_reports.csv",
        ["author", "topic", "draft_text", "final_text", "draft_scores", "final_scores"],
        reports_rows,
    )
    write_csv(
        PROCESSED_DIR / "exposia_annotations.csv",
        ["author", "annotation_id", "review", "role", "tag", "annotated_text"],
        annotation_rows,
    )
    write_csv(
        PROCESSED_DIR / "exposia_comments.csv",
        ["author", "comment_id", "annotation_id", "review", "role", "comment_text", "tags"],
        comment_rows,
    )
    write_csv(
        PROCESSED_DIR / "exposia_grading_dataset.csv",
        ["author", "submission_type", "text", "criteria_json", "total_score"],
        grading_rows,
    )

    return {
        "number of exposes": len(reports_rows),
        "number of draft texts": sum(1 for row in reports_rows if row["draft_text"]),
        "number of final texts": sum(1 for row in reports_rows if row["final_text"]),
        "number of annotations": len(annotation_rows),
        "number of comments": len(comment_rows),
        "number of grading records": len(grading_rows),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """Write rows to CSV using UTF-8 for multilingual text."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    stats = build_datasets()

    print("\nDataset statistics")
    print("------------------")
    for label, value in stats.items():
        print(f"{label}: {value}")


if __name__ == "__main__":
    main()
