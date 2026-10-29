import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  FileText,
  CheckCircle,
  AlertTriangle,
  PlusCircle,
  UploadCloud,
  Copy,
  Check,
  ArrowRight,
  RefreshCw,
  Clock,
  ShieldCheck,
  Award,
  Cpu,
  Lock,
  Layers,
  ChevronRight,
} from 'lucide-react';
import { api } from '../api';

export default function Dashboard({ onNavigate, setActiveExam, setActiveSheet, setActiveEval }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedCode, setCopiedCode] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [dashData, healthData] = await Promise.all([
        api.getDashboardMetrics(),
        api.getDetailedHealth().catch(() => null),
      ]);
      setMetrics(dashData);
      setProviderStatus(healthData);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleCopy = (code, e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const handleSelectExam = (exam, targetPage) => {
    if (setActiveExam) setActiveExam(exam);
    if (onNavigate) onNavigate(targetPage);
  };

  const handleOpenReview = (ev) => {
    if (setActiveEval) setActiveEval(ev);
    if (onNavigate) onNavigate('evaluation');
  };

  return (
    <div>
      {/* Top Action Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '14px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)' }}>
            Teacher Assessment Dashboard
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Live metrics from the KTU AI evaluation engine and local SQLite database
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={fetchDashboardData} title="Refresh data">
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('answer-sheets')}>
            <UploadCloud size={14} /> Upload Scripts
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate('create-exam')}>
            <PlusCircle size={15} /> Create Examination
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '20px' }}>
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Metrics Grid */}
      <div className="metrics-grid" style={{ marginBottom: '24px' }}>
        <div className="metric-card" onClick={() => onNavigate('examinations')} style={{ cursor: 'pointer' }}>
          <div className="metric-icon-wrap" style={{ backgroundColor: '#eff6ff', color: '#1d4ed8' }}>
            <BookOpen size={24} />
          </div>
          <div className="metric-info">
            <span className="metric-value">{loading ? '...' : metrics?.total_exams ?? 0}</span>
            <span className="metric-label">Active Examinations</span>
          </div>
        </div>

        <div className="metric-card" onClick={() => onNavigate('answer-sheets')} style={{ cursor: 'pointer' }}>
          <div className="metric-icon-wrap" style={{ backgroundColor: '#f0fdf4', color: '#15803d' }}>
            <FileText size={24} />
          </div>
          <div className="metric-info">
            <span className="metric-value">{loading ? '...' : metrics?.total_answer_sheets ?? 0}</span>
            <span className="metric-label">Answer Sheets Uploaded</span>
          </div>
        </div>

        <div className="metric-card" onClick={() => onNavigate('results')} style={{ cursor: 'pointer' }}>
          <div className="metric-icon-wrap" style={{ backgroundColor: '#ecfdf5', color: '#047857' }}>
            <CheckCircle size={24} />
          </div>
          <div className="metric-info">
            <span className="metric-value">{loading ? '...' : metrics?.completed_evaluations ?? 0}</span>
            <span className="metric-label">Completed Evaluations</span>
          </div>
        </div>

        <div className="metric-card" onClick={() => onNavigate('review-queue')} style={{ cursor: 'pointer' }}>
          <div className="metric-icon-wrap" style={{ backgroundColor: '#fffbeb', color: '#b45309' }}>
            <Clock size={24} />
          </div>
          <div className="metric-info">
            <span className="metric-value" style={{ color: (metrics?.pending_reviews ?? 0) > 0 ? '#d97706' : 'var(--text-primary)' }}>
              {loading ? '...' : metrics?.pending_reviews ?? 0}
            </span>
            <span className="metric-label">Pending Teacher Reviews</span>
          </div>
        </div>
      </div>

      {/* Privacy & Provider Readiness Banner */}
      <div
        className="card"
        style={{
          padding: '16px 20px',
          marginBottom: '24px',
          backgroundColor: '#f8fafc',
          borderLeft: '4px solid #1d4ed8',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ShieldCheck size={22} color="#1d4ed8" />
            <div>
              <div style={{ fontWeight: '700', fontSize: '13px', color: 'var(--text-primary)' }}>
                Offline Local Privacy & AI Provider Status
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Strict on-premise execution: <strong>ALLOW_CLOUD_LLM=False</strong>. Student answer papers never leave local device.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }} />
              <span>PaddleOCR: <strong>PP-OCRv6 Local</strong></span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: providerStatus?.llm_status?.ollama_connected ? '#10b981' : '#f59e0b',
                }}
              />
              <span>
                LLM Provider: <strong>{providerStatus?.llm_status?.ollama_connected ? 'Ollama (Local)' : 'Deterministic Fallback'}</strong>
              </span>
            </div>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onNavigate('model-config')}
              style={{ padding: '4px 8px', fontSize: '11px' }}
            >
              Configure
            </button>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Recent Exams & Pending Reviews */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px', marginBottom: '24px' }}>
        {/* Left Column: Recent Examinations with Progress */}
        <div className="card" style={{ padding: '20px' }}>
          <div className="card-header" style={{ marginBottom: '16px' }}>
            <div>
              <h3 className="card-title" style={{ fontSize: '16px' }}>Configured Examinations</h3>
              <span className="card-subtitle">Active courses and examination papers</span>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('examinations')}>
              All Exams <ChevronRight size={13} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                <RefreshCw size={18} className="spin" style={{ margin: '0 auto 8px' }} />
                <p style={{ fontSize: '12px' }}>Loading examinations...</p>
              </div>
            ) : metrics?.recent_exams?.length > 0 ? (
              metrics.recent_exams.slice(0, 5).map((exam) => (
                <div
                  key={exam.id}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-color)',
                    backgroundColor: '#ffffff',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '12px',
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <strong style={{ fontSize: '13px', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {exam.title}
                      </strong>
                      <span className="badge badge-primary" style={{ fontSize: '10px' }}>
                        {exam.course_code}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '3px' }}>
                      Code: <code style={{ color: 'var(--primary)' }}>{exam.exam_code}</code> • Max: {exam.total_marks}m • {exam.sheet_count} Answer Sheets
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleSelectExam(exam, 'answer-sheets')}
                      style={{ padding: '4px 8px', fontSize: '11px' }}
                      title="Upload or inspect scripts"
                    >
                      <UploadCloud size={12} /> Scripts
                    </button>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSelectExam(exam, 'results')}
                      style={{ padding: '4px 8px', fontSize: '11px' }}
                      title="View Results Matrix"
                    >
                      Results
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-muted)' }}>
                No examinations found. Click <strong>Create Examination</strong> to add one.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Pending Teacher Review Stream */}
        <div className="card" style={{ padding: '20px' }}>
          <div className="card-header" style={{ marginBottom: '16px' }}>
            <div>
              <h3 className="card-title" style={{ fontSize: '16px' }}>Review Queue Highlights</h3>
              <span className="card-subtitle">Student scripts flagged or awaiting teacher approval</span>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('review-queue')}>
              Full Queue <ChevronRight size={13} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                <RefreshCw size={18} className="spin" style={{ margin: '0 auto 8px' }} />
                <p style={{ fontSize: '12px' }}>Loading review queue...</p>
              </div>
            ) : metrics?.recent_evaluations?.length > 0 ? (
              metrics.recent_evaluations.slice(0, 5).map((ev) => (
                <div
                  key={ev.id}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-color)',
                    backgroundColor: ev.is_flagged ? '#fffbeb' : '#ffffff',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: '600', fontSize: '13px' }}>
                      {ev.student_identifier}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      Q{ev.question_number} • Suggested: <strong>{ev.marks_awarded} / {ev.max_marks}m</strong>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      className={`badge ${
                        ev.confidence_score >= 0.75 ? 'badge-success' : 'badge-warning'
                      }`}
                      style={{ fontSize: '10px' }}
                    >
                      {Math.round(ev.confidence_score * 100)}%
                    </span>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleOpenReview(ev)}
                      style={{ padding: '3px 8px', fontSize: '11px' }}
                    >
                      Inspect
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-muted)' }}>
                No pending evaluations. Upload scripts and run evaluations to inspect.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
