import { Link, useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, Binoculars, Copy, Download, ExternalLink, Lightbulb, Mail, Play, Target } from 'lucide-react'
import { api, apiUrl } from '../api'
import { Badge, Button, CAT_COLORS, Card, Empty, ErrorNote, PageHeader, Select, cx, fmtDate, fmtTime, typeTone, useApp, useLoad, verTone } from '../ui'

const SECTIONS: [string, string][] = [['customers', 'Customer Signals'], ['competitors', 'Competitor Intelligence'], ['market', 'Market Intelligence'], ['internal', 'Internal Business Intelligence']]
const prioTone = (p: string) => (p === 'high' ? 'red' : p === 'medium' ? 'amber' : 'gray')

function Refs({ refs }: { refs?: number[] }) {
  return refs?.length ? <span className="ml-1 whitespace-nowrap">{refs.map((r) => <a key={r} href={`#ref-${r}`} className="ml-0.5 text-[11px] font-semibold text-brand-500">[{r}]</a>)}</span> : null
}

export default function BriefPage() {
  const { company, track } = useApp()
  const { briefId } = useParams()
  const nav = useNavigate()
  const list = useLoad(() => (company ? api<any[]>(`/api/companies/${company.id}/briefs`) : Promise.resolve([])), [company?.id])
  const id = briefId ?? list.data?.[0]?.id
  const brief = useLoad(() => (id ? api(`/api/briefs/${id}`) : Promise.resolve(null)), [id])
  if (!company) return <Empty title="Select or create a company first" />

  const run = async () => { const r = await api(`/api/companies/${company.id}/briefs/run`, { method: 'POST' }); track(r.job_id, 'Generating Monday Brief', () => list.reload()) }
  const setAction = async (aid: number, status: string) => { await api(`/api/actions/${aid}`, { method: 'PATCH', json: { status } }); brief.reload() }
  const b = brief.data
  const c = b?.content

  return (
    <>
      <PageHeader title="Monday Morning Brief" subtitle="Decision-relevant intelligence for leadership: facts quoted from sources, analysis labelled as analysis."
        actions={<>
          {!!list.data?.length && <Select value={id ?? ''} onChange={(e) => nav(`/brief/${e.target.value}`)}>{list.data.map((x) => <option key={x.id} value={x.id}>Brief #{x.id} · {fmtDate(x.created_at)} · {x.trigger}</option>)}</Select>}
          <Button onClick={run}><Play className="h-4 w-4" />Generate now</Button>
        </>} />
      <ErrorNote msg={list.error || brief.error} />
      {!b && <Empty title="No brief yet" action={<Button onClick={run}>Generate the first brief</Button>}>The weekly job crawls approved sources, analyses new developments, ranks them and writes the brief.</Empty>}
      {b && c && (
        <div className="grid gap-6 xl:grid-cols-[1fr_300px]">
          <div className="space-y-5">
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-brand-500">Monday Morning Brief</p>
                  <h2 className="mt-1 text-2xl font-bold">{c.company}</h2>
                  <p className="mt-1 text-sm text-muted">{fmtDate(c.period_start)} → {fmtDate(c.period_end)} · generated {fmtTime(c.generated_at)} · {c.stats.signals} signals from {c.stats.sources_monitored} monitored sources</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <a href={apiUrl(`/api/briefs/${b.id}/export.md`)}><Button variant="ghost" size="sm"><Download className="h-3.5 w-3.5" />Markdown</Button></a>
                  <a href={apiUrl(`/api/briefs/${b.id}/export.html`)} target="_blank" rel="noreferrer"><Button variant="ghost" size="sm"><Mail className="h-3.5 w-3.5" />Email-ready HTML</Button></a>
                  <Button variant="ghost" size="sm" onClick={() => navigator.clipboard?.writeText(b.markdown)}><Copy className="h-3.5 w-3.5" />Copy</Button>
                </div>
              </div>
              {c.limitations?.length > 0 && (
                <div className="mt-4 rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
                  <p className="mb-1 flex items-center gap-1 font-semibold"><AlertTriangle className="h-3.5 w-3.5" />Limitations, stated rather than filled</p>
                  {c.limitations.map((l: string, i: number) => <p key={i}>• {l}</p>)}
                </div>
              )}
            </Card>

            <Card title="1 · Executive Summary" subtitle="The most important developments leadership should know">
              {c.executive_summary.length ? (
                <ol className="space-y-3">
                  {c.executive_summary.map((x: any, i: number) => (
                    <li key={i} className="flex gap-3">
                      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-500 text-xs font-bold text-white">{i + 1}</span>
                      <div><p className="font-semibold text-ink">{x.headline}<Refs refs={x.refs} /></p><p className="text-sm text-muted">{x.so_what}</p></div>
                    </li>
                  ))}
                </ol>
              ) : <p className="text-sm text-muted">No significant developments this period.</p>}
            </Card>

            {SECTIONS.map(([key, title], n) => (
              <Card key={key} title={<span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CAT_COLORS[key] }} />{n + 2} · {title}</span>}>
                {c[key].length ? (
                  <div className="space-y-3">
                    {c[key].map((s: any) => (
                      <div key={s.signal_id} className="rounded-xl border border-line p-4">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <a id={`sig-${s.ref}`} href={`#ref-${s.ref}`} className="text-xs font-bold text-brand-500">[{s.ref}]</a>
                          <p className="font-semibold text-ink">{s.title}</p>
                          <span className="ml-auto flex gap-1"><Badge tone={typeTone(s.type)}>{s.type}</Badge><Badge tone={verTone(s.verification)}>{s.verification}</Badge><Badge>impact {s.impact}/5</Badge><Badge>urgency {s.urgency}/5</Badge></span>
                        </div>
                        <p className="mt-2 text-sm"><span className="text-xs font-semibold uppercase text-muted">Evidence · </span>{s.what_happened}</p>
                        <p className="mt-1 text-sm"><span className="text-xs font-semibold uppercase text-brand-500">Why it matters · </span>{s.why_it_matters}</p>
                        {s.consider_doing && <p className="mt-1 text-sm"><span className="text-xs font-semibold uppercase text-muted">Implication · </span>{s.consider_doing}</p>}
                      </div>
                    ))}
                  </div>
                ) : <p className="text-sm italic text-muted">No meaningful {title.toLowerCase()} development was detected in this period.</p>}
              </Card>
            ))}

            <div className="grid gap-5 lg:grid-cols-2">
              <Card title={<span className="flex items-center gap-2"><Lightbulb className="h-4 w-4 text-emerald-500" />6 · Opportunities Identified</span>}>
                {c.opportunities.length ? c.opportunities.map((o: any, i: number) => (
                  <div key={i} className="mb-3 border-b border-line pb-3 last:mb-0 last:border-0 last:pb-0">
                    <p className="font-semibold text-ink">{o.title}<Refs refs={o.refs} /> <Badge tone={prioTone(o.priority)}>{o.priority}</Badge></p>
                    <p className="mt-1 text-xs text-muted"><b>Evidence:</b> {o.evidence}</p>
                    <p className="text-xs text-muted"><b>Impact:</b> {o.impact}</p>
                    <p className="text-xs text-ink"><b>Next step:</b> {o.next_step}</p>
                  </div>
                )) : <p className="text-sm italic text-muted">No evidence-backed opportunities this period.</p>}
              </Card>
              <Card title={<span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-rose-500" />7 · Risks & Threats</span>}>
                {c.risks.length ? c.risks.map((r: any, i: number) => (
                  <div key={i} className="mb-3 border-b border-line pb-3 last:mb-0 last:border-0 last:pb-0">
                    <p className="font-semibold text-ink">{r.title}<Refs refs={r.refs} /> <Badge tone={prioTone(r.urgency)}>{r.urgency} urgency</Badge></p>
                    <p className="mt-1 text-xs text-muted">{r.possible_impact}</p>
                  </div>
                )) : <p className="text-sm italic text-muted">No significant risks detected this period.</p>}
              </Card>
            </div>

            <Card title={<span className="flex items-center gap-2"><Target className="h-4 w-4 text-brand-500" />8 · Recommended Actions for This Week</span>} subtitle="Track progress here; status is saved">
              {b.actions.length ? (
                <ul className="space-y-2">
                  {b.actions.map((a: any) => (
                    <li key={a.id} className={cx('flex flex-wrap items-start gap-3 rounded-xl border border-line p-3', a.status === 'done' && 'opacity-60')}>
                      <Badge tone={prioTone(a.priority)}>{a.priority}</Badge>
                      <div className="min-w-0 flex-1">
                        <p className={cx('text-sm font-medium', a.status === 'done' && 'line-through')}>{a.action}</p>
                        <p className="text-xs text-muted">{a.reason} · <b>Owner:</b> {a.owner}</p>
                      </div>
                      <Select value={a.status} onChange={(e) => setAction(a.id, e.target.value)} className="py-1 text-xs">
                        <option value="open">Open</option><option value="in_progress">In progress</option><option value="done">Done</option><option value="dismissed">Dismissed</option>
                      </Select>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm italic text-muted">No actions recommended this period.</p>}
            </Card>

            <Card title={<span className="flex items-center gap-2"><Binoculars className="h-4 w-4 text-amber-500" />9 · What We Should Watch</span>}>
              {c.watch.length ? <ul className="space-y-2">{c.watch.map((w: any, i: number) => <li key={i} className="text-sm"><b>{w.item}</b><Refs refs={w.refs} /> <span className="text-muted">— {w.why}</span></li>)}</ul>
                : <p className="text-sm italic text-muted">Nothing flagged.</p>}
            </Card>

            <Card title="10 · Source Appendix" subtitle="Original source, link, publication date, discovery date, evidence snippet and verification" pad={false}>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-xs">
                  <thead><tr className="border-b border-line text-left text-muted"><th className="px-5 py-2.5">Ref</th><th className="px-2">Development / source</th><th className="px-2">Published</th><th className="px-2">Discovered</th><th className="px-2">Evidence snippet</th><th className="px-5">Verification</th></tr></thead>
                  <tbody>
                    {c.appendix.map((a: any) => (
                      <tr key={a.ref} id={`ref-${a.ref}`} className="border-b border-line align-top last:border-0 target:bg-brand-50 dark:target:bg-brand-500/10">
                        <td className="px-5 py-2.5 font-bold text-brand-500">[{a.ref}]</td>
                        <td className="max-w-[240px] px-2 py-2.5"><p className="font-medium text-ink">{a.title}</p>
                          {a.url.startsWith('http') ? <a href={a.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-500"><ExternalLink className="h-3 w-3" />{a.publisher || a.source}</a> : <span className="text-muted">{a.publisher} (internal)</span>}</td>
                        <td className="px-2 py-2.5 whitespace-nowrap">{a.published}</td>
                        <td className="px-2 py-2.5 whitespace-nowrap">{a.discovered}</td>
                        <td className="max-w-[300px] px-2 py-2.5 italic text-muted">“{a.snippet}”</td>
                        <td className="px-5 py-2.5"><Badge tone={verTone(a.verification)}>{a.verification}</Badge><p className="mt-1 text-muted">reliability {a.source_reliability} · evidence {a.evidence_strength}{!a.full_text_accessed && ' · snippet only'}</p></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!c.appendix.length && <p className="p-5 text-sm text-muted">No sources cited.</p>}
              </div>
            </Card>
          </div>

          <div className="space-y-4">
            <Card title="This brief">
              <div className="space-y-2 text-sm">
                {SECTIONS.map(([k, t]) => <div key={k} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CAT_COLORS[k] }} /><span className="text-muted">{t.split(' ')[0]}</span><span className="ml-auto font-semibold">{c.stats[k]}</span></div>)}
                <div className="flex items-center gap-2 border-t border-line pt-2"><span className="text-muted">Actions done</span><span className="ml-auto font-semibold">{b.actions.filter((a: any) => a.status === 'done').length}/{b.actions.length}</span></div>
              </div>
            </Card>
            <Card title="Brief history">
              <ul className="space-y-1.5">
                {(list.data ?? []).map((x) => (
                  <li key={x.id}><Link to={`/brief/${x.id}`} className={cx('flex items-center justify-between rounded-lg px-2.5 py-2 text-sm', x.id === b.id ? 'bg-brand-50 font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300' : 'hover:bg-card2')}>
                    <span>#{x.id} · {fmtDate(x.created_at)}</span><span className="text-xs text-muted">{x.stats?.signals ?? 0} sig · {x.trigger}</span></Link></li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </>
  )
}
