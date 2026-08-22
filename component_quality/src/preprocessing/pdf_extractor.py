import fitz


def extract_text_from_pdf(file_path: str) -> str:
    text = []
    doc = fitz.open(file_path)

    for page in doc:
        text.append(page.get_text())

    doc.close()
    return "\n".join(text)