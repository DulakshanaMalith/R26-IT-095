# Model Card: Exposia Weakness Classifier

## Model Purpose
The Weakness Classifier aims to identify areas of academic research proposals (exposés) that lack clarity, evidence, structural completeness, or academic rigor.

## Intended Use
To provide supportive, formative feedback to students drafting research proposals. 
**Non-intended Use**: This model is NOT intended to automatically grade students, fail proposals, or make final academic judgments without human review.

## Training Dataset
- **Source**: Exposia (Student drafts and expert reviewer comments).
- **Size**: 2,228 annotated text spans.
- **Class Distribution**: 59.8% Weakness, 40.2% Non-Weakness.
- **Data Split**: GroupShuffleSplit by author (80% Train, 20% Test) to completely eliminate author-style data leakage.

## Architecture & Preprocessing
- **Preprocessing**: Extracts the annotation target text along with its surrounding sentence prefix and suffix to provide contextual semantic meaning. 
- **Current Production Model**: TF-IDF Vectorizer (max 5000 features, unigrams) + LinearSVC (balanced class weights).
- **Experimental Candidates**: Sentence-BERT (all-MiniLM-L6-v2) + Logistic Regression.

## Evaluation Metrics (Grouped by Author)
- **Majority Class Baseline**: 54.11%
- **Test Accuracy**: 54.91% (SVM) / 55.70% (SBERT)
- **CV Macro F1**: 0.5607 (SVM) / 0.5617 (SBERT)
- **Test Macro F1**: 0.5476 (SVM) / 0.5570 (SBERT)
- **Generalization Gap**: ~0.12 - 0.18

## Confusion Matrix (SVM)
| True \ Predicted | Non-Weakness | Weakness |
| :--- | :---: | :---: |
| **Non-Weakness** | 114 | 59 |
| **Weakness** | 111 | 93 |

## Known Limitations & Risks
1. **Severe Label Ambiguity**: The dataset contains exact duplicate text strings with conflicting labels (25+ instances). What one reviewer flags as a weakness, another ignores.
2. **Author Overfitting**: The model learns author-specific writing styles rather than general semantic "weakness" indicators. When evaluated strictly on unseen authors, performance regresses to the baseline.
3. **Risk**: High false-positive and false-negative rates. The model is currently constrained by dataset quality and should be used cautiously as a heuristic rather than an absolute source of truth.

## Reproducibility
The canonical evaluation pipeline is implemented in `train_svm_classifier.py` and strictly utilizes `GroupKFold` on the `author` field. Training records and hyperparameter configurations are automatically preserved as JSON artifacts in the `results/experiments/` directory.
