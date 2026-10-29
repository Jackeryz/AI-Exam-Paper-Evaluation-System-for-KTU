import React, { useEffect, useState } from 'react';
import {
  UploadCloud,
  FileText,
  Play,
  Eye,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Search,
  Check,
  Edit3,
  Save,
  X,
  Layers,
  Sparkles,
  Undo2,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Clock,
  SkipForward,
} from 'lucide-react';
import { api } from '../api';

export default function AnswerSheets({ activeExam, setActiveExam, setActiveSheet, onNavigate }) {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(activeExam?.id || '');
  const [answerSheets, setAnswerSheets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Upload Form State
  const [files, setFiles] = useState([]);
  const [studentRoll, setStudentRoll] = useState('');

  // Processing status trackers
  const [processingSheetId, setProcessingSheetId] = useState(null);
  const [refiningSheetId, setRefiningSheetId] = useState(null);
  const [evaluatingSheetId, setEvaluatingSheetId] = useState(null);

  // OCR Modal Inspection State
  const [inspectingSheet, setInspectingSheet] = useState(null);
  const [editedText, setEditedText] = useState('');
  const [inspectTab, setInspectTab] = useState('traceability'); // 'traceability' | 'sidebyside' | 'segmentation' | 'editor'
  const [savingCorrection, setSavingCorrection] = useState(false);
  const [editingSegmentId, setEditingSegmentId] = useState(null);
  const [segmentText, setSegmentText] = useState('');
  const [savingSegment, setSavingSegment] = useState(false);

  // Fetch all exams for dropdown
  useEffect(() => {
    api.getExams().then((data) => {
      setExams(data);
      if (!selectedExamId && data.length > 0) {
        setSelectedExamId(data[0].id);
        setActiveExam(data[0]);
      }
    }).catch(console.error);
  }, []);

  // When selected exam changes, load its answer sheets
  const fetchSheets = async (examId) => {
    if (!examId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getAnswerSheets(examId);
      setAnswerSheets(data);
    } catch (err) {
      setError(err.message || 'Failed to load answer sheets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedExamId) {
      fetchSheets(selectedExamId);
      const current = exams.find((e) => e.id === parseInt(selectedExamId));
      if (current) setActiveExam(current);
    }
  }, [selectedExamId]);

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedExamId || files.length === 0) {
      setError('Please select an examination and at least one answer sheet file.');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      setSuccessMsg(null);

      const formData = new FormData();
      files.forEach((f) => formData.append('files', f));
      if (studentRoll) formData.append('student_identifier', studentRoll);

      const res = await api.uploadAnswerSheets(selectedExamId, formData);
      setSuccessMsg(`Successfully uploaded ${res.uploaded_count || files.length} answer sheet(s).`);
      setFiles([]);
      setStudentRoll('');
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'Error uploading answer sheets.');
    } finally {
      setUploading(false);
    }
  };

  const handleProcessOCR = async (sheetId) => {
    try {
      setProcessingSheetId(sheetId);
      setError(null);
      await api.processSheetOCR(sheetId);
      setSuccessMsg(`OCR extraction completed using PaddleOCR PP-OCRv6 for Sheet #${sheetId}.`);
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'OCR processing failed.');
    } finally {
      setProcessingSheetId(null);
    }
  };

  const handleRefineOCR = async (sheetId) => {
    try {
      setRefiningSheetId(sheetId);
      setError(null);
      const updated = await api.refineSheetOCR(sheetId);
      setSuccessMsg(`LLM refinement completed for Sheet #${sheetId}.`);
      if (inspectingSheet && inspectingSheet.id === sheetId) {
        setInspectingSheet(updated);
        setEditedText(updated.corrected_text || updated.refined_ocr_text || updated.raw_ocr_text || '');
      }
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'LLM refinement failed.');
    } finally {
      setRefiningSheetId(null);
    }
  };

  const handleRunEvaluation = async (sheetId) => {
    try {
      setEvaluatingSheetId(sheetId);
      setError(null);
      await api.evaluateSheet(sheetId);
      setSuccessMsg(`AI Evaluation completed for Sheet #${sheetId}.`);
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'AI evaluation failed.');
    } finally {
      setEvaluatingSheetId(null);
    }
  };

  const handleOpenInspect = async (sheet) => {
    try {
      const details = await api.getAnswerSheetDetails(sheet.id);
      setInspectingSheet(details);
      setEditedText(details.corrected_text || details.refined_ocr_text || details.raw_ocr_text || '');
      setInspectTab('traceability');
    } catch (err) {
      setError('Failed to fetch detailed OCR results.');
    }
  };

  const handleAcceptRefinement = async () => {
    if (!inspectingSheet) return;
    try {
      setSavingCorrection(true);
      await api.approveRefinement(inspectingSheet.id, { action: 'ACCEPT_REFINEMENT' });
      setSuccessMsg(`Refinement accepted & approved for ${inspectingSheet.student_identifier || `Sheet #${inspectingSheet.id}`}.`);
      setInspectingSheet(null);
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'Failed to accept refinement.');
    } finally {
      setSavingCorrection(false);
    }
  };

  const handleRevertToRaw = async () => {
    if (!inspectingSheet) return;
    try {
      setSavingCorrection(true);
      await api.approveRefinement(inspectingSheet.id, { action: 'REVERT_TO_RAW' });
      setSuccessMsg(`Reverted to raw unmodified OCR text for ${inspectingSheet.student_identifier || `Sheet #${inspectingSheet.id}`}.`);
      setInspectingSheet(null);
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'Failed to revert to raw OCR.');
    } finally {
      setSavingCorrection(false);
    }
  };

  const handleSaveCorrection = async () => {
    if (!inspectingSheet) return;
    try {
      setSavingCorrection(true);
      await api.approveRefinement(inspectingSheet.id, { action: 'MANUAL_EDIT', edited_text: editedText });
      setSuccessMsg(`Manual OCR edits saved and approved for ${inspectingSheet.student_identifier || `Sheet #${inspectingSheet.id}`}.`);
      setInspectingSheet(null);
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'Failed to save manual OCR correction.');
    } finally {
      setSavingCorrection(false);
    }
  };

  const handleSaveSegment = async (segmentId) => {
    if (!inspectingSheet) return;
    try {
      setSavingSegment(true);
      setError(null);
      const updated = await api.correctSegmentText(inspectingSheet.id, segmentId, segmentText);
      setSuccessMsg('Question segment text updated successfully.');
      setInspectingSheet(updated);
      setEditingSegmentId(null);
      fetchSheets(selectedExamId);
    } catch (err) {
      setError(err.message || 'Failed to save segment correction.');
    } finally {
      setSavingSegment(false);
    }
  };

  return (
    <div>
      {/* Top Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700' }}>Student Answer Sheets & OCR Studio</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Upload handwritten scripts, run PaddleOCR PP-OCRv6 text extraction, and evaluate answers
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => fetchSheets(selectedExamId)}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success">
          <CheckCircle size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Select Examination Bar */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '13px', fontWeight: '600' }}>Examination:</label>
          <select
            className="form-select"
            style={{ width: 'auto', minWidth: '320px' }}
            value={selectedExamId}
            onChange={(e) => setSelectedExamId(e.target.value)}
          >
            {exams.map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.course_code} - {ex.title} ({ex.exam_code})
              </option>
            ))}
          </select>

          {activeExam && (
            <div className="exam-code-tag">
              <span>Code: {activeExam.exam_code}</span>
            </div>
          )}
        </div>
      </div>

      {/* Batch Upload Form */}
      <div className="card">
        <h3 className="card-title" style={{ marginBottom: '16px' }}>Upload Answer Sheets</h3>
        <form onSubmit={handleUpload}>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Select Answer Sheet Files (PDF, JPG, PNG) *</label>
              <input
                type="file"
                multiple
                className="form-input"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={handleFileChange}
                required
              />
              <span className="form-hint">
                {files.length > 0
                  ? `${files.length} file(s) selected: ${files.map((f) => f.name).join(', ')}`
                  : 'Select one or more student answer scripts'}
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">Student Roll Number / Identifier (Optional)</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. TVE21CS045 (or leave blank to auto-detect)"
                value={studentRoll}
                onChange={(e) => setStudentRoll(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={uploading || files.length === 0}
            >
              {uploading ? (
                <>
                  <span className="spinner" /> Uploading Batch...
                </>
              ) : (
                <>
                  <UploadCloud size={16} /> Upload {files.length ? `${files.length} Sheet(s)` : 'Sheets'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Answer Sheets Table */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Uploaded Answer Scripts</h3>
            <span className="card-subtitle">
              {answerSheets.length} student answer sheets registered for this examination
            </span>
          </div>
        </div>

        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Student Identifier</th>
                <th>Original File</th>
                <th>Pages</th>
                <th>OCR & Refinement Status</th>
                <th>Recognition Confidence</th>
                <th>Evaluations</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px' }}>
                    <span className="spinner spinner-primary" /> Loading answer sheets...
                  </td>
                </tr>
              ) : answerSheets.length > 0 ? (
                answerSheets.map((sheet) => {
                  const isOCRProcessing = processingSheetId === sheet.id;
                  const isEvaluating = evaluatingSheetId === sheet.id;
                  const hasOCR = !!sheet.ocr_result;
                  const hasEvals = sheet.evaluations && sheet.evaluations.length > 0;

                  return (
                    <tr key={sheet.id}>
                      <td>
                        <strong>{sheet.student_identifier || `Student #${sheet.id}`}</strong>
                      </td>
                      <td>
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {sheet.original_filename || 'Uploaded Document'}
                        </span>
                      </td>
                      <td>{sheet.page_count} page(s)</td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                          <span
                            className={`badge ${
                              sheet.status === 'EVALUATED'
                                ? 'badge-success'
                                : sheet.status === 'OCR_COMPLETED'
                                ? 'badge-info'
                                : sheet.status === 'FAILED'
                                ? 'badge-danger'
                                : 'badge-neutral'
                            }`}
                          >
                            {sheet.status}
                          </span>
                          {/* OCR Refinement Status Badge */}
                          {sheet.refinement_status === 'REFINED' && (
                            <span
                              className="badge badge-success"
                              style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '3px' }}
                              title={sheet.refinement_model && sheet.refinement_provider ? `${sheet.refinement_model} via ${sheet.refinement_provider}` : 'LLM Refined'}
                            >
                              <Sparkles size={10} /> LLM Refined
                            </span>
                          )}
                          {sheet.refinement_status === 'FAILED_FALLBACK_RAW' && (
                            <span
                              className="badge badge-warning"
                              style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '3px', backgroundColor: '#fef3c7', color: '#92400e', borderColor: '#fcd34d' }}
                              title={sheet.refinement_error || 'Refinement unavailable — raw OCR retained'}
                            >
                              <AlertTriangle size={10} /> Fallback (Raw OCR)
                            </span>
                          )}
                          {sheet.refinement_status === 'SKIPPED' && (
                            <span
                              className="badge badge-neutral"
                              style={{ fontSize: '10px' }}
                              title="Refinement skipped by configuration or empty text"
                            >
                              Refinement Skipped
                            </span>
                          )}
                          {sheet.refinement_status === 'TEACHER_APPROVED' && (
                            <span
                              className="badge badge-info"
                              style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '3px', backgroundColor: '#e0f2fe', color: '#0369a1', borderColor: '#bae6fd' }}
                              title="Teacher-approved transcription"
                            >
                              <ShieldCheck size={10} /> Teacher Approved
                            </span>
                          )}
                          {sheet.refinement_status === 'TEACHER_REVERTED_RAW' && (
                            <span
                              className="badge badge-neutral"
                              style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '3px' }}
                              title="Teacher reverted to raw OCR"
                            >
                              <Undo2 size={10} /> Reverted to Raw
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        {hasOCR ? (
                          <span
                            className={`badge ${
                              (sheet.ocr_result.confidence || 0) >= 0.70 ? 'badge-success' : 'badge-warning'
                            }`}
                          >
                            {Math.round((sheet.ocr_result.confidence || 0) * 100)}% ({sheet.ocr_result.engine_used || 'PP-OCRv6'})
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Not Run</span>
                        )}
                      </td>
                      <td>
                        {hasEvals ? (
                          <span className="badge badge-success">
                            {sheet.evaluations.length} Questions Graded
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Pending</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            disabled={isOCRProcessing}
                            onClick={() => handleProcessOCR(sheet.id)}
                            title="Run local PP-OCRv6 handwritten text recognition"
                          >
                            {isOCRProcessing ? <span className="spinner spinner-primary" /> : <Play size={12} />}
                            {hasOCR ? 'Re-run OCR' : 'Run OCR (v6)'}
                          </button>

                          {hasOCR && (
                            <button
                              className="btn btn-secondary btn-sm"
                              disabled={refiningSheetId === sheet.id}
                              onClick={() => handleRefineOCR(sheet.id)}
                              title="Run / Retry LLM OCR refinement"
                            >
                              {refiningSheetId === sheet.id ? <span className="spinner spinner-primary" /> : <Sparkles size={12} />}
                              Refine
                            </button>
                          )}

                          {hasOCR && (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                if (setActiveSheet) setActiveSheet(sheet);
                                if (onNavigate) onNavigate('ocr-review');
                              }}
                              title="Open dedicated side-by-side OCR inspection and correction studio"
                            >
                              <FileSearch size={12} /> OCR Studio
                            </button>
                          )}

                          {hasOCR && (
                            <button
                              className="btn btn-outline btn-sm"
                              onClick={() => handleOpenInspect(sheet)}
                              title="Quick modal OCR inspection"
                            >
                              <Eye size={12} /> Quick Inspect
                            </button>
                          )}

                          {hasOCR && (
                            <button
                              className="btn btn-primary btn-sm"
                              disabled={isEvaluating}
                              onClick={() => handleRunEvaluation(sheet.id)}
                              title="Run deterministic AI evaluation against approved rubric"
                            >
                              {isEvaluating ? <span className="spinner" /> : <Sparkles size={12} />}
                              Evaluate
                            </button>
                          )}

                          {hasEvals && (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                if (setActiveSheet) setActiveSheet(sheet);
                                if (onNavigate) onNavigate('review-queue');
                              }}
                              title="Navigate to Teacher Review queue to inspect and edit evaluations"
                            >
                              <CheckSquare size={12} /> Review Marks
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
                    No answer sheets uploaded for this examination yet. Use the upload form above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* OCR Inspection & Correction Modal */}
      {inspectingSheet && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '960px', width: '95%' }}>
            <div className="modal-header">
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <h3 className="modal-title" style={{ margin: 0 }}>
                    OCR Inspection & Traceability — {inspectingSheet.student_identifier || `Sheet #${inspectingSheet.id}`}
                  </h3>
                  {inspectingSheet.is_teacher_approved ? (
                    <span className="badge badge-success" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <ShieldCheck size={12} /> Teacher Approved
                    </span>
                  ) : inspectingSheet.refinement_status === 'REFINED' ? (
                    <span className="badge badge-success" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Sparkles size={12} /> LLM Refined
                    </span>
                  ) : inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW' ? (
                    <span className="badge badge-warning" style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: '#fef3c7', color: '#92400e', borderColor: '#fcd34d' }}>
                      <AlertTriangle size={12} /> Fallback (Raw OCR)
                    </span>
                  ) : inspectingSheet.refinement_status === 'SKIPPED' ? (
                    <span className="badge badge-neutral">Refinement Skipped</span>
                  ) : inspectingSheet.refinement_status === 'TEACHER_REVERTED_RAW' ? (
                    <span className="badge badge-neutral" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Undo2 size={12} /> Reverted to Raw
                    </span>
                  ) : (
                    <span className="badge badge-neutral">Unreviewed</span>
                  )}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '14px' }}>
                  <span><strong>Engine:</strong> {inspectingSheet.ocr_result?.engine_used || 'PaddleOCR PP-OCRv6'}</span>
                  <span><strong>OCR Conf:</strong> {Math.round((inspectingSheet.ocr_confidence ?? inspectingSheet.ocr_result?.confidence ?? 0) * 100)}%</span>
                  <span>
                    <strong>Refinement Model:</strong>{' '}
                    {inspectingSheet.refinement_provider
                      ? `${inspectingSheet.refinement_provider} / ${inspectingSheet.refinement_model || 'qwen3'}`
                      : 'None (LLM not run)'}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  disabled={refiningSheetId === inspectingSheet.id}
                  onClick={() => handleRefineOCR(inspectingSheet.id)}
                  title="Run or retry LLM refinement using configured provider"
                >
                  {refiningSheetId === inspectingSheet.id ? <span className="spinner spinner-primary" /> : <Sparkles size={13} />}
                  Refine with LLM
                </button>
                <button
                  className="btn-copy"
                  onClick={() => setInspectingSheet(null)}
                  style={{ fontSize: '18px' }}
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Accessible OCR Refinement Status Banner */}
            <div
              role="status"
              aria-live="polite"
              style={{
                margin: '16px 24px 12px 24px',
                padding: '14px 18px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                backgroundColor:
                  inspectingSheet.is_teacher_approved
                    ? '#f0f9ff'
                    : inspectingSheet.refinement_status === 'REFINED'
                    ? '#f0fdf4'
                    : inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW'
                    ? '#fffbeb'
                    : inspectingSheet.refinement_status === 'SKIPPED'
                    ? '#f8fafc'
                    : '#f8fafc',
                border:
                  inspectingSheet.is_teacher_approved
                    ? '1px solid #bae6fd'
                    : inspectingSheet.refinement_status === 'REFINED'
                    ? '1px solid #bbf7d0'
                    : inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW'
                    ? '1px solid #fde68a'
                    : inspectingSheet.refinement_status === 'SKIPPED'
                    ? '1px solid #e2e8f0'
                    : '1px solid #e2e8f0',
              }}
            >
              {inspectingSheet.is_teacher_approved ? (
                <ShieldCheck size={20} color="#0284c7" style={{ flexShrink: 0, marginTop: '2px' }} />
              ) : inspectingSheet.refinement_status === 'REFINED' ? (
                <CheckCircle2 size={20} color="#16a34a" style={{ flexShrink: 0, marginTop: '2px' }} />
              ) : inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW' ? (
                <AlertTriangle size={20} color="#d97706" style={{ flexShrink: 0, marginTop: '2px' }} />
              ) : inspectingSheet.refinement_status === 'SKIPPED' ? (
                <SkipForward size={20} color="#64748b" style={{ flexShrink: 0, marginTop: '2px' }} />
              ) : (
                <Clock size={20} color="#94a3b8" style={{ flexShrink: 0, marginTop: '2px' }} />
              )}

              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: '600', fontSize: '14px', color: 'var(--text-primary)' }}>
                  {inspectingSheet.is_teacher_approved
                    ? (inspectingSheet.refinement_status === 'TEACHER_REVERTED_RAW'
                        ? 'Teacher Reverted to Original Raw OCR'
                        : 'Teacher-approved transcription')
                    : inspectingSheet.refinement_status === 'REFINED'
                    ? `LLM refinement completed${
                        inspectingSheet.refinement_model && inspectingSheet.refinement_provider
                          ? ` — ${inspectingSheet.refinement_model} via ${inspectingSheet.refinement_provider}`
                          : ''
                      }`
                    : inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW'
                    ? 'Refinement unavailable — raw OCR retained'
                    : inspectingSheet.refinement_status === 'SKIPPED'
                    ? 'Refinement skipped — using original OCR'
                    : 'Awaiting OCR / refinement processing'}
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: '1.5' }}>
                  {inspectingSheet.is_teacher_approved ? (
                    'This answer sheet has been verified and approved by the teacher. Approved corrections take precedence over automated refinement and drive subsequent question segmentation and AI evaluation.'
                  ) : inspectingSheet.refinement_status === 'REFINED' ? (
                    'PP-OCRv6 handwritten extraction was successfully refined by local LLM without altering student knowledge, phrasing, or mathematical formulas.'
                  ) : inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW' ? (
                    <>
                      <span>
                        LLM refinement could not be completed. The original raw text extracted by PaddleOCR PP-OCRv6 has been preserved intact as the working transcription.
                      </span>
                      {inspectingSheet.refinement_error && (
                        <div style={{ marginTop: '5px', fontWeight: '500', color: '#92400e' }}>
                          <strong>Reason:</strong> {inspectingSheet.refinement_error}
                        </div>
                      )}
                    </>
                  ) : inspectingSheet.refinement_status === 'SKIPPED' ? (
                    'Refinement was intentionally skipped or disabled by configuration. The original PaddleOCR PP-OCRv6 extraction is in use.'
                  ) : (
                    'This answer script has been uploaded and is waiting for OCR extraction.'
                  )}
                </div>

                {inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW' && (
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={refiningSheetId === inspectingSheet.id}
                    onClick={() => handleRefineOCR(inspectingSheet.id)}
                    style={{ marginTop: '8px', fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                    aria-label="Retry LLM refinement on raw OCR text"
                  >
                    {refiningSheetId === inspectingSheet.id ? (
                      <>
                        <span className="spinner spinner-primary" /> Retrying Refinement...
                      </>
                    ) : (
                      <>
                        <RefreshCw size={12} /> Retry Refinement
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Modal Navigation Tabs */}
            <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-color)', padding: '0 24px', backgroundColor: 'var(--bg-secondary)' }}>
              <button
                className={`tab-btn ${inspectTab === 'traceability' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'none',
                  border: 'none',
                  borderBottom: inspectTab === 'traceability' ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  fontWeight: inspectTab === 'traceability' ? '600' : '400',
                  color: inspectTab === 'traceability' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                onClick={() => setInspectTab('traceability')}
              >
                <Layers size={14} /> Proposed Changes & Uncertain Spans
                {inspectingSheet.proposed_changes?.length > 0 && (
                  <span className="badge badge-neutral" style={{ fontSize: '10px', padding: '1px 6px' }}>
                    {inspectingSheet.proposed_changes.length}
                  </span>
                )}
              </button>

              <button
                className={`tab-btn ${inspectTab === 'sidebyside' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'none',
                  border: 'none',
                  borderBottom: inspectTab === 'sidebyside' ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  fontWeight: inspectTab === 'sidebyside' ? '600' : '400',
                  color: inspectTab === 'sidebyside' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                onClick={() => setInspectTab('sidebyside')}
              >
                <Eye size={14} /> Side-by-Side Comparison
              </button>

              <button
                className={`tab-btn ${inspectTab === 'segmentation' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'none',
                  border: 'none',
                  borderBottom: inspectTab === 'segmentation' ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  fontWeight: inspectTab === 'segmentation' ? '600' : '400',
                  color: inspectTab === 'segmentation' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                onClick={() => setInspectTab('segmentation')}
              >
                <Layers size={14} /> Question Segmentation
                {inspectingSheet.extracted_answers?.length > 0 && (
                  <span className="badge badge-neutral" style={{ fontSize: '10px', padding: '1px 6px' }}>
                    {inspectingSheet.extracted_answers.length}
                  </span>
                )}
              </button>

              <button
                className={`tab-btn ${inspectTab === 'editor' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'none',
                  border: 'none',
                  borderBottom: inspectTab === 'editor' ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  fontWeight: inspectTab === 'editor' ? '600' : '400',
                  color: inspectTab === 'editor' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                onClick={() => setInspectTab('editor')}
              >
                <Edit3 size={14} /> Editable Final Text
              </button>
            </div>

            <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
              {inspectTab === 'traceability' && (
                <div>
                  {/* Uncertain Spans Alert */}
                  {inspectingSheet.uncertain_spans && inspectingSheet.uncertain_spans.length > 0 && (
                    <div className="alert alert-warning" style={{ marginBottom: '16px' }}>
                      <AlertTriangle size={18} />
                      <div>
                        <strong>Uncertain Handwritten Spans Detected ({inspectingSheet.uncertain_spans.length})</strong>
                        <div style={{ fontSize: '12px', marginTop: '4px' }}>
                          These segments exhibited ambiguous legibility or questionable OCR character certainty:
                        </div>
                        <ul style={{ margin: '6px 0 0 16px', fontSize: '12px' }}>
                          {inspectingSheet.uncertain_spans.map((u, i) => (
                            <li key={i}>
                              <code>{u.fragment}</code> — {u.reason} ({u.flag})
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  {/* Proposed Corrections Table */}
                  <div style={{ marginBottom: '16px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px' }}>
                      Traceable LLM Corrections ({inspectingSheet.proposed_changes?.length || 0})
                    </h4>
                    {inspectingSheet.proposed_changes && inspectingSheet.proposed_changes.length > 0 ? (
                      <div className="table-responsive">
                        <table className="table" style={{ fontSize: '12px' }}>
                          <thead>
                            <tr>
                              <th>Original Fragment</th>
                              <th></th>
                              <th>Refined Fragment</th>
                              <th>Category</th>
                              <th>Reason</th>
                              <th>Confidence</th>
                              <th>Review Required</th>
                            </tr>
                          </thead>
                          <tbody>
                            {inspectingSheet.proposed_changes.map((ch, idx) => (
                              <tr key={idx}>
                                <td>
                                  <code style={{ color: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
                                    {ch.original_fragment}
                                  </code>
                                </td>
                                <td>
                                  <ArrowRight size={12} color="var(--text-muted)" />
                                </td>
                                <td>
                                  <code style={{ color: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)' }}>
                                    {ch.refined_fragment}
                                  </code>
                                </td>
                                <td>
                                  <span className="badge badge-neutral" style={{ fontSize: '11px' }}>
                                    {ch.category}
                                  </span>
                                </td>
                                <td>{ch.reason}</td>
                                <td>{Math.round((ch.confidence || 0) * 100)}%</td>
                                <td>
                                  {ch.requires_review ? (
                                    <span className="badge badge-warning" style={{ fontSize: '11px' }}>
                                      Review
                                    </span>
                                  ) : (
                                    <span className="badge badge-success" style={{ fontSize: '11px' }}>
                                      Verified
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', backgroundColor: 'var(--bg-secondary)', borderRadius: '6px' }}>
                        {inspectingSheet.refinement_status === 'FAILED_FALLBACK_RAW' ? (
                          <span>
                            Refinement was unavailable for this answer sheet ({inspectingSheet.refinement_error || 'LLM service offline'}). No automated changes were proposed; original raw PP-OCRv6 text remains intact.
                          </span>
                        ) : inspectingSheet.refinement_status === 'SKIPPED' ? (
                          <span>
                            Refinement was skipped for this answer sheet. Original raw PP-OCRv6 text is being used directly without automated modifications.
                          </span>
                        ) : (
                          <span>
                            No changes proposed by the refinement model. The OCR extraction was deemed clear or no character substitutions were performed.
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {inspectTab === 'sidebyside' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <label className="form-label" style={{ fontWeight: '600' }}>
                      1. Raw OCR Output (PaddleOCR PP-OCRv6):
                    </label>
                    <div className="code-block" style={{ height: '340px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontSize: '12px' }}>
                      {inspectingSheet.raw_ocr_text || inspectingSheet.ocr_result?.raw_text || 'No text extracted.'}
                    </div>
                  </div>

                  <div>
                    <label className="form-label" style={{ fontWeight: '600' }}>
                      2. LLM-Refined Transcription (
                      {inspectingSheet.refinement_status === 'REFINED' && inspectingSheet.refinement_provider
                        ? `${inspectingSheet.refinement_model || 'qwen3'} via ${inspectingSheet.refinement_provider}`
                        : 'Unavailable / Fallback'}
                      ):
                    </label>
                    {inspectingSheet.refinement_status === 'REFINED' && inspectingSheet.refined_ocr_text ? (
                      <div className="code-block" style={{ height: '340px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontSize: '12px', border: '1px solid var(--accent-primary)' }}>
                        {inspectingSheet.refined_ocr_text}
                      </div>
                    ) : (
                      <div
                        className="code-block"
                        style={{
                          height: '340px',
                          overflowY: 'auto',
                          fontSize: '12px',
                          border: '1px dashed #fcd34d',
                          backgroundColor: '#fffbeb',
                          color: '#92400e',
                          padding: '16px',
                        }}
                      >
                        <div style={{ fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <AlertTriangle size={15} color="#d97706" />
                          {inspectingSheet.refinement_status === 'SKIPPED'
                            ? 'Refinement Skipped — Using Original Raw OCR'
                            : 'Refinement Unavailable — Raw OCR Retained'}
                        </div>
                        <p style={{ margin: '0 0 12px 0', fontSize: '12px', lineHeight: '1.5' }}>
                          {inspectingSheet.refinement_error ||
                            (inspectingSheet.refinement_status === 'SKIPPED'
                              ? 'Refinement was skipped or disabled. The system retains and uses unmodified PP-OCRv6 raw text.'
                              : 'LLM refinement was unavailable. The system safely fell back to the original PP-OCRv6 text.')}
                        </p>
                        <div style={{ borderTop: '1px solid #fde68a', paddingTop: '10px' }}>
                          <span style={{ fontWeight: '600', fontSize: '11px', textTransform: 'uppercase', color: '#78350f' }}>
                            Retained Raw Text:
                          </span>
                          <div style={{ marginTop: '6px', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', color: '#1e293b' }}>
                            {inspectingSheet.raw_ocr_text || inspectingSheet.ocr_result?.raw_text || 'No text extracted.'}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {inspectTab === 'segmentation' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: '700', margin: 0 }}>
                        Segmented Question Responses ({inspectingSheet.extracted_answers?.length || 0})
                      </h4>
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
                        Individual student answers segmented from script text. You can inspect and edit text per question.
                      </p>
                    </div>
                  </div>

                  {inspectingSheet.extracted_answers?.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                      {inspectingSheet.extracted_answers.map((ea) => (
                        <div
                          key={ea.id}
                          style={{
                            border: '1px solid var(--border-color)',
                            borderRadius: '8px',
                            padding: '14px 16px',
                            background: '#ffffff',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span className="badge badge-primary" style={{ fontWeight: '700', fontSize: '13px' }}>
                                Q{ea.question_number}
                              </span>
                              {ea.page_number && (
                                <span className="badge badge-neutral" style={{ fontSize: '11px' }}>
                                  Page {ea.page_number}
                                </span>
                              )}
                              {ea.is_manually_corrected ? (
                                <span className="badge badge-success" style={{ fontSize: '11px' }}>
                                  Teacher Edited
                                </span>
                              ) : (
                                <span className="badge badge-neutral" style={{ fontSize: '11px' }}>
                                  Auto-Segmented
                                </span>
                              )}
                            </div>

                            {editingSegmentId !== ea.id && (
                              <button
                                className="btn btn-secondary btn-sm"
                                style={{ fontSize: '11px', padding: '2px 8px' }}
                                onClick={() => {
                                  setEditingSegmentId(ea.id);
                                  setSegmentText(ea.corrected_text || ea.refined_text || ea.raw_ocr_text || '');
                                }}
                              >
                                <Edit3 size={12} /> Edit Segment
                              </button>
                            )}
                          </div>

                          {editingSegmentId === ea.id ? (
                            <div style={{ marginTop: '8px' }}>
                              <textarea
                                className="form-textarea"
                                style={{ minHeight: '120px', fontFamily: 'var(--font-mono)', fontSize: '12px', marginBottom: '8px' }}
                                value={segmentText}
                                onChange={(e) => setSegmentText(e.target.value)}
                              />
                              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => setEditingSegmentId(null)}
                                >
                                  Cancel
                                </button>
                                <button
                                  className="btn btn-primary btn-sm"
                                  disabled={savingSegment}
                                  onClick={() => handleSaveSegment(ea.id)}
                                >
                                  {savingSegment ? <span className="spinner" /> : <Save size={12} />} Save Segment
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div
                              style={{
                                background: '#f8fafc',
                                padding: '10px 12px',
                                borderRadius: '6px',
                                fontFamily: 'var(--font-mono)',
                                fontSize: '12px',
                                lineHeight: '1.6',
                                whiteSpace: 'pre-wrap',
                              }}
                            >
                              {ea.corrected_text || ea.refined_text || ea.raw_ocr_text || 'No text extracted for this segment.'}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
                      No questions segmented yet. Accept or save approved OCR text to run question segmentation.
                    </div>
                  )}
                </div>
              )}

              {inspectTab === 'editor' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <label className="form-label" style={{ fontWeight: '600', margin: 0 }}>
                      3. Teacher-Approved Final Text (`corrected_text`):
                    </label>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      Used for Question Segmentation & Grading
                    </span>
                  </div>
                  <textarea
                    className="form-textarea"
                    style={{ minHeight: '340px', fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: '1.6' }}
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                    placeholder="Enter or verify student answer script transcription..."
                  />
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
                    * Saving manual edits will approve the script, re-segment question responses, and drive subsequent AI grading with full teacher precedence.
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="btn btn-outline btn-sm"
                  disabled={savingCorrection}
                  onClick={handleRevertToRaw}
                  title="Reject LLM refinement and revert strictly to unmodified raw OCR"
                >
                  <Undo2 size={13} /> Revert to Raw OCR
                </button>

                <button
                  className="btn btn-secondary btn-sm"
                  disabled={savingCorrection}
                  onClick={handleAcceptRefinement}
                  title="Accept all LLM transcription corrections and approve"
                >
                  <Check size={13} /> Accept LLM Refinement
                </button>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setInspectingSheet(null)}>
                  Close
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  disabled={savingCorrection}
                  onClick={handleSaveCorrection}
                  title="Save edited final text and persist teacher approval"
                >
                  {savingCorrection ? <span className="spinner" /> : <Save size={13} />} Save Manual Edits & Approve
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
