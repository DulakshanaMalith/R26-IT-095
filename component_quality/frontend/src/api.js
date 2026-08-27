function sameLocalApiBaseUrl(configuredUrl) {
  if (typeof window === "undefined") return configuredUrl;
  try {
    const apiUrl = new URL(configuredUrl);
    const pageHost = window.location.hostname;
    const loopbackHosts = new Set(["localhost", "127.0.0.1"]);
    if (
      apiUrl.protocol === window.location.protocol &&
      loopbackHosts.has(apiUrl.hostname) &&
      loopbackHosts.has(pageHost) &&
      apiUrl.hostname !== pageHost
    ) {
      apiUrl.hostname = pageHost;
      return apiUrl.toString().replace(/\/$/, "");
    }
  } catch {
    return configuredUrl;
  }
  return configuredUrl;
}

export const API_BASE_URL = sameLocalApiBaseUrl(import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:9000");
const TEMP_DEV_SUPERVISOR_ID = import.meta.env.VITE_DEMO_SUPERVISOR_ID || "";
const TEMP_USE_LEGACY_SUPERVISOR_DATA = true;

async function request(path, options = {}, fallbackMessage = "Backend request failed.") {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: "include",
      ...options,
    });
  } catch {
    throw new Error(`Backend is unavailable. Start FastAPI on ${API_BASE_URL}.`);
  }

  if (!response.ok) {
    let detail = fallbackMessage;
    let validation = null;
    try {
      const payload = await response.json();
      const serverDetail = payload.detail || payload.message || detail;
      if (typeof serverDetail === "string") {
        detail = serverDetail === "Not Found" ? fallbackMessage : serverDetail;
      } else if (serverDetail?.message) {
        detail = serverDetail.message;
        validation = serverDetail.document_validation || null;
      }
    } catch {
      // Keep the friendly fallback when the backend does not return JSON.
    }
    const error = new Error(detail);
    if (validation) error.documentValidation = validation;
    throw error;
  }

  return response.json();
}

export async function checkBackendStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/`);
    return response.ok;
  } catch {
    return false;
  }
}

export function analyzeText(text, metadata = {}) {
  return request(
    "/analyze",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        request_id: metadata.request_id || null,
        source: metadata.source || "unknown",
        filename: metadata.filename || null,
        student_name: metadata.student_name || null,
        student_id: metadata.student_id || null,
        proposal_title: metadata.proposal_title || null,
        analysis_id: metadata.analysis_id || null,
        learning_needs: metadata.learning_needs || [],
      }),
    },
    "The proposal analysis could not be completed.",
  );
}

export function predictWeakness(text) {
  return request(
    "/predict-weakness",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
    "Weakness prediction failed.",
  );
}

export function runLLMReview(proposalText, mode = "llm_rag_criteria", topK = 5) {
  return request(
    "/review",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proposal_text: proposalText,
        mode,
        top_k: topK,
      }),
    },
    "LLM review failed.",
  );
}

export function generateFeedback(text) {
  return request(
    "/generate-feedback",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
    "Feedback generation failed.",
  );
}

export function recommendResources(text, feedback = "", metadata = {}) {
  return request(
    "/recommend-resources",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        feedback,
        analysis_id: metadata.analysis_id || null,
        learning_needs: metadata.learning_needs || [],
      }),
    },
    "Could not generate learning resources.",
  );
}

export function createKnowledgeGraph(text, metadata = {}) {
  return request(
    "/knowledge-graph",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        filename: metadata.filename || null,
        analysis_id: metadata.analysis_id || null,
      }),
    },
    "Could not build the knowledge graph.",
  );
}

export function gradeReport(text, metadata = {}) {
  return request(
    "/grade-report",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        source: metadata.source || "unknown",
        filename: metadata.filename || null,
        analysis_id: metadata.analysis_id || null,
      }),
    },
    "Could not generate semantic grade.",
  );
}

export function generateReport(payload) {
  return fetch(`${API_BASE_URL}/generate-report`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function filenameFromContentDisposition(disposition = "", fallback = "ResearchPilot_Final_Feedback.pdf") {
  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch {
      return encodedMatch[1];
    }
  }
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || fallback;
}

async function pdfDownloadRequest(path, fallbackMessage) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { credentials: "include" });
  } catch {
    throw new Error(`Backend is unavailable. Start FastAPI on ${API_BASE_URL}.`);
  }

  if (!response.ok) {
    let detail = fallbackMessage;
    try {
      const payload = await response.json();
      detail = payload.detail || payload.message || detail;
    } catch {
      const text = await response.text();
      detail = text || detail;
    }
    throw new Error(detail);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/pdf")) {
    throw new Error("The server did not return a valid PDF file.");
  }

  const blob = await response.blob();
  const filename = filenameFromContentDisposition(response.headers.get("content-disposition") || "");
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return { filename, size: blob.size, download_url: null };
}

export function getAnalysisHistory() {
  return request("/analysis-history", {}, "Could not load analysis history.");
}

export function clearAnalysisHistory() {
  return request(
    "/analysis-history",
    { method: "DELETE" },
    "Could not clear proposal history.",
  );
}

export function deleteAnalysisHistoryRecord(analysisId) {
  return request(
    `/analysis-history/${encodeURIComponent(analysisId)}`,
    { method: "DELETE" },
    "Could not delete this proposal history record.",
  );
}

export function clearGradingHistory() {
  return request(
    "/grading-history",
    { method: "DELETE" },
    "Could not clear semantic grading history.",
  );
}

export function getSupervisorAnalytics() {
  return request("/supervisor-analytics", {}, "Could not load supervisor analytics.");
}

export function getKnowledgeGraphHistory() {
  return request("/knowledge-graph-history", {}, "Could not load knowledge graph history.");
}

export function getGradingHistory() {
  return request("/grading-history", {}, "Could not load semantic grading history.");
}

export function getGradingAnalytics() {
  return request("/grading-analytics", {}, "Could not load semantic grading analytics.");
}

export function getSupervisorStudents(supervisorId) {
  return request(
    `/supervisors/${encodeURIComponent(supervisorId)}/students`,
    {},
    "Could not load supervisor students.",
  );
}

export function createSupervisorStudent(supervisorId, payload) {
  return request(
    `/supervisors/${encodeURIComponent(supervisorId)}/students`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not create student.",
  );
}

export function loginSupervisor(payload) {
  return request(
    "/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not sign in.",
  );
}

export function devLoginSupervisor() {
  return request(
    "/auth/dev-login",
    { method: "POST" },
    "Development login failed.",
  );
}

export function registerSupervisor(payload) {
  return request(
    "/auth/register",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Registration failed.",
  );
}

export function getCurrentSupervisor() {
  return request("/auth/me", {}, "Could not load current supervisor.");
}

export function logoutSupervisor() {
  return request("/auth/logout", { method: "POST" }, "Could not sign out.");
}

export function getCurrentSupervisorStudents() {
  if (TEMP_USE_LEGACY_SUPERVISOR_DATA) {
    if (!TEMP_DEV_SUPERVISOR_ID) {
      return Promise.reject(new Error("Temporary supervisor ID is not configured."));
    }
    return getSupervisorStudents(TEMP_DEV_SUPERVISOR_ID);
  }
  return request("/me/students", {}, "Could not load supervisor students.");
}

export function removeSupervisorStudent(supervisorId, studentId) {
  return request(
    `/supervisors/${encodeURIComponent(supervisorId)}/students/${encodeURIComponent(studentId)}`,
    { method: "DELETE" },
    "Could not remove student from supervisor roster.",
  );
}

export function removeCurrentSupervisorStudent(studentId) {
  if (TEMP_USE_LEGACY_SUPERVISOR_DATA) {
    if (!TEMP_DEV_SUPERVISOR_ID) {
      return Promise.reject(new Error("Temporary supervisor ID is not configured."));
    }
    return removeSupervisorStudent(TEMP_DEV_SUPERVISOR_ID, studentId);
  }
  return request(
    `/me/students/${encodeURIComponent(studentId)}`,
    { method: "DELETE" },
    "Could not remove student from supervisor roster.",
  );
}

async function getTemporarySupervisorDashboard() {
  if (!TEMP_DEV_SUPERVISOR_ID) {
    throw new Error("Temporary supervisor ID is not configured.");
  }
  const students = await getSupervisorStudents(TEMP_DEV_SUPERVISOR_ID);
  const recentProposals = [];
  const studentsWithProposals = new Set();
  let analyzedCurrentVersions = 0;
  let waitingForAnalysis = 0;
  let revisionRequested = 0;
  let reviewed = 0;

  await Promise.all((students || []).map(async (student) => {
    const proposals = await getStudentProposals(student.student_id);
    if (proposals?.length) studentsWithProposals.add(student.student_id);
    await Promise.all((proposals || []).map(async (proposal) => {
      const versions = [...(await getProposalVersions(proposal.proposal_id) || [])]
        .sort((first, second) => (first.version_number || 0) - (second.version_number || 0));
      const currentVersion = versions.find((version) => version.version_id === proposal.current_version_id) || versions[versions.length - 1] || null;
      const analyses = currentVersion ? await getVersionAnalyses(currentVersion.version_id) : [];
      const reviews = currentVersion ? await getVersionSupervisorReviews(currentVersion.version_id) : [];
      const supervisorReviews = (reviews || []).filter((review) => review.supervisor_id === TEMP_DEV_SUPERVISOR_ID);
      const latestReview = [...supervisorReviews]
        .sort((first, second) => new Date(second.updated_at || second.created_at || 0) - new Date(first.updated_at || first.created_at || 0))[0] || null;

      if (currentVersion) {
        if (analyses?.length) analyzedCurrentVersions += 1;
        else waitingForAnalysis += 1;
      }
      if (latestReview) {
        reviewed += 1;
        if (latestReview.decision === "REQUEST_REVISION" || latestReview.decision === "REVISION_REQUESTED") {
          revisionRequested += 1;
        }
      }
      recentProposals.push({
        student_id: student.student_id,
        student_name: student.full_name,
        academic_student_id: student.academic_student_id,
        proposal_id: proposal.proposal_id,
        proposal_title: proposal.title,
        current_version_id: currentVersion?.version_id || null,
        current_version_number: currentVersion?.version_number || null,
        last_upload: currentVersion?.submitted_at || currentVersion?.created_at || proposal.updated_at || proposal.created_at || null,
        analysis_state: analyses?.length ? "Analyzed" : (currentVersion ? "Waiting for analysis" : "No version"),
        supervisor_review_state: latestReview?.decision || "Not reviewed",
      });
    }));
  }));

  recentProposals.sort((first, second) => new Date(second.last_upload || 0) - new Date(first.last_upload || 0));
  return {
    assigned_students: students?.length || 0,
    with_proposals: studentsWithProposals.size,
    analyzed_current_versions: analyzedCurrentVersions,
    waiting_for_analysis: waitingForAnalysis,
    revision_requested: revisionRequested,
    reviewed,
    recent_proposals: recentProposals.slice(0, 6),
  };
}

export function getCurrentSupervisorDashboard() {
  if (TEMP_USE_LEGACY_SUPERVISOR_DATA) {
    return getTemporarySupervisorDashboard();
  }
  return request("/me/dashboard", {}, "Could not load supervisor dashboard.");
}

export function createCurrentSupervisorStudent(payload) {
  if (TEMP_USE_LEGACY_SUPERVISOR_DATA) {
    if (!TEMP_DEV_SUPERVISOR_ID) {
      return Promise.reject(new Error("Temporary supervisor ID is not configured."));
    }
    return createSupervisorStudent(TEMP_DEV_SUPERVISOR_ID, payload);
  }
  return request(
    "/me/students",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not create student.",
  );
}

export function getStudent(studentId) {
  return request(`/students/${encodeURIComponent(studentId)}`, {}, "Could not load student details.");
}

export function updateStudentEmail(studentId, email) {
  return request(
    `/students/${encodeURIComponent(studentId)}/email`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    },
    "Could not save student email.",
  );
}

export function createStudent(payload) {
  return request(
    "/students",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not create student.",
  );
}

export function assignStudentToSupervisor(supervisorId, studentId, assignmentRole = "primary_supervisor") {
  return request(
    `/supervisors/${encodeURIComponent(supervisorId)}/students/${encodeURIComponent(studentId)}/assign`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assignment_role: assignmentRole }),
    },
    "Could not assign student to supervisor.",
  );
}

export function getStudentProposals(studentId) {
  return request(
    `/students/${encodeURIComponent(studentId)}/proposals`,
    {},
    "Could not load student proposals.",
  );
}

export function createStudentProposal(studentId, payload) {
  return request(
    `/students/${encodeURIComponent(studentId)}/proposals`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not create proposal.",
  );
}

export function getProposal(proposalId) {
  return request(`/proposals/${encodeURIComponent(proposalId)}`, {}, "Could not load proposal.");
}

export function deleteProposal(proposalId, supervisorId = TEMP_DEV_SUPERVISOR_ID) {
  return request(
    `/proposals/${encodeURIComponent(proposalId)}?supervisor_id=${encodeURIComponent(supervisorId || "")}`,
    { method: "DELETE" },
    "Could not delete proposal.",
  );
}

export function getProposalVersions(proposalId) {
  return request(
    `/proposals/${encodeURIComponent(proposalId)}/versions`,
    {},
    "Could not load proposal versions.",
  );
}

export function getProposalImprovement(proposalId) {
  return request(
    `/proposals/${encodeURIComponent(proposalId)}/improvement`,
    {},
    "Could not load proposal improvement tracking.",
  );
}

export function createProposalVersion(proposalId, payload) {
  return request(
    `/proposals/${encodeURIComponent(proposalId)}/versions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not create proposal version.",
  );
}

export function createRevisedProposalVersion(proposalId, payload) {
  return request(
    `/proposals/${encodeURIComponent(proposalId)}/revised-versions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        supervisor_id: payload.supervisor_id || TEMP_DEV_SUPERVISOR_ID,
      }),
    },
    "Could not create revised proposal version.",
  );
}

export function getProposalVersion(versionId) {
  return request(`/versions/${encodeURIComponent(versionId)}`, {}, "Could not load proposal version.");
}

export function getVersionAnalyses(versionId) {
  return request(`/versions/${encodeURIComponent(versionId)}/analyses`, {}, "Could not load linked analyses.");
}

export function getVersionGradings(versionId) {
  return request(`/versions/${encodeURIComponent(versionId)}/gradings`, {}, "Could not load gradings.");
}

export function getVersionSupervisorReviews(versionId) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/supervisor-reviews`,
    {},
    "Could not load supervisor reviews.",
  );
}

export function saveVersionSupervisorReview(versionId, payload) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/supervisor-reviews`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not save supervisor review.",
  );
}

export function saveMyVersionSupervisorReview(versionId, payload) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/my-supervisor-review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "Could not save supervisor review.",
  );
}

export function linkVersionAnalysis(versionId, analysisId) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/analyses/link`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId }),
    },
    "Could not link this analysis to the proposal version.",
  );
}

export async function getVersionReviewDraft(versionId, analysisId) {
  try {
    return await request(
      `/versions/${encodeURIComponent(versionId)}/review-draft?analysis_id=${encodeURIComponent(analysisId)}`,
      {},
      "Could not load AI supervisor review draft.",
    );
  } catch (error) {
    if (error.message === "AI supervisor review draft not found.") {
      return null;
    }
    throw error;
  }
}

export async function generateVersionReviewDraft(versionId, analysisId) {
  const response = await fetch(`${API_BASE_URL}/versions/${encodeURIComponent(versionId)}/review-draft`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId }),
  });

  if (!response.ok) {
    let detail = "AI review draft generation failed.";
    try {
      const payload = await response.json();
      detail = payload.detail || payload.message || detail;
    } catch {
      const text = await response.text();
      detail = text || detail;
    }
    if (response.status === 404 && detail === "Not Found") {
      detail = "Review draft endpoint is unavailable. Restart FastAPI so the current supervisor routes are loaded.";
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export function downloadSupervisorFinalFeedbackPdf(versionId, analysisId, supervisorId = TEMP_DEV_SUPERVISOR_ID) {
  return pdfDownloadRequest(
    `/versions/${encodeURIComponent(versionId)}/final-feedback.pdf?analysis_id=${encodeURIComponent(analysisId || "")}&supervisor_id=${encodeURIComponent(supervisorId || "")}`,
    "Could not generate final feedback PDF.",
  );
}

export function getFeedbackDelivery(versionId, analysisId, supervisorId = TEMP_DEV_SUPERVISOR_ID) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/feedback-delivery?analysis_id=${encodeURIComponent(analysisId || "")}&supervisor_id=${encodeURIComponent(supervisorId || "")}`,
    {},
    "Could not load feedback delivery state.",
  );
}

export function sendFeedbackToStudent(versionId, analysisId, supervisorId = TEMP_DEV_SUPERVISOR_ID) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/send-feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        analysis_id: analysisId,
        supervisor_id: supervisorId,
      }),
    },
    "Could not send feedback to the student.",
  );
}

export function getReviewOutcome(versionId, analysisId, supervisorId = TEMP_DEV_SUPERVISOR_ID) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/review-outcome?analysis_id=${encodeURIComponent(analysisId || "")}&supervisor_id=${encodeURIComponent(supervisorId || "")}`,
    {},
    "Could not load review outcome.",
  );
}

export function saveReviewOutcome(versionId, payload) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/review-outcome`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        supervisor_id: payload.supervisor_id || TEMP_DEV_SUPERVISOR_ID,
      }),
    },
    "Could not save review outcome.",
  );
}

export async function getSupervisorReviewDraft(versionId, analysisId, supervisorId = TEMP_DEV_SUPERVISOR_ID) {
  try {
    return await request(
      `/versions/${encodeURIComponent(versionId)}/supervisor-review-draft?analysis_id=${encodeURIComponent(analysisId)}&supervisor_id=${encodeURIComponent(supervisorId || "")}`,
      {},
      "Could not load supervisor review draft.",
    );
  } catch (error) {
    if (error.message === "Supervisor review draft not found.") {
      return null;
    }
    throw error;
  }
}

export function saveSupervisorReviewDraft(versionId, payload) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/supervisor-review-draft`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        supervisor_id: payload.supervisor_id || TEMP_DEV_SUPERVISOR_ID,
      }),
    },
    "Could not save supervisor review draft.",
  );
}

export function analyzeProposalVersion(versionId) {
  return request(
    `/versions/${encodeURIComponent(versionId)}/analyze`,
    { method: "POST" },
    "Could not analyze this proposal version.",
  );
}
