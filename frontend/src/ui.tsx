import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Loader2, CheckCircle2, XCircle, X } from 'lucide-react'
import { api, type Company, type Job } from './api'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

export function Card({ title, subtitle, action, children, className, pad = true }: {
  title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children?: ReactNode; className?: string; pad?: boolean
}) {
  return (
    <section className={cx('rounded-[22px] border border-line bg-card shadow-[0_1px_3px_rgba(21,19,29,.03)]', className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-6 pt-5">
          <div>
            {title && <h3 className="text-[16px] font-bold tracking-tight text-ink">{title}</h3>}
            {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={pad ? 'px-6 pb-6 pt-4' : ''}>{children}</div>
    </section>
  )
}

export function Button({ children, variant = 'primary', size = 'md', className, ...p }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'soft' | 'danger' | 'dark'; size?: 'sm' | 'md' }) {
  const v = {
    primary: 'bg-brand-500 text-white hover:bg-brand-600 shadow-[0_8px_20px_-8px_rgba(123,63,242,.7)]',
    dark: 'bg-night text-white hover:opacity-90 dark:bg-white dark:text-night',
    soft: 'bg-brand-50 text-brand-600 hover:bg-brand-100 dark:bg-brand-500/15 dark:text-brand-300',
    ghost: 'border border-line bg-card text-ink hover:bg-card2',
    danger: 'bg-rose-50 text-rose-600 hover:bg-rose-100 dark:bg-rose-500/15 dark:text-rose-300',
  }[variant]
  return (
    <button {...p} className={cx('inline-flex items-center justify-center gap-1.5 rounded-full font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed',
      size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-5 py-2.5 text-sm', v, className)}>{children}</button>
  )
}

const tones: Record<string, string> = {
  violet: 'bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300',
  green: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  red: 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300',
  amber: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  gray: 'bg-card2 text-muted',
  blue: 'bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
}
export function Badge({ children, tone = 'gray', className }: { children: ReactNode; tone?: keyof typeof tones | string; className?: string }) {
  return <span className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap', tones[tone] || tones.gray, className)}>{children}</span>
}

export const typeTone = (t: string) => (t === 'opportunity' ? 'green' : t === 'threat' ? 'red' : 'gray')
export const healthTone = (h: string) => ({ ok: 'green', stale: 'amber', dead: 'red', blocked: 'red', error: 'amber' } as any)[h] || 'gray'
export const verTone = (v: string) => (v === 'corroborated' ? 'green' : v === 'internal' ? 'blue' : 'amber')
export const CAT_COLORS: Record<string, string> = { customers: '#6d4aff', competitors: '#f2546b', market: '#22b8a0', internal: '#f5a524' }
export const CAT_LABEL: Record<string, string> = { customers: 'Customers', competitors: 'Competitors', market: 'Market', internal: 'Internal' }

export function Meter({ value, label, color = '#6d4aff' }: { value: number; label?: string; color?: string }) {
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted">
      {label && <span className="w-14 shrink-0">{label}</span>}
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-card2">
        <div className="h-full rounded-full" style={{ width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`, background: color }} />
      </div>
      <span className="w-7 text-right tabular-nums text-ink">{Math.round(value * 100)}</span>
    </div>
  )
}

const CHIP: Record<string, string> = {
  violet: 'bg-brand-50 text-brand-500 dark:bg-brand-500/15 dark:text-brand-300',
  peach: 'bg-orange-50 text-orange-500 dark:bg-orange-500/15 dark:text-orange-300',
  sky: 'bg-sky-50 text-sky-500 dark:bg-sky-500/15 dark:text-sky-300',
  lime: 'bg-lime-soft text-lime-ink dark:bg-lime-500/15 dark:text-lime-300',
  rose: 'bg-rose-50 text-rose-500 dark:bg-rose-500/15 dark:text-rose-300',
}
export function Chip({ children, tone = 'violet' }: { children: ReactNode; tone?: keyof typeof CHIP }) {
  return <div className={cx('grid h-10 w-10 shrink-0 place-items-center rounded-xl', CHIP[tone])}>{children}</div>
}

export function Stat({ label, value, hint, icon, tone = 'violet', foot }: {
  label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: keyof typeof CHIP; foot?: ReactNode
}) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-[15px] font-bold tracking-tight text-ink">{label}</h3>
        {icon && <Chip tone={tone}>{icon}</Chip>}
      </div>
      <p className="mt-4 font-display text-[34px] font-extrabold leading-none tracking-[-0.04em] text-ink tabular-nums">{value}</p>
      {hint && <p className="mt-2 text-xs text-muted">{hint}</p>}
      {foot && <div className="mt-4 flex items-center justify-between border-t border-line pt-3 text-xs">{foot}</div>}
    </Card>
  )
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[22px] border border-dashed border-line px-6 py-12 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {children && <p className="mt-1 max-w-md text-sm text-muted">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Input(p: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={cx('w-full rounded-2xl border border-line bg-card px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted focus:border-brand-400 focus:ring-2 focus:ring-brand-500/15', p.className)} />
}
export function Textarea(p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cx('w-full rounded-2xl border border-line bg-card px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted focus:border-brand-400 focus:ring-2 focus:ring-brand-500/15', p.className)} />
}
export function Select(p: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={cx('rounded-full border border-line bg-card px-3.5 py-2 text-sm text-ink outline-none focus:border-brand-400', p.className)} />
}

export const fmtDate = (s?: string | null) => (s ? new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
export const fmtTime = (s?: string | null) => (s ? new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z').toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—')
export const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, '') } catch { return u } }

/* ---------------- app state: selected company + background jobs ---------------- */

type Ctx = {
  companies: Company[]; company: Company | null; setCompanyId: (id: number) => void; reloadCompanies: () => Promise<void>
  track: (jobId: number, label: string, onDone?: (j: Job) => void) => void; jobs: TrackedJob[]; dismissJob: (id: number) => void
  version: number
}
type TrackedJob = { id: number; label: string; job?: Job }
const AppCtx = createContext<Ctx>(null as any)
export const useApp = () => useContext(AppCtx)

export function AppProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [companyId, setCompanyIdState] = useState<number | null>(() => {
    try { return Number(localStorage.getItem('ss.company')) || null } catch { return null }
  })
  const [jobs, setJobs] = useState<TrackedJob[]>([])
  const [version, setVersion] = useState(0)
  const callbacks = useRef<Record<number, (j: Job) => void>>({})

  const reloadCompanies = useCallback(async () => {
    const cs = await api<Company[]>('/api/companies')
    setCompanies(cs)
    setCompanyIdState((cur) => (cur && cs.some((c) => c.id === cur) ? cur : cs[0]?.id ?? null))
  }, [])
  useEffect(() => { reloadCompanies().catch(() => {}) }, [reloadCompanies])

  const setCompanyId = (id: number) => {
    setCompanyIdState(id)
    try { localStorage.setItem('ss.company', String(id)) } catch { /* storage unavailable */ }
  }

  const track = (id: number, label: string, onDone?: (j: Job) => void) => {
    if (onDone) callbacks.current[id] = onDone
    setJobs((js) => [...js.filter((j) => j.id !== id), { id, label }])
  }
  const dismissJob = (id: number) => setJobs((js) => js.filter((j) => j.id !== id))

  useEffect(() => {
    const active = jobs.filter((j) => !j.job || ['queued', 'running'].includes(j.job.status))
    if (!active.length) return
    const t = setInterval(async () => {
      for (const tj of active) {
        try {
          const j = await api<Job>(`/api/jobs/${tj.id}`)
          setJobs((js) => js.map((x) => (x.id === tj.id ? { ...x, job: j } : x)))
          if (!['queued', 'running'].includes(j.status)) {
            callbacks.current[tj.id]?.(j)
            delete callbacks.current[tj.id]
            setVersion((v) => v + 1)
            reloadCompanies().catch(() => {})
          }
        } catch { /* transient */ }
      }
    }, 2000)
    return () => clearInterval(t)
  }, [jobs, reloadCompanies])

  const company = companies.find((c) => c.id === companyId) ?? null
  return <AppCtx.Provider value={{ companies, company, setCompanyId, reloadCompanies, track, jobs, dismissJob, version }}>{children}</AppCtx.Provider>
}

export function JobTray() {
  const { jobs, dismissJob } = useApp()
  if (!jobs.length) return null
  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-[340px] max-w-[calc(100vw-2rem)] flex-col gap-2">
      {jobs.map(({ id, label, job }) => {
        const running = !job || ['queued', 'running'].includes(job.status)
        const failed = job?.status === 'failed'
        return (
          <div key={id} className="rounded-2xl border border-line bg-card p-3 shadow-lg shadow-black/5">
            <div className="flex items-start gap-2">
              {running ? <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-brand-500" /> : failed ? <XCircle className="mt-0.5 h-4 w-4 text-rose-500" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink">{label}</p>
                <p className="truncate text-xs text-muted">{failed ? job?.error.split('\n')[0] : job?.progress || 'Starting…'}</p>
              </div>
              {!running && <button onClick={() => dismissJob(id)} className="text-muted hover:text-ink"><X className="h-4 w-4" /></button>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const { version } = useApp()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const reload = useCallback(() => {
    setLoading(true)
    return fn().then((d) => { setData(d); setError('') }).catch((e) => setError(String(e.message || e))).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { reload() }, [reload, version])
  return { data, error, loading, reload, setData }
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: string }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="text-[30px] font-extrabold leading-tight tracking-[-0.04em] text-ink sm:text-[34px]">{title}</h1>
        {subtitle && <p className="mt-2 text-[15px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function ErrorNote({ msg }: { msg: string }) {
  return msg ? <div className="mb-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">{msg}</div> : null
}
