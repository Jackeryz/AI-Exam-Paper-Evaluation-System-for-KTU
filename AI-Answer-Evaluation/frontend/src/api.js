/**
 * Central API Client for KTU AI Evaluation Platform
 * Talks to FastAPI backend via /api/v1/...
 */

const API_BASE = '/api/v1';

let cachedToken = localStorage.getItem('ktu_auth_token') || null;

async function getOrFetchToken() {
  if (cachedToken) return cachedToken;
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'teacher@ktu.edu.in', password: 'teacher123' }),
    });
    if (res.ok) {
      const data = await res.json();
      cachedToken = data.access_token;
      localStorage.setItem('ktu_auth_token', cachedToken);
      return cachedToken;
    }
  } catch (err) {
    console.warn('Auto-login notice:', err);
  }
  return null;
}

async function request(endpoint, options = {}) {
  const token = await getOrFetchToken();
  const headers = { ...(options.headers || {}) };
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorDetail = 'Network request failed';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch (e) {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail || `HTTP error ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }

  // Handle binary/attachment responses
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('text/csv') || contentType.includes('application/vnd') || contentType.includes('application/pdf')) {
    return response.blob();
  }

  return response.json();
}

export const api = {
  // System Health
  getSystemStatus: () => fetch('/api/').then((res) => res.json()),
  getDetailedHealth: () => fetch('/api/health').then((res) => res.json()),

  // Dashboard & Analytics
  getDashboardMetrics: () => request('/analytics/dashboard'),
  getExamAnalytics: (examId) => request(`/analytics/exam/${examId}`),

  // Examinations
  getExams: () => request('/exams/'),
  getExam: (examId) => request(`/exams/${examId}`),
  getExamByCode: (code) => request(`/exams/code/${code}`),
  createExam: (data) =>
    request('/exams/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  updateExam: (examId, data) =>
    request(`/exams/${examId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  deleteExam: (examId) =>
    request(`/exams/${examId}`, {
      method: 'DELETE',
    }),
  uploadExamDocuments: (examId, formData) =>
    request(`/exams/${examId}/upload-documents`, {
      method: 'POST',
      body: formData,
    }),
  configureQuestions: (examId, questions) =>
    request(`/exams/${examId}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(questions),
    }),

  // Answer Sheets & OCR
  getAnswerSheets: (examId) => request(`/answer-sheets/exam/${examId}`),
  uploadAnswerSheets: (examId, formData) =>
    request(`/answer-sheets/upload/${examId}`, {
      method: 'POST',
      body: formData,
    }),
  getAnswerSheetDetails: (sheetId) => request(`/answer-sheets/${sheetId}`),
  processSheetOCR: (sheetId) =>
    request(`/answer-sheets/${sheetId}/process-ocr`, {
      method: 'POST',
    }),
  refineSheetOCR: (sheetId) =>
    request(`/answer-sheets/${sheetId}/refine-ocr`, {
      method: 'POST',
    }),
  correctOCRText: (sheetId, refinedText) =>
    request(`/answer-sheets/${sheetId}/ocr-correction`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ corrected_text: refinedText, refined_text: refinedText }),
    }),
  correctSegmentText: (sheetId, segmentId, text) =>
    request(`/answer-sheets/${sheetId}/ocr-correction`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ extracted_answer_id: segmentId, corrected_text: text }),
    }),
  approveRefinement: (sheetId, payload) =>
    request(`/answer-sheets/${sheetId}/approve-refinement`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // Reference Answers
  getProposals: (questionId) => request(`/reference-answers/question/${questionId}/proposals`),
  generateProposals: (questionId, providers = ['OLLAMA', 'LOCAL']) =>
    request(`/reference-answers/question/${questionId}/generate-proposals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ providers }),
    }),
  getApprovedReference: (questionId) => request(`/reference-answers/question/${questionId}/approved`),
  approveReferenceAnswer: (questionId, payload) =>
    request(`/reference-answers/question/${questionId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // Auth & Profile
  login: async (email, password) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Authentication failed');
    }
    const data = await res.json();
    cachedToken = data.access_token;
    localStorage.setItem('ktu_auth_token', cachedToken);
    return data;
  },
  logout: () => {
    cachedToken = null;
    localStorage.removeItem('ktu_auth_token');
  },
  getCurrentUser: () => request('/auth/me'),
  getToken: () => cachedToken || localStorage.getItem('ktu_auth_token'),

  // AI Evaluation
  evaluateSheet: (sheetId) =>
    request(`/evaluations/sheet/${sheetId}/run`, {
      method: 'POST',
    }),
  getEvaluationDetails: (evalId) => request(`/evaluations/${evalId}`),
  getSheetEvaluations: (sheetId) => request(`/evaluations/sheet/${sheetId}`),

  // Answer Sheet Document Preview URL
  getAnswerSheetFileUrl: (sheetId) => {
    const token = cachedToken || localStorage.getItem('ktu_auth_token');
    const authQuery = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${API_BASE}/answer-sheets/${sheetId}/file${authQuery}`;
  },

  // Teacher Review & Overrides
  getPendingReviews: (examId = null) =>
    request(`/reviews/pending${examId ? `?exam_id=${examId}` : ''}`),
  overrideEvaluation: (evalId, payload) =>
    request(`/reviews/evaluations/${evalId}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // Results & Reports
  getExamResultsSummary: (examId) => request(`/reports/exam/${examId}/summary`),
  getExportUrl: (examId, format = 'csv') => {
    const token = localStorage.getItem('ktu_auth_token') || cachedToken;
    const authQuery = token ? `&token=${encodeURIComponent(token)}` : '';
    return `${API_BASE}/reports/exam/${examId}/export?format=${format}${authQuery}`;
  },
};


