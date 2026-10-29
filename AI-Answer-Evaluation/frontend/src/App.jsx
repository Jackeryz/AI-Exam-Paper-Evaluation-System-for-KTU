import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import Examinations from './pages/Examinations';
import CreateExam from './pages/CreateExam';
import AnswerSheets from './pages/AnswerSheets';
import OCRReview from './pages/OCRReview';
import EvaluationReview from './pages/EvaluationReview';
import ReviewQueue from './pages/ReviewQueue';
import ReferenceAnswerStudio from './pages/ReferenceAnswerStudio';
import Results from './pages/Results';
import ModelConfig from './pages/ModelConfig';
import { api } from './api';

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [activeExam, setActiveExam] = useState(null);
  const [activeSheet, setActiveSheet] = useState(null);
  const [activeEval, setActiveEval] = useState(null);
  const [systemOnline, setSystemOnline] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Initial user fetch & health check
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const user = await api.getCurrentUser();
        setCurrentUser(user);
      } catch (err) {
        console.warn('Could not fetch user profile:', err);
      }
    };

    const checkHealth = async () => {
      try {
        const res = await api.getSystemStatus();
        if (res && res.status === 'ONLINE') {
          setSystemOnline(true);
        }
      } catch (err) {
        setSystemOnline(false);
      }
    };

    const fetchPending = async () => {
      try {
        const reviews = await api.getPendingReviews(activeExam?.id || null);
        const count = reviews.filter((r) => !r.is_reviewed || r.is_flagged).length;
        setPendingCount(count);
      } catch (err) {
        // silent fallback
      }
    };

    fetchUser();
    checkHealth();
    fetchPending();

    const interval = setInterval(() => {
      checkHealth();
      fetchPending();
    }, 20000);

    return () => clearInterval(interval);
  }, [activeExam]);

  const handleLogout = () => {
    api.logout();
    window.location.reload();
  };

  const getPageMeta = () => {
    switch (currentPage) {
      case 'dashboard':
        return {
          title: 'Evaluation Dashboard',
          subtitle: 'APJ Abdul Kalam Technological University (KTU) Evaluation Platform',
        };
      case 'examinations':
        return {
          title: 'Examinations Management',
          subtitle: 'All configured examination papers, courses, and unique examination codes',
        };
      case 'create-exam':
        return {
          title: 'Create Examination',
          subtitle: 'Configure examination paper, upload key & rubric, and setup question marks',
        };
      case 'answer-sheets':
        return {
          title: 'Answer Sheets & OCR Processing',
          subtitle: 'Upload handwritten scripts, run PP-OCRv6 text extraction, and manage student submissions',
        };
      case 'ocr-review':
        return {
          title: 'OCR Inspection & Correction Studio',
          subtitle: 'Side-by-side inspection of student handwriting scans alongside editable OCR transcripts',
        };
      case 'evaluation':
        return {
          title: 'AI Evaluation & Teacher Review',
          subtitle: 'Detailed criterion rubric breakdowns, evidence extraction quotes, and mark overrides',
        };
      case 'review-queue':
        return {
          title: 'Teacher Review Queue',
          subtitle: 'Queue of flagged and pending evaluations requiring teacher authorization',
        };
      case 'reference-studio':
        return {
          title: 'Reference Answer Studio',
          subtitle: 'Multi-model ideal answer synthesis, rubric criteria builder, and teacher approval',
        };
      case 'results':
        return {
          title: 'Results & Export Reports',
          subtitle: 'Consolidated student marks matrix and official CSV, Excel (.xlsx), and PDF exports',
        };
      case 'model-config':
        return {
          title: 'Settings & System Privacy',
          subtitle: 'Local PaddleOCR PP-OCRv6 telemetry, offline privacy safeguards, and user profile',
        };
      default:
        return { title: 'KTU AI Evaluation Platform', subtitle: '' };
    }
  };

  const meta = getPageMeta();

  return (
    <div className="app-layout">
      <Sidebar
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        systemOnline={systemOnline}
        pendingCount={pendingCount}
        currentUser={currentUser}
        onLogout={handleLogout}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />

      <div className="main-wrapper">
        <Header
          title={meta.title}
          subtitle={meta.subtitle}
          activeExam={activeExam}
          currentPage={currentPage}
          onNavigate={setCurrentPage}
          mobileOpen={mobileOpen}
          setMobileOpen={setMobileOpen}
          systemOnline={systemOnline}
        />

        <main className="main-content">
          {currentPage === 'dashboard' && (
            <Dashboard
              onNavigate={setCurrentPage}
              setActiveExam={setActiveExam}
              setActiveSheet={setActiveSheet}
              setActiveEval={setActiveEval}
            />
          )}

          {currentPage === 'examinations' && (
            <Examinations
              onNavigate={setCurrentPage}
              setActiveExam={setActiveExam}
            />
          )}

          {currentPage === 'create-exam' && (
            <CreateExam
              onNavigate={setCurrentPage}
              setActiveExam={setActiveExam}
            />
          )}

          {currentPage === 'answer-sheets' && (
            <AnswerSheets
              activeExam={activeExam}
              setActiveExam={setActiveExam}
              setActiveSheet={setActiveSheet}
              onNavigate={setCurrentPage}
            />
          )}

          {currentPage === 'ocr-review' && (
            <OCRReview
              activeExam={activeExam}
              setActiveExam={setActiveExam}
              activeSheet={activeSheet}
              setActiveSheet={setActiveSheet}
              onNavigate={setCurrentPage}
            />
          )}

          {currentPage === 'evaluation' && (
            <EvaluationReview
              activeExam={activeExam}
              setActiveExam={setActiveExam}
              activeSheet={activeSheet}
              setActiveSheet={setActiveSheet}
              activeEval={activeEval}
              setActiveEval={setActiveEval}
              onNavigate={setCurrentPage}
            />
          )}

          {currentPage === 'review-queue' && (
            <ReviewQueue
              activeExam={activeExam}
              setActiveExam={setActiveExam}
              setActiveSheet={setActiveSheet}
              setActiveEval={setActiveEval}
              onNavigate={setCurrentPage}
              onUpdatePendingCount={setPendingCount}
            />
          )}

          {currentPage === 'reference-studio' && (
            <ReferenceAnswerStudio
              activeExam={activeExam}
              setActiveExam={setActiveExam}
            />
          )}

          {currentPage === 'results' && (
            <Results
              activeExam={activeExam}
              setActiveExam={setActiveExam}
            />
          )}

          {currentPage === 'model-config' && (
            <ModelConfig
              currentUser={currentUser}
            />
          )}
        </main>
      </div>
    </div>
  );
}
