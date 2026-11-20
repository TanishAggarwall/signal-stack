import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Globe, Plus, Trash2 } from 'lucide-react'
import { api } from '../api'
import { Badge, Button, Card, ErrorNote, Input, PageHeader, fmtDate, useApp } from '../ui'

export default function Setup() {
  const { companies, setCompanyId, track, reloadCompanies, company } = useApp()
  const [name, setName] = useState('')
  const [website, setWebsite] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setErr('')
    try {
      const c = await api('/api/companies', { method: 'POST', json: { name, website } })
      await reloadCompanies()
      setCompanyId(c.id)
      track(c.job_id, `Researching ${c.name}`)
      setName(''); setWebsite('')
      nav('/profile')
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const remove = async (id: number, n: string) => {
    if (!confirm(`Delete ${n} and all its intelligence records? This cannot be undone.`)) return
    await api(`/api/companies/${id}`, { method: 'DELETE' })
    reloadCompanies()
  }

  return (
    <>
      <PageHeader title="Company Setup" subtitle="Start with just a name and website. Everything else is discovered: no competitors or sources are pre-configured." />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.3fr]">
        <Card title="Add a company" subtitle="We read the public website and public mentions, then build a profile marking verified facts vs assumptions.">
          <ErrorNote msg={err} />
          <form onSubmit={create} className="space-y-3">
            <label className="block text-sm font-medium">Company name<Input className="mt-1" required value={name} onChange={(e) => setName(e.target.value)} placeholder="MeetUniversity" /></label>
            <label className="block text-sm font-medium">Website<Input className="mt-1" required value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://www.meetuniversity.com" /></label>
            <Button disabled={busy} className="w-full"><Plus className="h-4 w-4" />Create and start research</Button>
          </form>
        </Card>
        <Card title="Configured companies" subtitle={`${companies.length} compan${companies.length === 1 ? 'y' : 'ies'}`}>
          <ul className="space-y-2">
            {companies.map((c) => (
              <li key={c.id} className={`flex items-center gap-3 rounded-xl border p-3 ${company?.id === c.id ? 'border-brand-300 bg-brand-50/50 dark:bg-brand-500/10' : 'border-line'}`}>
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500 text-sm font-bold text-white">{c.name.slice(0, 2).toUpperCase()}</div>
                <button className="min-w-0 flex-1 text-left" onClick={() => { setCompanyId(c.id); nav('/') }}>
                  <p className="font-semibold text-ink">{c.name}</p>
                  <p className="flex items-center gap-1 truncate text-xs text-muted"><Globe className="h-3 w-3" />{c.website} · added {fmtDate(c.created_at)}</p>
                </button>
                <div className="hidden gap-1 sm:flex">
                  <Badge tone="violet">{c.stage.replace('_', ' ')}</Badge>
                  <Badge>{c.counts?.sources ?? 0} sources</Badge>
                  <Badge>{c.counts?.signals ?? 0} signals</Badge>
                </div>
                <button className="text-muted hover:text-rose-500" onClick={() => remove(c.id, c.name)} title="Delete"><Trash2 className="h-4 w-4" /></button>
              </li>
            ))}
            {!companies.length && <p className="text-sm text-muted">No companies yet.</p>}
          </ul>
        </Card>
      </div>
    </>
  )
}
