"""Create a SLIIT-format thesis draft without changing the reviewed source DOCX.

The supplied PDF is the authority for A4 page geometry, type, spacing, chapter
titles, captions and pagination. Personal certification fields stay unsigned.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt
from docx.text.paragraph import Paragraph


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "IT22117014_Individual_Component_Dissertation_Submission_Candidate.docx"
OUTPUT = ROOT / "IT22117014_Individual_Thesis_SLIIT_Formatted_Draft.docx"


def find(doc: Document, text: str) -> Paragraph:
    matches = [p for p in doc.paragraphs if p.text == text]
    if len(matches) != 1:
        raise ValueError(f"Expected one paragraph {text!r}; found {len(matches)}")
    return matches[0]


def find_subheading(doc: Document, prefix: str) -> Paragraph:
    matches = [
        p for p in doc.paragraphs
        if p.style.name == "Heading 2" and p.text.startswith(prefix)
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one body subheading {prefix!r}; found {len(matches)}")
    return matches[0]


def remove(paragraph: Paragraph) -> None:
    paragraph._element.getparent().remove(paragraph._element)


def remove_empty_break_before(heading: Paragraph) -> None:
    previous = heading._p.getprevious()
    if previous is None or previous.tag != qn("w:p"):
        return
    paragraph = Paragraph(previous, heading._parent)
    if not paragraph.text.strip() and paragraph._p.xpath(".//w:br"):
        remove(paragraph)


def move_block_before(start: Paragraph, stop: Paragraph, target: Paragraph) -> None:
    """Move all document-body elements from start up to, not including, stop."""
    element = start._p
    while element is not stop._p:
        following = element.getnext()
        target._p.addprevious(element)
        element = following


def add_complex_field(paragraph: Paragraph, instruction: str) -> None:
    for kind, value in (("begin", None), (None, f" {instruction} "), ("separate", None), (None, "0"), ("end", None)):
        run = paragraph.add_run()
        if kind:
            child = OxmlElement("w:fldChar")
            child.set(qn("w:fldCharType"), kind)
        elif value == "0":
            child = OxmlElement("w:t")
            child.text = value
        else:
            child = OxmlElement("w:instrText")
            child.set(qn("xml:space"), "preserve")
            child.text = value
        run._r.append(child)


def bookmark(paragraph: Paragraph, name: str, bookmark_id: int) -> None:
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bookmark_id))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bookmark_id))
    paragraph._p.insert(1 if paragraph._p.pPr is not None else 0, start)
    paragraph._p.append(end)


def page_number(section, *, roman: bool, alignment) -> None:
    section.footer.is_linked_to_previous = False
    footer = section.footer.paragraphs[0]
    footer.clear()
    footer.alignment = alignment
    add_complex_field(footer, "PAGE")
    for run in footer.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
    for old in section._sectPr.xpath("./w:pgNumType"):
        section._sectPr.remove(old)
    setting = OxmlElement("w:pgNumType")
    setting.set(qn("w:fmt"), "lowerRoman" if roman else "decimal")
    setting.set(qn("w:start"), "1")
    section._sectPr.append(setting)


def title_case(title: str) -> str:
    preserve = {"IPMS", "PDF", "API", "WBS", "LPT", "Gantt", "GitHub", "XGBoost", "Jira", "T5", "NSGA-II", "PP1", "PP2", "Viva", "HMAC", "TF–IDF"}
    lowers = {"and", "or", "of", "the", "a", "an", "to", "in", "for", "with", "from", "on", "versus", "by"}
    result = []
    for index, word in enumerate(title.split()):
        raw = word.strip(".,:;()")
        if raw in preserve or raw.startswith("R26-"):
            result.append(word)
        elif raw.lower() in lowers and index:
            result.append(word.lower())
        else:
            result.append(word[:1].upper() + word[1:])
    return " ".join(result)


def set_heading(paragraph: Paragraph, number: str, title: str, level: int = 2) -> None:
    paragraph.text = f"{number} {title}" if level == 2 else f"{number} {title.upper()}"
    paragraph.style = f"Heading {level}"


def format_cover_and_preliminaries(doc: Document) -> None:
    find(doc, "INDIVIDUAL RESEARCH COMPONENT DISSERTATION").text = "INDIVIDUAL THESIS"
    title = find(doc, "Adaptive Scheduling and Generative Project Planning")
    title.text = "ADAPTIVE SCHEDULING AND GENERATIVE PROJECT PLANNING"
    identity = next(p for p in doc.paragraphs if p.text == "Lekamge R.L.M.D.\nIT22117014")
    identity.text = "Lekamge R.L.M.D.\n(IT22117014)"
    student_id = find(doc, "Student ID: IT22117014")
    for drawing in student_id._p.xpath(".//w:drawing"):
        drawing.getparent().remove(drawing)
    faculty = find(doc, "Faculty of Computing")
    faculty.text = "Department of Information Technology"
    faculty.insert_paragraph_before(
        "Dissertation submitted in partial fulfilment of the requirements for the",
        style="Normal",
    )
    faculty.insert_paragraph_before("BSc (Hons) in Information Technology", style="Normal")
    cover_end = next(p for p in doc.paragraphs if p._p.xpath("./w:pPr/w:sectPr"))
    for paragraph in list(doc.paragraphs):
        if paragraph.text == "" and paragraph._p.getparent() is not None:
            # Keep the two section-break paragraphs, which separate title,
            # preliminary Roman pagination and Arabic body pagination.
            if paragraph._p.xpath("./w:pPr/w:sectPr"):
                continue
            if paragraph._p.xpath(".//w:br"):
                continue
            if paragraph._p.getprevious() is not None and paragraph._p.getnext() is not None:
                # Empty title-page spacers are replaced by paragraph spacing.
                previous_text = "".join(paragraph._p.getprevious().itertext())
                if paragraph._p.getparent().index(paragraph._p) < paragraph._p.getparent().index(cover_end._p) and previous_text != "":
                    remove(paragraph)

    declaration = find(doc, "Declaration")
    declaration.text = "DECLARATION AND SUPERVISOR CERTIFICATION"
    ai = next(p for p in doc.paragraphs if p.text.startswith("Academic integrity and AI disclosure."))
    ai.text = "A draft AI-assistance disclosure is provided in Appendix B. The candidate must verify it against the module policy before signing this declaration."
    find(doc, "Signature: ______________________________     Date: _____10/10/2026_______").text = (
        "Candidate signature: __________________________     Date: __________________"
    )
    supervisor_table = doc.tables[0]
    supervisor_table.cell(1, 0).text = "Supervisor: [add official name]"
    supervisor_table.cell(2, 0).text = "Co-supervisor: [add official name]"
    for row in supervisor_table.rows[1:]:
        row.cells[1].text = "________________"
        row.cells[2].text = "__________"

    find(doc, "Abstract").text = "ABSTRACT"
    keyword = next(p for p in doc.paragraphs if p.text.startswith("Keywords:"))
    keyword.text = (
        "Keywords: proposal-driven scheduling; workload balancing; progress evidence; "
        "academic timetabling; XGBoost."
    )
    contents = find(doc, "Contents")
    remove_empty_break_before(contents)
    acknowledgements = contents.insert_paragraph_before("ACKNOWLEDGEMENTS", style="Heading 1")
    contents.insert_paragraph_before(
        "I thank my supervisor and co-supervisor for their academic guidance and feedback, "
        "and the members of the IPMS research group for coordinating the integration of "
        "our components. I acknowledge the researchers and dataset providers cited in the "
        "references. Before submission, I will confirm the names and specific assistance "
        "that should be acknowledged here, including any funding or substantial technical help.",
        style="Normal",
    )
    acknowledgements.paragraph_format.page_break_before = True
    contents.text = "TABLE OF CONTENTS"
    contents.paragraph_format.page_break_before = True

    list_figures = find(doc, "List of Figures and Tables")
    list_figures.text = "LIST OF FIGURES"
    list_abbreviations = find(doc, "List of Abbreviations")
    list_abbreviations.text = "LIST OF ABBREVIATIONS"
    remove_empty_break_before(list_abbreviations)
    element = list_figures._p.getnext()
    while element is not list_abbreviations._p:
        following = element.getnext()
        element.getparent().remove(element)
        element = following
    list_figures.paragraph_format.page_break_before = True
    list_abbreviations.paragraph_format.page_break_before = True


def restructure_chapters(doc: Document) -> None:
    set_heading(find(doc, "1. Introduction"), "1", "Introduction", 1)
    set_heading(find(doc, "2. Background and Related Work"), "2", "Literature Review and Related Work", 1)
    set_heading(find(doc, "3. Methodology"), "3", "Research Methodology", 1)
    set_heading(find(doc, "4. Implementation"), "4", "Product and Solution Design", 1)

    commerce = find(doc, "4.10 Practical use and commercialisation considerations")
    implementation_start = find(doc, "4.11 A proposal-to-task execution trace")
    original_conclusion = find(doc, "7. Conclusion and Future Work")
    move_block_before(commerce, implementation_start, original_conclusion)
    new_implementation = implementation_start.insert_paragraph_before(
        "5 IMPLEMENTATION, INTEGRATION AND TESTING", style="Heading 1"
    )
    new_implementation.paragraph_format.page_break_before = True
    for index, old in enumerate(range(11, 17), 1):
        paragraph = find_subheading(doc, f"4.{old} ")
        set_heading(paragraph, f"5.{index}", paragraph.text.split(" ", 1)[1])

    old_testing = find(doc, "5. Testing and Validation")
    results_heading = find(doc, "6. Results and Discussion")
    test_headings = []
    element = old_testing._p.getnext()
    while element is not results_heading._p:
        if element.tag == qn("w:p"):
            paragraph = Paragraph(element, old_testing._parent)
            if paragraph.style.name == "Heading 2":
                test_headings.append(paragraph)
        element = element.getnext()
    if len(test_headings) != 16:
        raise ValueError(f"Expected 16 testing subsections; found {len(test_headings)}")
    remove(old_testing)
    for old, paragraph in enumerate(test_headings, 1):
        set_heading(paragraph, f"5.{old + 6}", paragraph.text.split(" ", 1)[1])

    set_heading(find(doc, "6. Results and Discussion"), "6", "Results and Validation", 1)
    discussion_start = find(doc, "6.4 Interpreting the workload classifier")
    discussion_start.insert_paragraph_before("7 DISCUSSION", style="Heading 1")
    for old in range(4, 13):
        paragraph = find_subheading(doc, f"6.{old} ")
        set_heading(paragraph, f"7.{old - 3}", paragraph.text.split(" ", 1)[1])

    commerce.text = "8 COMMERCIALISATION AND SUSTAINABILITY"
    commerce.style = "Heading 1"
    value = next(p for p in doc.paragraphs if p.text.startswith("The immediate target environment"))
    value.insert_paragraph_before("8.1 Value proposition and target users", style="Heading 2")
    adoption = next(p for p in doc.paragraphs if p.text.startswith("A phased adoption path"))
    adoption.insert_paragraph_before("8.2 Adoption and evaluation path", style="Heading 2")
    original_conclusion.insert_paragraph_before(
        "8.3 Data rights, governance and sustainability", style="Heading 2"
    )
    original_conclusion.insert_paragraph_before(
        "The local Sourcetree export, Apache-project summary and Desharnais copy need their "
        "acquisition records and reuse terms checked before raw-data redistribution. The "
        "China subset matches a published Zenodo record, but matching content is not by "
        "itself a licence grant. Any institutional pilot would also need stable hosting, "
        "backups, access logs, student identity, consent and a retention policy. The project "
        "may align with SDG 4 by supporting educational project supervision, but educational "
        "impact has not been measured.", style="Normal"
    )
    commerce.insert_paragraph_before(
        "7.10 Summary of individual contribution", style="Heading 2"
    )
    commerce.insert_paragraph_before(
        "The component-level artefacts cover proposal-linked task extraction, versioned "
        "scheduling with live LPT assignment, document and GitHub evidence review, and "
        "academic-event planning. The student's exact personal implementation, evaluation, "
        "writing and integration responsibilities within the shared IPMS project must be "
        "confirmed against the team's approved contribution statement before this section "
        "is treated as a formal individual-authorship claim.", style="Normal"
    )
    set_heading(original_conclusion, "9", "Conclusion and Future Directions", 1)
    for old, original in ((1, "7.1 Summary of achieved objectives"),
                          (2, "7.2 Limitations and next research steps")):
        paragraph = find(doc, original)
        set_heading(paragraph, f"9.{old}", paragraph.text.split(" ", 1)[1])

    find(doc, "References").text = "REFERENCES"
    find(doc, "Appendix A. Evidence and Code Map").text = "APPENDIX A: EVIDENCE AND CODE MAP"
    appendix_b = doc.add_heading("APPENDIX B: ACADEMIC INTEGRITY AND AI-USE DISCLOSURE", level=1)
    appendix_b.paragraph_format.page_break_before = True
    doc.add_paragraph(
        "Draft disclosure for author review: OpenAI Codex assisted with drafting and editing "
        "parts of the dissertation, reorganising and formatting the document to the supplied "
        "SLIIT template, checking source-code claims, and comparing local dataset contents "
        "with public records. These tools were not a source of experimental observations. "
        "The author must verify all numerical results, citations, code descriptions and "
        "attributions, and add any other AI tools, prompts or affected sections required by "
        "the module's academic-integrity policy before signing the declaration."
    )


def caption_and_list(doc: Document) -> None:
    if "Thesis List Entry" not in doc.styles:
        doc.styles.add_style("Thesis List Entry", WD_STYLE_TYPE.PARAGRAPH)
    figure_numbers = {1: "3.1", 2: "3.2", 3: "6.1", 4: "7.1"}
    table_numbers = {1: "1.1", 2: "2.1", 3: "3.1", 4: "3.2", 5: "3.3", 6: "3.4", 7: "4.1", 8: "4.2", 9: "5.1", 10: "5.2", 11: "6.1", 12: "6.2", 13: "7.1"}
    figures = []
    tables = []
    serial = 100
    for paragraph in list(doc.paragraphs):
        match = re.match(r"^(Figure|Table) (\d+)\.\s*(.*)$", paragraph.text)
        if paragraph.style.name != "Caption" or match is None:
            continue
        kind, old_number, description = match.groups()
        new_number = (figure_numbers if kind == "Figure" else table_numbers)[int(old_number)]
        paragraph.text = f"{kind} {new_number}. {description}"
        key = f"bm_{kind.lower()}_{new_number.replace('.', '_')}"
        bookmark(paragraph, key, serial)
        serial += 1
        (figures if kind == "Figure" else tables).append((paragraph.text, key))
        if kind == "Table":
            previous = paragraph._p.getprevious()
            while previous is not None and previous.tag == qn("w:p") and not "".join(previous.itertext()).strip():
                previous = previous.getprevious()
            if previous is None or previous.tag != qn("w:tbl"):
                raise ValueError(f"Could not find table for {paragraph.text}")
            previous.addprevious(paragraph._p)
            note = paragraph.insert_paragraph_before(
                f"Table {new_number} presents {description.rstrip('.').lower()}.", style="Normal"
            )
            note.paragraph_format.keep_with_next = True
        else:
            previous = paragraph._p.getprevious()
            drawing = None
            for _ in range(6):
                if previous is None:
                    break
                if previous.tag == qn("w:p") and previous.xpath(".//w:drawing"):
                    drawing = previous
                    break
                previous = previous.getprevious()
            if drawing is None:
                raise ValueError(f"Could not find drawing for {paragraph.text}")
            drawing_paragraph = Paragraph(drawing, paragraph._parent)
            note = drawing_paragraph.insert_paragraph_before(
                f"Figure {new_number} shows {description.rstrip('.').lower()}.", style="Normal"
            )
            note.paragraph_format.keep_with_next = True

    # The appendix evidence map is a genuine table too, but is not a numbered
    # research-result table; chapter-prefixed appendix numbering distinguishes it.
    evidence = doc.tables[-1]._tbl
    caption_element = OxmlElement("w:p")
    evidence.addprevious(caption_element)
    appendix_caption = Paragraph(caption_element, doc._body)
    appendix_caption.style = "Caption"
    appendix_caption.text = "Table A.1. Evidence and code map."
    bookmark(appendix_caption, "bm_table_A_1", serial)
    tables.append((appendix_caption.text, "bm_table_A_1"))
    intro = next(p for p in doc.paragraphs if p.text.startswith("The following project-local files substantiate"))
    intro.add_run(" Table A.1 maps each evidence type to its project-local file.")

    list_abbreviations = find(doc, "LIST OF ABBREVIATIONS")
    table_list_heading = None
    for kind, entries in (("Figure", figures), ("Table", tables)):
        if kind == "Table":
            table_list_heading = list_abbreviations.insert_paragraph_before("LIST OF TABLES", style="Heading 1")
            table_list_heading.paragraph_format.page_break_before = True
        for label, key in entries:
            paragraph = list_abbreviations.insert_paragraph_before(style="Normal")
            paragraph.add_run(label)
            paragraph.add_run("\t")
            add_complex_field(paragraph, f"PAGEREF {key} \\h")
            paragraph.style = "Thesis List Entry"


def format_document(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)
    for name, size in (("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 12)):
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.paragraph_format.line_spacing = 1.0
        style.paragraph_format.space_before = Pt(12 if name == "Heading 1" else 10)
        style.paragraph_format.space_after = Pt(10 if name == "Heading 1" else 6)
        style.paragraph_format.keep_with_next = True
    caption = doc.styles["Caption"]
    caption.font.name = "Times New Roman"
    caption.font.size = Pt(10.5)
    caption.paragraph_format.line_spacing = 1.0
    caption.paragraph_format.space_after = Pt(6)
    caption.paragraph_format.keep_with_next = True
    if "Thesis List Entry" not in doc.styles:
        listing = doc.styles.add_style("Thesis List Entry", WD_STYLE_TYPE.PARAGRAPH)
    else:
        listing = doc.styles["Thesis List Entry"]
    listing.base_style = normal
    listing.font.name = "Times New Roman"
    listing.font.size = Pt(11)
    listing.paragraph_format.line_spacing = 1.0
    listing.paragraph_format.space_after = Pt(1)
    listing.paragraph_format.tab_stops.add_tab_stop(
        Inches(5.55), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
    )
    for style_name in ("toc 1", "toc 2", "TOC 1", "TOC 2"):
        if style_name in doc.styles:
            style = doc.styles[style_name]
            style.font.name = "Times New Roman"
            style.font.size = Pt(9.5)
            style.paragraph_format.line_spacing = 1.0
            style.paragraph_format.space_after = Pt(0)

    for section in doc.sections:
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.left_margin = Mm(40)
        section.right_margin = Mm(25)
        section.top_margin = Mm(25)
        section.bottom_margin = Mm(40)
        section.header_distance = Mm(12.5)
        section.footer_distance = Mm(15)
        section.header.is_linked_to_previous = False
        section.header.paragraphs[0].clear()
    doc.sections[0].footer.is_linked_to_previous = False
    doc.sections[0].footer.paragraphs[0].clear()
    page_number(doc.sections[1], roman=True, alignment=WD_ALIGN_PARAGRAPH.CENTER)
    page_number(doc.sections[2], roman=False, alignment=WD_ALIGN_PARAGRAPH.RIGHT)

    cover_end = next(p for p in doc.paragraphs if p._p.xpath("./w:pPr/w:sectPr"))
    body_start = find(doc, "1 INTRODUCTION")
    references = find(doc, "REFERENCES")
    appendix = find(doc, "APPENDIX A: EVIDENCE AND CODE MAP")
    in_cover = True
    in_references = False
    declaration = find(doc, "DECLARATION AND SUPERVISOR CERTIFICATION")
    for paragraph in doc.paragraphs:
        if paragraph._p is references._p:
            in_references = True
        if paragraph._p is appendix._p:
            in_references = False
        if paragraph.style.name in ("Heading 1", "Heading 2", "Heading 3"):
            for run in paragraph.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(14 if paragraph.style.name == "Heading 1" else 12)
                run.bold = True
            if paragraph.style.name == "Heading 1":
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                if paragraph._p is not declaration._p:
                    paragraph.paragraph_format.page_break_before = True
            continue
        if paragraph.style.name == "Caption":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.line_spacing = 1.0
            for run in paragraph.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(10.5)
            continue
        if paragraph.style.name.startswith("toc ") or paragraph.style.name.startswith("TOC "):
            paragraph.paragraph_format.line_spacing = 1.0
            paragraph.paragraph_format.space_after = Pt(0)
            for run in paragraph.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(9.5)
            continue
        if paragraph.style.name == "Thesis List Entry":
            paragraph.paragraph_format.line_spacing = 1.0
            for run in paragraph.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(11)
            continue
        if in_cover:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.line_spacing = 1.5
            for run in paragraph.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(16 if paragraph.style.name == "Title" or paragraph.text == "INDIVIDUAL THESIS" else 14)
                if paragraph.style.name == "Title" or paragraph.text == "INDIVIDUAL THESIS":
                    run.bold = True
            if paragraph.text == "INDIVIDUAL THESIS":
                paragraph.paragraph_format.space_before = Pt(55)
            elif paragraph.text.startswith("Lekamge"):
                paragraph.paragraph_format.space_before = Pt(95)
            elif paragraph.text.startswith("Dissertation submitted"):
                paragraph.paragraph_format.space_before = Pt(40)
            if paragraph._p is cover_end._p:
                in_cover = False
            continue
        if paragraph._p is cover_end._p:
            in_cover = False
        paragraph.paragraph_format.line_spacing = 1.5
        paragraph.paragraph_format.space_after = Pt(6)
        for run in paragraph.runs:
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)
        if paragraph.text.startswith("[1]") or (in_references and re.match(r"^\[\d+\]", paragraph.text)):
            paragraph.paragraph_format.line_spacing = 1.0
            paragraph.paragraph_format.space_after = Pt(12)
        if paragraph.text.startswith("Undergraduate project teams must turn proposals"):
            paragraph.paragraph_format.line_spacing = 1.0
            for run in paragraph.runs:
                run.font.size = Pt(11)
        if paragraph.text.startswith("Keywords:"):
            paragraph.paragraph_format.line_spacing = 1.0
            for run in paragraph.runs:
                run.font.size = Pt(11)
    # Ensure the cover's final section-break paragraph does not count as body.
    cover_end.paragraph_format.space_after = Pt(0)

    for table in doc.tables:
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        grid = table._tbl.tblGrid.gridCol_lst
        if grid:
            widths = [col.w for col in grid]
            total = sum(widths)
            target = Mm(145)
            if total:
                ratio = target / total
                for col, width in zip(grid, widths):
                    col.w = int(width * ratio)
                for row in table.rows:
                    for cell, width in zip(row.cells, widths):
                        cell.width = int(width * ratio)
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.line_spacing = 1.0
                    paragraph.paragraph_format.space_after = Pt(0)
                    for run in paragraph.runs:
                        run.font.name = "Times New Roman"
                        run.font.size = Pt(10.5)
    # The front declaration table benefits from full-size text.
    for row in doc.tables[0].rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(12)
    for paragraph in doc.paragraphs:
        if paragraph._p.xpath(".//w:drawing"):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def main() -> None:
    doc = Document(SOURCE)
    format_cover_and_preliminaries(doc)
    restructure_chapters(doc)
    caption_and_list(doc)
    # Repair a legacy replacement character in the abbreviation table.
    for row in doc.tables[1].rows:
        for cell in row.cells:
            if "�" in cell.text:
                cell.text = cell.text.replace("�", "–")
    format_document(doc)
    doc.core_properties.title = "Adaptive Scheduling and Generative Project Planning"
    doc.core_properties.subject = "SLIIT-formatted individual thesis draft; author certification pending"
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
