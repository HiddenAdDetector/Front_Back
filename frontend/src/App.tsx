import { FormEvent, useEffect, useMemo, useState } from 'react'

type Finding = { technique: string; evidence_text: string; url: string; location: string; extra_finding?: string }
type Report = { report_type: string; model_status: string; review_required: boolean; message: string; candidate_count: number; visited_pages: number; failed_pages: number; extracted_elements: number; stop_reason: string; technique_counts?: Record<string, number> }
type Progress = Record<string, unknown>
type Job = { status: string; url: string; progress?: Progress; logs?: string[]; findings?: Finding[]; result?: { findings: Finding[] }; report?: Report; error?: string }

const API = 'http://127.0.0.1:8080/api'

export default function App() {
  const [url, setUrl] = useState('https://example.com')
  const [jobId, setJobId] = useState<string>()
  const [job, setJob] = useState<Job>()
  const [error, setError] = useState('')
  const progress = job?.progress ?? {}
  const findings = job?.findings ?? job?.result?.findings ?? []
  const active = ['queued', 'running', 'stopping'].includes(job?.status ?? '')
  const statusText = useMemo(() => ({ queued: '대기 중', running: '탐색 중', completed: '탐색 완료', stopping: '중지 중', stopped: '중지됨', failed: '실패' }[job?.status ?? ''] ?? '대기 중'), [job?.status])

  useEffect(() => {
    if (!jobId || !active) return
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${API}/crawl/${jobId}`)
        if (response.ok) setJob(await response.json())
        else setError(`작업 상태 조회 실패 (${response.status})`)
      } catch { setError('Spring Boot 백엔드와 연결이 끊겼습니다.') }
    }, 700)
    return () => window.clearInterval(timer)
  }, [jobId, active])

  async function start(event: FormEvent) {
    event.preventDefault(); setError(''); setJob(undefined)
    try {
      const response = await fetch(`${API}/crawl`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) })
      if (!response.ok) throw new Error(await response.text())
      const data = await response.json(); setJobId(data.job_id); setJob({ status: 'queued', url })
    } catch (exception) { setError('Spring Boot 백엔드가 127.0.0.1:8080에서 실행 중인지 확인하세요. ' + (exception instanceof Error ? exception.message : '연결 실패')) }
  }

  async function stop() { if (jobId) await fetch(`${API}/crawl/${jobId}/stop`, { method: 'POST' }) }

  const screenshot = String(progress.screenshot_data_url ?? '')
  const currentUrl = String(progress.current_url ?? job?.url ?? '-')
  const phase = String(progress.phase ?? 'waiting')
  const report = job?.report

  return <div className="app-shell">
    <header className="topbar"><div><div className="brand">AdSentinel</div><div className="tagline">Live Web Exploration Monitor</div></div><div className={`status-pill ${active ? 'active' : ''}`}><span className="status-dot" />{statusText}</div></header>
    <main className="content">
      <section className="top-section"><div><div className="eyebrow">LIVE TEST SESSION</div><h1>Playwright Monitor</h1><p>{job?.url ?? '탐색 대상 URL을 입력하세요.'}</p></div><div className="engine-badge">{String(progress.engine ?? 'Playwright Java')} · {String(progress.browser_status ?? 'idle')}</div></section>
      <section className="control-card"><form onSubmit={start}><input value={url} onChange={event => setUrl(event.target.value)} placeholder="https://example.com"/><button type="submit" disabled={active}>탐색 시작</button><button type="button" className="stop" onClick={stop} disabled={!active}>탐색 중지</button></form>{error && <div className="error">{error}</div>}</section>
      <section className="progress-card"><div className="progress-heading"><div><b>탐색 진행 상태</b><span>{currentUrl}</span></div><strong>{statusText}</strong></div><div className="progress-track"><div className={active ? 'progress-fill running' : 'progress-fill'} style={{ width: active ? '68%' : job?.status === 'completed' ? '100%' : '4%' }} /></div></section>
      <section className="metrics">{[['visited_pages', '방문 페이지'], ['queued_pages', '대기 페이지'], ['extracted_elements', '추출 요소'], ['failed_pages', '실패 페이지']].map(([key, label]) => <div className="metric" key={key}><span>{label}</span><strong>{String(progress[key] ?? 0)}</strong></div>)}</section>
      <section className="monitor-grid"><div className="panel browser-panel"><div className="panel-head"><div><b>Browser Session</b><span className="live-label"><i className={active ? 'dot live' : 'dot'} />{active ? 'LIVE' : statusText.toUpperCase()}</span></div><span className="page-label">{currentUrl}</span></div><div className="browser-bar"><span className="browser-dots"><i /><i /><i /></span><span>{currentUrl}</span></div><div className="screen">{screenshot ? <img src={screenshot} alt="Playwright live page" /> : <div className="screen-empty"><div className={active ? 'spinner' : ''} /><b>{active ? 'Playwright가 실제 페이지를 탐색 중입니다.' : '탐색을 시작하면 브라우저 화면이 표시됩니다.'}</b><span>Java Playwright · DOM/CSS extraction</span></div>}</div><div className="phase-bar">현재 단계: <b>{phase}</b> · 수집 요소 {String(progress.extracted_elements ?? 0)}개</div></div><aside className="panel side-panel"><div className="panel-head"><b>실시간 로그</b><span>{findings.length} findings</span></div><div className="logs">{(job?.logs ?? []).slice(-12).map((log, index) => <div key={`${log}-${index}`}>{log}</div>)}{(job?.logs ?? []).length === 0 && <div><i className={active ? 'dot live' : 'dot'} />Playwright 대기 중</div>}</div><div className="issue-title">실시간 탐지 결과</div><div className="issue-list">{findings.length === 0 ? <div className="empty-small">아직 탐지 결과가 없습니다.</div> : findings.slice(-5).map((finding, index) => <div className="issue" key={`${finding.location}-${index}`}><b>{finding.technique}</b><span>{finding.evidence_text}</span><small>{finding.location}</small></div>)}</div></aside></section>
      <section className="panel results-panel"><div className="panel-head"><b>탐지 결과 전체</b><span>{findings.length}건</span></div>{findings.length === 0 ? <div className="empty">탐색 중인 페이지에서 결과가 발견되면 여기에 즉시 표시됩니다.</div> : <div className="table-wrap"><table><thead><tr><th>기법</th><th>원문</th><th>URL</th><th>선택자</th></tr></thead><tbody>{findings.map((finding, index) => <tr key={`${finding.location}-${index}`}><td><b>{finding.technique}</b></td><td>{finding.evidence_text}</td><td>{finding.url}</td><td>{finding.location}</td></tr>)}</tbody></table></div>}</section>
      {report && <section className="panel report-panel"><div className="panel-head"><b>탐지 리포트</b><span className="report-status">{report.model_status === 'not_connected' ? '후보 리포트 · 모델 미연결' : '확정 리포트'}</span></div><p className="report-message">{report.message}</p><div className="report-grid"><div><span>후보 건수</span><strong>{report.candidate_count}</strong></div><div><span>방문 페이지</span><strong>{report.visited_pages}</strong></div><div><span>추출 요소</span><strong>{report.extracted_elements}</strong></div><div><span>종료 사유</span><strong>{report.stop_reason}</strong></div></div><div className="report-techniques">{Object.entries(report.technique_counts ?? {}).map(([technique, count]) => <span key={technique}>{technique} <b>{count}</b></span>)}</div></section>}
    </main>
  </div>
}
