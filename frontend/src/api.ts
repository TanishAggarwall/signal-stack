const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = opts
  const res = await fetch(BASE + path, {
    ...rest,
    headers: json !== undefined ? { 'Content-Type': 'application/json', ...(rest.headers || {}) } : rest.headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try { const j = await res.json(); msg = j.detail || msg } catch { /* not json */ }
    throw new Error(msg)
  }
  const ct = res.headers.get('content-type') || ''
  return (ct.includes('json') ? res.json() : res.text()) as Promise<T>
}

export const apiUrl = (p: string) => BASE + p

export type Company = {
  id: number; name: string; website: string; stage: string; summary: string; industry: string
  keywords: string[]; settings: Record<string, any>; context_version: number; created_at: string
  counts?: { sources: number; signals: number; briefs: number }; next_runs?: Record<string, string | null>
}
export type Signal = {
  id: number; category: string; title: string; what_happened: string; event_date: string | null
  evidence_quote: string; verification: string; why_it_matters: string; business_area: string
  signal_type: 'opportunity' | 'threat' | 'neutral'; consider_doing: string; impact: number; urgency: number
  relevance: number; source_reliability: number; evidence_strength: number; recency: number; novelty: number
  score: number; rank_explanation: string; competitor_name: string; competitor_id: number | null
  created_at: string; source_url?: string; publisher?: string; published_at?: string | null; fetched_at?: string
  full_text?: boolean; corroborating_doc_ids: number[]
}
export type Source = {
  id: number; category: string; kind: string; name: string; url: string; query: string; reason: string
  specific: number; recent: number; credible: number; status: string; discovered_by: string; health: string
  last_checked: string | null; last_new_item: string | null; last_error: string; fail_count: number
  total_items: number; total_signals: number; competitor_id: number | null; duplicate_of: number | null
  removed_reason: string
}
export type Job = {
  id: number; company_id: number; job_type: string; trigger: string; status: string; started_at: string
  finished_at: string | null; progress: string; stats: Record<string, any>; error: string
}
