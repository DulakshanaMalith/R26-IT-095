"""Run the Exposia quality-assessment and mentorship demo pipeline."""

from __future__ import annotations

import pickle
import re
import sys
from pathlib import Path
from typing import Any

from resource_recommender import recommend_resources
from train_feedback_retrieval import get_feedback


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"
OUTPUT_PATH = RESULTS_DIR / "demo_pipeline_output.txt"

SVM_MODEL_PATH = MODELS_DIR / "weakness_svm_model.pkl"
GRADING_MODEL_PATH = MODELS_DIR / "semantic_grading_model.pkl"


def load_pickle_artifact(path: Path) -> Any | None:
    """Load a trusted local pickle artifact, or return None if unavailable."""
    if not path.exists():
        return None

    try:
        with path.open("rb") as file:
            return pickle.load(file)
    except (OSError, pickle.PickleError, AttributeError, EOFError) as exc:
        print(f"Warning: could not load {path.name}: {exc}")
        return None


def resolve_estimator(artifact: Any) -> tuple[Any | None, Any | None]:
    """Support either a saved estimator or a dictionary-style model artifact."""
    if artifact is None:
        return None, None
    if hasattr(artifact, "predict"):
        return artifact, None
    if isinstance(artifact, dict):
        for key in ("model", "pipeline", "classifier"):
            estimator = artifact.get(key)
            if estimator is not None and hasattr(estimator, "predict"):
                return estimator, artifact.get("label_encoder")
    return None, None


def fallback_tag_predictor(text: str) -> str:
    """Predict a broad annotation tag using transparent keyword rules."""
    normalized = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    tokens = set(normalized.split())

    def contains_keyword(keyword: str) -> bool:
        return keyword in normalized if " " in keyword else keyword in tokens

    strength_keywords = (
        "clear",
        "well written",
        "well defined",
        "strong",
        "excellent",
        "good justification",
    )
    highlight_keywords = ("heading", "title", "url", "doi", "highlight")
    weakness_keywords = (
        "unclear",
        "broad",
        "missing",
        "unsupported",
        "weak",
        "not explain",
        "no citation",
        "no reference",
        "lacks",
        "incomplete",
    )

    if any(contains_keyword(keyword) for keyword in weakness_keywords):
        return "Weakness"
    if any(contains_keyword(keyword) for keyword in strength_keywords):
        return "Strength"
    if any(contains_keyword(keyword) for keyword in highlight_keywords):
        return "Highlight"
    return "Other"


def predict_weakness_tag(text: str, svm_artifact: Any | None) -> tuple[str, str]:
    """Use the saved Linear SVM when available, otherwise use fallback rules."""
    estimator, label_encoder = resolve_estimator(svm_artifact)
    if estimator is None:
        return fallback_tag_predictor(text), "keyword fallback"

    try:
        prediction = estimator.predict([text])[0]
        if label_encoder is not None:
            prediction = label_encoder.inverse_transform([prediction])[0]
        return str(prediction), "TF-IDF + Linear SVM"
    except (ValueError, TypeError, AttributeError) as exc:
        print(f"Warning: SVM prediction failed; using keyword fallback: {exc}")
        return fallback_tag_predictor(text), "keyword fallback"


def retrieve_feedback_safely(text: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve feedback without stopping the full demo if retrieval fails."""
    try:
        return get_feedback(text, top_k=top_k)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        print(f"Warning: feedback retrieval unavailable: {exc}")
        return []


def predict_score(text: str, grading_artifact: Any | None) -> float | None:
    """Predict a report score when the semantic grading model is available."""
    estimator, _ = resolve_estimator(grading_artifact)
    if estimator is None:
        return None

    try:
        return float(estimator.predict([text])[0])
    except (ValueError, TypeError, AttributeError) as exc:
        print(f"Warning: semantic score prediction failed: {exc}")
        return None


def format_demo_output(
    input_text: str,
    predicted_tag: str,
    prediction_source: str,
    feedback_matches: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    predicted_score: float | None,
) -> str:
    """Format one complete end-to-end demonstration."""
    lines = [
        "Input Text:",
        input_text,
        "",
        f"Predicted Tag: {predicted_tag}",
        f"Tag Prediction Source: {prediction_source}",
        "",
        "Retrieved Feedback:",
    ]

    if feedback_matches:
        for rank, match in enumerate(feedback_matches, start=1):
            lines.extend(
                [
                    f"  {rank}. Similarity: {match['similarity_score']:.4f}",
                    f"     Matched annotation: {match['annotated_text']}",
                    f"     Feedback: {match['comment_text']}",
                ]
            )
    else:
        lines.append("  Feedback retrieval unavailable.")

    lines.extend(["", "Recommended Resources:"])
    for rank, resource in enumerate(resources, start=1):
        lines.extend(
            [
                f"  {rank}. [{resource['category']}] {resource['title']}",
                f"     {resource['description']}",
                f"     URL: {resource['url']}",
                f"     Keyword score: {resource['score']}",
            ]
        )

    score_text = "Unavailable" if predicted_score is None else f"{predicted_score:.2f}"
    lines.extend(["", f"Predicted Score: {score_text}"])
    return "\n".join(lines)


def run_demo_case(
    input_text: str,
    svm_artifact: Any | None,
    grading_artifact: Any | None,
) -> str:
    """Run all pipeline stages for one input text."""
    predicted_tag, prediction_source = predict_weakness_tag(input_text, svm_artifact)
    feedback_matches = retrieve_feedback_safely(input_text, top_k=3)
    feedback_context = " ".join(
        match["comment_text"] for match in feedback_matches
    )
    resources = recommend_resources(
        weakness_text=input_text,
        feedback_text=feedback_context,
        top_k=3,
    )
    predicted_score = predict_score(input_text, grading_artifact)

    return format_demo_output(
        input_text,
        predicted_tag,
        prediction_source,
        feedback_matches,
        resources,
        predicted_score,
    )


def main() -> None:
    """Run three examples through the integrated mentorship pipeline."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    svm_artifact = load_pickle_artifact(SVM_MODEL_PATH)
    grading_artifact = load_pickle_artifact(GRADING_MODEL_PATH)

    if svm_artifact is None:
        print("SVM model not found; using the keyword-based tag predictor.")
    if grading_artifact is None:
        print("Semantic grading model not found; score prediction will be skipped.")

    sample_inputs = [
        "The research question is too broad and unclear, so the intended scope is not well defined.",
        "The methodology does not explain participant sampling, data collection, or the analysis procedure.",
        "This important claim is unsupported because the paragraph has no citation or academic reference.",
    ]

    demo_sections = []
    for index, input_text in enumerate(sample_inputs, start=1):
        section = run_demo_case(input_text, svm_artifact, grading_artifact)
        titled_section = f"DEMO {index}\n{'=' * 80}\n{section}"
        demo_sections.append(titled_section)
        print("\n" + titled_section)

    full_output = "\n\n".join(demo_sections) + "\n"
    OUTPUT_PATH.write_text(full_output, encoding="utf-8")
    print(f"\nDemo pipeline output saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, OSError, RuntimeError) as error:
        print(f"Demo pipeline failed: {error}")
        raise SystemExit(1) from error
