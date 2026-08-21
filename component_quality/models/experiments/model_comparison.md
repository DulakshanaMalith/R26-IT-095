# Model Comparison Report training/models/experiments/model_comparison.md

This report summarizes the experimental results of the model improvement study conducted on the frozen N=55 alpha dataset. All candidate models were evaluated against the exact same 20-seed author GroupShuffleSplits established during the robustness phase.

## 1. Weakness Classification
**Task:** Binary Classification (Weakness vs Non-Weakness) on Paragraph-level text.

| Model | Mean F1 | Std F1 | Min | Max |
|-------|---------|--------|-----|-----|
| TF-IDF + LinearSVC (Alpha Baseline) | 0.502 | 0.056 | 0.415 | 0.627 |
| TF-IDF + LogisticRegression | 0.494 | 0.048 | 0.407 | 0.570 |
| TF-IDF (Words + Chars) + LinearSVC | 0.495 | 0.042 | 0.424 | 0.570 |
| **all-MiniLM-L6-v2 + LogisticRegression** | **0.559** | **0.052** | **0.461** | **0.671** |

**Conclusion:** The semantic embedding baseline substantially outperforms the purely lexical TF-IDF approaches. While the TF-IDF models hovered around 0.49-0.50 F1, the dense embeddings raised the signal to 0.559. Error analysis indicates that TF-IDF falsely flags paragraphs containing words like "struggle" or "gap" even when they are part of a legitimate literature review. The dense vectors mitigate these lexical false positives.
**System Alignment:** The `all-MiniLM-L6-v2` transformer is already loaded in RAM for the backend RAG subsystem. Repurposing it as a feature extractor for Weakness classification costs zero additional memory.

## 2. Semantic Grading
**Task:** Regression (0-42 scale) on Final submissions only.

| Model | Mean MAE | Std MAE | Min | Max | Mean R² |
|-------|----------|---------|-----|-----|---------|
| Mean Predictor (Training Set) | 2.894 | 0.574 | 2.010 | 4.119 | -0.262 |
| TF-IDF + Ridge (Alpha Baseline) | 2.838 | 0.578 | 1.846 | 3.951 | -0.181 |
| TF-IDF + ElasticNet | 2.894 | 0.574 | 2.010 | 4.119 | -0.262 |
| TF-IDF + RandomForestRegressor | 2.734 | 0.482 | 1.810 | 3.991 | -0.174 |
| Rubric-Aware + Ridge | 2.846 | 0.573 | 1.867 | 3.934 | -0.185 |

**Conclusion:** RandomForest achieved the lowest MAE (2.734) and reduced the standard deviation across splits. However, all models produce a negative mean R², indicating they struggle to generalize structurally across held-out authors on such a small dataset. 
**Rubric-Aware Result:** Prepending the explicit textual rubric sub-scores did not meaningfully improve the MAE (2.846 vs 2.838). Ridge failed to leverage the injected numerical categories. 

## 3. Final Recommendation

**Weakness:** **EXPERIMENTAL CANDIDATE (Semantic_MiniLM_LogReg) RECOMMENDED.** The ~6 point F1 bump and natural synergy with the existing RAG embedding pipeline makes this a highly efficient and accurate improvement. 
**Grading:** **CURRENT ALPHA BASELINE (Ridge) RECOMMENDED.** While RandomForest technically scored slightly better MAE, its R² remained negative and it severely overfits training noise on N=55. The Ridge baseline remains the most theoretically sound linear model for high-dimensional TF-IDF on small samples.

**Primary Bottleneck:** Dataset Size. Algorithmic changes yielded a ceiling on Grading performance. Additional diverse annotated data is expected to improve the reliability of evaluation and may improve model performance.
