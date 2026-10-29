import React, { useState } from 'react';
import {
  PlusCircle,
  Trash2,
  UploadCloud,
  CheckCircle,
  Copy,
  Check,
  AlertCircle,
  ArrowRight,
  BookOpen,
} from 'lucide-react';
import { api } from '../api';

export default function CreateExam({ onNavigate, setActiveExam }) {
  // Form fields
  const [formData, setFormData] = useState({
    title: '',
    course_code: '',
    semester: 'S4',
    exam_type: 'Regular',
    academic_year: '2024-2025',
    total_marks: 50,
    duration_minutes: 120,
    description: '',
  });

  // Attached files
  const [qpFile, setQpFile] = useState(null);
  const [keyFile, setKeyFile] = useState(null);
  const [rubricFile, setRubricFile] = useState(null);
  const [studyMaterialFile, setStudyMaterialFile] = useState(null);

  // Configured Questions
  const [questions, setQuestions] = useState([
    { question_number: '1(a)', text: 'Define the basic principles and objectives of the topic.', max_marks: 5, mandatory_keywords: 'principles, objectives, scope' },
    { question_number: '1(b)', text: 'Explain the working methodology with a neat diagram.', max_marks: 5, mandatory_keywords: 'methodology, block diagram, components' },
    { question_number: '2(a)', text: 'Critically analyze the significance and real-world applications.', max_marks: 10, mandatory_keywords: 'significance, applications, analysis' },
  ]);

  // Submission state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [createdExam, setCreatedExam] = useState(null);
  const [copiedCode, setCopiedCode] = useState(false);

  // Calculate sum of question marks
  const currentTotalMarks = questions.reduce((sum, q) => sum + (parseFloat(q.max_marks) || 0), 0);
  const isMarksValid = currentTotalMarks === parseFloat(formData.total_marks);

  const handleAddQuestion = () => {
    const nextIndex = questions.length + 1;
    setQuestions([
      ...questions,
      {
        question_number: `${nextIndex}(a)`,
        text: '',
        max_marks: 5,
        mandatory_keywords: '',
      },
    ]);
  };

  const handleRemoveQuestion = (idx) => {
    if (questions.length <= 1) return;
    setQuestions(questions.filter((_, i) => i !== idx));
  };

  const handleQuestionChange = (idx, field, val) => {
    const updated = [...questions];
    updated[idx][field] = field === 'max_marks' ? (parseFloat(val) || 0) : val;
    setQuestions(updated);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!formData.title || !formData.course_code) {
      setError('Please provide examination title and KTU course code.');
      return;
    }

    if (!isMarksValid) {
      setError(`Sum of question marks (${currentTotalMarks} marks) does not match total examination marks (${formData.total_marks} marks). Please adjust question marks.`);
      return;
    }

    try {
      setLoading(true);

      // 1. Create Examination
      const examPayload = {
        title: formData.title,
        subject: formData.title,
        subject_code: formData.course_code.toUpperCase(),
        course_code: formData.course_code.toUpperCase(),
        max_marks: parseFloat(formData.total_marks),
        total_marks: parseFloat(formData.total_marks),
        exam_type: formData.exam_type,
        academic_year: formData.academic_year,
        semester: formData.semester,
        duration_minutes: parseInt(formData.duration_minutes),
        instructions: formData.description,
        description: formData.description,
      };

      const examResult = await api.createExam(examPayload);
      const examId = examResult.id;

      // 2. Upload Documents if provided
      if (qpFile || keyFile || rubricFile || studyMaterialFile) {
        const docData = new FormData();
        if (qpFile) docData.append('question_paper', qpFile);
        if (keyFile) docData.append('answer_key', keyFile);
        if (rubricFile) docData.append('rubric_scheme', rubricFile);
        if (studyMaterialFile) docData.append('study_material', studyMaterialFile);

        await api.uploadExamDocuments(examId, docData);
      }

      // 3. Save Configured Questions
      const formattedQuestions = questions.map((q) => ({
        question_number: q.question_number,
        text: q.text,
        max_marks: q.max_marks,
        mandatory_keywords: q.mandatory_keywords ? q.mandatory_keywords.split(',').map((k) => k.trim()) : [],
      }));

      await api.configureQuestions(examId, formattedQuestions);

      // Fetch the updated full exam
      const finalExam = await api.getExam(examId);
      setCreatedExam(finalExam);
      setActiveExam(finalExam);
    } catch (err) {
      setError(err.message || 'Error creating examination. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (createdExam?.exam_code) {
      navigator.clipboard.writeText(createdExam.exam_code);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    }
  };

  if (createdExam) {
    return (
      <div className="card" style={{ maxWidth: '800px', margin: '40px auto', padding: '36px', textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
          <div style={{ width: '64px', height: '64px', borderRadius: '50%', backgroundColor: '#ecfdf5', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#059669' }}>
            <CheckCircle size={36} />
          </div>
        </div>
        <h2 style={{ fontSize: '22px', fontWeight: '700', marginBottom: '8px' }}>
          Examination Created Successfully!
        </h2>
        <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
          Your KTU examination has been registered in the database with configured questions and documents.
        </p>

        <div style={{ background: '#0f172a', padding: '20px', borderRadius: '12px', display: 'inline-flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
          <div style={{ textAlign: 'left' }}>
            <span style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Unique KTU Examination Code
            </span>
            <div style={{ fontSize: '22px', fontWeight: '700', color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
              {createdExam.exam_code}
            </div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={handleCopy}>
            {copiedCode ? <Check size={14} color="#10b981" /> : <Copy size={14} />} {copiedCode ? 'Copied!' : 'Copy Code'}
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '14px' }}>
          <button
            className="btn btn-primary"
            onClick={() => {
              setActiveExam(createdExam);
              onNavigate('answer-sheets');
            }}
          >
            <UploadCloud size={16} /> Upload Student Answer Sheets <ArrowRight size={14} />
          </button>
          <button
            className="btn btn-outline"
            onClick={() => {
              setActiveExam(createdExam);
              onNavigate('reference-studio');
            }}
          >
            Open Reference Answer Studio
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: '700' }}>Create New Examination</h2>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Configure university examination details, upload official documents, and setup questions & marks
        </p>
      </div>

      {error && (
        <div className="alert alert-danger">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Step 1: Exam General Details */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: '16px' }}>1. Basic Examination Information</h3>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Subject / Examination Title *</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Constitution of India & Professional Ethics"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Course Code *</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. MCN301, EST130, HUT200"
                value={formData.course_code}
                onChange={(e) => setFormData({ ...formData, course_code: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Semester</label>
              <select
                className="form-select"
                value={formData.semester}
                onChange={(e) => setFormData({ ...formData, semester: e.target.value })}
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
                value={formData.exam_type}
                onChange={(e) => setFormData({ ...formData, exam_type: e.target.value })}
              >
                <option value="Regular">Regular End Semester Examination</option>
                <option value="Internal">Internal Assessment / Mid-Term</option>
                <option value="Supplementary">Supplementary Examination</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Total Maximum Marks *</label>
              <input
                type="number"
                className="form-input"
                value={formData.total_marks}
                onChange={(e) => setFormData({ ...formData, total_marks: e.target.value })}
                min="5"
                max="100"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Duration (Minutes)</label>
              <input
                type="number"
                className="form-input"
                value={formData.duration_minutes}
                onChange={(e) => setFormData({ ...formData, duration_minutes: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Description / Instructions</label>
            <textarea
              className="form-textarea"
              placeholder="e.g. Answer all questions from Part A. Each question carries 5 marks."
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
        </div>

        {/* Step 2: Upload Documents */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: '16px' }}>2. Official Documents & Answer Key</h3>
          <p className="card-subtitle" style={{ marginBottom: '16px' }}>
            Upload official examination papers and answer guides (PDF, PNG, JPG supported)
          </p>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Question Paper (PDF/Image)</label>
              <input
                type="file"
                className="form-input"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => setQpFile(e.target.files[0])}
              />
              <span className="form-hint">{qpFile ? qpFile.name : 'No file selected'}</span>
            </div>

            <div className="form-group">
              <label className="form-label">Official Answer Key (PDF/Image/Text)</label>
              <input
                type="file"
                className="form-input"
                accept=".pdf,.png,.jpg,.jpeg,.txt"
                onChange={(e) => setKeyFile(e.target.files[0])}
              />
              <span className="form-hint">{keyFile ? keyFile.name : 'No file selected'}</span>
            </div>

            <div className="form-group">
              <label className="form-label">Marking Scheme / Rubric (Optional)</label>
              <input
                type="file"
                className="form-input"
                accept=".pdf,.png,.jpg,.jpeg,.txt"
                onChange={(e) => setRubricFile(e.target.files[0])}
              />
              <span className="form-hint">{rubricFile ? rubricFile.name : 'Optional'}</span>
            </div>
          </div>
        </div>

        {/* Step 3: Question Configuration */}
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">3. Questions & Maximum Marks Configuration</h3>
              <span className="card-subtitle">
                Configure question numbers, prompts, and mark allocations
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div
                style={{
                  fontSize: '13px',
                  fontWeight: '600',
                  color: isMarksValid ? 'var(--success)' : 'var(--danger)',
                }}
              >
                Allocated: {currentTotalMarks} / {formData.total_marks} Marks
                {isMarksValid ? ' (Valid)' : ' (Mismatch)'}
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleAddQuestion}
              >
                <PlusCircle size={14} /> Add Question
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {questions.map((q, idx) => (
              <div
                key={idx}
                style={{
                  padding: '16px',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: '700' }}>#{idx + 1}</span>
                    <input
                      type="text"
                      className="form-input"
                      style={{ width: '100px', fontWeight: '600' }}
                      placeholder="e.g. 1(a)"
                      value={q.question_number}
                      onChange={(e) => handleQuestionChange(idx, 'question_number', e.target.value)}
                      required
                    />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '12px', fontWeight: '500' }}>Marks:</span>
                      <input
                        type="number"
                        className="form-input"
                        style={{ width: '70px', fontWeight: '600' }}
                        value={q.max_marks}
                        onChange={(e) => handleQuestionChange(idx, 'max_marks', e.target.value)}
                        min="1"
                        max="50"
                        required
                      />
                    </div>
                    {questions.length > 1 && (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ color: 'var(--danger)' }}
                        onClick={() => handleRemoveQuestion(idx)}
                        title="Remove question"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: '8px' }}>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Question prompt/text (e.g. State and explain the fundamental rights enshrined in Article 19)"
                    value={q.text}
                    onChange={(e) => handleQuestionChange(idx, 'text', e.target.value)}
                    required
                  />
                </div>

                <div className="form-group" style={{ marginBottom: '0' }}>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Mandatory keywords/concepts (comma-separated, e.g. freedom of speech, assembly, reasonable restrictions)"
                    value={q.mandatory_keywords}
                    onChange={(e) => handleQuestionChange(idx, 'mandatory_keywords', e.target.value)}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Submit Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '20px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => onNavigate('examinations')}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading || !isMarksValid}
          >
            {loading ? (
              <>
                <span className="spinner" /> Creating Examination...
              </>
            ) : (
              <>
                <CheckCircle size={18} /> Register Examination & Generate Code
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
