import React from 'react';
import {
  LayoutDashboard,
  BookOpen,
  FileText,
  FileSearch,
  Award,
  Clock,
  BarChart3,
  ShieldCheck,
  LogOut,
  X,
  Lock,
} from 'lucide-react';

export default function Sidebar({
  currentPage,
  setCurrentPage,
  systemOnline,
  pendingCount = 0,
  currentUser = null,
  onLogout = () => {},
  mobileOpen = false,
  setMobileOpen = () => {},
}) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'examinations', label: 'Examinations', icon: BookOpen },
    { id: 'answer-sheets', label: 'Answer Sheets', icon: FileText },
    { id: 'ocr-review', label: 'OCR Review', icon: FileSearch },
    { id: 'evaluation', label: 'Evaluation', icon: Award },
    { id: 'review-queue', label: 'Review Queue', icon: Clock, badge: pendingCount > 0 ? pendingCount : null },
    { id: 'results', label: 'Reports & Export', icon: BarChart3 },
    { id: 'model-config', label: 'Settings & Privacy', icon: ShieldCheck },
  ];

  const handleNavClick = (id) => {
    setCurrentPage(id);
    if (setMobileOpen) setMobileOpen(false);
  };

  const teacherName = currentUser?.full_name || 'Prof. Evaluation Teacher';
  const teacherRole = currentUser?.role === 'ADMIN' ? 'System Administrator' : 'KTU Evaluator';
  const initials = teacherName
    .split(' ')
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'ET';

  return (
    <>
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <span className="brand-badge">KTU APJ ABDUL KALAM UNIV</span>
            <h2 className="brand-title">KTU AI Evaluation</h2>
            <p className="brand-sub">Handwritten Assessment Platform</p>
          </div>
          {setMobileOpen && (
            <button
              className="btn-copy"
              onClick={() => setMobileOpen(false)}
              style={{ display: mobileOpen ? 'flex' : 'none', color: '#94a3b8' }}
              title="Close menu"
            >
              <X size={18} />
            </button>
          )}
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                className={`nav-link ${isActive ? 'active' : ''}`}
                onClick={() => handleNavClick(item.id)}
              >
                <Icon size={18} />
                <span style={{ flex: 1, textAlign: 'left' }}>{item.label}</span>
                {item.badge && (
                  <span
                    style={{
                      backgroundColor: isActive ? '#ffffff' : '#f59e0b',
                      color: isActive ? '#1d4ed8' : '#ffffff',
                      fontSize: '11px',
                      fontWeight: '700',
                      padding: '1px 6px',
                      borderRadius: '10px',
                      lineHeight: '1.4',
                    }}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          {/* User Profile Widget */}
          <div className="user-profile-widget">
            <div className="user-profile-info">
              <div className="user-avatar">{initials}</div>
              <div style={{ minWidth: 0 }}>
                <div className="user-meta-name" title={teacherName}>
                  {teacherName}
                </div>
                <div className="user-meta-role">{teacherRole}</div>
              </div>
            </div>
            <button
              className="btn-signout"
              onClick={onLogout}
              title="Sign out of KTU Evaluation session"
            >
              <LogOut size={16} />
            </button>
          </div>

          {/* Privacy & System Status */}
          <div className="system-status" style={{ justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                className="status-dot"
                style={{ backgroundColor: systemOnline ? '#10b981' : '#ef4444' }}
              />
              <span style={{ fontSize: '11px' }}>
                {systemOnline ? 'PaddleOCR PP-OCRv6 Local' : 'Connecting backend...'}
              </span>
            </div>
            <span
              style={{
                fontSize: '10px',
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
              }}
              title="Cloud LLMs blocked: Student data strictly stays on local device"
            >
              <Lock size={10} /> Offline
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
