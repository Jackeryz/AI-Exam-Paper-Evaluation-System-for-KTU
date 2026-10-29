import React, { useEffect, useState } from 'react';
import {
  FileSearch,
  Eye,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Edit3,
  Save,
  Check,
  ShieldCheck,
  ArrowRight,
  Sparkles,
  Layers,
  Undo2,
  FileText,
  AlertCircle,
  Maximize2,
  ExternalLink,
} from 'lucide-react';
import { api } from '../api';

export default function OCRReview({
  activeExam,
  setActiveExam,
  activeSheet,
  setActiveSheet,
  onNavigate,
}) {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(activeExam?.id || '');
  const [sheets, setSheets] = useState([]);
  const [selectedSheetId, setSelectedSheetId] = useState(activeSheet?.id || '');
  const [currentSheet, setCurrentSheet] = useState(null);

  const [loading, setLoading] = useState(false);
  const [sheetLoading, setSheetLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Tab: 'approved' | 'refined' | 'raw' | 'segments'
  const [activeTab, setActiveTab] = useState('approved');
  const [transcript, setTranscript] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Per-segment editing
  const [editingSegmentId, setEditingSegmentId] = useState(null);
  const [segmentText, setSegmentText] = useState('');

  // Initial load of examinations
  useEffect(() => {
    api.getExams()
      .then((data) => {
        setExams(data);
        if (!selectedExamId && data.length > 0) {
          const initialExam = activeExam || data[0];
          setSelectedExamId(initialExam.id);
          if (!activeExam) setActiveExam(initialExam);
        }
      })
      .catch((err) => setError(err.message || 'Failed to fetch examinations'));
  }, []);

  // When exam changes, fetch its answer sheets
  useEffect(() => {
    if (selectedExamId) {
      setLoading(true);
      setError(null);
      api.getAnswerSheets(selectedExamId)
        .then((data) => {
          setSheets(data);
          if (data.length > 0) {
            // Keep activeSheet if belonging to this exam, else select first
            const matched = data.find((s) => s.id === (activeSheet?.id || selectedSheetId));
            const toSelect = matched ? matched.id : data[0].id;
            setSelectedSheetId(toSelect);
          } else {
            setSelectedSheetId('');
            setCurrentSheet(null);
          }
        })
        .catch((err) => setError(err.message || 'Failed to fetch answer sheets'))
        .finally(() => setLoading(false));

      const examObj = exams.find((e) => e.id === parseInt(selectedExamId));
      if (examObj) setActiveExam(examObj);
    }
  }, [selectedExamId]);

  // Load detailed sheet details when selectedSheetId changes
  const loadSheetDetails = async (sheetId) => {
    if (!sheetId) return;
    try {
      setSheetLoading(true);
      setError(null);
      const detail = await api.getAnswerSheetDetails(sheetId);
      setCurrentSheet(detail);
      if (setActiveSheet) setActiveSheet(detail);

      // Default active tab to approved if approved, else refined, else raw
      if (detail.is_ocr_approved && detail.approved_ocr_text) {
        setActiveTab('approved');
        setTranscript(detail.approved_ocr_text);
      } else if (detail.refined_ocr_text) {
        setActiveTab('refined');
        setTranscript(detail.refined_ocr_text);
      } else {
        setActiveTab('raw');
        setTranscript(detail.raw_ocr_text || '');
      }
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(err.message || 'Failed to load answer sheet details');
    } finally {
      setSheetLoading(false);
    }
  };

  useEffect(() => {
    if (selectedSheetId) {
      loadSheetDetails(selectedSheetId);
    }
  }, [selectedSheetId]);

  // Switch tab text
  const handleTabChange = (tab) => {
    if (hasUnsavedChanges) {
      if (!window.confirm('You have unsaved changes in this tab. Switch tabs anyway?')) {
        return;
      }
    }
    setActiveTab(tab);
    setHasUnsavedChanges(false);
    if (!currentSheet) return;

    if (tab === 'approved') {
      setTranscript(currentSheet.approved_ocr_text || currentSheet.refined_ocr_text || currentSheet.raw_ocr_text || '');
    } else if (tab === 'refined') {
      setTranscript(currentSheet.refined_ocr_text || currentSheet.raw_ocr_text || '');
    } else if (tab === 'raw') {
      setTranscript(currentSheet.raw_ocr_text || '');
    }
  };

  const handleTextChange = (e) => {
    setTranscript(e.target.value);
    setHasUnsavedChanges(true);
  };

  // Save manual corrections
  const handleSaveCorrection = async () => {
    if (!currentSheet) return;
    try {
      setSaving(true);
      setError(null);
      const updated = await api.correctOCRText(currentSheet.id, transcript);
      setSuccessMsg('OCR transcript corrections saved successfully.');
      setCurrentSheet(updated);
      setHasUnsavedChanges(false);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save transcript corrections.');
    } finally {
      setSaving(false);
    }
  };

  // Approve transcript for AI evaluation
  const handleApprove = async () => {
    if (!currentSheet) return;
    try {
      setSaving(true);
      setError(null);
      const updated = await api.approveRefinement(currentSheet.id, {
        approved_text: transcript,
      });
      setSuccessMsg('OCR transcript approved! This text is now designated for AI grading.');
      setCurrentSheet(updated);
      setActiveTab('approved');
      setHasUnsavedChanges(false);
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err) {
      setError(err.message || 'Failed to approve OCR transcript.');
    } finally {
      setSaving(false);
    }
  };

  // Trigger PaddleOCR reprocessing
  const handleReprocessOCR = async () => {
    if (!currentSheet) return;
    if (!window.confirm('Re-run PaddleOCR on this document? This will refresh raw text extraction.')) {
      return;
    }
    try {
      setProcessing(true);
      setError(null);
      await api.processSheetOCR(currentSheet.id);
      setSuccessMsg('PaddleOCR completed successfully.');
      await loadSheetDetails(currentSheet.id);
    } catch (err) {
      setError(err.message || 'OCR processing failed.');
    } finally {
      setProcessing(false);
    }
  };

  // Segment editing handlers
  const handleEditSegment = (seg) => {
    setEditingSegmentId(seg.id);
    setSegmentText(seg.extracted_text || '');
  };

  const handleSaveSegment = async (segId) => {
    try {
      setSaving(true);
      await api.correctSegmentText(currentSheet.id, segId, segmentText);
      setEditingSegmentId(null);
      await loadSheetDetails(currentSheet.id);
      setSuccessMsg('Question segment text updated.');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to update segment.');
    } finally {
      setSaving(false);
    }
  };

  // Word & character counts
  const wordCount = transcript.trim() ? transcript.trim().split(/\s+/).length : 0;
  const charCount = transcript.length;

  const fileUrl = currentSheet ? api.getAnswerSheetFileUrl(currentSheet.id) : null;
  const isPdf = currentSheet?.file_path?.toLowerCase().endsWith('.pdf');

  return (
    <div>
      {/* Top Controls Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)' }}>
            OCR Inspection & Correction Studio
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Inspect original student handwriting alongside PaddleOCR extracted transcripts
          </p>
        </div>

        {/* Exam & Script Selectors */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <select
            className="input"
            style={{ width: '220px', padding: '6px 12px', fontSize: '13px' }}
            value={selectedExamId}
            onChange={(e) => setSelectedExamId(e.target.value)}
          >
            {exams.map((exam) => (
              <option key={exam.id} value={exam.id}>
                {exam.course_code ? `${exam.course_code} - ` : ''}{exam.title}
              </option>
            ))}
          </select>

          <select
            className="input"
            style={{ width: '200px', padding: '6px 12px', fontSize: '13px' }}
            value={selectedSheetId}
            onChange={(e) => setSelectedSheetId(e.target.value)}
            disabled={sheets.length === 0}
          >
            {sheets.length === 0 ? (
              <option value="">No answer sheets found</option>
            ) : (
              sheets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.student_identifier} ({s.ocr_status}) {s.is_ocr_approved ? '✓' : ''}
                </option>
              ))
            )}
          </select>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => loadSheetDetails(selectedSheetId)}
            disabled={!selectedSheetId || sheetLoading}
            title="Refresh current sheet"
          >
            <RefreshCw size={14} className={sheetLoading ? 'spin' : ''} />
          </button>
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

      {/* Main Studio Area */}
      {!currentSheet ? (
        <div className="card" style={{ padding: '60px 20px', textAlign: 'center' }}>
          <FileSearch size={48} style={{ color: 'var(--text-muted)', marginBottom: '16px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>
            No Answer Sheet Selected
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '420px', margin: '0 auto 20px' }}>
            Select an examination and student answer sheet above, or upload answer sheets to begin PaddleOCR transcript inspection.
          </p>
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate('answer-sheets')}>
            Go to Answer Sheets
          </button>
        </div>
      ) : (
        <div className="ocr-split-container">
          {/* Left Pane: Original Document Preview */}
          <div className="ocr-pane">
            <div className="ocr-pane-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Eye size={16} color="var(--primary)" />
                <span>Original Document Preview</span>
                <span className="badge badge-secondary" style={{ fontSize: '11px' }}>
                  {isPdf ? 'PDF Document' : 'Image Scan'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <a
                  href={fileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '4px 8px', fontSize: '11px', textDecoration: 'none' }}
                  title="Open full file in new tab"
                >
                  <ExternalLink size={12} /> Fullscreen
                </a>
              </div>
            </div>

            <div className="doc-viewer-wrap">
              {fileUrl ? (
                isPdf ? (
                  <iframe
                    src={`${fileUrl}#toolbar=1&navpanes=0`}
                    className="doc-viewer-frame"
                    title={`Student Answer Sheet ${currentSheet.student_identifier}`}
                  />
                ) : (
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', overflow: 'auto' }}>
                    <img
                      src={fileUrl}
                      alt={`Handwritten answer by ${currentSheet.student_identifier}`}
                      className="doc-image-preview"
                    />
                  </div>
                )
              ) : (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  File preview unavailable
                </div>
              )}
            </div>

            <div className="ocr-word-count-bar">
              <span><strong>File:</strong> {currentSheet.file_path ? currentSheet.file_path.split(/[\\/]/).pop() : 'Uploaded Script'}</span>
              <span style={{ color: 'var(--text-muted)' }}>Script #{currentSheet.id}</span>
            </div>
          </div>

          {/* Right Pane: Extracted Transcript & Corrections */}
          <div className="ocr-pane">
            <div className="ocr-pane-header" style={{ flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={16} color="var(--primary)" />
                <span style={{ fontWeight: '700' }}>{currentSheet.student_identifier}</span>
                {currentSheet.is_ocr_approved ? (
                  <span className="badge badge-success" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircle size={11} /> Approved for AI
                  </span>
                ) : (
                  <span className="badge badge-warning" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <AlertCircle size={11} /> Pending Approval
                  </span>
                )}
                {currentSheet.ocr_confidence && (
                  <span className="badge badge-info" title="PaddleOCR Recognition Confidence">
                    {Math.round(currentSheet.ocr_confidence * 100)}% Conf
                  </span>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleReprocessOCR}
                  disabled={processing}
                  title="Re-run PaddleOCR model"
                >
                  <RefreshCw size={13} className={processing ? 'spin' : ''} />
                  <span>{processing ? 'Processing...' : 'Re-run OCR'}</span>
                </button>

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleSaveCorrection}
                  disabled={saving || !hasUnsavedChanges}
                  title="Save manual transcript adjustments"
                >
                  <Save size={13} />
                  <span>{saving ? 'Saving...' : 'Save Draft'}</span>
                </button>

                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleApprove}
                  disabled={saving}
                  title="Approve transcript for evaluation engine"
                >
                  <Check size={14} />
                  <span>Approve Transcript</span>
                </button>
              </div>
            </div>

            {/* Warning Banner */}
            <div
              style={{
                backgroundColor: '#fffbeb',
                borderBottom: '1px solid #fde68a',
                padding: '10px 16px',
                fontSize: '12px',
                color: '#92400e',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <AlertTriangle size={14} style={{ flexShrink: 0 }} />
              <span>
                <strong>Transcription Notice:</strong> Mathematical formulas, symbols, and cursive handwriting can have character variances. Verify key technical terms before evaluation.
              </span>
            </div>

            {/* View Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', backgroundColor: 'var(--bg-subtle)', padding: '0 12px' }}>
              <button
                className={`tab-btn ${activeTab === 'approved' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === 'approved' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: activeTab === 'approved' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: activeTab === 'approved' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={() => handleTabChange('approved')}
              >
                <CheckCircle size={13} />
                <span>Approved Text</span>
                {currentSheet.is_ocr_approved && (
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                )}
              </button>

              <button
                className={`tab-btn ${activeTab === 'refined' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === 'refined' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: activeTab === 'refined' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: activeTab === 'refined' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={() => handleTabChange('refined')}
              >
                <Sparkles size={13} />
                <span>Refined Transcript</span>
              </button>

              <button
                className={`tab-btn ${activeTab === 'raw' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === 'raw' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: activeTab === 'raw' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: activeTab === 'raw' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={() => handleTabChange('raw')}
              >
                <Layers size={13} />
                <span>Immutable Raw OCR</span>
              </button>

              <button
                className={`tab-btn ${activeTab === 'segments' ? 'active' : ''}`}
                style={{
                  padding: '10px 16px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === 'segments' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: activeTab === 'segments' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: activeTab === 'segments' ? '600' : '500',
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={() => handleTabChange('segments')}
              >
                <Layers size={13} />
                <span>Question Segments ({currentSheet.extracted_answers?.length || 0})</span>
              </button>
            </div>

            {/* Tab Content */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '520px', position: 'relative' }}>
              {activeTab === 'segments' ? (
                <div style={{ padding: '16px', overflowY: 'auto', flex: 1, backgroundColor: 'var(--bg-main)' }}>
                  {(!currentSheet.extracted_answers || currentSheet.extracted_answers.length === 0) ? (
                    <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No per-question segmented answers identified yet. Run OCR segmentation on this script.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {currentSheet.extracted_answers.map((seg) => (
                        <div key={seg.id} className="card" style={{ padding: '16px', margin: 0 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span className="badge badge-primary">
                                Question ID #{seg.question_id || 'Unassigned'}
                              </span>
                              {seg.confidence_score && (
                                <span className="badge badge-info" style={{ fontSize: '11px' }}>
                                  {Math.round(seg.confidence_score * 100)}% Conf
                                </span>
                              )}
                            </div>
                            {editingSegmentId === seg.id ? (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button className="btn btn-secondary btn-sm" onClick={() => setEditingSegmentId(null)}>
                                  Cancel
                                </button>
                                <button className="btn btn-primary btn-sm" onClick={() => handleSaveSegment(seg.id)} disabled={saving}>
                                  Save Segment
                                </button>
                              </div>
                            ) : (
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleEditSegment(seg)}
                                title="Edit this question segment"
                              >
                                <Edit3 size={12} /> Edit
                              </button>
                            )}
                          </div>

                          {editingSegmentId === seg.id ? (
                            <textarea
                              className="input"
                              rows={5}
                              style={{ width: '100%', fontFamily: 'var(--font-mono)', fontSize: '13px' }}
                              value={segmentText}
                              onChange={(e) => setSegmentText(e.target.value)}
                            />
                          ) : (
                            <div
                              style={{
                                whiteSpace: 'pre-wrap',
                                fontSize: '13px',
                                color: 'var(--text-primary)',
                                backgroundColor: 'var(--bg-subtle)',
                                padding: '10px 14px',
                                borderRadius: 'var(--radius-md)',
                                fontFamily: 'var(--font-mono)',
                              }}
                            >
                              {seg.extracted_text || <span style={{ color: 'var(--text-muted)' }}>[Empty Segment]</span>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <textarea
                    value={transcript}
                    onChange={handleTextChange}
                    readOnly={activeTab === 'raw'}
                    placeholder="Extracted handwritten answer text..."
                    style={{
                      flex: 1,
                      width: '100%',
                      padding: '16px 20px',
                      border: 'none',
                      resize: 'none',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '13.5px',
                      lineHeight: '1.6',
                      color: activeTab === 'raw' ? 'var(--text-secondary)' : 'var(--text-primary)',
                      backgroundColor: activeTab === 'raw' ? '#f8fafc' : '#ffffff',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                  {activeTab === 'raw' && (
                    <div
                      style={{
                        padding: '8px 16px',
                        backgroundColor: '#f1f5f9',
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        borderTop: '1px solid var(--border-color)',
                      }}
                    >
                      Raw PaddleOCR transcript is immutable to preserve an unalterable audit record of machine output.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Word & Char Count Bar with Next Steps */}
            <div className="ocr-word-count-bar">
              <div style={{ display: 'flex', gap: '16px' }}>
                <span><strong>Words:</strong> {wordCount}</span>
                <span><strong>Characters:</strong> {charCount}</span>
                {hasUnsavedChanges && (
                  <span style={{ color: '#d97706', fontWeight: '600' }}>
                    ● Unsaved Changes
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onNavigate('answer-sheets')}
                >
                  Back to Sheets
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    if (onNavigate) onNavigate('evaluation');
                  }}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <span>Proceed to Evaluation</span>
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
