import { useRef, useState } from 'react'
import { FileUp, Upload as UploadIcon } from 'lucide-react'
import { api, type Signal } from '../api'
import { Badge, Button, Card, Empty, ErrorNote, Input, PageHeader, fmtTime, useApp, useLoad } from '../ui'
import { SignalCard } from './Feed'

export default function Internal() {
  const { company, track } = useApp()
  const ups = useLoad(() => (company ? api<any[]>(`/api/companies/${company.id}/uploads`) : Promise.resolve([])), [company?.id])
  const sigs = useLoad(() => (company ? api<Signal[]>(`/api/companies/${company.id}/signals?category=internal&sort=score`) : Promise.resolve([])), [company?.id])
  const file = useRef<HTMLInputElement>(null)
  const [label, setLabel] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (!company) return <Empty title="Select or create a company first" />

  const upload = async () => {
    const f = file.current?.files?.[0]
    if (!f) return
    setBusy(true); setErr('')
    const fd = new FormData()
    fd.append('file', f)
    fd.append('label', label)
    try {
      const r = await api(`/api/companies/${company.id}/uploads`, { method: 'POST', body: fd })
      track(r.job_id, `Analysing ${f.name}`, () => { ups.reload(); sigs.reload() })
      ups.reload()
      if (file.current) file.current.value = ''
      setLabel('')
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Internal Intelligence" subtitle="CRM exports, sales-call or meeting transcripts, support conversations, internal reports, product feedback. Supported: CSV, Excel, PDF and text." />
      <ErrorNote msg={err || ups.error} />
      <div className="mb-6 grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card title="Upload a file" subtitle="Insights are extracted with a verbatim quote from the file; anything that can't be quoted is discarded.">
          <div className="space-y-3">
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-line p-6 text-center hover:border-brand-300">
              <FileUp className="h-7 w-7 text-brand-500" />
              <span className="text-sm text-muted">Choose CSV, XLSX, PDF, TXT or MD (max 15MB)</span>
              <input ref={file} type="file" accept=".csv,.xlsx,.xls,.pdf,.txt,.md" className="text-xs" />
            </label>
            <Input placeholder="Label, e.g. 'Q3 lost deals CRM export'" value={label} onChange={(e) => setLabel(e.target.value)} />
            <Button onClick={upload} disabled={busy}><UploadIcon className="h-4 w-4" />Upload & analyse</Button>
          </div>
        </Card>
        <Card title="Uploaded files">
          {(ups.data ?? []).length ? (
            <ul className="divide-y divide-line">
              {ups.data!.map((u) => (
                <li key={u.id} className="flex items-center gap-3 py-2.5 text-sm">
                  <Badge tone="blue">{u.kind}</Badge>
                  <div className="min-w-0 flex-1"><p className="truncate font-medium">{u.filename}</p><p className="text-xs text-muted">{u.label || 'No label'} · {fmtTime(u.created_at)} · {u.chars.toLocaleString()} chars</p></div>
                  <Badge tone={u.analyzed ? 'green' : 'amber'}>{u.analyzed ? `${u.insights} insights` : 'analysing'}</Badge>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-muted">No internal files yet. If none are provided, the brief says so rather than guessing.</p>}
        </Card>
      </div>
      <h2 className="mb-3 text-lg font-semibold">Internal signals</h2>
      <div className="space-y-3">
        {(sigs.data ?? []).map((s) => <SignalCard key={s.id} s={s} />)}
        {sigs.data && !sigs.data.length && <Empty title="No internal insights yet" />}
      </div>
    </>
  )
}
