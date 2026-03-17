/**
 * ARGUS API Client — typed fetch wrapper for all 17 endpoints.
 * ALL data comes from real backend calls. NO mocked data. NO hardcoded values.
 */

const BASE = '/api';

class ApiError extends Error {
  constructor(status, statusText, body) {
    super(`API Error ${status}: ${statusText}`);
    this.status = status;
    this.statusText = statusText;
    this.body = body;
  }
}

async function request(path, options = {}) {
  const url = `${BASE}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch { body = null; }
    throw new ApiError(response.status, response.statusText, body);
  }

  return response.json();
}

// ═══ HEALTH ═══
export const getHealth = () => request('/health');

// ═══ GENERATION ═══
export const generateWorld = (params) =>
  request('/generate', { method: 'POST', body: JSON.stringify(params) });

// ═══ GRAPH ═══
export const getGraphStats = () => request('/graph/stats');

export const getGraphVisualization = (limit = 500) =>
  request(`/graph/visualization?limit=${limit}`);

export const getNodes = ({ page = 1, per_page = 50, type, search } = {}) => {
  const params = new URLSearchParams({ page, per_page });
  if (type) params.set('type', type);
  if (search) params.set('search', search);
  return request(`/graph/nodes?${params}`);
};

export const getNode = (nodeId) => request(`/graph/nodes/${nodeId}`);

export const getNodeTransactions = (nodeId) =>
  request(`/graph/nodes/${nodeId}/transactions`);

export const getNodeConnections = (nodeId) =>
  request(`/graph/nodes/${nodeId}/connections`);

// ═══ INVESTIGATION ═══
export const runInvestigation = (params) =>
  request('/investigation/investigate', { method: 'POST', body: JSON.stringify(params) });

export const getInvestigations = () => request('/investigation/list');

export const getInvestigation = (caseId) =>
  request(`/investigation/${caseId}`);

export const getInvestigationProgress = (caseId) =>
  request(`/investigation/${caseId}/progress`);

// ═══ EVIDENCE ═══
export const getEvidence = ({ entity_id, type, keyword, limit = 50 } = {}) => {
  const params = new URLSearchParams();
  if (entity_id) params.set('entity_id', entity_id);
  if (type) params.set('type', type);
  if (keyword) params.set('keyword', keyword);
  if (limit) params.set('limit', limit);
  return request(`/evidence?${params}`);
};

// ═══ ASSESSMENT ═══
export const runAssessment = (caseId) =>
  request('/assess', { method: 'POST', body: JSON.stringify({ case_id: caseId }) });

export const getGroundTruthSummary = () => request('/ground-truth/summary');

export const getConfig = () => request('/config');

// ═══ RESET ═══
export const resetState = () => request('/reset', { method: 'POST' });
