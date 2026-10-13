# IEEE Overleaf Paper Package

This folder contains the updated, evidence-backed IEEE conference draft for the scheduling component. The prose uses direct design reasoning and reports both successful and unsuccessful results without changing the verified measurements.

## Files

- `main.tex` — IEEE conference manuscript.
- `references.bib` — BibTeX references used by the manuscript.
- `SOURCE_AUDIT.md` — traceability notes for the implementation, datasets, results, and claim boundaries.
- `workload_baseline_results.csv` — summary table from the controlled workload-allocation experiment.
- `workload_baseline_summary.json` — experiment configuration and machine-readable results.
- `evaluate_workload_balancing.py` — reproducibility script for the allocation comparison.

## Upload to Overleaf

1. Create a **Blank Project** in Overleaf.
2. Upload every file from the ZIP.
3. Set `main.tex` as the main document.
4. Select the **pdfLaTeX** compiler.
5. Recompile twice so that all references and table numbers resolve.

The author block is intentionally empty. Add the required author information before submission unless the conference uses a separate anonymous-review process.

## Six-page target

The source is designed for approximately six IEEE conference pages, including references. The exact pagination can change after Overleaf updates the bibliography or inserts conference metadata.

1. Compile with **pdfLaTeX** and confirm the page count.
2. Keep the IEEE font size and margins unchanged.
3. If the references move to page 7, shorten a non-essential implementation paragraph rather than reducing font size.
4. Keep `\balance` before the bibliography so the final columns are balanced.

## Evidence boundary

The paper reports a reproducible controlled workload baseline: 100 trials for historical-profile and cold-start scenarios. It does not claim that the hybrid beats LPT, that synthetic trials represent a student cohort, that a Git commit proves completion, or that effort estimates are exact. Before submission, rerun the evaluation, retain the outputs, and review every paragraph in your own words. You must be able to explain every method and result and follow the university and conference policies for authorship and writing assistance.
