import { useState } from 'react'
import { ChevronDown, ExternalLink, EyeOff, Quote } from 'lucide-react'
import { api, type Signal } from '../api'
import { Badge, CAT_COLORS, CAT_LABEL, Card, Empty, ErrorNote, Input, Meter, PageHeader, Select, fmtDate, host, typeTone, useApp, useLoad, verTone } from '../ui'

export function SignalCard({ s, onDismiss }: { s: Signal; onDismiss?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <Card pad={false}>
      <div className="flex gap-4 p-5">
        <div className="flex flex-col items-center">
          <div className="grid h-12 w-12 place-items-center rounded-xl text-base font-bold text-white" style={{ background: CAT_COLORS[s.category] }}>{Math.round(s.score)}</div>
          <span className="mt-1 text-[10px] text-muted">score</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone="violet">{CAT_LABEL[s.category]}</Badge>
            <Badge tone={typeTone(s.signal_type)}>{s.signal_type}</Badge>
            <Badge tone={verTone(s.verification)}>{s.verification}</Badge>
            {s.competitor_name && <Badge tone="red">{s.competitor_name}</Badge>}
            {s.business_area && <Badge>{s.business_area}</Badge>}
            <span className="ml-auto text-xs text-muted">{fmtDate(s.event_date || s.published_at || s.created_at)}</span>
          </div>
          <h3 className="mt-2 font-semibold text-ink">{s.title}</h3>
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl bg-card2 p-3">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">What happened · evidence</p>
              <p className="text-sm text-ink">{s.what_happened}</p>
              <p className="mt-2 flex gap-1.5 text-xs italic text-muted"><Quote className="h-3.5 w-3.5 shrink-0" />{s.evidence_quote}</p>
              {s.source_url && (s.source_url.startsWith('http') ?
                <a href={s.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-brand-500"><ExternalLink className="h-3 w-3" />{s.publisher || host(s.source_url)}{!s.full_text && ' (headline/snippet only)'}</a>
                : <p className="mt-2 text-xs text-muted">{s.publisher} (internal file)</p>)}
            </div>
            <div className="rounded-xl border border-brand-100 p-3 dark:border-brand-500/20">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-brand-500">Why it matters · AI analysis</p>
              <p className="text-sm text-ink">{s.why_it_matters}</p>
              {s.consider_doing && <p className="mt-2 text-sm"><span className="font-semibold">Consider: </span>{s.consider_doing}</p>}
            </div>
          </div>
          <button onClick={() => setOpen(!open)} className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-ink">
            <ChevronDown className={`h-3.5 w-3.5 transition ${open ? 'rotate-180' : ''}`} />Why this rank
          </button>
          {open && (
            <div className="mt-2 grid gap-x-6 gap-y-1.5 rounded-xl bg-card2 p-3 md:grid-cols-2">
              <p className="text-xs text-ink md:col-span-2">{s.rank_explanation}</p>
              <Meter label="Relevance" value={s.relevance} />
              <Meter label="Impact" value={(s.impact - 1) / 4} />
              <Meter label="Urgency" value={(s.urgency - 1) / 4} />
              <Meter label="Source rel." value={s.source_reliability} color="#22b8a0" />
              <Meter label="Evidence" value={s.evidence_strength} color="#22b8a0" />
              <Meter label="Recency" value={s.recency} color="#f5a524" />
              <Meter label="Novelty" value={s.novelty} color="#f5a524" />
              <p className="text-[11px] text-muted md:col-span-2">Source reliability, evidence strength and strategic relevance are separate measures. AI judgement alone is never treated as proof.</p>
            </div>
          )}
        </div>
        {onDismiss && <button onClick={onDismiss} className="self-start text-muted hover:text-ink" title="Dismiss as noise"><EyeOff className="h-4 w-4" /></button>}
      </div>
    </Card>
  )
}

export default function Feed() {
  const { company } = useApp()
  const [f, setF] = useState({ category: '', competitor_id: '', signal_type: '', verification: '', min_relevance: '', min_impact: '', since: '', until: '', sort: 'date' })
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as any).toString()
  const { data, error, reload } = useLoad(() => (company ? api<Signal[]>(`/api/companies/${company.id}/signals?${qs}`) : Promise.resolve([])), [company?.id, qs])
  const comps = useLoad(() => (company ? api<any[]>(`/api/companies/${company.id}/competitors`) : Promise.resolve([])), [company?.id])
  if (!company) return <Empty title="Select or create a company first" />
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value })
  const dismiss = async (id: number) => { await api(`/api/companies/${company.id}/signals/${id}/dismiss`, { method: 'POST' }); reload() }

  return (
    <>
      <PageHeader title="Intelligence Feed" subtitle="Developments in date order, each with its evidence, source link and verification status." />
      <ErrorNote msg={error} />
      <Card className="mb-5">
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <Select value={f.category} onChange={set('category')}><option value="">All categories</option>{Object.entries(CAT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
          <Select value={f.competitor_id} onChange={set('competitor_id')}><option value="">All competitors</option>{(comps.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
          <Select value={f.signal_type} onChange={set('signal_type')}><option value="">Opportunity, threat or neutral</option><option value="opportunity">Opportunities</option><option value="threat">Threats</option><option value="neutral">Neutral</option></Select>
          <Select value={f.verification} onChange={set('verification')}><option value="">Any verification</option><option value="corroborated">Corroborated</option><option value="single-source">Single source</option><option value="internal">Internal</option></Select>
          <Select value={f.sort} onChange={set('sort')}><option value="date">Newest first</option><option value="score">Highest score</option></Select>
          <Select value={f.min_relevance} onChange={set('min_relevance')}><option value="">Any relevance</option><option value="0.5">Relevance ≥ 0.5</option><option value="0.7">Relevance ≥ 0.7</option></Select>
          <Select value={f.min_impact} onChange={set('min_impact')}><option value="">Any impact</option><option value="3">Impact ≥ 3</option><option value="4">Impact ≥ 4</option></Select>
          <Input type="date" value={f.since} onChange={set('since')} title="From" />
          <Input type="date" value={f.until} onChange={set('until')} title="To" />
        </div>
      </Card>
      <p className="mb-3 text-sm text-muted">{data?.length ?? 0} signals</p>
      <div className="space-y-3">
        {(data ?? []).map((s) => <SignalCard key={s.id} s={s} onDismiss={() => dismiss(s.id)} />)}
        {data && !data.length && <Empty title="No signals match">Run monitoring from the Source Manager, or relax the filters.</Empty>}
      </div>
    </>
  )
}
