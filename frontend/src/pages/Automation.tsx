import { useEffect, useState } from 'react'
import { ClipboardCheck, Play, Save } from 'lucide-react'
import { api, type Job } from '../api'
import { Badge, Button, Card, Empty, ErrorNote, Input, PageHeader, Select, fmtTime, useApp, useLoad } from '../ui'

const statusTone = (s: string) => ({ success: 'green', failed: 'red', partial: 'amber', running: 'violet', queued: 'gray' } as any)[s]

export default function Automation() {
  const { company, track, reloadCompanies } = useApp()
  const detail = useLoad(() => (company ? api(`/api/companies/${company.id}`) : Promise.resolve(null)), [company?.id])
  const jobs = useLoad(() => (company ? api<Job[]>(`/api/jobs?company_id=${company.id}&limit=40`) : Promise.resolve([])), [company?.id])
  const audits = useLoad(() => (company ? api<any[]>(`/api/companies/${company.id}/audits`) : Promise.resolve([])), [company?.id])
  const [s, setS] = useState<Record<string, any>>({})
  const [saved, setSaved] = useState('')
  useEffect(() => { if (detail.data) setS(detail.data.settings) }, [detail.data])
  if (!company) return <Empty title="Select or create a company first" />

  const save = async () => {
    const r = await api(`/api/companies/${company.id}/settings`, { method: 'PUT', json: { ...s, monitoring_frequency_hours: Number(s.monitoring_frequency_hours), source_refresh_days: Number(s.source_refresh_days), audit_day_of_month: Number(s.audit_day_of_month), lookback_days: Number(s.lookback_days) } })
    setSaved(`Saved. Next brief: ${fmtTime(r.next_runs.weekly)}`)
    detail.reload(); reloadCompanies()
  }
  const runAudit = async () => { const r = await api(`/api/companies/${company.id}/audit/run`, { method: 'POST' }); track(r.job_id, 'Running Signal Stack audit', () => audits.reload()) }
  const runBrief = async () => { const r = await api(`/api/companies/${company.id}/briefs/run`, { method: 'POST' }); track(r.job_id, 'Generating Monday Brief') }
  const set = (k: string) => (e: any) => setS({ ...s, [k]: e.target.value })
  const failed = (jobs.data ?? []).filter((j) => j.status === 'failed')
  const audit = audits.data?.[0]?.report

  return (
    <>
      <PageHeader title="Settings & Automation" subtitle="Two independent automated processes: the weekly intelligence brief and the monthly Signal Stack audit. Every run is logged."
        actions={<><Button variant="ghost" onClick={runAudit}><ClipboardCheck className="h-4 w-4" />Run audit now</Button><Button onClick={runBrief}><Play className="h-4 w-4" />Run brief now</Button></>} />
      <ErrorNote msg={detail.error} />
      {failed.length > 0 && <div className="mb-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"><b>{failed.length} failed run(s).</b> Latest: {failed[0].job_type} at {fmtTime(failed[0].started_at)}: {failed[0].error.split('\n')[0]}</div>}
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card title="Schedule" subtitle={saved || 'Changes reschedule the jobs immediately'}>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">Briefing day<Select className="mt-1 w-full" value={s.briefing_day ?? 'mon'} onChange={set('briefing_day')}>{['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map((d) => <option key={d}>{d}</option>)}</Select></label>
            <label className="text-sm">Briefing time<Input className="mt-1" type="time" value={s.briefing_time ?? '07:00'} onChange={set('briefing_time')} /></label>
            <label className="text-sm">Time zone<Input className="mt-1" value={s.timezone ?? ''} onChange={set('timezone')} placeholder="Asia/Kolkata" /></label>
            <label className="text-sm">Monitoring frequency (hours)<Input className="mt-1" type="number" min={0} value={s.monitoring_frequency_hours ?? 24} onChange={set('monitoring_frequency_hours')} /></label>
            <label className="text-sm">Source refresh (days)<Input className="mt-1" type="number" min={1} value={s.source_refresh_days ?? 7} onChange={set('source_refresh_days')} /></label>
            <label className="text-sm">Monthly audit day<Input className="mt-1" type="number" min={1} max={28} value={s.audit_day_of_month ?? 1} onChange={set('audit_day_of_month')} /></label>
            <label className="text-sm">Lookback for first brief (days)<Input className="mt-1" type="number" min={3} max={90} value={s.lookback_days ?? 30} onChange={set('lookback_days')} /></label>
          </div>
          <Button className="mt-4" onClick={save}><Save className="h-4 w-4" />Save settings</Button>
        </Card>
        <Card title="Next scheduled runs">
          <div className="space-y-3 text-sm">
            {[['weekly', 'A · Weekly Intelligence Brief', 'Crawl approved sources → detect changes → analyse → rank → save brief'],
              ['audit', 'B · Monthly Signal Stack Audit', 'Dead URLs, duplicates, inactive or declining sources, new candidates, health report'],
              ['monitor', 'Monitoring crawl', 'Collect new items between briefs']].map(([k, t, d]) => (
              <div key={k} className="rounded-xl bg-card2 p-3"><div className="flex justify-between gap-2"><p className="font-semibold">{t}</p><p className="font-medium text-brand-500">{fmtTime(detail.data?.next_runs?.[k])}</p></div><p className="mt-0.5 text-xs text-muted">{d}</p></div>
            ))}
            <p className="text-xs text-muted">Free hosts may sleep. A GitHub Actions cron also calls the protected <code>/api/cron/weekly</code> endpoint. Missed runs are logged as failures below.</p>
          </div>
        </Card>
      </div>

      <Card className="mb-6" title="Latest source-health report" subtitle={audits.data?.[0] ? `Audit #${audits.data[0].id} · ${fmtTime(audits.data[0].created_at)}` : 'No audit yet'}>
        {audit ? (
          <div className="grid gap-4 md:grid-cols-3">
            {[['dead', 'Dead URLs', 'red'], ['blocked', 'Blocked (robots / access)', 'red'], ['duplicates', 'Duplicates', 'amber'], ['inactive', 'Inactive', 'amber'], ['declining_relevance', 'Declining relevance', 'amber'], ['new_candidates', 'New sources proposed', 'green']].map(([k, t, tone]) => (
              <div key={k} className="rounded-xl border border-line p-3">
                <div className="flex items-center justify-between"><p className="text-sm font-semibold">{t}</p><Badge tone={tone}>{audit[k]?.length ?? 0}</Badge></div>
                <ul className="mt-2 space-y-1 text-xs text-muted">{(audit[k] ?? []).slice(0, 5).map((x: any) => <li key={x.id} className="truncate">• {x.name}{x.detail ? ` — ${x.detail}` : ''}</li>)}</ul>
              </div>
            ))}
            <div className="rounded-xl bg-card2 p-3 text-sm md:col-span-3"><b>Recommendations:</b> remove {audit.recommend_remove?.length ?? 0} source(s) · review {audit.recommend_add?.length ?? 0} proposed addition(s) in the Source Manager.</div>
          </div>
        ) : <Empty title="No audit has run yet" action={<Button onClick={runAudit}>Run the first audit</Button>} />}
      </Card>

      <Card title="Run history" subtitle="Manual, scheduled and cron runs, including failures" pad={false}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-5 py-2.5">#</th><th>Job</th><th>Trigger</th><th>Status</th><th>Started</th><th>Finished</th><th className="px-5">Result</th></tr></thead>
            <tbody>
              {(jobs.data ?? []).map((j) => (
                <tr key={j.id} className="border-b border-line align-top last:border-0">
                  <td className="px-5 py-2.5 text-muted">{j.id}</td><td className="py-2.5 font-medium">{j.job_type.replace(/_/g, ' ')}</td><td><Badge>{j.trigger}</Badge></td>
                  <td><Badge tone={statusTone(j.status)}>{j.status}</Badge></td><td className="text-xs">{fmtTime(j.started_at)}</td><td className="text-xs">{fmtTime(j.finished_at)}</td>
                  <td className="max-w-[360px] px-5 py-2.5 text-xs text-muted">{j.status === 'failed' ? <span className="text-rose-500">{j.error.split('\n')[0]}</span> : summarize(j.stats) || j.progress}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

function summarize(s: Record<string, any>) {
  if (!s) return ''
  const parts: string[] = []
  if (s.crawl) parts.push(`${s.crawl.new_documents} new docs from ${s.crawl.sources} sources`)
  if (s.analysis) parts.push(`${s.analysis.signals} signals (${s.analysis.rejected_unverified_quote} rejected: quote not found)`)
  if (s.brief_id) parts.push(`brief #${s.brief_id}`)
  if (!parts.length) Object.entries(s).slice(0, 5).forEach(([k, v]) => typeof v !== 'object' && parts.push(`${k.replace(/_/g, ' ')}: ${v}`))
  return parts.join(' · ')
}
