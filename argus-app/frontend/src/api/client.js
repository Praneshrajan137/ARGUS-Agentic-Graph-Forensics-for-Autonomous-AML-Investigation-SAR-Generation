/**
 * ARGUS API Client — typed fetch wrapper for all 17 endpoints.
 * ALL data comes from real backend calls. NO mocked data. NO hardcoded values.
 */

const BASE = '/api';

/** Default timeout: 10s for reads, overridden per-call for long operations */
const DEFAULT_TIMEOUT_MS = 10_000;

/** Stale-state detection: tracks backend generation epoch */
let _epoch = null;

export class ApiError extends Error {
  constructor(status, statusText, body) {
    const detail = body?.detail || statusText;
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.body = body;
  }
}

async function request(path, options = {}) {
  const { timeout = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options;
  const url = `${BASE}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  const config = {
    headers: { 'Content-Type': 'application/json' },
    signal: controller.signal,
    ...fetchOptions,
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError(0, 'Request timed out', { detail: `Request to ${path} timed out after ${timeout}ms` });
    }
    // Network error (backend down, CORS, etc.)
    throw new ApiError(0, 'Network error', { detail: 'Cannot reach the ARGUS backend. Is the server running?' });
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch { body = null; }
    throw new ApiError(response.status, response.statusText, body);
  }

  // Track server epoch for stale-state detection
  const serverEpoch = parseInt(response.headers.get('X-ARGUS-Epoch'), 10);
  if (!isNaN(serverEpoch)) {
    if (_epoch !== null && serverEpoch !== _epoch) {
      window.dispatchEvent(new CustomEvent('argus:epoch-change', {
        detail: { prev: _epoch, next: serverEpoch },
      }));
    }
    _epoch = serverEpoch;
  }

  return response.json();
}

// ═══ HEALTH ═══
export const getHealth = () => request('/health');

// ═══ GENERATION ═══
export const generateWorld = (params) =>
  request('/generate', { method: 'POST', body: JSON.stringify(params), timeout: 60_000 });

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
  request('/investigation/investigate', { method: 'POST', body: JSON.stringify(params), timeout: 30_000 });

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

// ═══ BENCHMARK ═══
export const runBenchmark = (params) =>
  request('/benchmark/run', { method: 'POST', body: JSON.stringify(params), timeout: 10_000 });

export const getBenchmark = (benchmarkId) =>
  request(`/benchmark/${benchmarkId}`, { timeout: 30_000 });

export const getBenchmarkProgress = (benchmarkId) =>
  request(`/benchmark/${benchmarkId}/progress`);

export const getBenchmarks = () => request('/benchmark/list');

// ═══ PURPLE AGENT ═══
export const getAgentCard = () => request('/agent/agent.json');

export const getAgentHealth = () => request('/agent/health');

export const getAgentConfig = () => request('/agent/config');

export const runBaselineInvestigation = (params) =>
  request('/investigation/baseline', { method: 'POST', body: JSON.stringify(params), timeout: 30_000 });

// ═══ RESET ═══
export const resetState = () => request('/reset', { method: 'POST' });
