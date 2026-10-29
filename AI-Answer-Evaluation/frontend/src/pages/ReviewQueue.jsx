import React, { useEffect, useState } from 'react';
import {
  Clock,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Search,
  Filter,
  CheckSquare,
  Award,
  FileSearch,
  RefreshCw,
  Edit3,
  Sliders,
  ChevronRight,
  ShieldCheck,
  X,
  Save,
} from 'lucide-react';
import { api } from '../api';

export default function ReviewQueue({
  activeExam,
  setActiveExam,
  setActiveSheet,
  setActiveEval,
  onNavigate,
  onUpdatePendingCount,
}) {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(activeExam?.id || '');
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Status Filter: 'pending' | 'flagged' | 'reviewed' | 'all'
  const [statusFilter, setStatusFilter] = useState('pending');
  const [searchTerm, setSearchTerm] = useState('');

  // Current index for sequential progression
  const [currentIndex, setCurrentIndex] = useState(0);

  // Quick Override Modal
  const [overrideModal, setOverrideModal] = useState(false);
  const [activeItem, setActiveItem] = useState(null);
  const [overrideMarks, setOverrideMarks] = useState('');
  const [overrideFeedback, setOverrideFeedback] = useState('');
  const [overrideComments, setOverrideComments] = useState('');
  const [savingOverride, setSavingOverride] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Load exams
  useEffect(() => {
    api.getExams()
      .then((data) => {
        setExams(data);
        if (!selectedExamId && data.length > 0) {
          const initial = activeExam || data[0];
          setSelectedExamId(initial.id);
          if (!activeExam) setActiveExam(initial);
        }
      })
      .catch((err) => setError(err.message || 'Failed to fetch exams'));
  }, []);

  // Fetch reviews for selected exam
  const fetchReviews = async (examId) => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getPendingReviews(examId || null);
      setReviews(data);

      // Report pending count up for sidebar badge
      const pendingTotal = data.filter((r) => !r.is_reviewed || r.is_flagged).length;
      if (onUpdatePendingCount) onUpdatePendingCount(pendingTotal);
    } catch (err) {
      setError(err.message || 'Failed to fetch review queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews(selectedExamId);
    if (selectedExamId) {
      const found = exams.find((e) => e.id === parseInt(selectedExamId));
      if (found) setActiveExam(found);
    }
  }, [selectedExamId]);

  // Filtered reviews
  const filteredReviews = reviews.filter((r) => {
    // Status filter
    if (statusFilter === 'pending' && r.is_reviewed) return false;
    if (statusFilter === 'flagged' && !r.is_flagged) return false;
    if (statusFilter === 'reviewed' && !r.is_reviewed) return false;

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchRoll = r.student_identifier?.toLowerCase().includes(term);
      const matchQ = (r.question_number || `Q${r.question_id}`)?.toLowerCase().includes(term);
      if (!matchRoll && !matchQ) return false;
    }
    return true;
  });

  // Step through queue
  const handleNext = () => {
    if (currentIndex < filteredReviews.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  // Open full evaluation page
  const handleOpenEvaluation = (item) => {
    if (setActiveEval) setActiveEval(item);
    if (setActiveSheet) setActiveSheet({ id: item.sheet_id, student_identifier: item.student_identifier });
    if (onNavigate) onNavigate('evaluation');
  };

  // Open OCR inspection
  const handleOpenOCR = (item) => {
    if (setActiveSheet) setActiveSheet({ id: item.sheet_id, student_identifier: item.student_identifier });
    if (onNavigate) onNavigate('ocr-review');
  };

  // Quick Override
  const handleOpenOverride = (item) => {
    setActiveItem(item);
    const existingMarks = item.teacher_feedback?.teacher_marks ?? item.marks_awarded;
    setOverrideMarks(existingMarks.toString());
    setOverrideFeedback(item.teacher_feedback?.feedback || item.feedback || '');
    setOverrideComments(item.teacher_feedback?.comments || 'Teacher verified and approved marks.');
    setModalError(null);
    setOverrideModal(true);
  };

  const handleSaveOverride = async () => {
    if (!activeItem) return;
    const num = parseFloat(overrideMarks);
    if (isNaN(num) || num < 0.0 || num > activeItem.max_marks) {
      setModalError(`Awarded marks must be between 0.0 and ${activeItem.max_marks}.`);
      return;
    }

    try {
      setSavingOverride(true);
      setModalError(null);
      await api.overrideEvaluation(activeItem.id, {
        teacher_id: 1,
        teacher_marks: num,
        teacher_feedback: overrideFeedback,
        comments: overrideComments,
      });

      setSuccessMsg(`Marks updated to ${num} / ${activeItem.max_marks} for Student ${activeItem.student_identifier}.`);
      setOverrideModal(false);
      await fetchReviews(selectedExamId);
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err) {
      setModalError(err.message || 'Failed to submit mark override.');
    } finally {
      setSavingOverride(false);
    }
  };

  const pendingCount = reviews.filter((r) => !r.is_reviewed || r.is_flagged).length;
  const reviewedCount = reviews.filter((r) => r.is_reviewed).length;
  const flaggedCount = reviews.filter((r) => r.is_flagged).length;

  return (
    <div>
      {/* Review Queue Hero Banner */}
      <div className="review-queue-header">
        <div>
          <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.85, fontWeight: '700' }}>
            KTU Teacher Evaluation Queue
          </span>
          <h2 style={{ fontSize: '20px', fontWeight: '700', marginTop: '2px' }}>
            Pending Mark Approvals & Audits
          </h2>
          <p style={{ fontSize: '13px', opacity: 0.9, marginTop: '2px' }}>
            Systematically inspect AI scoring, verify criterion evidence, and authorize official grades
          </p>
        </div>

        <div className="queue-progress-group">
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '22px', fontWeight: '700' }}>
              {pendingCount}
            </div>
            <div style={{ fontSize: '11px', opacity: 0.85 }}>Pending Review</div>
          </div>
          <div style={{ width: '1px', height: '36px', backgroundColor: 'rgba(255, 255, 255, 0.25)' }} />
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '22px', fontWeight: '700' }}>
              {reviewedCount}
            </div>
            <div style={{ fontSize: '11px', opacity: 0.85 }}>Completed</div>
          </div>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success" style={{ marginBottom: '16px' }}>
          <CheckCircle size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Controls & Filter Bar */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
          {/* Exam Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)' }}>
              Examination:
            </span>
            <select
              className="input"
              style={{ width: '240px', padding: '6px 12px', fontSize: '13px' }}
              value={selectedExamId}
              onChange={(e) => setSelectedExamId(e.target.value)}
            >
              <option value="">All Examinations</option>
              {exams.map((exam) => (
                <option key={exam.id} value={exam.id}>
                  {exam.course_code ? `${exam.course_code} - ` : ''}{exam.title}
                </option>
              ))}
            </select>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => fetchReviews(selectedExamId)}
              title="Refresh queue"
            >
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
            </button>
          </div>

          {/* Filter Tabs */}
          <div style={{ display: 'flex', gap: '4px', backgroundColor: 'var(--bg-subtle)', padding: '4px', borderRadius: 'var(--radius-md)' }}>
            <button
              className={`btn btn-sm ${statusFilter === 'pending' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px', fontSize: '12px' }}
              onClick={() => setStatusFilter('pending')}
            >
              Pending ({pendingCount})
            </button>
            <button
              className={`btn btn-sm ${statusFilter === 'flagged' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px', fontSize: '12px' }}
              onClick={() => setStatusFilter('flagged')}
            >
              Flagged ({flaggedCount})
            </button>
            <button
              className={`btn btn-sm ${statusFilter === 'reviewed' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px', fontSize: '12px' }}
              onClick={() => setStatusFilter('reviewed')}
            >
              Reviewed ({reviewedCount})
            </button>
            <button
              className={`btn btn-sm ${statusFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px', fontSize: '12px' }}
              onClick={() => setStatusFilter('all')}
            >
              All ({reviews.length})
            </button>
          </div>

          {/* Search Box */}
          <div style={{ position: 'relative', width: '200px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="input"
              placeholder="Search student or Q#..."
              style={{ paddingLeft: '30px', fontSize: '13px', width: '100%' }}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Queue Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <RefreshCw size={24} className="spin" style={{ margin: '0 auto 12px' }} />
            <p style={{ fontSize: '13px' }}>Loading review records...</p>
          </div>
        ) : filteredReviews.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center' }}>
            <CheckCircle size={44} color="#10b981" style={{ margin: '0 auto 16px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '6px' }}>
              No Pending Reviews
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '420px', margin: '0 auto' }}>
              {statusFilter === 'pending'
                ? 'All submitted evaluation scores have been audited and approved by the teacher.'
                : 'No evaluations match the selected filter criteria.'}
            </p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '40px' }}>#</th>
                  <th>Student Roll</th>
                  <th>Question</th>
                  <th>AI Score</th>
                  <th>Teacher Marks</th>
                  <th>Confidence</th>
                  <th>Method</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredReviews.map((item, index) => {
                  const isOverridden = !!item.teacher_feedback;
                  const finalMarks = isOverridden ? item.teacher_feedback.teacher_marks : item.marks_awarded;

                  return (
                    <tr
                      key={item.id}
                      style={{
                        backgroundColor: item.is_flagged ? '#fffbeb' : index % 2 === 0 ? '#ffffff' : '#f8fafc',
                      }}
                    >
                      <td style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                        {index + 1}
                      </td>
                      <td>
                        <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>
                          {item.student_identifier}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Script #{item.sheet_id}
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-primary">
                          {item.question_number || `Q${item.question_id}`}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '6px' }}>
                          (Max: {item.max_marks}m)
                        </span>
                      </td>
                      <td>
                        <div style={{ fontWeight: '600', color: 'var(--text-secondary)' }}>
                          {item.marks_awarded} / {item.max_marks}
                        </div>
                      </td>
                      <td>
                        {isOverridden ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <span style={{ fontWeight: '700', color: '#1d4ed8' }}>
                              {finalMarks} / {item.max_marks}
                            </span>
                            <span
                              className="badge badge-info"
                              style={{ fontSize: '10px', padding: '1px 5px' }}
                              title={item.teacher_feedback?.comments}
                            >
                              Overridden
                            </span>
                          </div>
                        ) : item.is_reviewed ? (
                          <span style={{ fontWeight: '600', color: '#059669' }}>
                            {finalMarks} / {item.max_marks} (Confirmed)
                          </span>
                        ) : (
                          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                            Awaiting Audit
                          </span>
                        )}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            item.confidence_score >= 0.85
                              ? 'badge-success'
                              : item.confidence_score >= 0.65
                              ? 'badge-warning'
                              : 'badge-danger'
                          }`}
                          style={{ fontSize: '11px' }}
                        >
                          {Math.round(item.confidence_score * 100)}%
                        </span>
                      </td>
                      <td>
                        <span
                          style={{
                            fontSize: '11px',
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {item.evaluation_method || item.eval_type || 'DETERMINISTIC'}
                        </span>
                      </td>
                      <td>
                        {item.is_reviewed ? (
                          <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <CheckCircle size={11} /> Approved
                          </span>
                        ) : item.is_flagged ? (
                          <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <AlertTriangle size={11} /> Low Confidence
                          </span>
                        ) : (
                          <span className="badge badge-warning" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={11} /> Pending
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleOpenOCR(item)}
                            title="Inspect handwriting OCR"
                          >
                            <FileSearch size={13} />
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleOpenOverride(item)}
                            title="Quick mark override"
                          >
                            <Edit3 size={13} /> Override
                          </button>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleOpenEvaluation(item)}
                            title="Open detailed evaluation breakdown"
                          >
                            <span>Inspect</span>
                            <ArrowRight size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick Mark Override Modal */}
      {overrideModal && activeItem && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '520px' }}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit3 size={18} color="var(--primary)" />
                <h3 style={{ fontSize: '16px', fontWeight: '700' }}>
                  Teacher Mark Override
                </h3>
              </div>
              <button
                className="btn-close"
                onClick={() => setOverrideModal(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {modalError && (
                <div className="alert alert-danger">
                  <AlertTriangle size={14} />
                  <span>{modalError}</span>
                </div>
              )}

              <div
                style={{
                  backgroundColor: 'var(--bg-subtle)',
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-md)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontWeight: '700', fontSize: '14px' }}>
                    Student: {activeItem.student_identifier}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Question: {activeItem.question_number || `Q${activeItem.question_id}`}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    AI Score: {activeItem.marks_awarded} / {activeItem.max_marks}
                  </div>
                  <div style={{ fontSize: '12px', color: '#10b981', fontWeight: '600' }}>
                    Max: {activeItem.max_marks} Marks
                  </div>
                </div>
              </div>

              <div>
                <label className="form-label" style={{ fontWeight: '600', fontSize: '13px', display: 'block', marginBottom: '6px' }}>
                  Awarded Marks (0.0 to {activeItem.max_marks}):
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  max={activeItem.max_marks}
                  className="input"
                  style={{ width: '100%', fontSize: '15px', fontWeight: '600' }}
                  value={overrideMarks}
                  onChange={(e) => setOverrideMarks(e.target.value)}
                />
              </div>

              <div>
                <label className="form-label" style={{ fontWeight: '600', fontSize: '13px', display: 'block', marginBottom: '6px' }}>
                  Teacher Feedback for Student:
                </label>
                <textarea
                  className="input"
                  rows={3}
                  style={{ width: '100%', fontSize: '13px' }}
                  value={overrideFeedback}
                  onChange={(e) => setOverrideFeedback(e.target.value)}
                  placeholder="Suggestions or guidance for the student..."
                />
              </div>

              <div>
                <label className="form-label" style={{ fontWeight: '600', fontSize: '13px', display: 'block', marginBottom: '6px' }}>
                  Audit Comment / Teacher Rationale:
                </label>
                <input
                  type="text"
                  className="input"
                  style={{ width: '100%', fontSize: '13px' }}
                  value={overrideComments}
                  onChange={(e) => setOverrideComments(e.target.value)}
                  placeholder="E.g., Granted partial marks for diagram steps..."
                />
              </div>
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setOverrideModal(false)}
                disabled={savingOverride}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSaveOverride}
                disabled={savingOverride}
              >
                <Save size={14} />
                <span>{savingOverride ? 'Saving...' : 'Authorize Marks'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
