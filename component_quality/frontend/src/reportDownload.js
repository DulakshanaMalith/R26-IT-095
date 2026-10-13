import { generateReport } from "./api";

export function buildAnalysisReportPayload(record = {}, graph = {}, semanticGrade = null) {
  const gradePayload = semanticGrade || record.semantic_grade || null;
  const completenessPayload = gradePayload?.proposal_completeness || record.proposal_completeness || record.final_proposal_assessment?.proposal_completeness || null;
  const readinessPayload = gradePayload?.submission_readiness || record.submission_readiness || record.final_proposal_assessment?.submission_readiness || null;
  const finalAssessmentPayload = gradePayload?.final_proposal_assessment || record.final_proposal_assessment || null;
  const finalReadinessPayload = gradePayload?.final_readiness || record.final_readiness || finalAssessmentPayload?.final_readiness || null;
  const graphPayload = graph?.concepts || graph?.edges || graph?.missing_concepts || graph?.missingConcepts
    ? graph
    : record.knowledge_graph || record.graph || record.knowledgeGraph || {};
  return {
    analysis_id: record.analysis_id || record.id || null,
    input_text: record.input_text || record.input_preview || "",
    student_name: record.student_name || record.studentName || null,
    student_id: record.student_id || record.studentId || null,
    proposal_title: record.proposal_title || record.proposalTitle || record.title || null,
    filename: record.filename || null,
    source: record.source || "unknown",
    analysis_timestamp: record.timestamp || record.analysis_timestamp || null,
    predicted_tag: record.predicted_tag || "",
    feedback: record.retrieved_feedback || record.feedback || [],
    knowledge_graph: {
      concepts: graphPayload?.concepts || [],
      edges: graphPayload?.edges || [],
      missing_concepts: graphPayload?.missing_concepts || graphPayload?.missingConcepts || [],
    },
    recommendations: record.recommended_resources || record.recommendations || [],
    semantic_grade: gradePayload
      ? {
          ...gradePayload,
          section_scores: gradePayload.section_scores || record.section_scores || {},
        }
      : null,
    proposal_completeness: completenessPayload,
    submission_readiness: readinessPayload,
    final_readiness: finalReadinessPayload,
    final_readiness_percentage: gradePayload?.final_readiness_percentage || record.final_readiness_percentage || finalReadinessPayload?.percentage || null,
    final_readiness_label: gradePayload?.final_readiness_label || record.final_readiness_label || finalReadinessPayload?.label || null,
    final_proposal_assessment: finalAssessmentPayload,
  };
}

function filenameFromDisposition(disposition = "") {
  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch {
      return encodedMatch[1];
    }
  }
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || "ResearchPilot_Report.pdf";
}

export async function generateAndDownloadReport(payload) {
  const response = await generateReport(payload);
  if (!response.ok) {
    let message = "Failed to generate PDF report.";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {
      const text = await response.text();
      message = text || message;
    }
    throw new Error(message);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/pdf")) {
    throw new Error("The server did not return a valid PDF file.");
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const disposition = response.headers.get("content-disposition") || "";
  const filename = filenameFromDisposition(disposition);

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);

  return {
    filename,
    download_url: null,
    size: blob.size,
  };
}
