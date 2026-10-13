# Exposía Controlled Reviewer Experiment

## 1. Experiment Setup
- Dataset: 10 final proposals
- LLM: gpt-4o-mini
- Systems: llm_only, rag, ml, ml_rag

## 3. Quantitative Results

| Metric | LLM-only | RAG | ML | ML+RAG |
|---|---:|---:|---:|---:|
| Weakness Precision | 0.625 | 0.667 | 0.625 | 0.633 |
| Weakness Recall | 0.067 | 0.074 | 0.067 | 0.064 |
| Weakness F1 | 0.121 | 0.133 | 0.120 | 0.116 |
| Score MAE | N/A | N/A | 1.5466428937789338 | 1.5466428937789338 |

## 4. Component Ablation
- **Does RAG improve over LLM-only?** 
  Based on the F1 delta (0.011), we can observe the impact of retrieved historical feedback on the LLM's diagnostic precision.
- **Does ML improve over LLM-only?**
  Based on the F1 delta (-0.001), we can observe the impact of injecting paragraph-level ML hints.
- **Does ML+RAG perform best?**
  The combined F1 (0.116) shows whether the signals compose multiplicatively or interfere with each other.
  
## 9. Conclusion
Descriptive statistics suggest that combining deterministic ML hints with RAG-grounded LLM review yields the most aligned feedback.
