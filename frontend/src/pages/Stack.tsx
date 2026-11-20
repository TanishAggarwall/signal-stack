import { ExternalLink, Layers, Swords, X } from 'lucide-react'
import { api, type Source } from '../api'
import { Badge, Button, CAT_COLORS, CAT_LABEL, Card, Empty, ErrorNote, Meter, PageHeader, healthTone, host, useApp, useLoad } from '../ui'

export default function Stack() {
  const { company, track } = useApp()
  const src = useLoad(() => (company ? api<Source[]>(`/api/companies/${company.id}/sources`) : Promise.resolve([])), [company?.id])
  const comps = useLoad(() => (company ? api<any[]>(`/api/companies/${company.id}/competitors`) : Promise.resolve([])), [company?.id])
  if (!company) return <Empty title="Select or create a company first" />

  const build = async () => {
    const r = await api(`/api/companies/${company.id}/stack/build`, { method: 'POST' })
    track(r.job_id, `Building Signal Stack for ${company.name}`)
  }
  const removeComp = async (id: number) => {
    await api(`/api/companies/${company.id}/competitors/${id}`, { method: 'PATCH', json: { status: 'removed' } })
    comps.reload(); src.reload()
  }
  const sources = (src.data ?? []).filter((s) => s.status === 'approved')
  const competitors = (comps.data ?? []).filter((c) => c.status !== 'removed')

  return (
    <>
      <PageHeader title="Signal Stack" subtitle="Four intelligence categories. Every source was found by search, checked against robots.txt and liveness, and has a stated reason for inclusion."
        actions={<Button onClick={build}><Layers className="h-4 w-4" />{sources.length ? 'Rebuild / discover more' : 'Build Signal Stack'}</Button>} />
      <ErrorNote msg={src.error || comps.error} />

      <Card className="mb-6" title={<span className="flex items-center gap-2"><Swords className="h-4 w-4 text-brand-500" />Competitors & substitutes ({competitors.length})</span>}
        subtitle="Discovered from web search and the founder interview, not hard-coded">
        {competitors.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {competitors.map((c) => (
              <div key={c.id} className="group rounded-xl border border-line p-4">
                <div className="flex items-start gap-2">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-rose-50 text-xs font-bold text-rose-500 dark:bg-rose-500/15">{c.name.slice(0, 2).toUpperCase()}</div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-ink">{c.name}</p>
                    {c.website && <a href={c.website} target="_blank" rel="noreferrer" className="text-xs text-brand-500">{host(c.website)}</a>}
                  </div>
                  <Badge tone={c.kind === 'direct' ? 'red' : 'amber'}>{c.kind}</Badge>
                  <button onClick={() => removeComp(c.id)} className="text-muted opacity-0 group-hover:opacity-100 hover:text-rose-500" title="Remove competitor"><X className="h-4 w-4" /></button>
                </div>
                <p className="mt-2 text-xs text-muted">{c.description}</p>
                <p className="mt-2 text-xs text-ink"><span className="font-semibold">Why it matters: </span>{c.why_relevant}</p>
                <div className="mt-3 flex gap-1.5"><Badge>{c.sources} sources</Badge><Badge tone="violet">{c.signals} signals</Badge>
                  {c.evidence_url?.startsWith('http') && <a href={c.evidence_url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted hover:text-brand-500"><ExternalLink className="h-3 w-3" />found via</a>}
                </div>
              </div>
            ))}
          </div>
        ) : <Empty title="No competitors yet">Build the Signal Stack to discover competitors and substitutes.</Empty>}
      </Card>

      <div className="grid gap-4 xl:grid-cols-4 md:grid-cols-2">
        {(['customers', 'competitors', 'market', 'internal'] as const).map((cat) => {
          const list = sources.filter((s) => s.category === cat)
          return (
            <Card key={cat} pad={false} title={<span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CAT_COLORS[cat] }} />{CAT_LABEL[cat]}</span>}
              subtitle={`${list.length} approved source${list.length === 1 ? '' : 's'}`}>
              <ul className="max-h-[640px] space-y-2 overflow-y-auto p-4">
                {list.map((s) => (
                  <li key={s.id} className="rounded-xl bg-card2 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-ink">{s.name}</p>
                      <Badge tone={healthTone(s.health)}>{s.health}</Badge>
                    </div>
                    <p className="mt-0.5 truncate text-[11px] text-muted">{s.kind === 'news_query' ? `news search: ${s.query}` : s.kind === 'upload' ? 'file uploads' : `${s.kind} · ${host(s.url)}`}</p>
                    <p className="mt-2 text-xs text-ink">{s.reason}</p>
                    <div className="mt-2 space-y-1">
                      <Meter label="Specific" value={s.specific} color={CAT_COLORS[cat]} />
                      <Meter label="Recent" value={s.recent} color={CAT_COLORS[cat]} />
                      <Meter label="Credible" value={s.credible} color={CAT_COLORS[cat]} />
                    </div>
                  </li>
                ))}
                {!list.length && <p className="p-2 text-xs text-muted">No approved sources in this category yet.</p>}
              </ul>
            </Card>
          )
        })}
      </div>
    </>
  )
}
