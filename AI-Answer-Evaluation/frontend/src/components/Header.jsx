import React, { useState } from 'react';
import { Copy, Check, Menu, ChevronRight, ShieldCheck, BookOpen } from 'lucide-react';

export default function Header({
  title,
  subtitle,
  activeExam,
  currentPage,
  onNavigate,
  mobileOpen,
  setMobileOpen,
  systemOnline,
}) {
  const [copied, setCopied] = useState(false);

  const handleCopyCode = (e) => {
    e.stopPropagation();
    if (activeExam?.exam_code) {
      navigator.clipboard.writeText(activeExam.exam_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getBreadcrumbLabel = (page) => {
    switch (page) {
      case 'dashboard':
        return 'Dashboard';
      case 'examinations':
        return 'Examinations';
      case 'create-exam':
        return 'Create Examination';
      case 'answer-sheets':
        return 'Answer Sheets';
      case 'ocr-review':
        return 'OCR Review';
      case 'evaluation':
        return 'Evaluation';
      case 'review-queue':
        return 'Review Queue';
      case 'results':
        return 'Reports & Export';
      case 'model-config':
        return 'Settings & Privacy';
      default:
        return 'Overview';
    }
  };

  return (
    <header className="top-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {setMobileOpen && (
          <button
            className="mobile-toggle"
            onClick={() => setMobileOpen(!mobileOpen)}
            title="Toggle Menu"
            aria-label="Toggle navigation"
          >
            <Menu size={20} />
          </button>
        )}

        <div className="page-title-group">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              color: 'var(--text-muted)',
              marginBottom: '3px',
            }}
          >
            <span
              style={{ cursor: 'pointer', hover: { color: 'var(--primary)' } }}
              onClick={() => onNavigate && onNavigate('dashboard')}
            >
              KTU AI
            </span>
            <ChevronRight size={12} />
            <span style={{ color: 'var(--text-secondary)', fontWeight: '500' }}>
              {getBreadcrumbLabel(currentPage)}
            </span>
            {activeExam && (
              <>
                <ChevronRight size={12} />
                <span
                  style={{
                    color: 'var(--primary)',
                    fontWeight: '600',
                    maxWidth: '180px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={`${activeExam.course_code}: ${activeExam.title}`}
                >
                  {activeExam.course_code || activeExam.exam_code}
                </span>
              </>
            )}
          </div>
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
        {activeExam && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'var(--bg-subtle)',
              border: '1px solid var(--border-color)',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <BookOpen size={14} color="var(--primary)" />
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: '500' }}>
              {activeExam.course_code ? `${activeExam.course_code} - ` : ''}
              <strong>{activeExam.title}</strong>
            </span>
            <div className="exam-code-tag" style={{ marginLeft: '4px' }}>
              <span>{activeExam.exam_code}</span>
              <button
                className="btn-copy"
                onClick={handleCopyCode}
                title="Copy Exam Code"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: '2px' }}
              >
                {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
              </button>
            </div>
          </div>
        )}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            backgroundColor: systemOnline ? '#f0fdf4' : '#fef2f2',
            padding: '5px 10px',
            borderRadius: 'var(--radius-full)',
            border: `1px solid ${systemOnline ? '#bbf7d0' : '#fecaca'}`,
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: systemOnline ? '#10b981' : '#ef4444',
            }}
          />
          <span style={{ fontWeight: '600', fontSize: '11px', color: systemOnline ? '#15803d' : '#b91c1c' }}>
            {systemOnline ? 'System Online' : 'Connecting...'}
          </span>
        </div>
      </div>
    </header>
  );
}

