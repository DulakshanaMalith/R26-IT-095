from src.preprocessing.pdf_extractor import extract_text_from_pdf
from src.preprocessing.text_cleaner import clean_text
from src.preprocessing.section_splitter import split_sections
from src.utils.file_utils import load_json, save_text_file
from src.utils.pdf_exporter import save_feedback_as_pdf

from src.grading.rubric_matcher import match_rubric
from src.grading.score_calculator import calculate_scores
from src.grading.ml_predictor import predict_ml_score
from src.grading.final_score import calculate_final_hybrid_score

from src.diagnosis.weakness_detector import detect_weaknesses
from src.recommendation.recommender import recommend_resources
from src.feedback.feedback_generator import generate_feedback


def main():
    report_path = "data/raw/reports/sample_report.pdf"
    rubric_path = "data/raw/rubric/rubric.json"

    # 1. Extract and preprocess report
    raw_text = extract_text_from_pdf(report_path)
    cleaned_text = clean_text(raw_text)
    sections = split_sections(cleaned_text)

    # 2. Load rubric and perform semantic grading
    rubric = load_json(rubric_path)
    rubric_results = match_rubric(sections, rubric)
    score_summary = calculate_scores(rubric_results, rubric)

    # 3. Predict ML-based overall score
    ml_result = predict_ml_score(cleaned_text)

    # 4. Combine semantic + ML score into final hybrid score
    hybrid_result = calculate_final_hybrid_score(
        semantic_score=score_summary["overall_score"],
        ml_score=ml_result["normalized_ml_score"]
    )

    # 5. Detect weaknesses and recommend resources
    weaknesses = detect_weaknesses(rubric_results, threshold=0.50)
    recommendations = recommend_resources(weaknesses)

    # 6. Generate final feedback report
    feedback_data = generate_feedback(
        rubric_results=rubric_results,
        weaknesses=weaknesses,
        recommendations=recommendations,
        score_summary=score_summary,
        ml_result=ml_result,
        hybrid_result=hybrid_result
    )

    # 7. Print result
    print("\n" + "=" * 50)
    print(feedback_data["text"])
    print("=" * 50)

    # 8. Save result to file
    output_path = "outputs/feedback_report.txt"
    save_text_file(feedback_data["text"], output_path)
    print(f"Report saved to: {output_path}")

    # 9. Save feedback as PDF
    pdf_output_path = "outputs/feedback_report.pdf"
    save_feedback_as_pdf(feedback_data, pdf_output_path)

    print(f"\nPDF report saved to: {pdf_output_path}")


if __name__ == "__main__":
    main()