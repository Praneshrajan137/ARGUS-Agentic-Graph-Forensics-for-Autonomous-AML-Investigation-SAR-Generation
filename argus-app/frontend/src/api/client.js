/**
 * ARGUS API Client — supports both the isolated Production Workbench API and
 * the separate Research Runtime API. Uses cookie sessions + in-memory CSRF token
 * (never localStorage) and supports caller AbortSignal cancellation.
 */

const BASE = '/api';
const DEFAULT_TIMEOUT_MS = 10_000;
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

let _epoch = null;
let _csrfToken = null;

export function setCsrfToken(token) {
  _csrfToken = token || null;
}

export function getCsrfToken() {
  return _csrfToken;
}

export class ApiError extends Error {
  constructor(status, statusText, body, { isNetworkError = false, isAborted = false } = {}) {
    const detail = body?.detail || statusText;
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.body = body;
    this.isNetworkError = isNetworkError;
    this.isAborted = isAborted;
  }
}

async function request(path, options = {}) {
  const { timeout = DEFAULT_TIMEOUT_MS, signal: callerSignal, isMultipart = false, ...fetchOptions } = options;
  const url = `${BASE}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  const onCallerAbort = () => controller.abort();
  if (callerSignal) {
    if (callerSignal.aborted) {
      clearTimeout(timeoutId);
      throw new ApiError(0, 'Aborted', { detail: 'Request cancelled' }, { isAborted: true });
    }
    callerSignal.addEventListener('abort', onCallerAbort, { once: true });
  }

  const method = (fetchOptions.method || 'GET').toUpperCase();
  const headers = {
    ...(isMultipart ? {} : { 'Content-Type': 'application/json' }),
    ...(UNSAFE_METHODS.has(method) && _csrfToken ? { 'X-CSRF-Token': _csrfToken } : {}),
    ...(fetchOptions.headers || {}),
  };

  const config = {
    credentials: 'include',
    ...fetchOptions,
    headers,
    signal: controller.signal,
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (err) {
    if (callerSignal?.aborted) {
      throw new ApiError(0, 'Aborted', { detail: 'Request cancelled' }, { isAborted: true });
    }
    if (err.name === 'AbortError') {
      throw new ApiError(0, 'Request timed out', { detail: `Request to ${path} timed out after ${timeout}ms` }, { isNetworkError: true });
    }
    throw new ApiError(0, 'Network error', { detail: 'Cannot reach the ARGUS backend. Check connectivity.' }, { isNetworkError: true });
  } finally {
    clearTimeout(timeoutId);
    if (callerSignal) callerSignal.removeEventListener('abort', onCallerAbort);
  }

  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch { body = null; }
    throw new ApiError(response.status, response.statusText, body);
  }

  const serverEpoch = parseInt(response.headers?.get?.('X-ARGUS-Epoch'), 10);
  if (!Number.isNaN(serverEpoch)) {
    if (_epoch !== null && serverEpoch !== _epoch) {
      window.dispatchEvent(new CustomEvent('argus:epoch-change', {
        detail: { prev: _epoch, next: serverEpoch },
      }));
    }
    _epoch = serverEpoch;
  }

  return response.json();
}

// ═══ PRODUCTION RUNTIME & AUTH ═══
export const getRuntime = (opts) => request('/runtime', opts);
export const getProdReady = (opts) => request('/health/ready', opts);
export const getProdWorkers = (opts) => request('/health/workers', opts);
export const getAuthMe = (opts) => request('/auth/me', opts);
export const logout = () => request('/auth/logout', { method: 'POST' });

// ═══ PRODUCTION DATASETS & INTAKE ═══
export const getDatasets = (opts) => request('/datasets', opts);
export const createDataset = (params) =>
  request('/datasets', { method: 'POST', body: JSON.stringify(params) });
export const getDatasetImports = (datasetId, opts) =>
  request(`/datasets/${datasetId}/imports`, opts);
export const uploadImportBatch = (datasetId, formData, idempotencyKey) =>
  request(`/datasets/${datasetId}/imports`, {
    method: 'POST',
    body: formData,
    isMultipart: true,
    timeout: 60_000,
    headers: { 'Idempotency-Key': idempotencyKey },
  });

// ═══ PRODUCTION CASES, JOBS, OBSERVATIONS, REVIEW & EXPORT ═══
export const getCases = (opts) => request('/cases', opts);
export const createCase = (params) =>
  request('/cases', { method: 'POST', body: JSON.stringify(params) });
export const getCase = (caseId, opts) => request(`/cases/${caseId}`, opts);
export const getCaseRecords = (caseId, eventIds, opts) => {
  const qs = eventIds?.length ? `?event_ids=${encodeURIComponent(eventIds.join(','))}` : '';
  return request(`/cases/${caseId}/records${qs}`, opts);
};
export const enqueueCaseAnalysis = (caseId, params, idempotencyKey) =>
  request(`/cases/${caseId}/analyze`, {
    method: 'POST',
    body: JSON.stringify(params),
    headers: { 'Idempotency-Key': idempotencyKey },
  });
export const getJobStatus = (jobId, opts) => request(`/jobs/${jobId}`, opts);
export const cancelJob = (jobId) => request(`/jobs/${jobId}/cancel`, { method: 'POST' });
export const addCaseObservation = (caseId, params) =>
  request(`/cases/${caseId}/observations`, { method: 'POST', body: JSON.stringify(params) });
export const addFindingDisposition = (caseId, params) =>
  request(`/cases/${caseId}/dispositions`, { method: 'POST', body: JSON.stringify(params) });
export const addCaseComment = (caseId, params) =>
  request(`/cases/${caseId}/comments`, { method: 'POST', body: JSON.stringify(params) });
export const createCaseArtifact = (caseId, params) =>
  request(`/cases/${caseId}/artifacts`, { method: 'POST', body: JSON.stringify(params) });
export const getArtifact = (artifactId, opts) => request(`/artifacts/${artifactId}`, opts);
export const freezeArtifact = (artifactId) =>
  request(`/artifacts/${artifactId}/freeze`, { method: 'POST' });
export const reviewArtifact = (artifactId, params) =>
  request(`/artifacts/${artifactId}/review`, { method: 'POST', body: JSON.stringify(params) });
export const exportArtifact = (artifactId, params = { allow_historical: false }) =>
  request(`/artifacts/${artifactId}/export`, { method: 'POST', body: JSON.stringify(params) });
export const closeCase = (caseId, params) =>
  request(`/cases/${caseId}/close`, { method: 'POST', body: JSON.stringify(params) });

// ═══ RESEARCH RUNTIME (SEPARATE MODE ONLY) ═══
export const getHealth = (opts) => request('/health', opts);
export const generateWorld = (params) =>
  request('/generate', { method: 'POST', body: JSON.stringify(params), timeout: 180_000 });
export const getGraphStats = (opts) => request('/graph/stats', opts);
export const getGraphVisualization = (limit = 5000, opts) =>
  request(`/graph/visualization?limit=${limit}`, opts);
export const getNodes = ({ page = 1, per_page = 50, type, search } = {}, opts) => {
  const params = new URLSearchParams({ page, per_page });
  if (type) params.set('type', type);
  if (search) params.set('search', search);
  return request(`/graph/nodes?${params}`, opts);
};
export const getNode = (nodeId, opts) => request(`/graph/nodes/${nodeId}`, opts);
export const getNodeTransactions = (nodeId, opts) => request(`/graph/nodes/${nodeId}/transactions`, opts);
export const getNodeConnections = (nodeId, opts) => request(`/graph/nodes/${nodeId}/connections`, opts);
export const runInvestigation = (params) =>
  request('/investigation/investigate', { method: 'POST', body: JSON.stringify(params), timeout: 10_000 });
export const getInvestigations = (opts) => request('/investigation/list', opts);
export const getInvestigation = (caseId, opts) => request(`/investigation/${caseId}`, opts);
export const getInvestigationProgress = (caseId, opts) => request(`/investigation/${caseId}/progress`, opts);
export const getEvidence = ({ entity_id, type, keyword, limit = 50 } = {}, opts) => {
  const params = new URLSearchParams();
  if (entity_id) params.set('entity_id', entity_id);
  if (type) params.set('type', type);
  if (keyword) params.set('keyword', keyword);
  if (limit) params.set('limit', limit);
  return request(`/evidence?${params}`, opts);
};
export const runAssessment = (caseId) =>
  request('/assess', { method: 'POST', body: JSON.stringify({ case_id: caseId }) });
export const getGroundTruthSummary = (opts) => request('/ground-truth/summary', opts);
export const getConfig = (opts) => request('/config', opts);
export const runBenchmark = (params) =>
  request('/benchmark/run', { method: 'POST', body: JSON.stringify(params), timeout: 10_000 });
export const getBenchmark = (benchmarkId, opts) => request(`/benchmark/${benchmarkId}`, { timeout: 30_000, ...opts });
export const getBenchmarkProgress = (benchmarkId, opts) => request(`/benchmark/${benchmarkId}/progress`, opts);
export const getBenchmarks = (opts) => request('/benchmark/list', opts);
export const getAgentCard = (opts) => request('/agent/agent.json', opts);
export const getAgentHealth = (opts) => request('/agent/health', opts);
export const getAgentConfig = (opts) => request('/agent/config', opts);
export const runBaselineInvestigation = (params) =>
  request('/investigation/baseline', { method: 'POST', body: JSON.stringify(params), timeout: 30_000 });
export const resetState = () => request('/reset', { method: 'POST' });
