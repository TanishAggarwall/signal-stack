import { useState } from 'react'
import { Check, ExternalLink, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { api } from '../api'
import { Badge, Button, Card, Empty, ErrorNote, Input, PageHeader, Textarea, fmtTime, useApp, useLoad } from '../ui'

const STATUS_TONE: Record<string, string> = { verified: 'green', assumption: 'amber', founder: 'violet' }
const STATUS_HELP: Record<string, string> = {
  verified: 'Quoted from a page we fetched (link shown)', assumption: 'AI inference, not confirmed', founder: 'Stated by the founder',
}

export default function Profile() {
  const { company, track } = useApp()
  const { data, error, reload } = useLoad(() => (company ? api(`/api/companies/${company.id}/profile`) : Promise.resolve(null)), [company?.id])
  const [editing, setEditing] = useState<number | null>(null)
  const [draft, setDraft] = useState({ field: '', value: '' })
  const [adding, setAdding] = useState(false)
  const [change, setChange] = useState('')
  if (!company) return <Empty title="Select or create a company first" />

  const save = async (id?: number) => {
    if (id) await api(`/api/companies/${company.id}/profile/facts/${id}`, { method: 'PUT', json: draft })
    else await api(`/api/companies/${company.id}/profile/facts`, { method: 'POST', json: draft })
    setEditing(null); setAdding(false); reload()
  }
  const del = async (id: number) => { await api(`/api/companies/${company.id}/profile/facts/${id}`, { method: 'DELETE' }); reload() }
  const rerun = async () => { const r = await api(`/api/companies/${company.id}/research`, { method: 'POST' }); track(r.job_id, 'Re-running company research') }
  const submitChange = async () => {
    const r = await api(`/api/companies/${company.id}/context`, { method: 'POST', json: { change } })
    track(r.job_id, 'Reassessing Signal Stack for new context')
    setChange('')
  }

  const facts: any[] = data?.facts ?? []
  const groups = facts.reduce((acc: Record<string, any[]>, f) => ((acc[f.field] ||= []).push(f), acc), {})
  const counts = { verified: facts.filter((f) => f.status === 'verified').length, assumption: facts.filter((f) => f.status === 'assumption').length, founder: facts.filter((f) => f.status === 'founder').length }

  return (
    <>
      <PageHeader title="Company Intelligence Profile" subtitle="Everything the system believes about the business, with where each belief came from. Edit anything."
        actions={<><Button variant="ghost" onClick={rerun}><RefreshCw className="h-4 w-4" />Re-run research</Button><Button onClick={() => { setAdding(true); setDraft({ field: 'other', value: '' }) }}><Plus className="h-4 w-4" />Add fact</Button></>} />
      <ErrorNote msg={error} />
      <div className="mb-6 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Card title="Summary">
          <p className="text-sm leading-relaxed text-ink">{data?.company.summary || 'Research has not finished yet.'}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">{(data?.company.keywords ?? []).map((k: string) => <Badge key={k} tone="violet">{k}</Badge>)}</div>
        </Card>
        <Card title="Evidence status">
          {(['verified', 'founder', 'assumption'] as const).map((s) => (
            <div key={s} className="mb-2 flex items-center gap-3">
              <Badge tone={STATUS_TONE[s]}>{s}</Badge><span className="flex-1 text-xs text-muted">{STATUS_HELP[s]}</span><span className="font-semibold tabular-nums">{counts[s]}</span>
            </div>
          ))}
        </Card>
      </div>

      {adding && (
        <Card className="mb-4" title="New fact">
          <div className="grid gap-2 sm:grid-cols-[200px_1fr_auto]">
            <Input value={draft.field} onChange={(e) => setDraft({ ...draft, field: e.target.value })} placeholder="field" />
            <Input value={draft.value} onChange={(e) => setDraft({ ...draft, value: e.target.value })} placeholder="value" />
            <div className="flex gap-2"><Button onClick={() => save()}>Save</Button><Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button></div>
          </div>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {Object.entries(groups).map(([field, list]) => (
          <Card key={field} title={field.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())}>
            <ul className="space-y-3">
              {(list as any[]).map((f) => (
                <li key={f.id} className="group">
                  {editing === f.id ? (
                    <div className="space-y-2">
                      <Textarea rows={3} value={draft.value} onChange={(e) => setDraft({ ...draft, value: e.target.value })} />
                      <div className="flex gap-2"><Button size="sm" onClick={() => save(f.id)}><Check className="h-3.5 w-3.5" />Save</Button><Button size="sm" variant="ghost" onClick={() => setEditing(null)}><X className="h-3.5 w-3.5" /></Button></div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-2">
                      <Badge tone={STATUS_TONE[f.status]} className="mt-0.5">{f.status}</Badge>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-ink">{f.value}</p>
                        {f.status === 'verified' && f.source_url && (
                          <p className="mt-1 text-xs text-muted">“{f.evidence.slice(0, 160)}” <a href={f.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-brand-500"><ExternalLink className="h-3 w-3" />source</a></p>
                        )}
                        {f.status !== 'verified' && f.evidence && <p className="mt-1 text-xs text-muted">{f.evidence.slice(0, 180)}</p>}
                      </div>
                      <div className="flex gap-1 opacity-0 transition group-hover:opacity-100">
                        <button className="text-muted hover:text-ink" onClick={() => { setEditing(f.id); setDraft({ field: f.field, value: f.value }) }}><Pencil className="h-3.5 w-3.5" /></button>
                        <button className="text-muted hover:text-rose-500" onClick={() => del(f.id)}><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title="Change business context" subtitle="E.g. a new product line, a new market or a pivot. The system re-scores every source, flags those no longer useful and proposes new ones.">
          <Textarea rows={4} value={change} onChange={(e) => setChange(e.target.value)} placeholder="We are launching a student-loan and accommodation marketplace for Indian students going to Germany and Ireland…" />
          <Button className="mt-3" disabled={!change.trim()} onClick={submitChange}>Reassess Signal Stack</Button>
        </Card>
        <Card title="Context change history">
          {(data?.context_changes ?? []).length ? (
            <ul className="space-y-4">
              {data.context_changes.map((c: any) => (
                <li key={c.id} className="rounded-xl border border-line p-3 text-sm">
                  <p className="text-xs text-muted">{fmtTime(c.created_at)}</p>
                  <p className="mt-1 font-medium">“{c.change_text}”</p>
                  <p className="mt-2 text-muted">{c.result.summary}</p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <div><p className="text-xs font-semibold text-rose-500">No longer useful ({c.result.no_longer_useful?.length ?? 0})</p>
                      {(c.result.no_longer_useful ?? []).map((s: any) => <p key={s.id} className="text-xs text-muted">• {s.name}: {s.why}</p>)}</div>
                    <div><p className="text-xs font-semibold text-emerald-600">New sources proposed ({c.result.new_sources?.length ?? 0})</p>
                      {(c.result.new_sources ?? []).map((s: any) => <p key={s.id} className="text-xs text-muted">• {s.name}</p>)}</div>
                  </div>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-muted">No context changes yet.</p>}
        </Card>
      </div>
    </>
  )
}
