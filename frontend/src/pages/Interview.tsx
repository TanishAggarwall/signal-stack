import { useEffect, useRef, useState } from 'react'
import { Bot, Check, CornerDownRight, EyeOff, Loader2, Pencil, Send, Sparkles } from 'lucide-react'
import { api } from '../api'
import { Badge, Button, Card, Empty, ErrorNote, PageHeader, Textarea, cx, useApp, useLoad } from '../ui'

export default function Interview() {
  const { company, reloadCompanies } = useApp()
  const { data, error, setData } = useLoad(() => (company ? api(`/api/companies/${company.id}/interview`) : Promise.resolve(null)), [company?.id])
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [editId, setEditId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [data?.turns?.length])
  if (!company) return <Empty title="Select or create a company first" />

  const run = async (fn: () => Promise<any>) => {
    setBusy(true); setErr('')
    try { setData(await fn()) } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const start = () => run(() => api(`/api/companies/${company.id}/interview/next`, { method: 'POST' }))
  const send = (skip = false) => run(async () => {
    const r = await api(`/api/companies/${company.id}/interview/${data.pending.id}/answer`, { method: 'POST', json: { answer, skip } })
    setAnswer('')
    reloadCompanies()
    return r
  })
  const saveEdit = (id: number, skip = false) => run(async () => {
    const r = await api(`/api/companies/${company.id}/interview/${id}`, { method: 'PUT', json: { answer: editText, skip } })
    setEditId(null)
    return r
  })

  const turns: any[] = data?.turns ?? []
  const pct = data ? Math.round((data.core_done / data.core_total) * 100) : 0

  return (
    <>
      <PageHeader title="AI Founder Interview" subtitle="Ten questions written for this company from its research profile and your earlier answers. One at a time, with follow-ups. Skip anything confidential." />
      <ErrorNote msg={error || err} />
      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <Card pad={false}>
          <div className="max-h-[62vh] min-h-[360px] space-y-5 overflow-y-auto p-5">
            {!turns.length && (
              <Empty title="Ready when you are" action={<Button onClick={start} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}Start interview</Button>}>
                The first question is generated from what we learned about {company.name}.
              </Empty>
            )}
            {turns.map((t) => (
              <div key={t.id} className={cx('space-y-2', t.is_followup && 'pl-8')}>
                <div className="flex gap-3">
                  <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-500 text-white">{t.is_followup ? <CornerDownRight className="h-4 w-4" /> : <Bot className="h-4 w-4" />}</div>
                  <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-card2 px-4 py-3">
                    <div className="mb-1 flex flex-wrap items-center gap-1.5">
                      <Badge tone="violet">{t.is_followup ? 'Follow-up' : `Question ${turns.filter((x) => !x.is_followup && x.seq <= t.seq).length}`}</Badge>
                      <Badge>{t.topic.replace(/_/g, ' ')}</Badge>
                    </div>
                    <p className="text-sm text-ink">{t.question}</p>
                    {t.rationale && <p className="mt-1.5 text-xs text-muted">Why we ask: {t.rationale}</p>}
                  </div>
                </div>
                {(t.answer !== null || t.skipped) && (
                  editId === t.id ? (
                    <div className="ml-auto max-w-[85%] space-y-2">
                      <Textarea rows={3} value={editText} onChange={(e) => setEditText(e.target.value)} />
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>Cancel</Button>
                        <Button size="sm" variant="ghost" onClick={() => saveEdit(t.id, true)}>Mark confidential</Button>
                        <Button size="sm" onClick={() => saveEdit(t.id)} disabled={busy}><Check className="h-3.5 w-3.5" />Save</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="group flex justify-end gap-2">
                      <button onClick={() => { setEditId(t.id); setEditText(t.answer ?? '') }} className="self-center text-muted opacity-0 transition group-hover:opacity-100" title="Edit answer"><Pencil className="h-3.5 w-3.5" /></button>
                      <div className={cx('max-w-[85%] rounded-2xl rounded-tr-sm px-4 py-3 text-sm', t.skipped ? 'border border-dashed border-line text-muted' : 'bg-brand-500 text-white')}>
                        {t.skipped ? <span className="flex items-center gap-1.5"><EyeOff className="h-3.5 w-3.5" />Skipped (confidential)</span> : t.answer}
                      </div>
                    </div>
                  )
                )}
              </div>
            ))}
            {busy && turns.length > 0 && <p className="flex items-center gap-2 text-xs text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" />Updating profile and writing the next question…</p>}
            {data?.complete && <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">Interview complete. Your answers are in the Intelligence Profile. Next: build the Signal Stack.</div>}
            <div ref={bottom} />
          </div>
          {data?.pending && (
            <div className="border-t border-line p-4">
              <Textarea rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Type your answer…"
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && answer.trim()) send() }} />
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-xs text-muted">Ctrl + Enter to send</span>
                <div className="flex gap-2">
                  <Button variant="ghost" onClick={() => send(true)} disabled={busy}><EyeOff className="h-4 w-4" />Skip (confidential)</Button>
                  <Button onClick={() => send()} disabled={busy || !answer.trim()}><Send className="h-4 w-4" />Answer</Button>
                </div>
              </div>
            </div>
          )}
        </Card>
        <div className="space-y-4">
          <Card title="Progress">
            <p className="text-3xl font-bold tabular-nums">{data?.core_done ?? 0}<span className="text-base text-muted">/{data?.core_total ?? 10}</span></p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-card2"><div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} /></div>
            <p className="mt-2 text-xs text-muted">{turns.filter((t) => t.is_followup).length} follow-up(s) · {turns.filter((t) => t.skipped).length} skipped</p>
          </Card>
          <Card title="Topics covered">
            <ul className="space-y-1.5 text-sm">
              {['revenue_lines', 'best_customers', 'customer_problems', 'why_us', 'competitors', 'market_changes', 'material_risks', 'growth_priorities', 'internal_data', 'decisions'].map((k) => {
                const done = turns.some((t) => t.topic === k && !t.is_followup && (t.answer !== null || t.skipped))
                return <li key={k} className="flex items-center gap-2"><span className={cx('grid h-4 w-4 place-items-center rounded-full', done ? 'bg-brand-500 text-white' : 'bg-card2')}>{done && <Check className="h-3 w-3" />}</span><span className={done ? 'text-ink' : 'text-muted'}>{k.replace(/_/g, ' ')}</span></li>
              })}
            </ul>
          </Card>
        </div>
      </div>
    </>
  )
}
