"""Text cleaning and normalization utilities."""

import re
from pathlib import Path
from .io import read_text_file

def find_latex_file(folder: Path) -> Path | None:
    """Return the main LaTeX file in a submission folder."""
    if not folder.exists():
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
