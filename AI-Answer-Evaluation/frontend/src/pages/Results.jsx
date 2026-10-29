import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  Download,
  FileSpreadsheet,
  FileText,
  RefreshCw,
  Search,
  CheckCircle,
  AlertTriangle,
  Award,
} from 'lucide-react';
import { api } from '../api';

export default function Results({ activeExam, setActiveExam }) {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState(activeExam?.id || '');
  const [reportData, setReportData] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    api.getExams().then((data) => {
      setExams(data);
      if (!selectedExamId && data.length > 0) {
        setSelectedExamId(data[0].id);
        setActiveExam(data[0]);
      }
    }).catch(console.error);
  }, []);

  const fetchResults = async (examId) => {
    if (!examId) return;
    try {
      setLoading(true);
      setError(null);
      const [summary, analyticsData] = await Promise.all([
        api.getExamResultsSummary(examId),
        api.getExamAnalytics(examId),
      ]);
      setReportData(summary);
      setAnalytics(analyticsData);
    } catch (err) {
      setError(err.message || 'Failed to load examination results');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedExamId) {
      fetchResults(selectedExamId);
      const cur = exams.find((e) => e.id === parseInt(selectedExamId));
      if (cur) setActiveExam(cur);
    }
  }, [selectedExamId]);

  const filteredStudents = (reportData?.students || []).filter((s) =>
    s.student_identifier.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div>
      {/* Top Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: '700' }}>Examination Results & Reports</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Consolidated marks matrix, performance analytics, and official exports
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => fetchResults(selectedExamId)}>
            <RefreshCw size={14} /> Refresh
          </button>
          {selectedExamId && (
            <>
              <a
                href={api.getExportUrl(selectedExamId, 'csv')}
                className="btn btn-secondary btn-sm"
                download
                title="Download CSV"
              >
                <Download size={14} /> Export CSV
              </a>
              <a
                href={api.getExportUrl(selectedExamId, 'excel')}
                className="btn btn-primary btn-sm"
                download
                title="Download Excel Spreadsheet"
              >
                <FileSpreadsheet size={14} /> Export Excel (.xlsx)
              </a>
              <a
                href={api.getExportUrl(selectedExamId, 'pdf')}
                className="btn btn-secondary btn-sm"
                download
                title="Download PDF Summary"
              >
                <FileText size={14} /> PDF Report
              </a>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="alert alert-danger">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Exam Selector */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '13px', fontWeight: '600' }}>Select Examination:</label>
          <select
            className="form-select"
            style={{ width: 'auto', minWidth: '320px' }}
            value={selectedExamId}
            onChange={(e) => setSelectedExamId(e.target.value)}
          >
            {exams.map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.subject_code || ex.course_code || 'KTU'} - {ex.title} ({ex.exam_code})
              </option>
            ))}
          </select>

          {reportData && (
            <div className="exam-code-tag">
              <span>{reportData.exam_code}</span>
            </div>
          )}
        </div>
      </div>

      {/* Analytics KPI Overview */}
      {analytics && (
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-icon-wrap" style={{ backgroundColor: '#eff6ff', color: '#1d4ed8' }}>
              <Award size={24} />
            </div>
            <div className="metric-info">
              <span className="metric-value">
                {analytics.average_marks} <span style={{ fontSize: '14px', fontWeight: '400', color: 'var(--text-muted)' }}>/ {analytics.total_marks}</span>
              </span>
              <span className="metric-label">Class Average Marks</span>
            </div>
          </div>

          <div className="metric-card">
            <div className="metric-icon-wrap" style={{ backgroundColor: '#ecfdf5', color: '#047857' }}>
              <CheckCircle size={24} />
            </div>
            <div className="metric-info">
              <span className="metric-value">{analytics.pass_percentage}%</span>
              <span className="metric-label">Pass Rate (KTU 40% Standard)</span>
            </div>
          </div>

          <div className="metric-card">
            <div className="metric-icon-wrap" style={{ backgroundColor: '#f0fdf4', color: '#15803d' }}>
              <BarChart3 size={24} />
            </div>
            <div className="metric-info">
              <span className="metric-value">{analytics.highest_marks}</span>
              <span className="metric-label">Highest Score Achieved</span>
            </div>
          </div>

          <div className="metric-card">
            <div className="metric-icon-wrap" style={{ backgroundColor: '#fef2f2', color: '#dc2626' }}>
              <AlertTriangle size={24} />
            </div>
            <div className="metric-info">
              <span className="metric-value">{analytics.lowest_marks}</span>
              <span className="metric-label">Lowest Score</span>
            </div>
          </div>
        </div>
      )}

      {/* Student Marks Matrix Table */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Student Question-Wise Results Matrix</h3>
            <span className="card-subtitle">
              {reportData?.students?.length || 0} students evaluated for this examination
            </span>
          </div>
          <div style={{ width: '260px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search student roll number..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Student Roll / ID</th>
                {reportData?.questions?.map((q) => (
                  <th key={q.id}>
                    Q{q.question_number} ({q.max_marks}m)
                  </th>
                ))}
                <th>Total Awarded</th>
                <th>Percentage</th>
                <th>Confidence</th>
                <th>Review Status</th>
                <th>Overridden</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6 + (reportData?.questions?.length || 0)} style={{ textAlign: 'center', padding: '30px' }}>
                    <span className="spinner spinner-primary" /> Loading marks matrix...
                  </td>
                </tr>
              ) : filteredStudents.length > 0 ? (
                filteredStudents.map((s) => (
                  <tr key={s.sheet_id}>
                    <td>
                      <strong>{s.student_identifier}</strong>
                    </td>
                    {reportData?.questions?.map((q) => {
                      const score = s.question_scores[q.question_number];
                      return (
                        <td key={q.id}>
                          {score !== undefined ? (
                            <span>{score}</span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>-</span>
                          )}
                        </td>
                      );
                    })}
                    <td>
                      <strong style={{ color: '#1d4ed8' }}>
                        {s.total_awarded} / {s.max_marks}
                      </strong>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          s.percentage >= 40 ? 'badge-success' : 'badge-danger'
                        }`}
                      >
                        {s.percentage}%
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          s.average_confidence >= 0.70 ? 'badge-success' : 'badge-warning'
                        }`}
                      >
                        {Math.round(s.average_confidence * 100)}%
                      </span>
                    </td>
                    <td>
                      {s.is_reviewed ? (
                        <span className="badge badge-success">Approved</span>
                      ) : s.is_flagged ? (
                        <span className="badge badge-warning">Needs Review</span>
                      ) : (
                        <span className="badge badge-info">AI Graded</span>
                      )}
                    </td>
                    <td>
                      {s.has_override ? (
                        <span className="badge badge-success">Teacher Override</span>
                      ) : (
                        <span className="badge badge-neutral">No</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={6 + (reportData?.questions?.length || 0)}
                    style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}
                  >
                    No evaluation records available. Complete answer sheet evaluations to view results.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
