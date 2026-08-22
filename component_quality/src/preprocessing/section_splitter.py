import re


SECTION_PATTERNS = {
    "introduction": r"(1\.?\s*introduction.*?)(?=1\.1|2\.|2\s|objectives|\Z)",
    "literature_review": r"(literature review.*?)(?=research gap|2\.|3\.|\Z)",
    "research_gap": r"(research gap.*?)(?=2\. objectives|3\. methodology|3\.|\Z)",
    "objectives": r"(2\.?\s*objectives.*?)(?=3\.|\Z)",
    "methodology": r"(3\.?\s*methodology.*?)(?=4\.|\Z)",
    "references": r"(references.*?)(?=\Z)"
}


def split_sections(text: str) -> dict:
    original_text = text
    lower_text = text.lower()
    sections = {}

    for section_name, pattern in SECTION_PATTERNS.items():
        match = re.search(pattern, lower_text, re.DOTALL)
        if match:
            start, end = match.span()
            sections[section_name] = original_text[start:end].strip()
        else:
            sections[section_name] = ""

    return sections