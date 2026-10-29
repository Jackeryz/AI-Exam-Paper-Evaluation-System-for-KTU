import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  PlusCircle,
  Copy,
  Check,
  Search,
  UploadCloud,
  Sparkles,
  BarChart3,
  FileText,
  AlertCircle,
  RefreshCw,
  Edit3,
  Trash2,
  Eye,
  X,
  Save,
  CheckCircle,
  Filter,
} from 'lucide-react';
import { api } from '../api';

export default function Examinations({ onNavigate, setActiveExam }) {
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [semesterFilter, setSemesterFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [copiedCode, setCopiedCode] = useState(null);

  // Exam Details & Edit Modal
  const [selectedExam, setSelectedExam] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editFormData, setEditFormData] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  const fetchExams = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getExams();
      setExams(data);
    } catch (err) {
      setError(err.message || 'Failed to load examinations');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExams();
  }, []);

  const handleCopy = (code) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const filteredExams = exams.filter((exam) => {
    const term = searchTerm.toLowerCase();
    const matchesSearch =
      exam.title.toLowerCase().includes(term) ||
      (exam.course_code && exam.course_code.toLowerCase().includes(term)) ||
      (exam.exam_code && exam.exam_code.toLowerCase().includes(term));

    const matchesSemester =
      semesterFilter === 'ALL' || exam.semester === semesterFilter;

    const matchesType =
      typeFilter === 'ALL' ||
      (typeFilter === 'Regular' && exam.exam_type?.toLowerCase().includes('reg')) ||
      (typeFilter === 'Internal' && (exam.exam_type?.toLowerCase().includes('int') || exam.exam_type?.toLowerCase().includes('mid'))) ||
      (typeFilter === 'Supplementary' && exam.exam_type?.toLowerCase().includes('sup'));

    return matchesSearch && matchesSemester && matchesType;
  });

  const handleSelect = (exam, targetPage) => {
    setActiveExam(exam);
    onNavigate(targetPage);
  };

  const handleOpenDetails = (exam) => {
    setSelectedExam(exam);
    setIsEditing(false);
    setEditFormData({
      title: exam.title || '',
      subject_code: exam.course_code || exam.subject_code || '',
      semester: exam.semester || 'S4',
      academic_year: exam.academic_year || '2024-2025',
      exam_type: exam.exam_type || 'Regular End-Semester',
      max_marks: exam.total_marks || exam.max_marks || 50,
      duration_minutes: exam.duration_minutes || 120,
      instructions: exam.instructions || '',
    });
  };

  const handleSaveEdit = async () => {
    if (!selectedExam) return;
    try {
      setSavingEdit(true);
      setError(null);
      const updated = await api.updateExam(selectedExam.id, {
        title: editFormData.title,
        subject: editFormData.title,
        subject_code: editFormData.subject_code.toUpperCase(),
        semester: editFormData.semester,
        academic_year: editFormData.academic_year,
        exam_type: editFormData.exam_type,
        max_marks: parseFloat(editFormData.max_marks),
        duration_minutes: parseInt(editFormData.duration_minutes),
        instructions: editFormData.instructions,
      });
      setSuccessMsg(`Examination "${updated.title}" updated successfully.`);
      setSelectedExam(updated);
      setIsEditing(false);
      fetchExams();
    } catch (err) {
      setError(err.message || 'Failed to update examination.');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDelete = async (examId) => {
    try {
      setError(null);
      await api.deleteExam(examId);
      setSuccessMsg('Examination deleted successfully.');
      setDeleteConfirmId(null);
      setSelectedExam(null);
      fetchExams();
    } catch (err) {
      setError(err.message || 'Failed to delete examination.');
    }
  };

  return (
    <div>
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700' }}>Manage Examinations</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            All KTU examinations, unique codes, configured questions, and uploaded scripts
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={fetchExams}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-primary" onClick={() => onNavigate('create-exam')}>
            <PlusCircle size={16} /> Create Examination
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success" style={{ marginBottom: '16px' }}>
          <CheckCircle size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Filter / Search Bar */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flex: 1, minWidth: '240px' }}>
            <Search size={18} color="var(--text-muted)" />
            <input
              type="text"
              className="form-input"
              style={{ border: 'none', background: 'transparent', padding: '0', fontSize: '14px', width: '100%' }}
              placeholder="Search by course code (e.g. CST301), title, or exam code..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Filter size={14} color="var(--text-muted)" />
              <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)' }}>Semester:</span>
              <select
                className="form-select"
                style={{ fontSize: '12px', padding: '4px 8px', width: 'auto' }}
                value={semesterFilter}
                onChange={(e) => setSemesterFilter(e.target.value)}
              >
                <option value="ALL">All Semesters</option>
                {['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'].map((sem) => (
                  <option key={sem} value={sem}>{sem}</option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)' }}>Type:</span>
              <select
                className="form-select"
                style={{ fontSize: '12px', padding: '4px 8px', width: 'auto' }}
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
              >
                <option value="ALL">All Types</option>
                <option value="Regular">Regular End-Semester</option>
                <option value="Internal">Internal Assessment</option>
                <option value="Supplementary">Supplementary</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Examinations Table */}
      <div className="card">
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Course & Subject Title</th>
                <th>Unique Exam Code</th>
                <th>Questions</th>
                <th>Total Marks</th>
                <th>Answer Sheets</th>
                <th>Documents Attached</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px' }}>
                    <span className="spinner spinner-primary" /> Loading examinations...
                  </td>
                </tr>
              ) : filteredExams.length > 0 ? (
                filteredExams.map((exam) => (
                  <tr key={exam.id}>
                    <td>
                      <div>
                        <strong>{exam.title}</strong>
                        <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                          <span className="badge badge-neutral">{exam.course_code || exam.subject_code}</span>
                          <span className="badge badge-info">{exam.semester || 'KTU'}</span>
                          <span className="badge badge-neutral">{exam.academic_year || '2024-2025'}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div className="exam-code-tag">
                        <span>{exam.exam_code}</span>
                        <button
                          className="btn-copy"
                          onClick={() => handleCopy(exam.exam_code)}
                          title="Copy Exam Code"
                        >
                          {copiedCode === exam.exam_code ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                        </button>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral">
                        {exam.questions?.length || 0} Questions
                      </span>
                    </td>
                    <td>
                      <strong>{exam.total_marks || exam.max_marks}</strong> Marks
                    </td>
                    <td>
                      <span className="badge badge-info">
                        {exam.total_sheets ?? exam.answer_sheets?.length ?? 0} Sheets
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {exam.question_paper_path && (
                          <span className="badge badge-success" title="Question Paper Attached">QP</span>
                        )}
                        {exam.answer_key_path && (
                          <span className="badge badge-success" title="Official Answer Key Attached">KEY</span>
                        )}
                        {exam.rubric_scheme_path && (
                          <span className="badge badge-success" title="Marking Scheme Attached">RUBRIC</span>
                        )}
                        {!exam.question_paper_path && !exam.answer_key_path && !exam.rubric_scheme_path && (
                          <span className="badge badge-neutral">None</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleOpenDetails(exam)}
                          title="View Details & Edit Configuration"
                        >
                          <Eye size={12} /> Details
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleSelect(exam, 'answer-sheets')}
                          title="Upload and Process Student Answer Scripts"
                        >
                          <UploadCloud size={12} /> Sheets
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => handleSelect(exam, 'reference-studio')}
                          title="Multi-Model Reference Answer & Rubric Studio"
                        >
                          <Sparkles size={12} /> Studio
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleSelect(exam, 'results')}
                          title="View Evaluated Results and Reports"
                        >
                          <BarChart3 size={12} /> Results
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          style={{ color: '#ef4444', borderColor: '#fca5a5' }}
                          onClick={() => setDeleteConfirmId(exam.id)}
                          title="Delete Examination"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                    <div style={{ maxWidth: '400px', margin: '0 auto', textAlign: 'center' }}>
                      <BookOpen size={40} color="var(--text-muted)" style={{ marginBottom: '12px', opacity: 0.5 }} />
                      <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '6px', color: 'var(--text-primary)' }}>
                        No Examinations Found
                      </h4>
                      <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '18px' }}>
                        {searchTerm || semesterFilter !== 'ALL' || typeFilter !== 'ALL'
                          ? 'No examinations matched your filters. Try clearing search filters.'
                          : 'No examinations have been created yet. Create an examination to start evaluating KTU answer scripts.'}
                      </p>
                      <button className="btn btn-primary btn-sm" onClick={() => onNavigate('create-exam')}>
                        <PlusCircle size={14} /> Create Examination
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '440px' }}>
            <div className="modal-header">
              <h3 className="modal-title" style={{ color: '#dc2626' }}>Confirm Deletion</h3>
              <button className="btn-copy" onClick={() => setDeleteConfirmId(null)}><X size={18} /></button>
            </div>
            <div className="modal-body" style={{ padding: '20px 24px' }}>
              <p style={{ fontSize: '14px', lineHeight: '1.5' }}>
                Are you sure you want to delete this examination? All associated configured questions, answer keys, uploaded answer sheets, OCR results, and evaluations will be permanently deleted.
              </p>
            </div>
            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setDeleteConfirmId(null)}>
                Cancel
              </button>
              <button
                className="btn btn-sm"
                style={{ backgroundColor: '#dc2626', color: '#ffffff' }}
                onClick={() => handleDelete(deleteConfirmId)}
              >
                Yes, Delete Examination
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Exam Details & Edit Modal */}
      {selectedExam && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '800px', width: '95%' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">{selectedExam.title}</h3>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px' }}>
                  <div className="exam-code-tag">
                    <span>{selectedExam.exam_code}</span>
                    <button
                      className="btn-copy"
                      onClick={() => handleCopy(selectedExam.exam_code)}
                      title="Copy Code"
                    >
                      {copiedCode === selectedExam.exam_code ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                    </button>
                  </div>
                  <span className="badge badge-info">{selectedExam.status || 'CONFIGURED'}</span>
                </div>
              </div>
              <button className="btn-copy" onClick={() => setSelectedExam(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body" style={{ maxHeight: '68vh', overflowY: 'auto', padding: '20px 24px' }}>
              {isEditing ? (
                /* Edit Form Mode */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Course / Examination Title *</label>
                      <input
                        type="text"
                        className="form-input"
                        value={editFormData.title}
                        onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Course Code (KTU) *</label>
                      <input
                        type="text"
                        className="form-input"
                        value={editFormData.subject_code}
                        onChange={(e) => setEditFormData({ ...editFormData, subject_code: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Semester</label>
                      <select
                        className="form-select"
                        value={editFormData.semester}
                        onChange={(e) => setEditFormData({ ...editFormData, semester: e.target.value })}
                      >
                        {['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'].map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Examination Type</label>
                      <select
                        className="form-select"
                        value={editFormData.exam_type}
                        onChange={(e) => setEditFormData({ ...editFormData, exam_type: e.target.value })}
                      >
                        <option value="Regular End-Semester">Regular End-Semester</option>
                        <option value="Internal Assessment 1">Internal Assessment 1</option>
                        <option value="Internal Assessment 2">Internal Assessment 2</option>
                        <option value="Supplementary">Supplementary</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Total Maximum Marks</label>
                      <input
                        type="number"
                        className="form-input"
                        value={editFormData.max_marks}
                        onChange={(e) => setEditFormData({ ...editFormData, max_marks: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Duration (Minutes)</label>
                      <input
                        type="number"
                        className="form-input"
                        value={editFormData.duration_minutes}
                        onChange={(e) => setEditFormData({ ...editFormData, duration_minutes: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Instructions / Description</label>
                    <textarea
                      className="form-textarea"
                      rows={3}
                      value={editFormData.instructions}
                      onChange={(e) => setEditFormData({ ...editFormData, instructions: e.target.value })}
                    />
                  </div>
                </div>
              ) : (
                /* Overview & Details Mode */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Summary Metric Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Questions</span>
                      <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
                        {selectedExam.questions?.length || 0}
                      </div>
                    </div>
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Max Marks</span>
                      <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
                        {selectedExam.total_marks || selectedExam.max_marks}
                      </div>
                    </div>
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Scripts Uploaded</span>
                      <div style={{ fontSize: '18px', fontWeight: '700', color: '#2563eb' }}>
                        {selectedExam.total_sheets ?? selectedExam.answer_sheets?.length ?? 0}
                      </div>
                    </div>
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', textAlign: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Evaluated</span>
                      <div style={{ fontSize: '18px', fontWeight: '700', color: '#16a34a' }}>
                        {selectedExam.evaluated_sheets || 0}
                      </div>
                    </div>
                  </div>

                  {/* Documents Attached */}
                  <div>
                    <h4 style={{ fontSize: '13px', fontWeight: '700', marginBottom: '8px', color: 'var(--text-secondary)' }}>
                      Persisted Documents
                    </h4>
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                      <div style={{ padding: '8px 12px', borderRadius: '6px', background: selectedExam.question_paper_path ? '#f0fdf4' : '#f8fafc', border: '1px solid var(--border-color)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <FileText size={14} color={selectedExam.question_paper_path ? '#16a34a' : '#94a3b8'} />
                        <span>Question Paper: <strong>{selectedExam.question_paper_path ? 'Persisted' : 'Not Uploaded'}</strong></span>
                      </div>
                      <div style={{ padding: '8px 12px', borderRadius: '6px', background: selectedExam.answer_key_path ? '#f0fdf4' : '#f8fafc', border: '1px solid var(--border-color)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <FileText size={14} color={selectedExam.answer_key_path ? '#16a34a' : '#94a3b8'} />
                        <span>Official Answer Key: <strong>{selectedExam.answer_key_path ? 'Persisted' : 'Not Uploaded'}</strong></span>
                      </div>
                      <div style={{ padding: '8px 12px', borderRadius: '6px', background: selectedExam.rubric_scheme_path ? '#f0fdf4' : '#f8fafc', border: '1px solid var(--border-color)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <FileText size={14} color={selectedExam.rubric_scheme_path ? '#16a34a' : '#94a3b8'} />
                        <span>Marking Scheme: <strong>{selectedExam.rubric_scheme_path ? 'Persisted' : 'Not Uploaded'}</strong></span>
                      </div>
                    </div>
                  </div>

                  {/* Configured Questions */}
                  <div>
                    <h4 style={{ fontSize: '13px', fontWeight: '700', marginBottom: '8px', color: 'var(--text-secondary)' }}>
                      Configured Question Allocation
                    </h4>
                    {selectedExam.questions?.length > 0 ? (
                      <div style={{ border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
                        <table className="data-table" style={{ margin: 0 }}>
                          <thead>
                            <tr>
                              <th>Q#</th>
                              <th>Question Description</th>
                              <th>Max Marks</th>
                              <th>Approved Reference</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedExam.questions.map((q) => (
                              <tr key={q.id}>
                                <td><strong>{q.question_number}</strong></td>
                                <td style={{ fontSize: '12px' }}>{q.text}</td>
                                <td><span className="badge badge-neutral">{q.max_marks}m</span></td>
                                <td>
                                  {q.approved_reference ? (
                                    <span className="badge badge-success">v{q.approved_reference.version} Approved</span>
                                  ) : (
                                    <span className="badge badge-warning">Pending Approval</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '8px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                        No questions configured yet for this examination.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                {!isEditing && (
                  <button
                    className="btn btn-outline btn-sm"
                    style={{ color: '#ef4444', borderColor: '#fca5a5' }}
                    onClick={() => setDeleteConfirmId(selectedExam.id)}
                  >
                    <Trash2 size={13} /> Delete Exam
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                {isEditing ? (
                  <>
                    <button className="btn btn-secondary btn-sm" onClick={() => setIsEditing(false)}>
                      Cancel
                    </button>
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={savingEdit}
                      onClick={handleSaveEdit}
                    >
                      {savingEdit ? <span className="spinner" /> : <Save size={13} />} Save Changes
                    </button>
                  </>
                ) : (
                  <>
                    <button className="btn btn-secondary btn-sm" onClick={() => setIsEditing(true)}>
                      <Edit3 size={13} /> Edit Metadata
                    </button>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => {
                        setActiveExam(selectedExam);
                        onNavigate('answer-sheets');
                      }}
                    >
                      <UploadCloud size={13} /> Upload Sheets
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
