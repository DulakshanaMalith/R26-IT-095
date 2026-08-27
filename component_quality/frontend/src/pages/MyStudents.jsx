import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, FileText, LoaderCircle, RefreshCw, Trash2, UserPlus, UsersRound } from "lucide-react";
import EmptyState from "../components/EmptyState";
import Loader from "../components/Loader";
import MetricCard from "../components/MetricCard";
import Modal from "../components/Modal";
import {
  createCurrentSupervisorStudent,
  getProposalVersions,
  getStudentProposals,
  getCurrentSupervisorStudents,
  getVersionAnalyses,
  getVersionSupervisorReviews,
  removeCurrentSupervisorStudent,
} from "../api";

const initialStudentForm = {
  academic_student_id: "",
  full_name: "",
  email: "",
  program: "Information Technology",
  cohort: "2022",
};

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function sortByVersionNumber(versions) {
  if (!versions || !Array.isArray(versions)) return [];
  return [...versions].sort((first, second) => (first.version_number || 0) - (second.version_number || 0));
}

function workflowStatusClass(status) {
  if (status === "Reviewed" || status === "Analyzed") return "success";
  if (status === "Revision Requested" || status === "Ready for Analysis") return "warning";
  return "neutral";
}

export default function MyStudents({ backendOnline, backendChecked, notify }) {
  const [students, setStudents] = useState([]);
  const [studentForm, setStudentForm] = useState(initialStudentForm);
  const [showAddForm, setShowAddForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [removingStudentId, setRemovingStudentId] = useState("");
  const [studentPendingRemoval, setStudentPendingRemoval] = useState(null);
  const [error, setError] = useState("");

  const rosterSummary = useMemo(() => {
    const proposals = students.filter((student) => student.current_proposal).length;
    const analyzed = students.filter((student) => student.latest_version_analyzed).length;
    const waiting = students.filter((student) => student.current_proposal && !student.latest_version_analyzed).length;
    return { proposals, analyzed, waiting };
  }, [students]);

  async function buildStudentSummary(student) {
    try {
      const proposals = await getStudentProposals(student.student_id);
      const currentProposal = [...(proposals || [])]
        .sort((first, second) => new Date(second.updated_at || second.created_at || 0) - new Date(first.updated_at || first.created_at || 0))[0] || null;
      if (!currentProposal) {
        return { ...student, current_proposal: null, current_version: null, latest_version_analyzed: false, proposal_status: "No Proposal" };
      }
      const versions = sortByVersionNumber(await getProposalVersions(currentProposal.proposal_id));
      const currentVersion = versions[versions.length - 1] || null;
      const analyses = currentVersion ? await getVersionAnalyses(currentVersion.version_id) : [];
      const reviews = currentVersion ? await getVersionSupervisorReviews(currentVersion.version_id) : [];
      const latestReview = [...(reviews || [])]
        .sort((first, second) => new Date(second.updated_at || second.created_at || 0) - new Date(first.updated_at || first.created_at || 0))[0] || null;

      let proposalStatus = currentVersion ? "Ready for Analysis" : "No Proposal";
      if (latestReview?.decision === "REQUEST_REVISION" || latestReview?.decision === "REVISION_REQUESTED") {
        proposalStatus = "Revision Requested";
      } else if (latestReview) {
        proposalStatus = "Reviewed";
      } else if (analyses?.length) {
        proposalStatus = "Analyzed";
      }
      return {
        ...student,
        current_proposal: currentProposal,
        current_version: currentVersion,
        latest_version_analyzed: Boolean(analyses?.length),
        latest_review: latestReview,
        proposal_status: proposalStatus,
      };
    } catch (summaryError) {
      console.error("Could not load student proposal summary.", summaryError);
      return { ...student, current_proposal: null, current_version: null, latest_version_analyzed: false, proposal_status: "No Proposal" };
    }
  }

  async function loadStudents() {
    if (!backendOnline) return;
    setLoading(true);
    setError("");
    try {
      const payload = await getCurrentSupervisorStudents();
      const summarized = await Promise.all((payload || []).map(buildStudentSummary));
      setStudents(summarized);
    } catch (loadError) {
      console.error("Could not load supervisor students.", loadError);
      setError(loadError.message || "Could not load students.");
      notify?.(loadError.message || "Could not load students.", "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (backendChecked && backendOnline) {
      loadStudents();
    }
  }, [backendChecked, backendOnline]);

  async function submitStudent(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await createCurrentSupervisorStudent({
        academic_student_id: studentForm.academic_student_id.trim(),
        full_name: studentForm.full_name.trim(),
        email: studentForm.email.trim() || null,
        program: studentForm.program.trim() || null,
        cohort: studentForm.cohort.trim() || null,
      });
      setStudentForm(initialStudentForm);
      setShowAddForm(false);
      await loadStudents();
      notify?.("Student added to supervisor roster.", "success");
    } catch (saveError) {
      console.error("Could not create student.", saveError);
      const message = saveError.message?.includes("academic student ID")
        ? "A student with this academic ID already exists."
        : saveError.message || "Could not create student.";
      setError(message);
      notify?.(message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function confirmRemoveStudent() {
    if (!studentPendingRemoval) return;
    setRemovingStudentId(studentPendingRemoval.student_id);
    setError("");
    try {
      await removeCurrentSupervisorStudent(studentPendingRemoval.student_id);
      const removedName = studentPendingRemoval.full_name;
      setStudentPendingRemoval(null);
      await loadStudents();
      notify?.(`${removedName} removed from My Students. Proposal history was not deleted.`, "success");
    } catch (removeError) {
      console.error("Could not remove student from supervisor roster.", removeError);
      const message = removeError.message || "Could not remove student from supervisor roster.";
      setError(message);
      notify?.(message, "error");
    } finally {
      setRemovingStudentId("");
    }
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">My Students</span>
          <h2>Supervisor student roster</h2>
          <p>Add assigned students, view proposal state, and open the existing Analyzer for a selected student.</p>
        </div>
        <div className="supervisor-action-row compact-actions">
          <button className="secondary-button" type="button" onClick={loadStudents} disabled={loading || !backendOnline}>
            {loading ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />}
            Refresh
          </button>
          <button className="primary-button" type="button" onClick={() => setShowAddForm((visible) => !visible)} disabled={!backendOnline}>
            <UserPlus size={16} />
            Add Student
          </button>
        </div>
      </div>

      {!backendOnline && backendChecked && (
        <article className="error-card">Backend is offline. Start FastAPI with APP_DATABASE_PATH configured.</article>
      )}
      {error && <article className="error-card">{error}</article>}

      <div className="metric-grid">
        <MetricCard icon={UsersRound} label="Assigned Students" value={students.length} detail="Linked to the current supervisor" />
        <MetricCard icon={FileText} label="With Proposals" value={rosterSummary.proposals} detail="At least one proposal record" />
        <MetricCard icon={CheckCircle2} label="Analyzed Current Versions" value={rosterSummary.analyzed} detail="Latest uploaded version has analysis" />
        <MetricCard icon={RefreshCw} label="Waiting For Analysis" value={rosterSummary.waiting} detail="Proposal exists, latest version is not analyzed" />
      </div>

      <div className={showAddForm ? "supervisor-flow-grid" : "workspace-main"}>
        {showAddForm && (
        <article className="workspace-panel">
          <div className="workspace-panel-header">
            <div>
              <span className="eyebrow">Add Student</span>
              <strong>Create academic student record</strong>
            </div>
            <UserPlus size={20} />
          </div>
          <form className="workspace-form compact" onSubmit={submitStudent}>
            <label>
              Academic Student ID
              <input
                value={studentForm.academic_student_id}
                onChange={(event) => setStudentForm((form) => ({ ...form, academic_student_id: event.target.value }))}
                required
              />
            </label>
            <label>
              Full name
              <input
                value={studentForm.full_name}
                onChange={(event) => setStudentForm((form) => ({ ...form, full_name: event.target.value }))}
                required
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={studentForm.email}
                onChange={(event) => setStudentForm((form) => ({ ...form, email: event.target.value }))}
              />
            </label>
            <div className="workspace-form-row">
              <label>
                Program
                <input
                  value={studentForm.program}
                  onChange={(event) => setStudentForm((form) => ({ ...form, program: event.target.value }))}
                />
              </label>
              <label>
                Cohort
                <input
                  value={studentForm.cohort}
                  onChange={(event) => setStudentForm((form) => ({ ...form, cohort: event.target.value }))}
                />
              </label>
            </div>
            <button className="primary-button" type="submit" disabled={saving || !backendOnline}>
              {saving ? <LoaderCircle className="spin" size={16} /> : <UserPlus size={16} />}
              Save Student
            </button>
            <button className="secondary-button" type="button" onClick={() => setShowAddForm(false)} disabled={saving}>
              Cancel
            </button>
          </form>
        </article>
        )}

        <div className="workspace-main">
          {loading ? (
            <Loader />
          ) : students.length ? (
            <div className="workspace-list">
              {students.map((student) => (
                <article className="workspace-list-item student-roster-card" key={student.student_id}>
                  <div className="workspace-panel-header">
                    <div>
                      <strong>{student.full_name}</strong>
                      <span>{student.academic_student_id}</span>
                      <small>{student.email || "No email saved"}</small>
                    </div>
                    <div className="supervisor-action-row compact-actions">
                      <Link className="primary-button compact-button" to={`/students/${student.student_id}/analyze`}>
                        Analyze / Review Proposal
                        <ArrowRight size={15} />
                      </Link>
                      <button
                        className="danger-button compact-button"
                        type="button"
                        onClick={() => setStudentPendingRemoval(student)}
                        disabled={Boolean(removingStudentId) || !backendOnline}
                      >
                        {removingStudentId === student.student_id ? <LoaderCircle className="spin" size={15} /> : <Trash2 size={15} />}
                        {removingStudentId === student.student_id ? "Removing..." : "Remove Student"}
                      </button>
                    </div>
                  </div>
                  <div className="result-summary">
                    <article><span>Program</span><strong>{student.program || "-"}</strong></article>
                    <article><span>Cohort</span><strong>{student.cohort || "-"}</strong></article>
                    <article><span>Current Proposal</span><strong>{student.current_proposal?.title || "Not uploaded"}</strong></article>
                    <article><span>Current Version</span><strong>{student.current_version ? `V${student.current_version.version_number}` : "None"}</strong></article>
                    <article><span>Latest Upload</span><strong>{formatDate(student.current_version?.created_at)}</strong></article>
                    <article>
                      <span>Status</span>
                      <strong className={`workflow-status ${workflowStatusClass(student.proposal_status)}`}>{student.proposal_status || "No Proposal"}</strong>
                    </article>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={UsersRound}
              title="No students are currently assigned."
              message="Add Student creates an academic roster record for this supervisor. It does not create a student login account."
            />
          )}
        </div>
      </div>

      <Modal
        eyebrow="Remove Student"
        title={studentPendingRemoval ? `Remove ${studentPendingRemoval.full_name}?` : "Remove Student"}
        onClose={() => {
          if (!removingStudentId) setStudentPendingRemoval(null);
        }}
      >
        {studentPendingRemoval && (
          <div className="modal-stack">
            <p className="muted">
              Remove {studentPendingRemoval.full_name} from My Students? This removes the student from your supervisor roster. It will not delete the student's saved proposal/version history.
            </p>
            <div className="result-summary">
              <article><span>Student</span><strong>{studentPendingRemoval.full_name}</strong></article>
              <article><span>Academic Student ID</span><strong>{studentPendingRemoval.academic_student_id}</strong></article>
              <article><span>Current Proposal</span><strong>{studentPendingRemoval.current_proposal?.title || "Not uploaded"}</strong></article>
            </div>
            <div className="supervisor-action-row compact-actions">
              <button className="secondary-button" type="button" onClick={() => setStudentPendingRemoval(null)} disabled={Boolean(removingStudentId)}>
                Cancel
              </button>
              <button className="danger-button" type="button" onClick={confirmRemoveStudent} disabled={Boolean(removingStudentId)}>
                {removingStudentId ? <LoaderCircle className="spin" size={16} /> : <Trash2 size={16} />}
                {removingStudentId ? "Removing..." : "Remove Student"}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </section>
  );
}
