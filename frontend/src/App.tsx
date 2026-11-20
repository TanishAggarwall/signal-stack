import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import {
  LayoutGrid, Building2, UserRound, MessagesSquare, Layers, Database, Rss, FileText, Upload, Settings2,
  Moon, Sun, Menu, X, ArrowUpRight, ShieldCheck,
} from 'lucide-react'
import { api } from './api'
import { cx, JobTray, Select, useApp } from './ui'
import Overview from './pages/Overview'
import Setup from './pages/Setup'
import Profile from './pages/Profile'
import Interview from './pages/Interview'
import Stack from './pages/Stack'
import Sources from './pages/Sources'
import Feed from './pages/Feed'
import BriefPage from './pages/Brief'
import Internal from './pages/Internal'
import Automation from './pages/Automation'

const NAV = [
  { group: 'Your company', items: [
    { to: '/', label: 'Overview', icon: LayoutGrid },
    { to: '/setup', label: 'Company setup', icon: Building2 },
    { to: '/profile', label: 'Intelligence profile', icon: UserRound },
    { to: '/interview', label: 'AI interview', icon: MessagesSquare },
  ] },
  { group: 'Intelligence', items: [
    { to: '/stack', label: 'Signal Stack', icon: Layers },
    { to: '/sources', label: 'Source manager', icon: Database },
    { to: '/feed', label: 'Intelligence feed', icon: Rss },
    { to: '/brief', label: 'Monday brief', icon: FileText },
    { to: '/internal', label: 'Internal data', icon: Upload },
  ] },
  { group: 'System', items: [{ to: '/automation', label: 'Settings & automation', icon: Settings2 }] },
]
const LABELS = Object.fromEntries(NAV.flatMap((g) => g.items.map((i) => [i.to, i.label])))

function useTheme() {
  const [dark, setDark] = useState(() => {
    try { const s = localStorage.getItem('ss.theme'); if (s) return s === 'dark' } catch { /* ignore */ }
    return false
  })
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try { localStorage.setItem('ss.theme', dark ? 'dark' : 'light') } catch { /* ignore */ }
  }, [dark])
  return [dark, setDark] as const
}

export default function App() {
  const { companies, company, setCompanyId, track } = useApp()
  const [dark, setDark] = useTheme()
  const [open, setOpen] = useState(false)
  const [providers, setProviders] = useState<string[] | null>(null)
  const loc = useLocation()
  useEffect(() => setOpen(false), [loc.pathname])
  useEffect(() => { api('/api/health').then((h) => setProviders(h.llm_providers)).catch(() => setProviders([])) }, [])
  const page = LABELS['/' + loc.pathname.split('/')[1]] ?? 'Overview'

  const runBrief = async () => {
    if (!company) return
    const r = await api(`/api/companies/${company.id}/briefs/run`, { method: 'POST' })
    track(r.job_id, `Generating Monday Brief for ${company.name}`)
  }

  const sidebar = (
    <aside className="flex h-full w-[264px] flex-col border-r border-line bg-card px-4 py-6">
      <div className="mb-8 flex items-center gap-3 px-2">
        <img src="/logo.svg" className="h-10 w-10" alt="" />
        <div>
          <p className="font-display text-[19px] font-extrabold leading-none tracking-tight text-ink">Signal Stack</p>
          <p className="mt-1 text-[9px] font-bold uppercase tracking-[.16em] text-muted">Monday-morning intelligence</p>
        </div>
      </div>
      <div className="mb-6 px-1">
        <p className="eyebrow mb-2 px-2">Monitoring</p>
        <Select className="w-full" value={company?.id ?? ''} onChange={(e) => setCompanyId(Number(e.target.value))}>
          {!companies.length && <option value="">No company yet</option>}
          {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </div>
      <nav className="flex flex-1 flex-col gap-5 overflow-y-auto">
        {NAV.map((g) => (
          <div key={g.group}>
            <p className="eyebrow mb-2 px-3">{g.group}</p>
            <div className="flex flex-col gap-1">
              {g.items.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} end={to === '/'}
                  className={({ isActive }) => cx('flex items-center gap-3 rounded-2xl px-3.5 py-2.5 text-[14px] font-medium transition',
                    isActive ? 'bg-brand-50 font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300' : 'text-muted hover:bg-card2 hover:text-ink')}>
                  <Icon className="h-[18px] w-[18px]" strokeWidth={1.8} />{label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="mt-4 rounded-[20px] bg-card2 p-4">
        <ShieldCheck className="h-5 w-5 text-brand-500" />
        <p className="mt-2 text-sm font-bold text-ink">Evidence first.</p>
        <p className="mt-1 text-xs leading-relaxed text-muted">Every development links to its source. If nothing happened, the brief says so.</p>
        <button onClick={() => setDark(!dark)} className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-brand-500">
          {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}{dark ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  )

  return (
    <div className="flex h-full">
      <div className="hidden lg:block">{sidebar}</div>
      {open && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          {sidebar}
          <button className="flex-1 bg-black/40" onClick={() => setOpen(false)} aria-label="Close menu" />
        </div>
      )}
      <main className="min-w-0 flex-1 overflow-y-auto">
        <header className="sticky top-0 z-30 flex h-[68px] items-center gap-3 border-b border-line bg-card/90 px-4 backdrop-blur sm:px-8">
          <button onClick={() => setOpen(!open)} className="text-ink lg:hidden">{open ? <X /> : <Menu />}</button>
          <p className="truncate text-sm text-muted"><span className="hidden sm:inline">{company?.name ?? 'Signal Stack'}</span><span className="mx-3 hidden text-line sm:inline">/</span><span className="font-medium text-ink">{page}</span></p>
          <div className="ml-auto flex items-center gap-2">
            {providers && (
              <span className={cx('hidden items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium sm:inline-flex', providers.length ? 'bg-lime-soft text-lime-ink dark:bg-lime-500/15 dark:text-lime-300' : 'bg-card2 text-muted')}>
                <span className={cx('h-1.5 w-1.5 rounded-full', providers.length ? 'bg-lime-ink' : 'bg-muted')} />
                {providers.length ? `AI connected · ${providers.join(' + ')}` : 'AI not connected'}
              </span>
            )}
            <button onClick={() => setDark(!dark)} className="grid h-9 w-9 place-items-center rounded-full border border-line text-muted hover:text-ink" aria-label="Toggle theme">
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            {company && (
              <button onClick={runBrief} className="inline-flex items-center gap-1.5 rounded-full bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_20px_-8px_rgba(123,63,242,.7)] hover:bg-brand-600">
                Run brief <ArrowUpRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </header>
        <div className="mx-auto max-w-[1320px] px-4 py-8 sm:px-8">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/setup" element={<Setup />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/interview" element={<Interview />} />
            <Route path="/stack" element={<Stack />} />
            <Route path="/sources" element={<Sources />} />
            <Route path="/feed" element={<Feed />} />
            <Route path="/brief" element={<BriefPage />} />
            <Route path="/brief/:briefId" element={<BriefPage />} />
            <Route path="/internal" element={<Internal />} />
            <Route path="/automation" element={<Automation />} />
          </Routes>
        </div>
      </main>
      <JobTray />
    </div>
  )
}
