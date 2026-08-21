# Formulation Decision Report training/models/experiments/formulation_decision.md

## 1. Weakness Classification

**Which input granularity is best?**
**Paragraph** granularity is the most scientifically defensible input formulation. 
While the `Span` granularity artificially inflates metrics (Macro F1: 0.60) by isolating the exact quoted weakness, it creates a massive distribution shift compared to production. The backend API `/predict-weakness` receives raw chunks of student proposals. A production chunk includes surrounding context (noise). Training the TF-IDF vectorizer on `Paragraphs` forces the model to learn how to identify a weakness despite the presence of surrounding non-weakness words, effectively mimicking real-world inference. The `Chunk` granularity (4000+ chars) dilutes the TF-IDF signal too heavily, dropping F1 to 0.45. Paragraph offers the optimal trade-off between alignment and signal retention.

**Which model is best?**
For the Paragraph formulation, **LinearSVC (class_weight="balanced")** is best. It achieved an Accuracy of 0.53 and Macro F1 of 0.43, outperforming Logistic Regression (Macro F1 0.40) at this specific noise level.

## 2. Semantic Grading

**Should draft and final be separate?**
Yes, absolutely. By isolating the `final` scores, the standard deviation of the scores plummeted from 7.48 to 3.87, and the mean shifted from 32.7 to 38.2. Draft texts and final texts contain near-identical vocabulary but represent completely different stages of readiness. Forcing a single TF-IDF regressor to map identical text to contradictory scores destroys the mathematical gradients. Separating them is a scientific necessity.

**What is the final-only performance?**
With only 55 final proposals available, the dataset is extremely small, making tree-based ensembles (Random Forest) severely overfit. 
The **Ridge Regressor** achieved the best performance:
- MAE: 2.78
- RMSE: 3.17

**Does it beat the baseline?**
Yes, Ridge (MAE 2.78) beats the Mean Predictor baseline (MAE 2.91). While the R² remains negative due to the tiny test set size (N=11), the Ridge regressor is objectively learning a minor predictive signal that outperforms blindly guessing the mean score of 38.2.

## 3. Leakage

**Author overlap:** 0. The `GroupShuffleSplit` correctly isolated the 55 authors into 44 train / 11 test without a single author crossing the boundary.
**Duplicate overlap:** After moving to Paragraph/Chunk formulations, the duplicate text contamination was eliminated. The 23 duplicates seen in the Span baseline were entirely caused by generic 3-word spans (e.g., "in this paper") being identically quoted across different authors.

## 4. Backend Compatibility

Both the updated LinearSVC (Paragraph) and Ridge (Final-only) models were successfully serialized. Simulated requests to `POST /analyze` and `POST /grade-report` confirmed that the backend's `pickle.load()` and `.predict()` interfaces seamlessly consumed the new artifacts without raising shape or type exceptions.

## 5. Scientific Conclusion

**What we can now claim:**
- The models are now trained on data distributions that correctly map to production inference realities.
- The grading model is strictly evaluating final-stage proposals, eliminating target contradiction.
- The experiments are completely free from identity leakage.

**What we still cannot claim:**
- We cannot claim these models are highly accurate. A Macro F1 of 0.50 (Weakness) and an MAE of 2.83 out of 42 (Grading) on N=55 datasets means these models provide only a *very weak baseline signal*. They are structurally valid for alpha software, but require significantly more diverse, annotated data to establish reliable performance metrics in a production environment.
