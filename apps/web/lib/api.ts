/**
 * API client connecting Next.js frontend to FastAPI backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function getApiKey(): string | undefined {
  // Never compile an API credential into a NEXT_PUBLIC_* browser bundle.
  // Read only keys supplied explicitly for the local session.
  if (typeof window !== 'undefined') {
    try {
      return localStorage.getItem('gridlens_api_key') || undefined;
    } catch {
      return undefined;
    }
  }
  return undefined;
}

function buildHeaders(json = false): Record<string, string> | undefined {
  const key = getApiKey();
  if (!json && !key) return undefined;
  const headers: Record<string, string> = {};
  if (json) headers['Content-Type'] = 'application/json';
  if (key) headers['X-GridLens-API-Key'] = key;
  return headers;
}

export async function fetchIncidents() {
  const headers = buildHeaders();
  const res = await fetch(
    `${API_BASE_URL}/incidents`,
    headers ? { cache: 'no-store', headers } : { cache: 'no-store' },
  );
  if (!res.ok) throw new Error('Failed to fetch incidents catalog');
  return res.json();
}

export async function fetchIncident(id: string) {
  const headers = buildHeaders();
  const res = await fetch(
    `${API_BASE_URL}/incidents/${id}`,
    headers ? { cache: 'no-store', headers } : { cache: 'no-store' },
  );
  if (!res.ok) throw new Error(`Failed to fetch incident ${id}`);
  return res.json();
}

export async function fetchComtrade(id: string) {
  const headers = buildHeaders();
  const res = await fetch(
    `${API_BASE_URL}/incidents/${id}/comtrade`,
    headers ? { cache: 'no-store', headers } : { cache: 'no-store' },
  );
  if (!res.ok) throw new Error(`Failed to fetch COMTRADE oscillography for ${id}`);
  return res.json();
}

export async function fetchSubstationTopology() {
  const headers = buildHeaders();
  const res = await fetch(
    `${API_BASE_URL}/graph/topology`,
    headers ? { cache: 'no-store', headers } : { cache: 'no-store' },
  );
  if (!res.ok) throw new Error('Failed to fetch substation topology');
  return res.json();
}

export async function runInvestigation(query: string, incidentId?: string, role: string = 'ENGINEER') {
  const res = await fetch(`${API_BASE_URL}/investigations`, {
    method: 'POST',
    headers: buildHeaders(true),
    body: JSON.stringify({
      user_query: query,
      incident_id: incidentId,
      user_role: role,
    }),
  });
  if (!res.ok) throw new Error('Investigation execution failed');
  return res.json();
}

export async function runValidation(bayId: string = 'BAY_F12', customMapping?: Record<string, string>) {
  const res = await fetch(`${API_BASE_URL}/validation/run`, {
    method: 'POST',
    headers: buildHeaders(true),
    body: JSON.stringify({
      bay_id: bayId,
      custom_ct_mapping: customMapping,
    }),
  });
  if (!res.ok) throw new Error('Validation run failed');
  return res.json();
}

export async function fetchEvaluationResults() {
  const headers = buildHeaders();
  const res = await fetch(
    `${API_BASE_URL}/evaluation/results`,
    headers ? { cache: 'no-store', headers } : { cache: 'no-store' },
  );
  if (!res.ok) throw new Error('Failed to fetch evaluation benchmark results');
  return res.json();
}

export async function triggerEvaluationRun() {
  const res = await fetch(`${API_BASE_URL}/evaluation/run`, {
    method: 'POST',
    headers: buildHeaders(true),
  });
  if (!res.ok) throw new Error('Failed to execute evaluation run');
  return res.json();
}

export async function submitSimulatedAction(actionType: string, equipmentId: string, role: string, justification: string) {
  const res = await fetch(`${API_BASE_URL}/actions/simulate`, {
    method: 'POST',
    headers: buildHeaders(true),
    body: JSON.stringify({
      action_type: actionType,
      target_equipment_id: equipmentId,
      user_role: role,
      justification: justification,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Action submission failed');
  }
  return res.json();
}

export async function approveSimulatedAction(actionId: string, role: string = 'APPROVER') {
  const res = await fetch(`${API_BASE_URL}/actions/${actionId}/approve`, {
    method: 'POST',
    headers: buildHeaders(true),
    body: JSON.stringify({
      approver_role: role,
      approver_username: 'supervisor_bob',
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Approval failed');
  }
  return res.json();
}

export async function fetchProvenance(investigationId: string) {
  const headers = buildHeaders();
  const res = await fetch(
    `${API_BASE_URL}/investigations/${investigationId}/provenance`,
    headers ? { cache: 'no-store', headers } : { cache: 'no-store' },
  );
  if (!res.ok) throw new Error(`Failed to fetch provenance for ${investigationId}`);
  return res.json();
}
