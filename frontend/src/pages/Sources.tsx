import { useState } from 'react'
import { Check, ExternalLink, History, Plus, RotateCw, Trash2, Undo2, X } from 'lucide-react'
import { api, type Source } from '../api'
import { Badge, Button, CAT_LABEL, Card, Empty, ErrorNote, Input, PageHeader, Select, Textarea, cx, fmtTime, healthTone, host, useApp, useLoad } from '../ui'

export default function Sources() {
  const { company, track } = useApp()
  const { data, error, reload } = useLoad(() => (company ? api<Source[]>(`/api/companies/${company.id}/sources`) : Promise.resolve([])), [company?.id])
  const [status, setStatus] = useState('approved')
  const [cat, setCat] = useState('')
  const [hist, setHist] = useState<any>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ category: 'market', name: '', url: '', query: '', reason: '' })
  const [err, setErr] = useState('')
  if (!company) return <Empty title="Select or create a company first" />

  const all = data ?? []
  const list = all.filter((s) => (!status || s.status === status) && (!cat || s.category === cat))
  const patch = async (s: Source, body: any) => { await api(`/api/companies/${company.id}/sources/${s.id}`, { method: 'PATCH', json: body }); reload() }
  const openHist = async (s: Source) => setHist(await api(`/api/companies/${company.id}/sources/${s.id}/history`))
  const add = async () => {
    setErr('')
    try { await api(`/api/companies/${company.id}/sources`, { method: 'POST', json: form }); setAdding(false); setForm({ ...form, name: '', url: '', query: '', reason: '' }); reload() }
    catch (e: any) { setErr(e.message) }
  }
  const crawl = async () => { const r = await api(`/api/companies/${company.id}/crawl`, { method: 'POST' }); track(r.job_id, 'Crawling approved sources') }
  const count = (st: string) => all.filter((s) => s.status === st).length
  const dups = all.filter((s) => s.duplicate_of)

  return (
    <>
      <PageHeader title="Source Manager" subtitle="Approve discovered sources, add or remove your own, and check each source's health and crawl history."
        actions={<><Button variant="ghost" onClick={crawl}><RotateCw className="h-4 w-4" />Crawl now</Button><Button onClick={() => setAdding(!adding)}><Plus className="h-4 w-4" />Add source</Button></>} />
      <ErrorNote msg={error || err} />

      {adding && (
        <Card className="mb-4" title="Add a source" subtitle="Give a URL (page or RSS feed) or a news-search query, and say why it should be monitored.">
          <div className="grid gap-3 md:grid-cols-2">
            <Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {['customers', 'competitors', 'market'].map((c) => <option key={c} value={c}>{CAT_LABEL[c]}</option>)}
            </Select>
            <Input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input placeholder="URL (page or feed)" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value, query: '' })} />
            <Input placeholder="…or news query, e.g. &quot;UK graduate route visa&quot;" value={form.query} onChange={(e) => setForm({ ...form, query: e.target.value, url: '' })} />
            <Textarea className="md:col-span-2" rows={2} placeholder="Reason for monitoring (required)" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          </div>
          <Button className="mt-3" disabled={!form.name || !form.reason || !(form.url || form.query)} onClick={add}>Add & approve</Button>
        </Card>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {[['approved', 'Approved'], ['proposed', 'Awaiting approval'], ['removed', 'Removed'], ['', 'All']].map(([v, l]) => (
          <button key={v} onClick={() => setStatus(v)} className={cx('rounded-full px-3 py-1.5 text-sm font-medium', status === v ? 'bg-brand-500 text-white' : 'bg-card text-muted border border-line')}>
            {l} {v && <span className="opacity-70">({count(v)})</span>}
          </button>
        ))}
        <Select className="ml-auto" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">All categories</option>
          {Object.entries(CAT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </div>
      {dups.length > 0 && <div className="mb-4 rounded-xl bg-amber-50 px-4 py-2.5 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">{dups.length} duplicate source(s) flagged by the last audit.</div>}

      <Card pad={false}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead><tr className="border-b border-line text-left text-xs text-muted">
              <th className="px-5 py-3 font-medium">Source</th><th className="px-3 py-3 font-medium">Category</th><th className="px-3 py-3 font-medium">Reason</th>
              <th className="px-3 py-3 font-medium">S / R / C</th><th className="px-3 py-3 font-medium">Health</th><th className="px-3 py-3 font-medium">Items · signals</th><th className="px-5 py-3 text-right font-medium">Actions</th>
            </tr></thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.id} className="border-b border-line align-top last:border-0">
                  <td className="max-w-[260px] px-5 py-3">
                    <p className="font-medium text-ink">{s.name}</p>
                    {s.kind === 'news_query' ? <p className="text-xs text-muted">news: {s.query}</p> : s.url.startsWith('http') ?
                      <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-brand-500"><ExternalLink className="h-3 w-3" />{host(s.url)} · {s.kind}</a> : <p className="text-xs text-muted">{s.kind}</p>}
                    <p className="text-[11px] text-muted">by {s.discovered_by}{s.duplicate_of ? ' · duplicate' : ''}</p>
                  </td>
                  <td className="px-3 py-3"><Badge>{CAT_LABEL[s.category]}</Badge></td>
                  <td className="max-w-[320px] px-3 py-3 text-xs text-ink">{s.reason}{s.removed_reason && <p className="mt-1 text-rose-500">{s.removed_reason}</p>}</td>
                  <td className="px-3 py-3 text-xs tabular-nums text-muted">{s.specific.toFixed(2)} / {s.recent.toFixed(2)} / {s.credible.toFixed(2)}</td>
                  <td className="px-3 py-3"><Badge tone={healthTone(s.health)}>{s.health}</Badge><p className="mt-1 text-[11px] text-muted">{fmtTime(s.last_checked)}</p>{s.last_error && <p className="max-w-[160px] truncate text-[11px] text-rose-500" title={s.last_error}>{s.last_error}</p>}</td>
                  <td className="px-3 py-3 text-xs tabular-nums">{s.total_items} · {s.total_signals}</td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => openHist(s)} title="History"><History className="h-3.5 w-3.5" /></Button>
                      {s.status !== 'approved' && <Button size="sm" variant="soft" onClick={() => patch(s, { status: 'approved' })}><Check className="h-3.5 w-3.5" />Approve</Button>}
                      {s.status === 'approved' && s.kind !== 'upload' && <Button size="sm" variant="danger" onClick={() => patch(s, { status: 'removed' })}><Trash2 className="h-3.5 w-3.5" /></Button>}
                      {s.status === 'removed' && <Button size="sm" variant="ghost" onClick={() => patch(s, { status: 'proposed' })}><Undo2 className="h-3.5 w-3.5" /></Button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!list.length && <div className="p-6"><Empty title="No sources here" /></div>}
        </div>
      </Card>

      {hist && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setHist(null)}>
          <div className="h-full w-full max-w-xl overflow-y-auto bg-card p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-start justify-between"><div><h2 className="text-lg font-bold">{hist.source.name}</h2><p className="text-xs text-muted">{hist.source.kind === 'news_query' ? hist.source.query : hist.source.url}</p></div><button onClick={() => setHist(null)}><X className="h-5 w-5" /></button></div>
            <h3 className="mb-2 text-sm font-semibold">Crawl history</h3>
            <ul className="mb-6 space-y-1.5 text-xs">
              {hist.checks.map((c: any) => (
                <li key={c.id} className="flex items-center gap-2 rounded-lg bg-card2 px-3 py-2">
                  <Badge tone={healthTone(c.status)}>{c.status}</Badge><span className="text-muted">{fmtTime(c.checked_at)}</span>
                  <span className="ml-auto">{c.items_seen} seen · <b>{c.new_items} new</b> · {c.duplicates} dup{c.changed ? ' · page changed' : ''}</span>
                </li>
              ))}
              {!hist.checks.length && <li className="text-muted">Not crawled yet.</li>}
            </ul>
            <h3 className="mb-2 text-sm font-semibold">Collected documents</h3>
            <ul className="space-y-2 text-xs">
              {hist.documents.map((d: any) => (
                <li key={d.id} className="rounded-lg border border-line p-2.5">
                  <a href={d.url} target="_blank" rel="noreferrer" className="font-medium text-ink hover:text-brand-500">{d.title || d.url}</a>
                  <p className="text-muted">{d.publisher} · published {d.published_at?.slice(0, 10) ?? 'unknown'} · found {d.fetched_at.slice(0, 10)}{d.duplicate_of ? ' · duplicate' : ''}{d.relevant === false ? ' · not relevant' : d.relevant ? ' · signal' : ''}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  )
}
