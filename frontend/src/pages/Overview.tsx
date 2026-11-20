import { Link, useNavigate } from 'react-router-dom'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, ArrowUpRight, CalendarClock, Database, Lightbulb, Radar, Sparkles, Swords } from 'lucide-react'
import { api } from '../api'
import { Badge, Button, CAT_COLORS, CAT_LABEL, Card, Chip, Empty, ErrorNote, Stat, cx, fmtDate, fmtTime, typeTone, useApp, useLoad } from '../ui'

const ORDER = ['created', 'researched', 'interviewed', 'stack_ready', 'monitoring']
const STEPS = [
  { key: 'researched', label: 'Research', to: '/profile' },
  { key: 'interviewed', label: 'Interview', to: '/interview' },
  { key: 'stack_ready', label: 'Signal Stack', to: '/stack' },
  { key: 'monitoring', label: 'Monitoring', to: '/sources' },
]
const HERO: Record<string, { title: string; text: string; cta: string; to: string }> = {
  created: { title: 'Getting to know the business.', text: 'We are reading the website and public mentions to build a first profile, separating verified facts from assumptions.', cta: 'View profile', to: '/profile' },
  researched: { title: "Let's hear it from the founder.", text: 'Ten questions written for this company. Your answers shape which competitors, customers and markets we watch.', cta: 'Start the interview', to: '/interview' },
  interviewed: { title: 'Time to build the Signal Stack.', text: 'We search for competitors and sources, check robots.txt and freshness, and justify every source we keep.', cta: 'Build Signal Stack', to: '/stack' },
  stack_ready: { title: 'Your sources are ready to watch.', text: 'Run the first crawl to collect evidence, analyse what changed and rank what matters.', cta: 'Open Source Manager', to: '/sources' },
  monitoring: { title: 'Your business, continuously in view.', text: 'Sources are monitored, developments are analysed and ranked, and a brief lands every Monday morning.', cta: 'Read the latest brief', to: '/brief' },
}
const tip = { contentStyle: { background: 'var(--card)', border: '1px solid var(--line)', borderRadius: 14, fontSize: 12, color: 'var(--ink)' } }

export default function Overview() {
  const { company, track } = useApp()
  const nav = useNavigate()
  const { data, error } = useLoad(() => (company ? api(`/api/companies/${company.id}/dashboard`) : Promise.resolve(null)), [company?.id])

  if (!company) {
    return (
      <section className="hero-grad relative overflow-hidden rounded-[28px] p-8 sm:p-12">
        <p className="eyebrow">Signal Stack</p>
        <h1 className="mt-3 max-w-xl text-[40px] font-extrabold leading-[1.05] tracking-[-0.045em]">Turn your company into a continuously monitored business.</h1>
        <p className="mt-4 max-w-lg text-muted">Enter a name and a website. We research it, interview the founder, build a justified Signal Stack and write your Monday Morning Brief.</p>
        <Button variant="dark" className="mt-8" onClick={() => nav('/setup')}>Set up a company <ArrowUpRight className="h-4 w-4" /></Button>
      </section>
    )
  }
  const k = data?.kpis
  const stageIdx = ORDER.indexOf(company.stage)
  const hero = HERO[company.stage] ?? HERO.created
  const donut = data ? Object.entries(data.by_category).map(([key, v]) => ({ name: CAT_LABEL[key], key, value: v as number })) : []
  const total = donut.reduce((a, b) => a + b.value, 0)
  const topSignal = data?.top_signals?.[0]
  const runCrawl = async () => { const r = await api(`/api/companies/${company.id}/crawl`, { method: 'POST' }); track(r.job_id, 'Crawling approved sources') }

  return (
    <>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-2">This week's intelligence</p>
          <h1 className="text-[32px] font-extrabold leading-tight tracking-[-0.045em] sm:text-[36px]">{company.name}, in view.</h1>
          <p className="mt-1.5 text-[15px] text-muted">{company.industry || 'Researching the business…'}</p>
          <p className="mt-3 flex items-center gap-2 text-xs text-muted"><span className="h-1.5 w-1.5 rounded-full bg-brand-500" />Facts are quoted from sources · analysis is labelled as analysis</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className="rounded-full border border-line bg-card px-4 py-2 text-sm text-muted">{new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
          <a href={company.website} target="_blank" rel="noreferrer" className="tag hover:text-brand-500">{company.website.replace(/^https?:\/\/(www\.)?/, '')}</a>
        </div>
      </div>
      <ErrorNote msg={error} />

      <div className="mb-5 grid gap-5 xl:grid-cols-3">
        <section className="hero-grad relative overflow-hidden rounded-[24px] p-7 xl:col-span-2 sm:p-8">
          <p className="eyebrow">Where you are</p>
          <h2 className="mt-3 max-w-md text-[30px] font-extrabold leading-[1.1] tracking-[-0.04em] text-ink">{hero.title}</h2>
          <p className="mt-3 max-w-sm text-[15px] leading-relaxed text-muted">{hero.text}</p>
          <div className="mt-6 flex flex-wrap gap-2">
            <Button variant="dark" onClick={() => nav(hero.to)}>{hero.cta} <ArrowUpRight className="h-4 w-4" /></Button>
            {stageIdx >= 3 && <Button variant="ghost" onClick={runCrawl}>Crawl now</Button>}
          </div>
          <div className="mt-8 flex flex-wrap gap-2">
            {STEPS.map((s, i) => {
              const done = stageIdx >= ORDER.indexOf(s.key)
              return (
                <Link key={s.key} to={s.to} className={cx('inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold',
                  done ? 'bg-white/80 text-brand-600 dark:bg-white/10 dark:text-brand-200' : 'border border-brand-200/60 text-muted dark:border-white/10')}>
                  <span className={cx('grid h-4 w-4 place-items-center rounded-full text-[9px]', done ? 'bg-brand-500 text-white' : 'bg-brand-100 text-brand-500 dark:bg-white/10')}>{i + 1}</span>{s.label}
                </Link>
              )
            })}
          </div>
          <div className="pointer-events-none absolute -right-6 top-1/2 hidden -translate-y-1/2 sm:block">
            <div className="relative h-64 w-64">
              <svg viewBox="0 0 260 260" className="absolute inset-0 h-full w-full text-brand-400/50">
                <ellipse cx="130" cy="130" rx="122" ry="60" fill="none" stroke="currentColor" strokeWidth="1.2" transform="rotate(-18 130 130)" />
                <ellipse cx="130" cy="130" rx="110" ry="48" fill="none" stroke="currentColor" strokeWidth="1" transform="rotate(24 130 130)" />
              </svg>
              <div className="orb absolute left-1/2 top-1/2 grid h-36 w-36 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full">
                <Radar className="h-14 w-14 text-white/90" strokeWidth={1.3} />
              </div>
            </div>
          </div>
          <p className="absolute bottom-5 right-7 hidden text-[10px] font-bold uppercase tracking-[.16em] text-muted sm:block">Signals, not noise.</p>
        </section>

        <Card>
          <div className="flex items-start justify-between">
            <Chip tone="lime"><CalendarClock className="h-5 w-5" /></Chip>
            <span className="tag">Automation</span>
          </div>
          <h3 className="mt-5 text-[20px] font-extrabold tracking-tight">Next Monday brief</h3>
          <p className="mt-1 text-sm text-muted">{fmtTime(data?.next_runs?.weekly)}</p>
          <div className="mt-4 space-y-2 text-sm">
            <Row dot="bg-brand-500" label="Monthly source audit" value={fmtDate(data?.next_runs?.audit)} />
            <Row dot="bg-lime-ink" label="Last brief" value={data?.last_brief ? fmtDate(data.last_brief.created_at) : 'none yet'} />
          </div>
          {data?.failed_jobs?.length ? (
            <p className="mt-4 flex items-start gap-1.5 rounded-2xl bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{data.failed_jobs.length} failed run(s). Latest: {data.failed_jobs[0].job_type.replace(/_/g, ' ')}
            </p>
          ) : null}
          <Link to="/automation" className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-brand-500">Schedule & run history <ArrowUpRight className="h-4 w-4" /></Link>
        </Card>
      </div>

      <div className="mb-5 grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Evidence-backed signals" value={k?.signals ?? '—'} hint="Each quoted from a stored source" icon={<Radar className="h-5 w-5" />}
          foot={<><span className="text-muted">{k?.documents ?? 0} documents</span><Link to="/feed" className="font-semibold text-brand-500">Explore ↗</Link></>} />
        <Stat label="Opportunities vs threats" tone="lime" value={<><span>{k?.opportunities ?? 0}</span><span className="text-muted"> / </span><span>{k?.threats ?? 0}</span></>} hint="AI classification of each signal" icon={<Lightbulb className="h-5 w-5" />}
          foot={<><span className="flex items-center gap-1.5 text-muted"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />opp. <span className="ml-2 h-1.5 w-1.5 rounded-full bg-rose-500" />threat</span><Link to="/feed" className="font-semibold text-brand-500">Explore ↗</Link></>} />
        <Stat label="Approved sources" tone="sky" value={k?.sources_approved ?? '—'} hint={`${k?.sources_proposed ?? 0} awaiting your approval`} icon={<Database className="h-5 w-5" />}
          foot={<><span className="text-muted">robots.txt respected</span><Link to="/sources" className="font-semibold text-brand-500">Manage ↗</Link></>} />
        <Stat label="Competitors tracked" tone="peach" value={k?.competitors ?? '—'} hint="Discovered, never hard-coded" icon={<Swords className="h-5 w-5" />}
          foot={<><span className="text-muted">{k?.briefs ?? 0} briefs so far</span><Link to="/stack" className="font-semibold text-brand-500">View ↗</Link></>} />
      </div>

      <div className="mb-5 grid gap-5 xl:grid-cols-3">
        <section className="rounded-[24px] bg-night p-7 text-white xl:col-span-2">
          <div className="flex items-start justify-between gap-3">
            <div><h3 className="text-[17px] font-bold">Signals over time</h3><p className="mt-1 text-xs text-white/55">Weekly developments by Signal Stack category</p></div>
            <span className="rounded-full border border-white/15 px-3 py-1 text-[10px] font-bold uppercase tracking-[.14em] text-white/60">By week</span>
          </div>
          {data?.weekly?.length ? (
            <ResponsiveContainer width="100%" height={240} className="mt-4">
              <BarChart data={data.weekly} barSize={26}>
                <CartesianGrid vertical={false} stroke="rgba(255,255,255,.08)" />
                <XAxis dataKey="week" tickFormatter={(w) => fmtDate(w).replace(/,? \d{4}/, '')} tick={{ fontSize: 11, fill: 'rgba(255,255,255,.5)' }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'rgba(255,255,255,.5)' }} axisLine={false} tickLine={false} width={26} />
                <Tooltip {...tip} cursor={{ fill: 'rgba(255,255,255,.05)' }} />
                {Object.keys(CAT_COLORS).map((c, i, arr) => <Bar key={c} dataKey={c} name={CAT_LABEL[c]} stackId="a" fill={CAT_COLORS[c]} radius={i === arr.length - 1 ? [6, 6, 0, 0] : 0} />)}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="mt-4 grid h-[240px] place-items-center border-y border-white/10 text-sm text-white/50">Your story starts with the first crawl.</div>
          )}
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-white/60">
            {Object.keys(CAT_COLORS).map((c) => <span key={c} className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: CAT_COLORS[c] }} />{CAT_LABEL[c]}</span>)}
          </div>
        </section>

        <section className="relative overflow-hidden rounded-[24px] bg-lime-soft p-7 dark:bg-lime-500/10">
          <p className="eyebrow !text-lime-ink">Top signal right now</p>
          {topSignal ? (
            <>
              <h3 className="mt-3 text-[22px] font-extrabold leading-tight tracking-[-0.03em] text-night dark:text-white">{topSignal.title}</h3>
              <p className="mt-2 line-clamp-3 text-sm text-night/60 dark:text-white/60">{topSignal.why_it_matters}</p>
              <div className="mt-3 flex gap-1.5"><Badge tone={typeTone(topSignal.signal_type)}>{topSignal.signal_type}</Badge><Badge>score {Math.round(topSignal.score)}</Badge></div>
              <Button variant="dark" className="mt-6" onClick={() => nav('/feed')}>See the evidence <ArrowUpRight className="h-4 w-4" /></Button>
            </>
          ) : (
            <>
              <h3 className="mt-3 text-[26px] font-extrabold leading-tight tracking-[-0.03em] text-night dark:text-white">Quiet for now.<br />Nothing invented.</h3>
              <p className="mt-2 text-sm text-night/60 dark:text-white/60">Signals appear here once sources are crawled and analysed.</p>
              <Button variant="dark" className="mt-6" onClick={() => nav('/stack')}>Open Signal Stack <ArrowUpRight className="h-4 w-4" /></Button>
            </>
          )}
          <Sparkles className="pointer-events-none absolute -bottom-6 -right-6 h-32 w-32 text-lime-ink/25" strokeWidth={1} />
        </section>
      </div>

      <div className="mb-5 grid gap-5 lg:grid-cols-3">
        <Card title="Signal mix" subtitle="Share by category">
          {total ? (
            <div className="relative">
              <ResponsiveContainer width="100%" height={190}>
                <PieChart>
                  <Pie data={donut} dataKey="value" innerRadius={60} outerRadius={84} paddingAngle={3} stroke="none" cornerRadius={6}>
                    {donut.map((d) => <Cell key={d.key} fill={CAT_COLORS[d.key]} />)}
                  </Pie>
                  <Tooltip {...tip} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-x-0 top-[72px] text-center"><p className="font-display text-2xl font-extrabold">{total}</p><p className="text-[11px] text-muted">signals</p></div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {donut.map((d) => <div key={d.key} className="flex items-center gap-2 text-xs"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CAT_COLORS[d.key] }} /><span className="text-muted">{d.name}</span><span className="ml-auto font-semibold tabular-nums">{d.value}</span></div>)}
              </div>
            </div>
          ) : <Empty title="Nothing to chart yet" />}
        </Card>
        <Card title="Impact × urgency" subtitle="Where the signals sit">
          <Heat cells={data?.heat ?? []} />
        </Card>
        <Card title="Collection activity" subtitle="New documents per day">
          {data?.collected_by_day?.length ? (
            <ResponsiveContainer width="100%" height={210}>
              <AreaChart data={data.collected_by_day}>
                <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7b3ff2" stopOpacity={0.3} /><stop offset="100%" stopColor="#7b3ff2" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid vertical={false} stroke="var(--line)" />
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} width={26} />
                <Tooltip {...tip} />
                <Area type="monotone" dataKey="documents" stroke="#7b3ff2" strokeWidth={2.5} fill="url(#g1)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : <Empty title="No crawls yet" />}
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="Top-ranked signals" subtitle="Relevance, impact, urgency, reliability, evidence, recency and novelty, combined" className="xl:col-span-2"
          action={<Link to="/feed" className="text-sm font-semibold text-brand-500">View all ↗</Link>}>
          {data?.top_signals?.length ? (
            <ul className="divide-y divide-line">
              {data.top_signals.map((s: any) => (
                <li key={s.id} className="flex items-center gap-4 py-3.5">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl font-display text-sm font-extrabold text-white" style={{ background: CAT_COLORS[s.category] }}>{Math.round(s.score)}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-ink">{s.title}</p>
                    <p className="mt-0.5 line-clamp-1 text-xs text-muted">{s.why_it_matters}</p>
                  </div>
                  <Badge tone={typeTone(s.signal_type)}>{s.signal_type}</Badge>
                </li>
              ))}
            </ul>
          ) : <Empty title="No ranked signals yet" />}
        </Card>
        <Card title="Source health" subtitle="Approved sources, last check">
          <div className="grid grid-cols-3 gap-2 text-center">
            {Object.entries(data?.source_health ?? {}).map(([h, n]) => (
              <div key={h} className="rounded-2xl bg-card2 px-2 py-3"><p className="font-display text-xl font-extrabold tabular-nums">{n as number}</p><p className="text-[11px] capitalize text-muted">{h}</p></div>
            ))}
          </div>
          <Link to="/sources" className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-brand-500">Open Source Manager <ArrowUpRight className="h-4 w-4" /></Link>
        </Card>
      </div>
    </>
  )
}

function Row({ label, value, dot }: { label: string; value: React.ReactNode; dot: string }) {
  return <div className="flex items-center gap-2"><span className={cx('h-1.5 w-1.5 rounded-full', dot)} /><span className="text-muted">{label}</span><span className="ml-auto font-semibold text-ink">{value}</span></div>
}

function Heat({ cells }: { cells: { impact: number; urgency: number }[] }) {
  const grid: number[][] = Array.from({ length: 5 }, () => Array(5).fill(0))
  cells.forEach((c) => { grid[5 - c.impact][c.urgency - 1]++ })
  const max = Math.max(1, ...grid.flat())
  return (
    <div>
      <div className="flex gap-2">
        <div className="flex flex-col justify-around text-[10px] text-muted">{[5, 4, 3, 2, 1].map((i) => <span key={i}>{i}</span>)}</div>
        <div className="grid flex-1 grid-cols-5 gap-1.5">
          {grid.flat().map((n, i) => (
            <div key={i} title={`${n} signal(s)`} className="grid aspect-square place-items-center rounded-lg text-[11px] font-semibold"
              style={{ background: n ? `rgba(123,63,242,${0.18 + 0.82 * (n / max)})` : 'var(--card2)', color: n / max > 0.5 ? '#fff' : 'var(--ink)' }}>{n || ''}</div>
          ))}
        </div>
      </div>
      <div className="mt-2 flex justify-between pl-4 text-[10px] text-muted"><span>urgency →</span><span>impact ↑</span></div>
    </div>
  )
}
