import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BookOpenCheck, Download, FileUp, GitCompareArrows, LoaderCircle, Send, Trash2, TriangleAlert } from "lucide-react";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.mjs?url";
import FeedbackCard from "../components/FeedbackCard";
import KnowledgeGraph from "../components/KnowledgeGraph";
import RecommendationCard from "../components/RecommendationCard";
import {
  analyzeText,
  createKnowledgeGraph,
  createProposalVersion,
  createRevisedProposalVersion,
  createStudentProposal,
  deleteProposal,
  getProposalVersions,
  getStudent,
  getStudentProposals,
  getFeedbackDelivery,
  getSupervisorReviewDraft,
  getReviewOutcome,
  getVersionAnalyses,
  getVersionReviewDraft,
  getVersionSupervisorReviews,
  gradeReport,
  linkVersionAnalysis,
  recommendResources,
  runLLMReview,
  downloadSupervisorFinalFeedbackPdf,
  generateVersionReviewDraft,
  saveSupervisorReviewDraft,
  saveReviewOutcome,
  sendFeedbackToStudent,
} from "../api";
import { generateAndDownloadReport } from "../reportDownload";
import LLMIssueCard from "../components/LLMIssueCard";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

function reviewOutcomeLabel(outcome) {
  if (outcome?.status === "COMPLETE") return "Complete";
  if (outcome?.status === "REVISION_REQUESTED") return "Revision Requested";
  if (outcome?.label) return outcome.label;
  return "Awaiting Supervisor Decision";
}

function titleFromPdfFilename(filename = "") {
  return filename
    .replace(/\.pdf$/i, "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function listToMultiline(items = []) {
  return (items || []).join("\n");
}

function multilineToList(value = "") {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function editableDraftFromContent(content = {}, supervisorComments = "") {
  return {
    overall_assessment: content.overall_assessment || "",
    strengths: listToMultiline(content.strengths || []),
    areas_requiring_improvement: listToMultiline(content.areas_requiring_improvement || []),
    methodology_feedback: content.methodology_feedback || "",
    evaluation_validation_feedback: content.evaluation_validation_feedback || "",
    recommendations: listToMultiline(content.recommendations || []),
    suggested_revision_instructions: listToMultiline(content.suggested_revision_instructions || []),
    supervisor_comments: supervisorComments || "",
  };
}

export default function Analyzer({ backendOnline, currentSupervisor, refreshData, notify }) {
  const { studentId: routeStudentId } = useParams();
  const analysisInFlightRef = useRef(false);
  const [text, setText] = useState("");
  const [studentName, setStudentName] = useState("");
  const [studentId, setStudentId] = useState("");
  const [contextStudent, setContextStudent] = useState(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState("");
  const [currentProposal, setCurrentProposal] = useState(null);
  const [proposalVersions, setProposalVersions] = useState([]);
  const [proposalContextLoading, setProposalContextLoading] = useState(false);
  const [proposalContextError, setProposalContextError] = useState("");
  const [savingFirstProposal, setSavingFirstProposal] = useState(false);
  const [deletingProposal, setDeletingProposal] = useState(false);
  const [proposalSaveStatus, setProposalSaveStatus] = useState("");
  const [linkedAnalysisId, setLinkedAnalysisId] = useState("");
  const [linkingAnalysis, setLinkingAnalysis] = useState(false);
  const [linkStatus, setLinkStatus] = useState("");
  const [linkError, setLinkError] = useState("");
  const [pendingLink, setPendingLink] = useState(null);
  const [versionAnalyses, setVersionAnalyses] = useState([]);
  const [supervisorReviews, setSupervisorReviews] = useState([]);
  const [aiReviewDraft, setAiReviewDraft] = useState(null);
  const [aiReviewDraftLoading, setAiReviewDraftLoading] = useState(false);
  const [aiReviewDraftError, setAiReviewDraftError] = useState("");
  const [supervisorReviewDraft, setSupervisorReviewDraft] = useState(null);
  const [editableReviewDraft, setEditableReviewDraft] = useState(null);
  const [reviewDraftSaving, setReviewDraftSaving] = useState(false);
  const [reviewDraftStatus, setReviewDraftStatus] = useState("");
  const [reviewDraftError, setReviewDraftError] = useState("");
  const [reviewDraftDirty, setReviewDraftDirty] = useState(false);
  const [finalFeedbackLoading, setFinalFeedbackLoading] = useState(false);
  const [finalFeedbackStatus, setFinalFeedbackStatus] = useState("");
  const [finalFeedbackError, setFinalFeedbackError] = useState("");
  const [feedbackDelivery, setFeedbackDelivery] = useState(null);
  const [feedbackDeliveryLoading, setFeedbackDeliveryLoading] = useState(false);
  const [feedbackDeliveryStatus, setFeedbackDeliveryStatus] = useState("");
  const [feedbackDeliveryError, setFeedbackDeliveryError] = useState("");
  const [reviewOutcome, setReviewOutcome] = useState(null);
  const [reviewOutcomeSaving, setReviewOutcomeSaving] = useState("");
  const [reviewOutcomeStatus, setReviewOutcomeStatus] = useState("");
  const [reviewOutcomeError, setReviewOutcomeError] = useState("");
  const [proposalTitle, setProposalTitle] = useState("");
  const [pdfFile, setPdfFile] = useState(null);
  const [result, setResult] = useState(null);
  const [graph, setGraph] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [analysisMeta, setAnalysisMeta] = useState({ source: "unknown", filename: null });
  const [grade, setGrade] = useState(null);
  const [llmReview, setLlmReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [llmLoading, setLlmLoading] = useState(false);
  const [graphLoading, setGraphLoading] = useState(false);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [gradingLoading, setGradingLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportStatus, setReportStatus] = useState("");
  const [reportError, setReportError] = useState("");
  const [reportDownload, setReportDownload] = useState(null);
  const [error, setError] = useState("");
  const [graphError, setGraphError] = useState("");
  const [llmError, setLlmError] = useState("");

  const wordCount = useMemo(() => (text.trim() ? text.trim().split(/\s+/).length : 0), [text]);
  const supervisorContextMode = Boolean(routeStudentId);
  const currentVersion = useMemo(() => proposalVersions[proposalVersions.length - 1] || null, [proposalVersions]);
  const orderedVersionAnalyses = useMemo(
    () => [...versionAnalyses].sort((first, second) => new Date(first.created_at || 0) - new Date(second.created_at || 0)),
    [versionAnalyses],
  );
  const currentVersionAnalyzed = orderedVersionAnalyses.length > 0 || Boolean(linkedAnalysisId);
  const latestLinkedAnalysisId = orderedVersionAnalyses[orderedVersionAnalyses.length - 1]?.analysis_id || "";
  const currentAnalysisId = linkedAnalysisId || latestLinkedAnalysisId;
  const proposalWorkflowState = currentVersionAnalyzed
    ? "Analyzed"
    : currentVersion
      ? "Ready for Analysis"
      : "No proposal submitted yet";
  const canDownloadReport = Boolean(
    result
      && (result.retrieved_feedback || []).length
      && graph
      && !graphLoading
      && !graphError,
  );
  const aiDraftGenerated = Boolean(aiReviewDraft?.draft);
  const supervisorReviewSaved = Boolean(supervisorReviewDraft);
  const finalFeedbackReady = Boolean(currentVersionAnalyzed && aiDraftGenerated && supervisorReviewSaved && !reviewDraftDirty);
  const feedbackSent = feedbackDelivery?.status === "SENT";
  const finalFeedbackDisabledReason = !currentVersionAnalyzed
    ? "Analyze the current proposal version first."
    : !aiDraftGenerated
      ? "Generate the AI review draft first."
      : (!supervisorReviewSaved || reviewDraftDirty)
        ? "Save the supervisor review before generating the final feedback PDF."
        : "";
  const reviewOutcomeComplete = reviewOutcome?.status === "COMPLETE";
  const revisionRequested = reviewOutcome?.status === "REVISION_REQUESTED";
  const reviewOutcomeDisabledReason = !finalFeedbackReady
    ? finalFeedbackDisabledReason
    : "";
  const canUploadRevisedProposal = Boolean(supervisorContextMode && currentProposal && currentVersion && revisionRequested && !reviewOutcomeComplete);

  async function extractPdfText(file) {
    const data = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data }).promise;
    const pages = [];
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const content = await page.getTextContent();
      pages.push(content.items.map((item) => item.str).join(" "));
    }
    const extracted = pages.join("\n\n").trim();
    if (!extracted) throw new Error("Unable to extract readable text from this PDF.");
    return extracted;
  }

  function resetSupervisorReviewDraftState() {
    setAiReviewDraft(null);
    setAiReviewDraftError("");
    setSupervisorReviewDraft(null);
    setEditableReviewDraft(null);
    setReviewDraftStatus("");
    setReviewDraftError("");
    setReviewDraftDirty(false);
    setFinalFeedbackStatus("");
    setFinalFeedbackError("");
    setFeedbackDelivery(null);
    setFeedbackDeliveryStatus("");
    setFeedbackDeliveryError("");
    setReviewOutcome(null);
    setReviewOutcomeStatus("");
    setReviewOutcomeError("");
  }

  function updateEditableReviewDraft(field, value) {
    setEditableReviewDraft((draft) => ({ ...(draft || editableDraftFromContent()), [field]: value }));
    setReviewDraftDirty(true);
    setReviewDraftStatus("");
    setFinalFeedbackStatus("");
    setFeedbackDeliveryStatus("");
    setReviewOutcomeStatus("");
  }

  async function loadStudentProposalContext(studentDbId) {
    setProposalContextLoading(true);
    setProposalContextError("");
    try {
      const proposals = await getStudentProposals(studentDbId);
      const proposal = (proposals || [])[0] || null;
      setCurrentProposal(proposal);
      if (!proposal) {
        setProposalVersions([]);
        setLinkedAnalysisId("");
        setVersionAnalyses([]);
        setSupervisorReviews([]);
        resetSupervisorReviewDraftState();
        return;
      }
      setProposalTitle(proposal.title || "");
      const versions = await getProposalVersions(proposal.proposal_id);
      setProposalVersions(versions || []);
    } catch (loadError) {
      const message = loadError.message || "Could not load proposal context.";
      setProposalContextError(message);
      notify?.(message, "error");
    } finally {
      setProposalContextLoading(false);
    }
  }

  async function loadSupervisorReviewState(versionId) {
    if (!versionId || !backendOnline) return;
    try {
      const [analysesPayload, reviewsPayload] = await Promise.all([
        getVersionAnalyses(versionId),
        getVersionSupervisorReviews(versionId),
      ]);
      const orderedAnalyses = [...(analysesPayload || [])].sort(
        (first, second) => new Date(first.created_at || 0) - new Date(second.created_at || 0),
      );
      setVersionAnalyses(orderedAnalyses);
      setSupervisorReviews(reviewsPayload || []);
      const latestAnalysisId = orderedAnalyses.at(-1)?.analysis_id || "";
      setLinkedAnalysisId(latestAnalysisId);
      resetSupervisorReviewDraftState();
      if (latestAnalysisId) {
        const draft = await getVersionReviewDraft(versionId, latestAnalysisId);
        setAiReviewDraft(draft);
        if (!draft?.draft) {
          setReviewDraftStatus("Status: Not generated for the current linked analysis.");
          return;
        }
        const savedDraft = await getSupervisorReviewDraft(
          versionId,
          latestAnalysisId,
          currentSupervisor?.supervisor_id,
        );
        setSupervisorReviewDraft(savedDraft);
        setEditableReviewDraft(
          savedDraft?.draft
            ? editableDraftFromContent(savedDraft.draft, savedDraft.supervisor_comments)
            : editableDraftFromContent(draft.draft),
        );
        setReviewDraftDirty(false);
        setReviewDraftStatus(savedDraft?.draft ? "Status: Supervisor review saved." : "Status: AI draft generated. Supervisor edits not saved yet.");
        if (savedDraft?.draft) {
          const delivery = await getFeedbackDelivery(
            versionId,
            latestAnalysisId,
            currentSupervisor?.supervisor_id,
          );
          setFeedbackDelivery(delivery);
          const outcome = await getReviewOutcome(
            versionId,
            latestAnalysisId,
            currentSupervisor?.supervisor_id,
          );
          setReviewOutcome(outcome);
        }
      }
    } catch (loadError) {
      const message = loadError.message || "Could not load supervisor review state.";
      setReviewOutcomeError(message);
      notify?.(message, "error");
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadContextStudent() {
      if (!routeStudentId) {
        setContextStudent(null);
        setContextError("");
        setContextLoading(false);
        setCurrentProposal(null);
        setProposalVersions([]);
        setProposalContextError("");
        setProposalContextLoading(false);
        setProposalSaveStatus("");
        setLinkedAnalysisId("");
        setLinkStatus("");
        setLinkError("");
        setPendingLink(null);
        setVersionAnalyses([]);
        setSupervisorReviews([]);
        resetSupervisorReviewDraftState();
        return;
      }

      setContextLoading(true);
      setContextError("");
      setProposalSaveStatus("");
      setLinkedAnalysisId("");
      setLinkStatus("");
      setLinkError("");
      setPendingLink(null);
      setVersionAnalyses([]);
      setSupervisorReviews([]);
      resetSupervisorReviewDraftState();
      try {
        const student = await getStudent(routeStudentId);
        if (cancelled) return;
        setContextStudent(student);
        setStudentName(student.full_name || "");
        setStudentId(student.academic_student_id || "");
        await loadStudentProposalContext(student.student_id);
      } catch (loadError) {
        if (cancelled) return;
        const message = loadError.message || "Could not load selected student.";
        setContextStudent(null);
        setStudentName("");
        setStudentId("");
        setCurrentProposal(null);
        setProposalVersions([]);
        setContextError(message);
        notify?.(message, "error");
      } finally {
        if (!cancelled) {
          setContextLoading(false);
        }
      }
    }

    loadContextStudent();
    return () => {
      cancelled = true;
    };
  }, [routeStudentId, notify]);

  useEffect(() => {
    setVersionAnalyses([]);
    setSupervisorReviews([]);
    resetSupervisorReviewDraftState();
    if (supervisorContextMode && currentVersion?.version_id && backendOnline) {
      loadSupervisorReviewState(currentVersion.version_id);
    }
  }, [backendOnline, currentSupervisor?.supervisor_id, currentVersion?.version_id, supervisorContextMode]);

  function handlePdfSelection(event) {
    const selectedFile = event.target.files?.[0] || null;
    setPdfFile(selectedFile);

    if (supervisorContextMode && !currentProposal && selectedFile && !proposalTitle.trim()) {
      const derivedTitle = titleFromPdfFilename(selectedFile.name);
      if (derivedTitle) {
        setProposalTitle(derivedTitle);
      }
    }
  }

  async function saveFirstProposalVersion() {
    if (!supervisorContextMode || !contextStudent) return;
    if (currentVersion) {
      setError("A first proposal version already exists. Revised proposal upload will be enabled in the next integration step.");
      return;
    }
    if (!pdfFile) {
      setError("Select a PDF before saving the first proposal.");
      return;
    }
    const title = proposalTitle.trim();
    if (!title) {
      setError("Enter a proposal title before saving the first proposal.");
      notify?.("Proposal title is required before saving V1.", "error");
      return;
    }

    setSavingFirstProposal(true);
    setError("");
    setProposalContextError("");
    setProposalSaveStatus("Extracting proposal PDF...");
    try {
      const extracted = await extractPdfText(pdfFile);
      setText(extracted);

      let proposal = currentProposal;
      if (!proposal) {
        setProposalSaveStatus("Creating proposal record...");
        proposal = await createStudentProposal(contextStudent.student_id, { title });
        setCurrentProposal(proposal);
      }

      const existingVersions = proposal ? await getProposalVersions(proposal.proposal_id) : [];
      if ((existingVersions || []).length) {
        setProposalVersions(existingVersions || []);
        setProposalTitle(proposal.title || title);
        setProposalSaveStatus("First proposal version already exists. Ready for analysis.");
        return;
      }

      setProposalSaveStatus("Saving first proposal version...");
      const version = await createProposalVersion(proposal.proposal_id, {
        original_filename: pdfFile.name,
        source_type: "pdf",
        extracted_text: extracted,
      });
      await loadStudentProposalContext(contextStudent.student_id);
      setProposalSaveStatus(`Saved ${pdfFile.name} as V${version.version_number}. Ready for analysis.`);
      notify?.("First proposal saved as V1. Ready for analysis.", "success");
    } catch (saveError) {
      const message = saveError.message || "Could not save the first proposal.";
      setProposalContextError(message);
      setError(message);
      setProposalSaveStatus("");
      notify?.(message, "error");
      if (contextStudent?.student_id) {
        await loadStudentProposalContext(contextStudent.student_id);
      }
    } finally {
      setSavingFirstProposal(false);
    }
  }

  async function saveRevisedProposalVersion() {
    if (!supervisorContextMode || !contextStudent || !currentProposal || !currentVersion) return;
    if (!canUploadRevisedProposal) {
      const message = "Request revision on the current proposal version before uploading a revised proposal.";
      setError(message);
      notify?.(message, "error");
      return;
    }
    if (!pdfFile) {
      setError("Select a revised PDF before saving the revised proposal.");
      return;
    }

    setSavingFirstProposal(true);
    setError("");
    setProposalContextError("");
    setProposalSaveStatus("Extracting revised proposal PDF...");
    try {
      const extracted = await extractPdfText(pdfFile);
      setText(extracted);
      setResult(null);
      setGrade(null);
      setGraph(null);
      setRecommendations([]);
      setLlmReview(null);
      setLinkedAnalysisId("");
      setLinkStatus("");
      setLinkError("");
      setPendingLink(null);
      setVersionAnalyses([]);
      setSupervisorReviews([]);
      resetSupervisorReviewDraftState();

      setProposalSaveStatus("Saving revised proposal version...");
      const version = await createRevisedProposalVersion(currentProposal.proposal_id, {
        original_filename: pdfFile.name,
        source_type: "pdf",
        extracted_text: extracted,
        supervisor_id: currentSupervisor?.supervisor_id,
      });
      await loadStudentProposalContext(contextStudent.student_id);
      setProposalSaveStatus(`Saved ${pdfFile.name} as V${version.version_number}. Ready for analysis.`);
      notify?.(`Revised proposal saved as V${version.version_number}. Ready for analysis.`, "success");
    } catch (saveError) {
      const message = saveError.message || "Could not save the revised proposal.";
      setProposalContextError(message);
      setError(message);
      setProposalSaveStatus("");
      notify?.(message, "error");
      if (contextStudent?.student_id) {
        await loadStudentProposalContext(contextStudent.student_id);
      }
    } finally {
      setSavingFirstProposal(false);
    }
  }

  async function deleteCurrentProposal() {
    if (!supervisorContextMode || !currentProposal || !contextStudent) return;
    const confirmed = window.confirm(
      "Delete this proposal? This will remove its saved proposal versions and workflow links/reviews. The student record will remain.",
    );
    if (!confirmed) return;

    setDeletingProposal(true);
    setError("");
    setProposalContextError("");
    setProposalSaveStatus("");
    try {
      await deleteProposal(currentProposal.proposal_id, currentSupervisor?.supervisor_id);
      setCurrentProposal(null);
      setProposalVersions([]);
      setPdfFile(null);
      setText("");
      setResult(null);
      setGrade(null);
      setGraph(null);
      setRecommendations([]);
      setLlmReview(null);
      setLinkedAnalysisId("");
      setLinkStatus("");
      setLinkError("");
      setPendingLink(null);
      setVersionAnalyses([]);
      setSupervisorReviews([]);
      resetSupervisorReviewDraftState();
      await loadStudentProposalContext(contextStudent.student_id);
      await refreshData();
      notify?.("Proposal deleted. The student remains ready for a fresh first proposal.", "success");
    } catch (deleteError) {
      const message = deleteError.message || "Could not delete proposal.";
      setProposalContextError(message);
      setError(message);
      notify?.(message, "error");
    } finally {
      setDeletingProposal(false);
    }
  }

  async function runAnalysis(sourceText, source, filename = null) {
    if (analysisInFlightRef.current) return;
    const cleaned = sourceText.trim();
    if (!backendOnline) {
      const message = "Could not analyze proposal. Please check that the backend is running and try again.";
      setError(message);
      notify?.(message, "error");
      return;
    }
    if (!cleaned) {
      const message = "Paste proposal text or upload a readable PDF before analyzing.";
      setError(message);
      notify?.("Missing input text. Add proposal content before analysis.", "error");
      return;
    }
    if (supervisorContextMode && (!contextStudent || contextError)) {
      const message = "Load a valid selected student before analyzing in supervisor context.";
      setError(message);
      notify?.(message, "error");
      return;
    }
    if (supervisorContextMode && !currentVersion) {
      const message = "Save this PDF as the first proposal version before running analysis.";
      setError(message);
      notify?.(message, "error");
      return;
    }

    const analysisId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    analysisInFlightRef.current = true;
    setLoading(true);
    setError("");
    setGraph(null);
    setGraphError("");
    setRecommendations([]);
    setGrade(null);
    setLlmReview(null);
    setResult(null);
    setReportLoading(false);
    setReportStatus("");
    setReportError("");
    setReportDownload(null);
    setLinkStatus("");
    setLinkError("");
    setPendingLink(null);

    try {
      const payload = await analyzeText(cleaned, {
        analysis_id: analysisId,
        request_id: analysisId,
        source,
        filename,
        student_name: studentName.trim() || null,
        student_id: studentId.trim() || null,
        proposal_title: proposalTitle.trim() || null,
      });
      setResult(payload);
      setRecommendations(payload.recommended_resources || []);
      const resolvedAnalysisId = payload.analysis_id || analysisId;
      setAnalysisMeta({ source, filename, analysis_id: resolvedAnalysisId });
      setGraphLoading(true);
      createKnowledgeGraph(cleaned, {
        filename,
        analysis_id: resolvedAnalysisId,
      })
        .then((graphPayload) => {
          setGraph(graphPayload);
        })
        .catch((graphRequestError) => {
          setGraphError(graphRequestError.message);
          notify?.("Knowledge graph generation failed. The main analysis is still available.", "error");
        })
        .finally(() => setGraphLoading(false));

      setLlmLoading(true);
      runLLMReview(cleaned, "llm_rag_criteria", 5)
        .then((payload) => {
          setLlmReview(payload.review || payload);
        })
        .catch((err) => {
          setLlmError(err.message);
          notify?.("Autonomous LLM review failed. Legacy results are available.", "error");
        })
        .finally(() => setLlmLoading(false));

      try {
        const gradePayload = await gradeReport(cleaned, {
          source,
          filename,
          analysis_id: resolvedAnalysisId,
        });
        setGrade(gradePayload);
      } catch (gradingError) {
        console.error("Structure evidence failed after analysis.", gradingError);
        notify?.("Structure evidence was not generated. The main analysis is still available.", "error");
        if (supervisorContextMode) {
          throw gradingError;
        }
      }
      if (supervisorContextMode && currentVersion?.version_id) {
        try {
          setLinkingAnalysis(true);
          await linkVersionAnalysis(currentVersion.version_id, resolvedAnalysisId);
          setLinkedAnalysisId(resolvedAnalysisId);
          setPendingLink(null);
          setLinkStatus("Analysis linked to current version.");
          await loadSupervisorReviewState(currentVersion.version_id);
        } catch (linkRequestError) {
          const message = linkRequestError.message || "Analysis completed, but the proposal version could not be linked.";
          setLinkError(message);
          setPendingLink({ versionId: currentVersion.version_id, analysisId: resolvedAnalysisId });
          notify?.("Analysis completed, but the proposal version could not be linked.", "error");
        } finally {
          setLinkingAnalysis(false);
        }
      }
      await refreshData();
      notify?.("Proposal analysis completed successfully.", "success");
    } catch (requestError) {
      const message = requestError.message || "Could not analyze proposal. Please check that the backend is running and try again.";
      setError(message);
      notify?.("Could not analyze proposal. Please check that the backend is running and try again.", "error");
    } finally {
      analysisInFlightRef.current = false;
      setLoading(false);
    }
  }

  async function retryAnalysisLink() {
    if (!pendingLink) return;
    setLinkingAnalysis(true);
    setLinkError("");
    try {
      await linkVersionAnalysis(pendingLink.versionId, pendingLink.analysisId);
      setLinkedAnalysisId(pendingLink.analysisId);
      setPendingLink(null);
      setLinkStatus("Analysis linked to current version.");
      await loadSupervisorReviewState(pendingLink.versionId);
      notify?.("Analysis linked to proposal version.", "success");
    } catch (linkRequestError) {
      const message = linkRequestError.message || "Could not link this analysis to the proposal version.";
      setLinkError(message);
      notify?.(message, "error");
    } finally {
      setLinkingAnalysis(false);
    }
  }

  async function generateAiSupervisorReviewDraft() {
    if (!supervisorContextMode) return;
    if (!currentVersion?.version_id) {
      const message = "No proposal version is selected for AI review draft generation.";
      setAiReviewDraftError(message);
      notify?.(message, "error");
      return;
    }
    if (!currentAnalysisId) {
      const message = "No linked analysis found for the current version. Analyze the current proposal version first.";
      setAiReviewDraftError(message);
      notify?.(message, "error");
      return;
    }
    setAiReviewDraftLoading(true);
    setAiReviewDraftError("");
    setReviewDraftStatus("");
    try {
      const draft = await generateVersionReviewDraft(currentVersion.version_id, currentAnalysisId);
      setAiReviewDraft(draft);
      setSupervisorReviewDraft(null);
      setEditableReviewDraft(editableDraftFromContent(draft.draft));
      setReviewDraftDirty(false);
      setReviewDraftStatus("Status: AI draft generated. Supervisor edits not saved yet.");
      notify?.("AI supervisor review draft generated.", "success");
    } catch (draftError) {
      const message = draftError.message || "Could not generate AI supervisor review draft.";
      setAiReviewDraftError(message);
      notify?.(message, "error");
    } finally {
      setAiReviewDraftLoading(false);
    }
  }

  async function saveEditedSupervisorReviewDraft() {
    if (!supervisorContextMode || !currentVersion?.version_id || !currentAnalysisId || !editableReviewDraft) return;
    setReviewDraftSaving(true);
    setReviewDraftError("");
    setReviewDraftStatus("");
    try {
      const saved = await saveSupervisorReviewDraft(currentVersion.version_id, {
        analysis_id: currentAnalysisId,
        supervisor_id: currentSupervisor?.supervisor_id,
        overall_assessment: editableReviewDraft.overall_assessment,
        strengths: multilineToList(editableReviewDraft.strengths),
        areas_requiring_improvement: multilineToList(editableReviewDraft.areas_requiring_improvement),
        methodology_feedback: editableReviewDraft.methodology_feedback,
        evaluation_validation_feedback: editableReviewDraft.evaluation_validation_feedback,
        recommendations: multilineToList(editableReviewDraft.recommendations),
        suggested_revision_instructions: multilineToList(editableReviewDraft.suggested_revision_instructions),
        supervisor_comments: editableReviewDraft.supervisor_comments,
      });
      setSupervisorReviewDraft(saved);
      setEditableReviewDraft(editableDraftFromContent(saved.draft, saved.supervisor_comments));
      setReviewDraftDirty(false);
      setReviewDraftStatus("Review draft saved.");
      setFinalFeedbackStatus("");
      setFinalFeedbackError("");
      const delivery = await getFeedbackDelivery(
        currentVersion.version_id,
        currentAnalysisId,
        currentSupervisor?.supervisor_id,
      );
      setFeedbackDelivery(delivery);
      setFeedbackDeliveryStatus("");
      setFeedbackDeliveryError("");
      notify?.("Supervisor review draft saved.", "success");
    } catch (saveError) {
      const message = saveError.message || "Could not save supervisor review draft.";
      setReviewDraftError(message);
      notify?.(message, "error");
    } finally {
      setReviewDraftSaving(false);
    }
  }

  async function downloadFinalFeedbackReport() {
    if (!supervisorContextMode || !currentVersion?.version_id || !currentAnalysisId || !finalFeedbackReady) {
      const message = finalFeedbackDisabledReason || "Final feedback PDF is not ready yet.";
      setFinalFeedbackError(message);
      notify?.(message, "error");
      return;
    }

    setFinalFeedbackLoading(true);
    setFinalFeedbackStatus("");
    setFinalFeedbackError("");
    try {
      const report = await downloadSupervisorFinalFeedbackPdf(
        currentVersion.version_id,
        currentAnalysisId,
        currentSupervisor?.supervisor_id,
      );
      setFinalFeedbackStatus(`Final feedback PDF generated: ${report.filename}`);
      notify?.("Final feedback PDF generated.", "success");
    } catch (downloadError) {
      const message = downloadError.message || "Could not generate final feedback PDF.";
      setFinalFeedbackError(message);
      notify?.(message, "error");
    } finally {
      setFinalFeedbackLoading(false);
    }
  }

  async function sendFinalFeedback() {
    if (!supervisorContextMode || !currentVersion?.version_id || !currentAnalysisId || !finalFeedbackReady) {
      const message = finalFeedbackDisabledReason || "Final feedback is not ready to send.";
      setFeedbackDeliveryError(message);
      notify?.(message, "error");
      return;
    }
    if (feedbackSent) {
      const sentAt = feedbackDelivery?.sent_at || feedbackDelivery?.created_at || "the recorded delivery time";
      const message = `This feedback was already sent on ${sentAt}.`;
      setFeedbackDeliveryError(message);
      notify?.(message, "error");
      return;
    }

    const recipient = contextStudent?.email || feedbackDelivery?.recipient_email || "";
    if (!recipient) {
      const message = "Student email is not available.";
      setFeedbackDeliveryError(message);
      notify?.(message, "error");
      return;
    }
    const versionLabel = `V${currentVersion.version_number}`;
    const confirmed = window.confirm(`Send final feedback to ${recipient}?\n\nThis will email the supervisor-approved feedback PDF for ${versionLabel}.`);
    if (!confirmed) return;

    setFeedbackDeliveryLoading(true);
    setFeedbackDeliveryStatus("");
    setFeedbackDeliveryError("");
    try {
      const delivery = await sendFeedbackToStudent(
        currentVersion.version_id,
        currentAnalysisId,
        currentSupervisor?.supervisor_id,
      );
      setFeedbackDelivery(delivery);
      setFeedbackDeliveryStatus(`Feedback sent successfully to ${delivery.recipient_email}.`);
      notify?.("Feedback sent successfully.", "success");
    } catch (sendError) {
      const message = sendError.message || "Could not send feedback to the student.";
      setFeedbackDeliveryError(message);
      notify?.(message, "error");
      try {
        const delivery = await getFeedbackDelivery(
          currentVersion.version_id,
          currentAnalysisId,
          currentSupervisor?.supervisor_id,
        );
        setFeedbackDelivery(delivery);
      } catch {
        // Keep the send failure visible if delivery state cannot be refreshed.
      }
    } finally {
      setFeedbackDeliveryLoading(false);
    }
  }

  async function recordReviewOutcome(decision) {
    if (!supervisorContextMode || !currentVersion?.version_id || !currentAnalysisId) {
      const message = "Analyze the current proposal version before recording the review outcome.";
      setReviewOutcomeError(message);
      notify?.(message, "error");
      return;
    }
    if (!finalFeedbackReady) {
      const message = reviewOutcomeDisabledReason || "Complete the feedback report workflow before recording the review outcome.";
      setReviewOutcomeError(message);
      notify?.(message, "error");
      return;
    }
    const label = decision === "COMPLETE_REVIEW" ? "complete this review" : "request a revision";
    const confirmed = window.confirm(`Confirm you want to ${label} for V${currentVersion.version_number}?`);
    if (!confirmed) return;

    setReviewOutcomeSaving(decision);
    setReviewOutcomeStatus("");
    setReviewOutcomeError("");
    try {
      const outcome = await saveReviewOutcome(currentVersion.version_id, {
        analysis_id: currentAnalysisId,
        supervisor_id: currentSupervisor?.supervisor_id,
        decision,
        comments: editableReviewDraft?.supervisor_comments || null,
      });
      await loadSupervisorReviewState(currentVersion.version_id);
      setReviewOutcome(outcome);
      setReviewOutcomeStatus(`Review outcome saved: ${reviewOutcomeLabel(outcome)}.`);
      await refreshData();
      notify?.(`Review outcome saved: ${reviewOutcomeLabel(outcome)}.`, "success");
    } catch (saveError) {
      const message = saveError.message || "Could not save review outcome.";
      setReviewOutcomeError(message);
      notify?.(message, "error");
    } finally {
      setReviewOutcomeSaving("");
    }
  }

  async function analyzePdf() {
    if (supervisorContextMode && currentVersion?.extracted_text) {
      setText(currentVersion.extracted_text);
      await runAnalysis(currentVersion.extracted_text, currentVersion.source_type || "pdf", currentVersion.original_filename || null);
      return;
    }
    if (!pdfFile) {
      setError("Select a PDF before using Analyze Uploaded Proposal.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const extracted = await extractPdfText(pdfFile);
      setText(extracted);
      await runAnalysis(extracted, "pdf", pdfFile.name);
    } catch (pdfError) {
      const message = pdfError.message || "Could not read the uploaded PDF.";
      setError(message);
      notify?.("PDF extraction failed. Upload a readable PDF or paste the proposal text.", "error");
      setLoading(false);
    }
  }

  async function generateRecommendations() {
    if (!result?.input_text) return;
    setRecommendationLoading(true);
    setError("");
    try {
      const feedbackContext = (result.retrieved_feedback || []).map((item) => item.comment_text || "").join(" ");
      const payload = await recommendResources(result.input_text, feedbackContext, {
        analysis_id: result.analysis_id || analysisMeta.analysis_id || null,
      });
      setRecommendations(payload.resources || []);
      await refreshData();
      notify?.("Learning resources generated successfully.", "success");
    } catch (requestError) {
      setError(requestError.message);
      notify?.("Could not generate learning resources. Please try again.", "error");
    } finally {
      setRecommendationLoading(false);
    }
  }

  async function generateSemanticGrade() {
    if (!result?.input_text) return;
    setGradingLoading(true);
    setError("");
    try {
      const payload = await gradeReport(result.input_text, {
        ...analysisMeta,
        analysis_id: result.analysis_id || analysisMeta.analysis_id || null,
      });
      setGrade(payload);
      await refreshData();
      notify?.("Structure evidence generated successfully.", "success");
    } catch (requestError) {
      setError(requestError.message);
      notify?.("Could not generate structure evidence. Please try again.", "error");
    } finally {
      setGradingLoading(false);
    }
  }

  async function downloadFeedbackReport() {
    if (!canDownloadReport) return;
    setReportLoading(true);
    setReportStatus("");
    setReportError("");
    setReportDownload(null);
    setError("");
    try {
      const payload = {
        analysis_id: result.analysis_id || analysisMeta.analysis_id || null,
        student_name: studentName.trim() || result.student_name || null,
        student_id: studentId.trim() || result.student_id || null,
        proposal_title: proposalTitle.trim() || result.proposal_title || null,
        filename: analysisMeta.filename || null,
        source: analysisMeta.source || "unknown",
        input_text: result.input_text,
        predicted_tag: result.predicted_tag,
        feedback: result.retrieved_feedback || [],
        knowledge_graph: {
          concepts: graph?.concepts || [],
          edges: graph?.edges || [],
          missing_concepts: graph?.missing_concepts || [],
        },
        recommendations,
        semantic_grade: grade
          ? {
              predicted_score: grade.predicted_score,
              max_score: grade.max_score,
              percentage_score: grade.percentage_score,
              score_label: grade.score_label,
              section_scores: grade.section_scores || {},
              model_status: grade.model_status,
              warning: grade.warning,
            }
          : null,
        proposal_completeness: grade?.proposal_completeness || null,
        submission_readiness: grade?.submission_readiness || null,
        final_proposal_assessment: grade?.final_proposal_assessment || null,
      };
      const response = await generateAndDownloadReport(payload);
      setReportStatus("Feedback report generated successfully.");
      setReportDownload(response);
      notify?.("Feedback report generated successfully.", "success");
    } catch (requestError) {
      console.error("Could not generate feedback report.", requestError);
      setReportStatus("");
      setReportError("Could not generate feedback report. Please try again.");
      setError(requestError.message);
      notify?.("Could not generate feedback report. Please try again.", "error");
    } finally {
      setReportLoading(false);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">{supervisorContextMode ? "Supervisor Analyzer" : "Analyzer"}</span>
          <h2>{supervisorContextMode ? "Analyzing Proposal" : "Proposal input and AI mentorship"}</h2>
          <p>{supervisorContextMode ? "Use the existing Analyzer with selected student context." : "Submit student proposal text or a PDF to the real backend models."}</p>
        </div>
      </div>

      {supervisorContextMode && (
        <article className="workspace-panel">
          <div className="workspace-panel-header">
            <div>
              <span className="eyebrow">Selected Student</span>
              <strong>{contextStudent?.full_name || "Loading student..."}</strong>
            </div>
            {contextLoading && <LoaderCircle className="spin" size={18} />}
          </div>
          {contextStudent ? (
            <div className="result-summary selected-student-grid">
              <article><span>Student</span><strong>{contextStudent.full_name}</strong></article>
              <article><span>Academic Student ID</span><strong>{contextStudent.academic_student_id}</strong></article>
              <article className="student-email-card"><span>Email</span><strong>{contextStudent.email || "No email saved"}</strong></article>
              <article><span>Program</span><strong>{contextStudent.program || "-"}</strong></article>
              <article><span>Cohort</span><strong>{contextStudent.cohort || "-"}</strong></article>
              <article className="student-proposal-card"><span>Current Proposal</span><strong>{currentProposal?.title || "No proposal submitted yet"}</strong></article>
              <article><span>Current Version</span><strong>{currentVersion ? `V${currentVersion.version_number}` : "None"}</strong></article>
              <article><span>Analysis State</span><strong className="workflow-status neutral">{proposalWorkflowState}</strong></article>
            </div>
          ) : (
            <p className={contextError ? "error-text" : "muted"}>
              {contextError || "Loading selected student context..."}
            </p>
          )}
          {proposalContextLoading && <p className="muted">Loading proposal context...</p>}
          {proposalContextError && <p className="error-text">{proposalContextError}</p>}
          {!proposalContextLoading && !currentProposal && !currentVersion && (
            <p className="muted">No proposal submitted yet. Upload a PDF, review the proposal title, then save the first proposal.</p>
          )}
          {currentProposal && routeStudentId && (
            <div className="supervisor-action-row">
              <Link className="secondary-button compact-button" to={`/students/${routeStudentId}/proposals/${currentProposal.proposal_id}/improvement`}>
                <GitCompareArrows size={15} />
                View Improvement
              </Link>
              <button
                className="secondary-button compact-button"
                type="button"
                onClick={deleteCurrentProposal}
                disabled={deletingProposal || !backendOnline}
              >
                {deletingProposal ? <LoaderCircle className="spin" size={15} /> : <Trash2 size={15} />}
                {deletingProposal ? "Deleting..." : "Delete Proposal"}
              </button>
            </div>
          )}
        </article>
      )}

      <article className="input-card analyzer-input-card">
        <div className="section-title compact">
          <div>
            <span className="eyebrow">Proposal Quality Analyzer</span>
            <h2>Analyze proposal text</h2>
          </div>
          <span className="word-pill">{wordCount} words</span>
        </div>
        <div className="student-meta-grid">
          <label>
            <span>Proposal title</span>
            <input
              type="text"
              value={proposalTitle}
              onChange={(event) => setProposalTitle(event.target.value)}
              placeholder="Enter proposal title"
            />
          </label>
          <label>
            <span>Student name</span>
            <input
              type="text"
              value={studentName}
              onChange={(event) => setStudentName(event.target.value)}
              placeholder="Enter student name"
              readOnly={supervisorContextMode}
            />
          </label>
          <label>
            <span>Student ID</span>
            <input
              type="text"
              value={studentId}
              onChange={(event) => setStudentId(event.target.value)}
              placeholder="Enter student ID"
              readOnly={supervisorContextMode}
            />
          </label>
        </div>
        
        {!backendOnline && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>Backend Offline. Please start the FastAPI server before analyzing proposals.</span>
          </div>
        )}
        <div className="action-row">
          {(!supervisorContextMode || !currentVersion || canUploadRevisedProposal) && (
            <label className="secondary-button upload-control">
              <FileUp size={17} />
              {canUploadRevisedProposal ? "Upload Revised Proposal" : "Upload PDF"}
              <input type="file" accept=".pdf,application/pdf" onChange={handlePdfSelection} />
            </label>
          )}
          {supervisorContextMode && !currentVersion && (
            <button
              className="secondary-button"
              type="button"
              onClick={saveFirstProposalVersion}
              disabled={savingFirstProposal || !pdfFile || !backendOnline || !contextStudent || contextLoading || proposalContextLoading || Boolean(contextError)}
            >
              {savingFirstProposal ? <LoaderCircle className="spin" size={17} /> : <FileUp size={17} />}
              {savingFirstProposal ? "Saving First Proposal..." : "Save as First Proposal"}
            </button>
          )}
          {supervisorContextMode && currentProposal && currentVersion && canUploadRevisedProposal && pdfFile && (
            <button
              className="secondary-button"
              type="button"
              onClick={saveRevisedProposalVersion}
              disabled={savingFirstProposal || !backendOnline || !contextStudent || contextLoading || proposalContextLoading || Boolean(contextError)}
            >
              {savingFirstProposal ? <LoaderCircle className="spin" size={17} /> : <FileUp size={17} />}
              {savingFirstProposal ? "Saving Revised Proposal..." : "Save as Revised Proposal"}
            </button>
          )}
          <button
            className="primary-button"
            type="button"
            onClick={analyzePdf}
            disabled={
              loading
                || !backendOnline
                || (supervisorContextMode
                  ? (!contextStudent || contextLoading || contextError || !currentVersion)
                  : !pdfFile)
            }
          >
            {loading ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}
            {supervisorContextMode ? "Analyze Current Version" : "Analyze Uploaded PDF"}
          </button>
        </div>
        {pdfFile && <p className="selected-file">Selected PDF: {pdfFile.name}</p>}
        {proposalSaveStatus && <p className="success-text">{proposalSaveStatus}</p>}
        {linkingAnalysis && <p className="muted">Linking analysis to current version...</p>}
        {linkStatus && <p className="success-text">{linkStatus}</p>}
        {linkError && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>{linkError}</span>
            {pendingLink && (
              <button className="secondary-button compact-button" type="button" onClick={retryAnalysisLink} disabled={linkingAnalysis}>
                Retry Link
              </button>
            )}
          </div>
        )}
        {error && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>{error}</span>
          </div>
        )}
      </article>

      {result && (
        <section className="results-card">
          <div className="section-title compact">
            <div>
              <span className="eyebrow">Proposal Overview</span>
              <h2>{currentProposal?.title || proposalTitle || "Analysis output"}</h2>
            </div>
            <span className="tag-pill">{result.predicted_tag}</span>
          </div>

          <div className="result-summary">
            <article>
              <span>Identified Weakness</span>
              <strong>{result.predicted_tag}</strong>
            </article>
            <article>
              <span>Retrieved Feedback</span>
              <strong>{(result.retrieved_feedback || []).length}</strong>
            </article>
            <article>
              <span>Recommendations</span>
              <strong>{recommendations.length}</strong>
            </article>
            {supervisorContextMode && currentVersion && (
              <article>
                <span>Proposal Version</span>
                <strong>V{currentVersion.version_number}</strong>
              </article>
            )}
          </div>

          <div className="feedback-grid">
            {(result.retrieved_feedback || []).map((item, index) => (
              <FeedbackCard key={`${index}-${item.comment_text}`} item={item} index={index} />
            ))}
          </div>

          <div className="section-title compact analyzer-section-spacer">
            <div>
              <span className="eyebrow">Generated Review</span>
              <h2>Autonomous reviewer</h2>
            </div>
          </div>
          
          {llmLoading ? (
            <div className="empty-state">
              <LoaderCircle className="spin inline-loader-icon" size={24} />
              <p>The autonomous reviewer is reading your proposal and retrieving grading criteria...</p>
            </div>
          ) : llmError ? (
            <div className="error-card">
              <TriangleAlert size={18} />
              <span>{llmError}</span>
            </div>
          ) : llmReview ? (
            <>
              <div className="grading-card completeness-card llm-overview-card">
                <p><strong>Overall Assessment: </strong>{llmReview.overall_assessment}</p>
              </div>
              <div className="feedback-grid">
                {(llmReview.issues || []).map((issue, index) => (
                  <LLMIssueCard key={`${index}-${issue.issue_id}`} issue={issue} index={index} />
                ))}
              </div>
            </>
          ) : null}

          <KnowledgeGraph graph={graph} loading={graphLoading} error={graphError} />

          <div className="grading-block">
            {gradingLoading && (
              <article className="generate-card">
                <div>
                  <strong>Checking proposal structure</strong>
                  <span>Preparing missing-section evidence for supervisor review.</span>
                </div>
                <LoaderCircle className="spin" size={17} />
              </article>
            )}
            {grade?.proposal_completeness && (
              <article className="grading-card completeness-card">
                <div className="section-title compact">
                  <div>
                    <span className="eyebrow">Structure Check</span>
                    <h2>Missing Sections</h2>
                  </div>
                </div>
                <div className="result-summary">
                  <article>
                    <span>Missing Sections</span>
                    <strong>{(grade.proposal_completeness.missing_sections || grade.missing_sections || []).length}</strong>
                  </article>
                </div>
                <div className="missing-section-list">
                  {(grade.proposal_completeness.missing_sections || grade.missing_sections || []).length ? (
                    (grade.proposal_completeness.missing_sections || grade.missing_sections || []).map((section) => <span key={section}>Missing: {section}</span>)
                  ) : (
                    <span>All essential proposal sections detected.</span>
                  )}
                </div>
              </article>
            )}
          </div>

          <div className="recommendation-block">
            {!recommendations.length ? (
              <article className="generate-card">
                <div>
                  <strong>Generate personalized learning resources</strong>
                  <span>Recommendations are shown only after this real backend call.</span>
                </div>
                <button className="primary-button" type="button" onClick={generateRecommendations} disabled={recommendationLoading}>
                  {recommendationLoading ? <LoaderCircle className="spin" size={17} /> : <BookOpenCheck size={17} />}
                  {recommendationLoading ? "Generating resources..." : "Generate Recommendations"}
                </button>
              </article>
            ) : (
              <div className="recommendation-grid">
                {recommendations.map((resource, index) => (
                  <RecommendationCard key={`${index}-${resource.title}`} resource={resource} />
                ))}
              </div>
            )}
          </div>

        </section>
      )}

      {supervisorContextMode && currentVersion && (
        <article className="workspace-panel analyzer-workflow-panel">
          <div className="workspace-panel-header">
            <div>
              <span className="eyebrow">AI Supervisor Review Draft</span>
              <strong>{aiReviewDraft ? "Generated feedback draft" : "Generate structured feedback"}</strong>
            </div>
            <span className="tag-pill">V{currentVersion.version_number}</span>
          </div>
          {currentAnalysisId && <p className="muted">Current analysis: {currentAnalysisId}</p>}
          {!aiReviewDraft && reviewDraftStatus && <p className="muted">{reviewDraftStatus}</p>}
          {!aiReviewDraft && (
            <div className="generate-card">
              <div>
                <strong>Generate AI Review Draft</strong>
                <span>Create a saved, structured draft from this version's linked analysis evidence.</span>
              </div>
              <button
                className="primary-button"
                type="button"
                onClick={generateAiSupervisorReviewDraft}
                disabled={aiReviewDraftLoading || !currentAnalysisId}
              >
                {aiReviewDraftLoading ? <LoaderCircle className="spin" size={17} /> : null}
                {aiReviewDraftLoading ? "Generating..." : "Generate AI Review Draft"}
              </button>
              {!currentAnalysisId && <p className="muted">Analyze the current proposal version first.</p>}
            </div>
          )}
          {aiReviewDraftError && <p className="error-text">{aiReviewDraftError}</p>}
          {aiReviewDraft?.draft && (
            <>
              <details className="review-draft-block">
                <summary>View Original AI Draft</summary>
                <section>
                  <span className="eyebrow">Overall Assessment</span>
                  <p>{aiReviewDraft.draft.overall_assessment}</p>
                </section>
                <section>
                  <span className="eyebrow">Strengths</span>
                  <ul>{(aiReviewDraft.draft.strengths || []).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
                </section>
                <section>
                  <span className="eyebrow">Areas Requiring Improvement</span>
                  <ul>{(aiReviewDraft.draft.areas_requiring_improvement || []).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
                </section>
                <section>
                  <span className="eyebrow">Methodology Feedback</span>
                  <p>{aiReviewDraft.draft.methodology_feedback}</p>
                </section>
                <section>
                  <span className="eyebrow">Evaluation / Validation Feedback</span>
                  <p>{aiReviewDraft.draft.evaluation_validation_feedback}</p>
                </section>
                <section>
                  <span className="eyebrow">Recommendations</span>
                  <ul>{(aiReviewDraft.draft.recommendations || []).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
                </section>
                <section>
                  <span className="eyebrow">Suggested Revision Instructions</span>
                  <ul>{(aiReviewDraft.draft.suggested_revision_instructions || []).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
                </section>
              </details>

              {editableReviewDraft && (
              <div className="workspace-form review-edit-form">
                  <div className="section-title compact">
                    <div>
                      <span className="eyebrow">Supervisor Review Draft</span>
                      <h2>{supervisorReviewDraft ? "Saved editable draft" : "Editable draft from AI original"}</h2>
                    </div>
                    {reviewDraftDirty && <span className="tag-pill">Unsaved changes</span>}
                  </div>
                  <label>
                    <span>Overall Assessment</span>
                    <textarea rows={4} value={editableReviewDraft.overall_assessment} onChange={(event) => updateEditableReviewDraft("overall_assessment", event.target.value)} />
                  </label>
                  <label>
                    <span>Strengths</span>
                    <textarea rows={4} value={editableReviewDraft.strengths} onChange={(event) => updateEditableReviewDraft("strengths", event.target.value)} />
                  </label>
                  <label>
                    <span>Areas Requiring Improvement</span>
                    <textarea rows={4} value={editableReviewDraft.areas_requiring_improvement} onChange={(event) => updateEditableReviewDraft("areas_requiring_improvement", event.target.value)} />
                  </label>
                  <label>
                    <span>Methodology Feedback</span>
                    <textarea rows={4} value={editableReviewDraft.methodology_feedback} onChange={(event) => updateEditableReviewDraft("methodology_feedback", event.target.value)} />
                  </label>
                  <label>
                    <span>Evaluation / Validation Feedback</span>
                    <textarea rows={4} value={editableReviewDraft.evaluation_validation_feedback} onChange={(event) => updateEditableReviewDraft("evaluation_validation_feedback", event.target.value)} />
                  </label>
                  <label>
                    <span>Recommendations</span>
                    <textarea rows={4} value={editableReviewDraft.recommendations} onChange={(event) => updateEditableReviewDraft("recommendations", event.target.value)} />
                  </label>
                  <label>
                    <span>Suggested Revision Instructions</span>
                    <textarea rows={4} value={editableReviewDraft.suggested_revision_instructions} onChange={(event) => updateEditableReviewDraft("suggested_revision_instructions", event.target.value)} />
                  </label>
                  <label>
                    <span>Supervisor Comments</span>
                    <textarea
                      rows={4}
                      value={editableReviewDraft.supervisor_comments}
                      onChange={(event) => updateEditableReviewDraft("supervisor_comments", event.target.value)}
                      placeholder="Add your own guidance for the student."
                    />
                  </label>
                  {supervisorReviewDraft?.updated_at && <p className="muted">Last saved: {new Date(supervisorReviewDraft.updated_at).toLocaleString()}</p>}
                  {reviewDraftStatus && <p className="success-text">{reviewDraftStatus}</p>}
                  {reviewDraftError && <p className="error-text">{reviewDraftError}</p>}
                  <div className="supervisor-action-row">
                    <button className="primary-button" type="button" onClick={saveEditedSupervisorReviewDraft} disabled={reviewDraftSaving}>
                      {reviewDraftSaving ? <LoaderCircle className="spin" size={16} /> : null}
                      {reviewDraftSaving ? "Saving..." : "Save Review Draft"}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
          <article className="generate-card report-download-card workflow-card">
            <div>
              <strong>Final Feedback Report</strong>
              <span>Generate the student-facing PDF from the saved supervisor-approved review and linked analysis evidence.</span>
            </div>
            <div className="result-summary workflow-status-grid">
              <article>
                <span>AI Review Draft</span>
                <strong className={`workflow-status ${aiDraftGenerated ? "success" : "neutral"}`}>{aiDraftGenerated ? "Generated" : "Not Generated"}</strong>
              </article>
              <article>
                <span>Supervisor Review</span>
                <strong className={`workflow-status ${supervisorReviewSaved && !reviewDraftDirty ? "success" : "warning"}`}>{supervisorReviewSaved && !reviewDraftDirty ? "Saved" : "Not Saved"}</strong>
              </article>
              <article>
                <span>Final Feedback PDF</span>
                <strong className={`workflow-status ${finalFeedbackReady ? "success" : "warning"}`}>{finalFeedbackReady ? "Ready" : "Not Ready"}</strong>
              </article>
              <article>
                <span>Feedback Delivery</span>
                <strong className={`workflow-status ${feedbackSent ? "success" : feedbackDelivery?.status === "FAILED" ? "warning" : "neutral"}`}>{feedbackDeliveryLoading ? "Sending..." : feedbackSent ? "Sent" : feedbackDelivery?.status === "FAILED" ? "Failed" : "Not Sent"}</strong>
              </article>
            </div>
            <button
              className="primary-button"
              type="button"
              onClick={downloadFinalFeedbackReport}
              disabled={finalFeedbackLoading || !finalFeedbackReady}
            >
              {finalFeedbackLoading ? <LoaderCircle className="spin" size={17} /> : <Download size={17} />}
              {finalFeedbackLoading ? "Generating final feedback..." : "Generate Final Feedback PDF"}
            </button>
            {!finalFeedbackReady && finalFeedbackDisabledReason && <p className="muted">{finalFeedbackDisabledReason}</p>}
            {finalFeedbackStatus && <p className="success-text">{finalFeedbackStatus}</p>}
            {finalFeedbackError && <p className="error-text">{finalFeedbackError}</p>}
            <div className="supervisor-action-row">
              <button
                className="secondary-button"
                type="button"
                onClick={sendFinalFeedback}
                disabled={feedbackDeliveryLoading || !finalFeedbackReady || feedbackSent}
              >
                {feedbackDeliveryLoading ? <LoaderCircle className="spin" size={17} /> : null}
                {feedbackDeliveryLoading ? "Sending..." : "Send Feedback"}
              </button>
            </div>
            {feedbackSent && (
              <p className="success-text">
                Feedback sent successfully. Recipient: {feedbackDelivery.recipient_email}. Sent: {feedbackDelivery.sent_at || feedbackDelivery.created_at}.
              </p>
            )}
            {!feedbackSent && finalFeedbackReady && !contextStudent?.email && <p className="muted">Student email is not available.</p>}
            {feedbackDeliveryStatus && <p className="success-text">{feedbackDeliveryStatus}</p>}
            {feedbackDeliveryError && <p className="error-text">{feedbackDeliveryError}</p>}
          </article>

          <article className="generate-card report-download-card workflow-card">
            <div>
              <strong>Review Outcome</strong>
              <span>Record the human supervisor decision for this proposal version after the final feedback workflow is ready.</span>
            </div>
            <div className="result-summary workflow-status-grid">
              <article>
                <span>Status</span>
                <strong className={`workflow-status ${reviewOutcomeComplete ? "success" : revisionRequested ? "warning" : "neutral"}`}>{reviewOutcomeLabel(reviewOutcome)}</strong>
              </article>
              <article>
                <span>Version</span>
                <strong>V{currentVersion.version_number}</strong>
              </article>
              <article>
                <span>Decision</span>
                <strong className={`workflow-status ${reviewOutcome?.decision ? "success" : "neutral"}`}>{reviewOutcome?.decision || "Not Recorded"}</strong>
              </article>
              <article>
                <span>Updated</span>
                <strong>{reviewOutcome?.updated_at ? new Date(reviewOutcome.updated_at).toLocaleString() : "Not Recorded"}</strong>
              </article>
            </div>
            {!feedbackSent && finalFeedbackReady && (
              <p className="muted">Feedback is not marked Sent. If development email is not configured, the backend can still record the outcome after the saved final review is ready.</p>
            )}
            <div className="supervisor-action-row">
              <button
                className="primary-button"
                type="button"
                onClick={() => recordReviewOutcome("COMPLETE_REVIEW")}
                disabled={Boolean(reviewOutcomeSaving) || !finalFeedbackReady || revisionRequested || reviewOutcomeComplete}
              >
                {reviewOutcomeSaving === "COMPLETE_REVIEW" ? <LoaderCircle className="spin" size={17} /> : null}
                {reviewOutcomeSaving === "COMPLETE_REVIEW" ? "Completing..." : "Complete Review"}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => recordReviewOutcome("REQUEST_REVISION")}
                disabled={Boolean(reviewOutcomeSaving) || !finalFeedbackReady || revisionRequested || reviewOutcomeComplete}
              >
                {reviewOutcomeSaving === "REQUEST_REVISION" ? <LoaderCircle className="spin" size={17} /> : null}
                {reviewOutcomeSaving === "REQUEST_REVISION" ? "Requesting..." : "Request Revision"}
              </button>
            </div>
            {!finalFeedbackReady && reviewOutcomeDisabledReason && <p className="muted">{reviewOutcomeDisabledReason}</p>}
            {reviewOutcomeComplete && <p className="success-text">Review complete for this proposal version. No revised PDF is required.</p>}
            {revisionRequested && <p className="success-text">Revision requested. Upload the revised proposal PDF above to create the next version.</p>}
            {reviewOutcomeStatus && <p className="success-text">{reviewOutcomeStatus}</p>}
            {reviewOutcomeError && <p className="error-text">{reviewOutcomeError}</p>}
          </article>
        </article>
      )}
    </section>
  );
}
