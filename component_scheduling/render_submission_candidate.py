"""Update Word fields and export a dissertation DOCX to PDF.

By default this uses a separate hidden Word instance. ``--attach`` instead
uses an existing Word session, opening only the supplied DOCX invisibly and
leaving the user's other open documents untouched.
"""

from __future__ import annotations

from pathlib import Path
import sys

import win32com.client


ROOT = Path(__file__).resolve().parent
DEFAULT_DOCX = ROOT / "IT22117014_Individual_Component_Dissertation_Submission_Candidate.docx"


def main() -> None:
    attach = "--attach" in sys.argv
    paths = [item for item in sys.argv[1:] if item != "--attach"]
    docx = Path(paths[0]).resolve() if paths else DEFAULT_DOCX
    pdf = docx.with_suffix(".pdf")
    app = win32com.client.GetActiveObject("Word.Application") if attach else win32com.client.DispatchEx("Word.Application")
    if not attach:
        app.Visible = False
        app.DisplayAlerts = 0
    document = None
    try:
        document = app.Documents.Open(
            FileName=str(docx),
            ReadOnly=False,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            Visible=False,
        )
        document.Fields.Update()
        for index in range(1, document.TablesOfContents.Count + 1):
            document.TablesOfContents.Item(index).Update()
        document.Fields.Update()
        for section in document.Sections:
            for collection in (section.Headers, section.Footers):
                for item in collection:
                    item.Range.Fields.Update()
        document.Repaginate()
        pages = document.ComputeStatistics(2)  # wdStatisticPages
        document.Save()
        document.ExportAsFixedFormat(str(pdf), 17)  # wdExportFormatPDF
        print(f"DOCX: {docx}")
        print(f"PDF: {pdf}")
        print(f"Word page count: {pages}")
    finally:
        if document is not None:
            document.Close(SaveChanges=False)
        if not attach:
            app.Quit()


if __name__ == "__main__":
    main()
