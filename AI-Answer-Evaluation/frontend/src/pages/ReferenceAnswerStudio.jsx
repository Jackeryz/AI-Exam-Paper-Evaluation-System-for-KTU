import React, { useEffect, useState } from 'react';
import {
  Sparkles,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  PlusCircle,
  Trash2,
  Save,
  Layers,
  Check,
  FileText,
  Sliders,
} from 'lucide-react';
import { api } from '../api';

export default function ReferenceAnswerStudio({ activeExam, setActiveExam }) {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(activeExam?.id || '');
  const [examDetails, setExamDetails] = useState(null);
  const [selectedQuestion, setSelectedQuestion] = useState(null);

  // Proposals & Approval state
  const [proposals, setProposals] = useState([]);
  const [approvedReference, setApprovedReference] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Consolidated Reference & Rubric Form State
  const [idealAnswer, setIdealAnswer] = useState('');
  const [requiredConcepts, setRequiredConcepts] = useState('');
  const [mandatoryKeywords, setMandatoryKeywords] = useState('');
  const [rubricCriteria, setRubricCriteria] = useState([
    { criterion: 'Core Definition & Principles', allocated_marks: 3, description: 'Accurate technical definition' },
    { criterion: 'Explanation & Methodology', allocated_marks: 4, description: 'Thorough explanation of process' },
    { criterion: 'Applications & Examples', allocated_marks: 3, description: 'Relevant real-world applications' },
  ]);

  // Load exams
  useEffect(() => {
    api.getExams().then((data) => {
      setExams(data);
      if (!selectedExamId && data.length > 0) {
        setSelectedExamId(data[0].id);
        setActiveExam(data[0]);
      }
    }).catch(console.error);
  }, []);

  // Load selected exam details
  const fetchExamDetails = async (examId) => {
    if (!examId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getExam(examId);
      setExamDetails(data);
      if (data.questions && data.questions.length > 0) {
        setSelectedQuestion(data.questions[0]);
      } else {
        setSelectedQuestion(null);
      }
    } catch (err) {
      setError(err.message || 'Failed to load exam details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedExamId) {
      fetchExamDetails(selectedExamId);
      const cur = exams.find((e) => e.id === parseInt(selectedExamId));
      if (cur) setActiveExam(cur);
    }
  }, [selectedExamId]);

  // When question changes, fetch its proposals and approved reference
  const loadQuestionData = async (q) => {
    if (!q) return;
    try {
      setLoading(true);
      setError(null);
      setSuccessMsg(null);

      // 1. Fetch proposals
      const propData = await api.getProposals(q.id);
      setProposals(propData);

      // 2. Fetch approved reference if exists
      try {
        const approvedData = await api.getApprovedReference(q.id);
        setApprovedReference(approvedData);
        setIdealAnswer(approvedData?.ideal_answer || '');
        setRequiredConcepts((approvedData?.required_concepts || []).join(', '));
        setMandatoryKeywords((approvedData?.mandatory_keywords || []).join(', '));
        if (approvedData?.rubric_criteria && approvedData.rubric_criteria.length > 0) {
          setRubricCriteria(approvedData.rubric_criteria);
        }
      } catch (e) {
        // Not yet approved, check if we have proposals to pre-fill
        setApprovedReference(null);
        if (propData && propData.length > 0) {
          const first = propData[0];
          setIdealAnswer(first.proposed_ideal_answer || '');
          setRequiredConcepts((first.required_concepts || []).join(', '));
          setMandatoryKeywords((first.key_terms || []).join(', '));
          if (first.suggested_rubric && first.suggested_rubric.length > 0) {
            setRubricCriteria(first.suggested_rubric);
          }
        } else {
          // Defaults for question max marks
          setIdealAnswer('');
          setRequiredConcepts('');
          setMandatoryKeywords('');
          distributeDefaultRubric(q.max_marks);
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load question reference data');
    } finally {
      setLoading(false);
    }
  };

  const distributeDefaultRubric = (maxMarks) => {
    const half = Math.floor(maxMarks / 2);
    const rem = maxMarks - half;
    setRubricCriteria([
      { criterion: 'Conceptual Understanding & Definition', allocated_marks: half, description: 'Clarity and accuracy' },
      { criterion: 'Explanation & Technical Details', allocated_marks: rem, description: 'Completeness and terminology' },
    ]);
  };

  useEffect(() => {
    if (selectedQuestion) {
      loadQuestionData(selectedQuestion);
    }
  }, [selectedQuestion]);

  const currentRubricSum = rubricCriteria.reduce((sum, r) => sum + (parseFloat(r.allocated_marks) || 0), 0);
  const isRubricValid = selectedQuestion && currentRubricSum === parseFloat(selectedQuestion.max_marks);

  const handleGenerateMultiModel = async () => {
    if (!selectedQuestion) return;
    try {
      setGenerating(true);
      setError(null);
      setSuccessMsg(null);
      const res = await api.generateProposals(selectedQuestion.id, ['OLLAMA', 'LOCAL_FALLBACK']);
      setSuccessMsg(`Generated ${res.proposals?.length || 2} reference answer proposal(s) across AI models.`);
      loadQuestionData(selectedQuestion);
    } catch (err) {
      setError(err.message || 'Failed to generate multi-model proposals.');
    } finally {
      setGenerating(false);
    }
  };

  const handleAddCriterion = () => {
    setRubricCriteria([
      ...rubricCriteria,
      { criterion: 'New Criterion', allocated_marks: 2, description: 'Evaluation criteria' },
    ]);
  };

  const handleRemoveCriterion = (idx) => {
    if (rubricCriteria.length <= 1) return;
    setRubricCriteria(rubricCriteria.filter((_, i) => i !== idx));
  };

  const handleCriterionChange = (idx, field, val) => {
    const updated = [...rubricCriteria];
    updated[idx][field] = field === 'allocated_marks' ? (parseFloat(val) || 0) : val;
    setRubricCriteria(updated);
  };

  const handleApprove = async () => {
    if (!selectedQuestion) return;
    if (!isRubricValid) {
      setError(`Rubric allocated marks (${currentRubricSum}) must equal question max marks (${selectedQuestion.max_marks}).`);
      return;
    }
    if (!(idealAnswer || '').trim()) {
      setError('Please provide an approved ideal answer text.');
      return;
    }

    try {
      setApproving(true);
      setError(null);

      const payload = {
        ideal_answer: idealAnswer,
        required_concepts: (requiredConcepts || '').split(',').map((c) => c.trim()).filter(Boolean),
        mandatory_keywords: (mandatoryKeywords || '').split(',').map((k) => k.trim()).filter(Boolean),
        rubric_criteria: rubricCriteria,
      };

      const res = await api.approveReferenceAnswer(selectedQuestion.id, payload);
      setApprovedReference(res);
      setSuccessMsg(`Reference Answer & Rubric approved successfully (Version ${res.version}).`);
    } catch (err) {
      setError(err.message || 'Approval failed.');
    } finally {
      setApproving(false);
    }
  };

  return (
    <div>
      {/* Top Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700' }}>Reference Answer & Rubric Studio</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Multi-model ideal answer synthesis, rubric design, and teacher approval with versioning
          </p>
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

      {/* Exam & Question Selector Bar */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <label style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', display: 'block' }}>
              Select Examination:
            </label>
            <select
              className="form-select"
              style={{ width: 'auto', minWidth: '280px', marginTop: '4px' }}
              value={selectedExamId}
              onChange={(e) => setSelectedExamId(e.target.value)}
            >
              {exams.map((ex) => (
                <option key={ex.id} value={ex.id}>
                  {ex.course_code} - {ex.title} ({ex.exam_code})
                </option>
              ))}
            </select>
          </div>

          {examDetails?.questions?.length > 0 && (
            <div>
              <label style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', display: 'block' }}>
                Select Question:
              </label>
              <select
                className="form-select"
                style={{ width: 'auto', minWidth: '220px', marginTop: '4px' }}
                value={selectedQuestion?.id || ''}
                onChange={(e) => {
                  const q = examDetails.questions.find((x) => x.id === parseInt(e.target.value));
                  setSelectedQuestion(q);
                }}
              >
                {examDetails.questions.map((q) => (
                  <option key={q.id} value={q.id}>
                    Question {q.question_number} ({q.max_marks} Marks)
                  </option>
                ))}
              </select>
            </div>
          )}

          {selectedQuestion && (
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px' }}>
              {approvedReference ? (
                <span className="badge badge-success" style={{ padding: '6px 12px', fontSize: '12px' }}>
                  <Check size={14} /> Approved v{approvedReference.version}
                </span>
              ) : (
                <span className="badge badge-warning" style={{ padding: '6px 12px', fontSize: '12px' }}>
                  Draft / Unapproved
                </span>
              )}
            </div>
          )}
        </div>

        {selectedQuestion && (
          <div style={{ marginTop: '16px', padding: '12px 16px', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--primary)' }}>
              Q{selectedQuestion.question_number} ({selectedQuestion.max_marks} Marks):
            </span>
            <p style={{ fontSize: '14px', marginTop: '4px', fontWeight: '500' }}>
              {selectedQuestion.text}
            </p>
          </div>
        )}
      </div>

      {selectedQuestion ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Left Column: Multi-Model AI Proposals */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">Multi-Model AI Proposals</h3>
                <span className="card-subtitle">
                  Compare answers and rubrics proposed by different LLMs
                </span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                disabled={generating}
                onClick={handleGenerateMultiModel}
              >
                {generating ? <span className="spinner spinner-primary" /> : <Sparkles size={14} />}
                Generate Proposals
              </button>
            </div>

            {proposals.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {proposals.map((prop, idx) => (
                  <div
                    key={prop.id || idx}
                    style={{
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      padding: '16px',
                      background: '#ffffff',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span className="badge badge-info">
                        Model: {prop.model_name} ({prop.provider})
                      </span>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: '11px', padding: '2px 8px' }}
                        onClick={() => {
                          setIdealAnswer(prop.proposed_ideal_answer);
                          setRequiredConcepts((prop.required_concepts || []).join(', '));
                          setMandatoryKeywords((prop.key_terms || []).join(', '));
                          if (prop.suggested_rubric && prop.suggested_rubric.length > 0) {
                            setRubricCriteria(prop.suggested_rubric);
                          }
                        }}
                      >
                        Use this draft
                      </button>
                    </div>

                    <div style={{ fontSize: '13px', marginBottom: '8px', maxHeight: '120px', overflowY: 'auto' }}>
                      <strong>Proposed Ideal Answer:</strong>
                      <p style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
                        {prop.proposed_ideal_answer}
                      </p>
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      <strong>Key Terms:</strong> {(prop.key_terms || []).join(', ')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                <Sparkles size={32} style={{ marginBottom: '8px', opacity: 0.5 }} />
                <p>No AI proposals generated yet.</p>
                <p style={{ fontSize: '12px' }}>
                  Click <strong>Generate Proposals</strong> to query configured LLM models against the official question paper and answer key.
                </p>
              </div>
            )}
          </div>

          {/* Right Column: Teacher Reference Editor & Rubric Allocation */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">Consolidated Reference & Rubric</h3>
                <span className="card-subtitle">
                  Edit and approve reference answer and criterion-level marks
                </span>
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: '700',
                  color: isRubricValid ? 'var(--success)' : 'var(--danger)',
                }}
              >
                Rubric Sum: {currentRubricSum} / {selectedQuestion.max_marks} Marks
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Approved Ideal Answer *</label>
              <textarea
                className="form-textarea"
                style={{ minHeight: '120px' }}
                placeholder="Consolidated, approved reference answer that students will be evaluated against..."
                value={idealAnswer}
                onChange={(e) => setIdealAnswer(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Required Concepts (Comma-separated)</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Fundamental Rights, Article 19, Reasonable restrictions"
                value={requiredConcepts}
                onChange={(e) => setRequiredConcepts(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Mandatory Keywords (Comma-separated)</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. sovereignty, public order, morality"
                value={mandatoryKeywords}
                onChange={(e) => setMandatoryKeywords(e.target.value)}
              />
            </div>

            {/* Rubric Criteria Builder */}
            <div style={{ marginTop: '20px', marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <label className="form-label" style={{ margin: 0 }}>
                  Marking Rubric Criteria ({currentRubricSum} / {selectedQuestion.max_marks} Marks)
                </label>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleAddCriterion}
                >
                  <PlusCircle size={12} /> Add Criterion
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {rubricCriteria.map((rc, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      gap: '8px',
                      alignItems: 'center',
                      background: 'var(--bg-subtle)',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    <input
                      type="text"
                      className="form-input"
                      style={{ flex: 2 }}
                      placeholder="Criterion Name (e.g. Definition)"
                      value={rc.criterion}
                      onChange={(e) => handleCriterionChange(idx, 'criterion', e.target.value)}
                    />
                    <input
                      type="number"
                      className="form-input"
                      style={{ width: '70px', fontWeight: '600' }}
                      placeholder="Marks"
                      value={rc.allocated_marks}
                      onChange={(e) => handleCriterionChange(idx, 'allocated_marks', e.target.value)}
                    />
                    <input
                      type="text"
                      className="form-input"
                      style={{ flex: 2 }}
                      placeholder="Guidance / Description"
                      value={rc.description || ''}
                      onChange={(e) => handleCriterionChange(idx, 'description', e.target.value)}
                    />
                    {rubricCriteria.length > 1 && (
                      <button
                        type="button"
                        className="btn-copy"
                        style={{ color: 'var(--danger)' }}
                        onClick={() => handleRemoveCriterion(idx)}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-primary"
                disabled={approving || !isRubricValid || !(idealAnswer || '').trim()}
                onClick={handleApprove}
              >
                {approving ? (
                  <>
                    <span className="spinner" /> Approving Reference...
                  </>
                ) : (
                  <>
                    <CheckCircle size={16} /> Approve Reference & Rubric
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
          Please select or configure questions for this examination.
        </div>
      )}
    </div>
  );
}
