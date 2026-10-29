import React, { useEffect, useState } from 'react';
import {
  CheckSquare,
  AlertTriangle,
  CheckCircle,
  Eye,
  Edit3,
  Save,
  RefreshCw,
  Search,
  Check,
  X,
  Sliders,
  Award,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  Cpu,
  HelpCircle,
  FileSearch,
  FileText,
  Clock,
  History,
} from 'lucide-react';
import { api } from '../api';

export default function EvaluationReview({
  activeExam,
  setActiveExam,
  activeSheet,
  setActiveSheet,
  activeEval,
  setActiveEval,
  onNavigate,
}) {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(activeExam?.id || '');
  const [reviews, setReviews] = useState([]);
  const [selectedEval, setSelectedEval] = useState(activeEval || null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Filter tabs: 'flagged' or 'all'
  const [tab, setTab] = useState('flagged');

  // Inspector tab: 'breakdown' | 'evidence' | 'feedback' | 'audit'
  const [inspectTab, setInspectTab] = useState('breakdown');

  // Override Modal state
  const [overrideModal, setOverrideModal] = useState(false);
  const [teacherMarks, setTeacherMarks] = useState('');
  const [teacherComments, setTeacherComments] = useState('');
  const [teacherFeedbackText, setTeacherFeedbackText] = useState('');
  const [savingOverride, setSavingOverride] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Load exams
  useEffect(() => {
    api.getExams()
      .then((data) => {
        setExams(data);
        if (!selectedExamId && data.length > 0) {
          const init = activeExam || data[0];
          setSelectedExamId(init.id);
          if (!activeExam && setActiveExam) setActiveExam(init);
        }
      })
      .catch(console.error);
  }, []);

  const fetchReviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getPendingReviews(selectedExamId || null);
      setReviews(data);

      if (data.length > 0) {
        if (activeEval) {
          const matched = data.find((d) => d.id === activeEval.id);
          setSelectedEval(matched || data[0]);
        } else if (!selectedEval) {
          setSelectedEval(data[0]);
        } else {
          const updated = data.find((d) => d.id === selectedEval.id);
          if (updated) setSelectedEval(updated);
        }
      } else {
        setSelectedEval(null);
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch review queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
    if (selectedExamId && setActiveExam) {
      const found = exams.find((e) => e.id === parseInt(selectedExamId));
      if (found) setActiveExam(found);
    }
  }, [selectedExamId]);

  const filteredReviews = reviews.filter((r) => {
    if (tab === 'flagged') return r.is_flagged || !r.is_reviewed;
    return true;
  });

  const currentIndex = filteredReviews.findIndex((r) => r.id === selectedEval?.id);

  const handlePrev = () => {
    if (currentIndex > 0) {
      const prev = filteredReviews[currentIndex - 1];
      setSelectedEval(prev);
      if (setActiveEval) setActiveEval(prev);
    }
  };

  const handleNext = () => {
    if (currentIndex >= 0 && currentIndex < filteredReviews.length - 1) {
      const next = filteredReviews[currentIndex + 1];
      setSelectedEval(next);
      if (setActiveEval) setActiveEval(next);
    }
  };

  const handleOpenOverride = (ev) => {
    setSelectedEval(ev);
    const existing = ev.teacher_feedback?.teacher_marks ?? ev.marks_awarded;
    setTeacherMarks(existing.toString());
    setTeacherComments(ev.teacher_feedback?.comments || '');
    setTeacherFeedbackText(ev.teacher_feedback?.feedback || ev.feedback || '');
    setModalError(null);
    setOverrideModal(true);
  };

  const handleSaveOverride = async () => {
    if (!selectedEval) return;
    const num = parseFloat(teacherMarks);
    if (isNaN(num) || num < 0.0 || num > selectedEval.max_marks) {
      setModalError(`Awarded marks must be between 0.0 and ${selectedEval.max_marks}.`);
      return;
    }

    try {
      setSavingOverride(true);
      setModalError(null);
      const updated = await api.overrideEvaluation(selectedEval.id, {
        teacher_id: 1,
        teacher_marks: num,
        teacher_feedback: teacherFeedbackText,
        comments: teacherComments || 'Teacher verified and approved marks.',
      });
      setSuccessMsg(`Marks updated to ${num} / ${selectedEval.max_marks} for Evaluation #${selectedEval.id}.`);
      setSelectedEval(updated);
      setOverrideModal(false);
      await fetchReviews();
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err) {
      setModalError(err.message || 'Failed to submit mark override.');
    } finally {
      setSavingOverride(false);
    }
  };

  const isLLM = selectedEval?.evaluation_method?.includes('LLM');
  const isOverridden = !!selectedEval?.teacher_feedback;
  const finalScore = isOverridden ? selectedEval.teacher_feedback.teacher_marks : selectedEval?.marks_awarded;

  return (
    <div>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)' }}>
            Evaluation & Teacher Review Studio
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Detailed criterion rubric verification, extracted answer evidence quotes, and teacher mark authorizations
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <select
            className="input"
            style={{ width: '220px', padding: '6px 12px', fontSize: '13px' }}
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

          <button className="btn btn-secondary btn-sm" onClick={fetchReviews} title="Refresh records">
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

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

      {/* Main Grid: Left Queue, Right Detail */}
      <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '24px' }}>
        {/* Left Column: Script Selection Queue */}
        <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '700' }}>
              Evaluation Records
            </h3>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              {filteredReviews.length} records
            </span>
          </div>

          {/* Filter Tabs */}
          <div style={{ display: 'flex', gap: '4px', backgroundColor: 'var(--bg-subtle)', padding: '3px', borderRadius: 'var(--radius-md)', marginBottom: '12px' }}>
            <button
              className={`btn btn-sm ${tab === 'flagged' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, border: 'none', padding: '4px 8px', fontSize: '11px' }}
              onClick={() => setTab('flagged')}
            >
              Pending ({reviews.filter((r) => r.is_flagged || !r.is_reviewed).length})
            </button>
            <button
              className={`btn btn-sm ${tab === 'all' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, border: 'none', padding: '4px 8px', fontSize: '11px' }}
              onClick={() => setTab('all')}
            >
              All ({reviews.length})
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '720px', overflowY: 'auto' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                <RefreshCw size={18} className="spin" style={{ margin: '0 auto 8px' }} />
                <p style={{ fontSize: '12px' }}>Loading queue...</p>
              </div>
            ) : filteredReviews.length > 0 ? (
              filteredReviews.map((ev) => {
                const isSelected = selectedEval?.id === ev.id;
                const isEvLLM = ev.evaluation_method?.includes('LLM');
                const hasOver = !!ev.teacher_feedback;

                return (
                  <div
                    key={ev.id}
                    onClick={() => {
                      setSelectedEval(ev);
                      if (setActiveEval) setActiveEval(ev);
                    }}
                    style={{
                      padding: '12px',
                      borderRadius: 'var(--radius-md)',
                      border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-color)',
                      backgroundColor: isSelected ? 'var(--primary-subtle)' : '#ffffff',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                        {ev.student_identifier || `Script #${ev.sheet_id}`}
                      </strong>
                      <span
                        className={`badge ${
                          ev.confidence_score >= 0.8
                            ? 'badge-success'
                            : ev.confidence_score >= 0.6
                            ? 'badge-warning'
                            : 'badge-danger'
                        }`}
                        style={{ fontSize: '10.5px' }}
                      >
                        {Math.round(ev.confidence_score * 100)}%
                      </span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Question {ev.question_number || `Q${ev.question_id}`}
                      </span>
                      <span style={{ fontSize: '12px', fontWeight: '700', color: hasOver ? '#1d4ed8' : '#059669' }}>
                        {hasOver ? ev.teacher_feedback.teacher_marks : ev.marks_awarded} / {ev.max_marks}m
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: '6px', marginTop: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                      {ev.is_reviewed ? (
                        <span className="badge badge-success" style={{ fontSize: '10px' }}>Reviewed</span>
                      ) : (
                        <span className="badge badge-warning" style={{ fontSize: '10px' }}>Needs Audit</span>
                      )}
                      {hasOver && (
                        <span className="badge badge-info" style={{ fontSize: '10px' }}>Overridden</span>
                      )}
                      <span
                        className="badge"
                        style={{
                          fontSize: '10px',
                          backgroundColor: isEvLLM ? '#e0f2fe' : '#f1f5f9',
                          color: isEvLLM ? '#0369a1' : '#475569',
                        }}
                      >
                        {isEvLLM ? 'LLM' : 'Fallback'}
                      </span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-muted)', fontSize: '13px' }}>
                No evaluations found in this queue.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Detailed Evaluation Inspector */}
        {selectedEval ? (
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {/* Header / Summary Bar */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-color)', backgroundColor: '#ffffff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '14px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <h3 style={{ fontSize: '17px', fontWeight: '700', color: 'var(--text-primary)' }}>
                      Student {selectedEval.student_identifier || `Script #${selectedEval.sheet_id}`}
                    </h3>
                    {selectedEval.is_reviewed && (
                      <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle size={12} /> Approved
                      </span>
                    )}
                    {selectedEval.is_flagged && !selectedEval.is_reviewed && (
                      <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <AlertTriangle size={12} /> Low Confidence
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <span>Question {selectedEval.question_number || `Q${selectedEval.question_id}`}</span>
                    <span>•</span>
                    <span>Max Marks: {selectedEval.max_marks}</span>
                    <span>•</span>
                    <span
                      className="badge"
                      style={{
                        fontSize: '11px',
                        backgroundColor: isLLM ? '#e0f2fe' : '#f1f5f9',
                        color: isLLM ? '#0369a1' : '#475569',
                      }}
                    >
                      {selectedEval.evaluation_method || 'DETERMINISTIC_HEURISTIC_FALLBACK'}
                    </span>
                    <span>•</span>
                    <span>Confidence: <strong>{Math.round(selectedEval.confidence_score * 100)}%</strong></span>
                  </div>
                </div>

                {/* Score & Stepper Controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block' }}>
                      {isOverridden ? 'Final Approved Marks' : 'AI Suggested Marks'}
                    </span>
                    <div style={{ fontSize: '24px', fontWeight: '800', color: isOverridden ? '#1d4ed8' : '#059669', lineHeight: 1.2 }}>
                      {finalScore} <span style={{ fontSize: '14px', fontWeight: '500', color: 'var(--text-muted)' }}>/ {selectedEval.max_marks}</span>
                    </div>
                    {isOverridden && (
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                        (AI Suggestion: {selectedEval.marks_awarded}m)
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleOpenOverride(selectedEval)}
                      title="Edit marks or audit comments"
                    >
                      <Edit3 size={14} /> Override Marks
                    </button>
                    {onNavigate && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          if (setActiveSheet) {
                            setActiveSheet({ id: selectedEval.sheet_id, student_identifier: selectedEval.student_identifier });
                          }
                          onNavigate('ocr-review');
                        }}
                        title="Inspect handwriting OCR preview"
                      >
                        <FileSearch size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Sequential Stepper */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--border-color)', fontSize: '12px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handlePrev}
                  disabled={currentIndex <= 0}
                  style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <ArrowLeft size={13} /> Previous Script
                </button>
                <span style={{ color: 'var(--text-muted)' }}>
                  Script {currentIndex + 1} of {filteredReviews.length}
                </span>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleNext}
                  disabled={currentIndex < 0 || currentIndex >= filteredReviews.length - 1}
                  style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  Next Script <ArrowRight size={13} />
                </button>
              </div>
            </div>

            {/* Factual Contradictions Warning */}
            {selectedEval.identified_contradictions && selectedEval.identified_contradictions.length > 0 && (
              <div className="alert alert-danger" style={{ margin: '16px 24px 0', borderRadius: 'var(--radius-md)' }}>
                <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                <div>
                  <strong style={{ fontSize: '13px' }}>Identified Factual Contradictions / Hallucinations:</strong>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: '12px' }}>
                    {selectedEval.identified_contradictions.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Inspector Navigation Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', backgroundColor: 'var(--bg-subtle)', padding: '0 20px', marginTop: '16px' }}>
              <button
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: inspectTab === 'breakdown' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: inspectTab === 'breakdown' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: inspectTab === 'breakdown' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
                onClick={() => setInspectTab('breakdown')}
              >
                Criterion Rubric Breakdown
              </button>
              <button
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: inspectTab === 'evidence' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: inspectTab === 'evidence' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: inspectTab === 'evidence' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
                onClick={() => setInspectTab('evidence')}
              >
                Supporting Answer Evidence
              </button>
              <button
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: inspectTab === 'feedback' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: inspectTab === 'feedback' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: inspectTab === 'feedback' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
                onClick={() => setInspectTab('feedback')}
              >
                Student Feedback & Points
              </button>
              <button
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: inspectTab === 'audit' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: inspectTab === 'audit' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: inspectTab === 'audit' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
                onClick={() => setInspectTab('audit')}
              >
                Audit History
              </button>
            </div>

            {/* Tab Body */}
            <div style={{ padding: '20px 24px' }}>
              {/* TAB 1: CRITERION BREAKDOWN */}
              {inspectTab === 'breakdown' && (
                <div>
                  <div style={{ marginBottom: '16px', padding: '12px', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                    <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--primary)', letterSpacing: '0.5px' }}>
                      QUESTION STATEMENT:
                    </span>
                    <p style={{ fontSize: '13px', marginTop: '4px', lineHeight: '1.5' }}>
                      {selectedEval.question?.text || 'Question text unavailable.'}
                    </p>
                  </div>

                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Criterion</th>
                          <th>Allocated</th>
                          <th>Awarded</th>
                          <th>Deducted</th>
                          <th>Supporting Answer Evidence</th>
                          <th>Deduction Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(selectedEval.criterion_deductions?.length > 0
                          ? selectedEval.criterion_deductions
                          : selectedEval.criterion_deductions_json?.length > 0
                          ? selectedEval.criterion_deductions_json
                          : []
                        ).map((c, idx) => (
                          <tr key={idx}>
                            <td><strong>{c.criterion || c.name}</strong></td>
                            <td>{c.allocated_marks}m</td>
                            <td>
                              <strong style={{ color: 'var(--success)' }}>
                                {c.awarded_marks}m
                              </strong>
                            </td>
                            <td>
                              <span style={{ color: c.deducted_marks > 0 ? 'var(--danger)' : 'var(--text-muted)' }}>
                                -{c.deducted_marks}m
                              </span>
                            </td>
                            <td style={{ fontSize: '11.5px', color: c.evidence ? '#0369a1' : 'var(--text-muted)', fontStyle: c.evidence ? 'italic' : 'normal', maxWidth: '280px' }}>
                              {c.evidence ? `"${c.evidence}"` : 'No matching evidence found'}
                            </td>
                            <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                              {c.deduction_reason || c.reason || 'Criteria fully satisfied.'}
                            </td>
                          </tr>
                        ))}
                        {(!selectedEval.criterion_deductions?.length && !selectedEval.criterion_deductions_json?.length) && (
                          <tr>
                            <td colSpan="6" style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)' }}>
                              No criterion breakdown recorded.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* TAB 2: SUPPORTING ANSWER EVIDENCE */}
              {inspectTab === 'evidence' && (
                <div>
                  <div style={{ marginBottom: '16px' }}>
                    <label className="form-label" style={{ fontWeight: '600' }}>
                      Student Handwritten Answer (Extracted via PaddleOCR PP-OCRv6):
                    </label>
                    <div
                      style={{
                        padding: '14px 16px',
                        background: '#f8fafc',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '13px',
                        lineHeight: '1.6',
                        fontFamily: 'var(--font-mono)',
                        whiteSpace: 'pre-wrap',
                        maxHeight: '350px',
                        overflowY: 'auto',
                      }}
                    >
                      {selectedEval.student_answer_text || 'No answer text extracted.'}
                    </div>
                  </div>

                  <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 'var(--radius-md)', padding: '12px 16px' }}>
                    <span style={{ fontSize: '12px', fontWeight: '700', color: '#1e40af' }}>
                      Evidence Extraction Methodology
                    </span>
                    <p style={{ fontSize: '12px', color: '#1e3a8a', marginTop: '4px' }}>
                      Answer evidence quotes are extracted directly from the student's handwritten transcript using semantic alignment and concept detection. Semantic similarity scores represent keyword overlap and heuristic matching, not proof of factual correctness.
                    </p>
                  </div>
                </div>
              )}

              {/* TAB 3: STUDENT FEEDBACK & POINTS */}
              {inspectTab === 'feedback' && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                    <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 'var(--radius-md)', padding: '14px' }}>
                      <span style={{ fontSize: '12px', fontWeight: '700', color: '#166534', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Check size={14} /> Points Correctly Addressed ({selectedEval.points_addressed?.length || 0})
                      </span>
                      <ul style={{ margin: '8px 0 0 16px', padding: 0, fontSize: '12px', color: '#14532d', lineHeight: '1.4' }}>
                        {selectedEval.points_addressed && selectedEval.points_addressed.length > 0 ? (
                          selectedEval.points_addressed.map((pt, idx) => <li key={idx}>{pt}</li>)
                        ) : (
                          <li style={{ listStyle: 'none', marginLeft: '-16px', color: '#6b7280' }}>No specific rubric points verified.</li>
                        )}
                      </ul>
                    </div>

                    <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 'var(--radius-md)', padding: '14px' }}>
                      <span style={{ fontSize: '12px', fontWeight: '700', color: '#92400e', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <AlertTriangle size={14} /> Missing Expected Points ({selectedEval.missing_points?.length || 0})
                      </span>
                      <ul style={{ margin: '8px 0 0 16px', padding: 0, fontSize: '12px', color: '#78350f', lineHeight: '1.4' }}>
                        {selectedEval.missing_points && selectedEval.missing_points.length > 0 ? (
                          selectedEval.missing_points.map((pt, idx) => <li key={idx}>{pt}</li>)
                        ) : (
                          <li style={{ listStyle: 'none', marginLeft: '-16px', color: '#6b7280' }}>All expected points covered.</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <div>
                      <label className="form-label" style={{ fontWeight: '600' }}>AI Suggested Student Feedback:</label>
                      <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', padding: '12px', borderRadius: 'var(--radius-md)', fontSize: '13px', minHeight: '80px' }}>
                        {selectedEval.feedback || 'No feedback recorded.'}
                      </div>
                    </div>
                    <div>
                      <label className="form-label" style={{ fontWeight: '600' }}>Improvement Suggestions:</label>
                      <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', padding: '12px', borderRadius: 'var(--radius-md)', fontSize: '13px', minHeight: '80px' }}>
                        {selectedEval.improvement_suggestions || 'Continue practicing comprehensive diagrams and technical keywords.'}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: AUDIT HISTORY */}
              {inspectTab === 'audit' && (
                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <History size={16} /> Evaluation Audit Trail
                  </h4>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {/* Initial AI Evaluation */}
                    <div style={{ padding: '12px 16px', background: '#f8fafc', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: '600', fontSize: '13px' }}>AI Initial Evaluation</span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Method: {selectedEval.evaluation_method || 'DETERMINISTIC'}
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', marginTop: '6px', color: 'var(--text-secondary)' }}>
                        Suggested Score: <strong>{selectedEval.marks_awarded} / {selectedEval.max_marks}</strong> (Confidence: {Math.round(selectedEval.confidence_score * 100)}%)
                      </div>
                    </div>

                    {/* Teacher Override if present */}
                    {isOverridden ? (
                      <div style={{ padding: '12px 16px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 'var(--radius-md)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: '700', fontSize: '13px', color: '#1d4ed8' }}>
                            Teacher Mark Authorization & Override
                          </span>
                          <span className="badge badge-info" style={{ fontSize: '10px' }}>
                            Authorized
                          </span>
                        </div>
                        <div style={{ fontSize: '13px', marginTop: '6px', color: '#1e3a8a' }}>
                          Final Authorized Marks: <strong>{selectedEval.teacher_feedback.teacher_marks} / {selectedEval.max_marks}</strong>
                        </div>
                        {selectedEval.teacher_feedback.comments && (
                          <div style={{ fontSize: '12px', marginTop: '4px', color: '#334155' }}>
                            <strong>Audit Comments:</strong> {selectedEval.teacher_feedback.comments}
                          </div>
                        )}
                        {selectedEval.teacher_feedback.feedback && (
                          <div style={{ fontSize: '12px', marginTop: '4px', color: '#334155' }}>
                            <strong>Teacher Feedback:</strong> {selectedEval.teacher_feedback.feedback}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', background: '#fafafa', borderRadius: 'var(--radius-md)' }}>
                        No teacher overrides recorded. Click "Override Marks" to adjust the score and record an audit log.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <Award size={48} style={{ color: 'var(--text-muted)', marginBottom: '16px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '6px' }}>
              No Evaluation Selected
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Select an evaluation record from the queue on the left to inspect criterion scoring and rubric evidence.
            </p>
          </div>
        )}
      </div>

      {/* Teacher Override Modal */}
      {overrideModal && selectedEval && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '540px' }}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit3 size={18} color="var(--primary)" />
                <h3 style={{ fontSize: '16px', fontWeight: '700' }}>
                  Override Evaluation Marks
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
                    Student: {selectedEval.student_identifier || `Script #${selectedEval.sheet_id}`}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Question: {selectedEval.question_number || `Q${selectedEval.question_id}`}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    AI Score: {selectedEval.marks_awarded} / {selectedEval.max_marks}
                  </div>
                  <div style={{ fontSize: '12px', color: '#10b981', fontWeight: '600' }}>
                    Max: {selectedEval.max_marks} Marks
                  </div>
                </div>
              </div>

              <div>
                <label className="form-label" style={{ fontWeight: '600', fontSize: '13px', display: 'block', marginBottom: '6px' }}>
                  Final Teacher Marks (Permitted: 0.0 to {selectedEval.max_marks}) *
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  max={selectedEval.max_marks}
                  className="input"
                  style={{ width: '100%', fontSize: '16px', fontWeight: '700' }}
                  value={teacherMarks}
                  onChange={(e) => setTeacherMarks(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="form-label" style={{ fontWeight: '600', fontSize: '13px', display: 'block', marginBottom: '6px' }}>
                  Audit Reason / Teacher Rationale *
                </label>
                <input
                  type="text"
                  className="input"
                  style={{ width: '100%', fontSize: '13px' }}
                  placeholder="e.g. Valid diagram and alternate derivation recognized"
                  value={teacherComments}
                  onChange={(e) => setTeacherComments(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="form-label" style={{ fontWeight: '600', fontSize: '13px', display: 'block', marginBottom: '6px' }}>
                  Teacher Revised Student Feedback
                </label>
                <textarea
                  className="input"
                  rows={3}
                  style={{ width: '100%', fontSize: '13px' }}
                  placeholder="Student guidance..."
                  value={teacherFeedbackText}
                  onChange={(e) => setTeacherFeedbackText(e.target.value)}
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
                disabled={savingOverride || teacherMarks === ''}
              >
                <Save size={14} />
                <span>{savingOverride ? 'Saving...' : 'Authorize & Save Override'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
