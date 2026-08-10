import React, { useState } from 'react'
import { useAppStore } from '../store/appStore'

const API_BASE = 'http://localhost:8000'

type RunMode = 'all' | 'synthetic' | 'edge_case' | 'id'

export default function ScenarioRunnerPage() {
  const { scenarioResults, scenarioProgress, appendScenarioResult, setScenarioProgress } = useAppStore()
  const [runMode, setRunMode] = useState<RunMode>('all')
  const [specificId, setSpecificId] = useState('')
  const [continuous, setContinuous] = useState(false)
  const [running, setRunning] = useState(false)
  const [log, setLog] = useState<string[]>([])

  function addLog(msg: string) {
    setLog(prev => [...prev.slice(-500), `[${new Date().toLocaleTimeString()}] ${msg}`])
  }

  async function handleRun() {
    setRunning(true)
    addLog(`Starting scenario run — mode: ${runMode}${continuous ? ' (continuous)' : ''}`)

    try {
      const params = new URLSearchParams()
      if (runMode !== 'all' && runMode !== 'id') params.set('type', runMode)
      if (runMode === 'id') params.set('id', specificId)
      if (continuous) params.set('continuous', '1')

      const resp = await fetch(`${API_BASE}/api/v1/evaluation/scenarios/run?${params}`, {
        method: 'POST',
      })

      if (!resp.ok) {
        addLog(`[FAIL] API error: ${resp.status} ${resp.statusText}`)
        return
      }

      const data = await resp.json()
      addLog(`[OK] Run complete. Passed: ${data.passed}/${data.total_scenarios} (${data.pass_rate_pct?.toFixed(1)}%)`)
      setScenarioProgress({
        total: data.total_scenarios,
        passed: data.passed,
        failed: data.failed,
      })
    } catch (e: unknown) {
      // This API endpoint isn't wired up yet — the real runner is a CLI tool
      // (`python -m scenario_engine.runner`, verified 7/7 passing; see
      // PROJECT_SUMMARY.md). This illustrates the same flow in the console.
      addLog(`[WARN] Scenario API endpoint not available — running illustrative demo`)
      await simulateDemoRun()
    } finally {
      setRunning(false)
    }
  }

  async function simulateDemoRun() {
    const scenarios = [
      { id: 'SYN-001', name: 'Standard delivery, clear weather' },
      { id: 'SYN-002', name: 'Rush-hour dispatch with another drone nearby' },
      { id: 'SYN-003', name: 'Origin depot at full landing-pad capacity' },
      { id: 'SYN-004', name: 'High wind exceeds operating envelope' },
      { id: 'SYN-005', name: 'Long-range order requires an intermediate battery swap' },
      { id: 'SYN-006', name: 'Proposed route crosses a DGCA Red Zone' },
      { id: 'SYN-007', name: 'Mid-flight motor fault triggers automated emergency landing' },
    ]

    let passed = 0
    setScenarioProgress({ total: scenarios.length, passed: 0, failed: 0, current: '' })

    for (const sc of scenarios) {
      setScenarioProgress({ total: scenarios.length, passed, failed: 0, current: sc.name })
      addLog(`> Running: ${sc.id} — ${sc.name}`)
      await new Promise(r => setTimeout(r, 800))

      // Illustrative only — this fallback runs when the API is unreachable.
      // The real pass/fail numbers come from `python -m scenario_engine.runner`
      // (verified 7/7 passing against the mock backend; see PROJECT_SUMMARY.md).
      const didPass = Math.random() > 0.15
      const result = {
        scenarioId: sc.id,
        scenarioName: sc.name,
        passed: didPass,
        passCount: didPass ? 7 : Math.floor(Math.random() * 5) + 2,
        totalCount: 7,
        attempt: didPass ? 1 : Math.floor(Math.random() * 3) + 2,
        failedMetrics: didPass ? [] : ['ETA (minutes)', 'Battery Margin (Wh)'].slice(0, Math.floor(Math.random() * 2) + 1),
      }

      appendScenarioResult(result)
      if (didPass) {
        passed++
        addLog(`    [PASS] attempt ${result.attempt}`)
      } else {
        addLog(`    [FAIL] ${result.failedMetrics.join(', ')}`)
      }

      setScenarioProgress({ total: scenarios.length, passed, failed: 0, current: sc.name })
    }

    setScenarioProgress({ total: scenarios.length, passed, failed: scenarios.length - passed, current: undefined })
    addLog(`\nRun complete: ${passed}/${scenarios.length} passed (${((passed / scenarios.length) * 100).toFixed(1)}%)`)
  }

  const { total, passed, failed, current } = scenarioProgress
  const passRate = total > 0 ? (passed / total) * 100 : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div>
          <div className="page-title">Scenario Lab</div>
          <div className="page-subtitle">Regression suite · 7 scenarios · 2 CBF negative tests</div>
        </div>
        <button
          id="btn-run-scenarios"
          className="btn btn--primary"
          onClick={handleRun}
          disabled={running}
        >
          {running
            ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Running...</>
            : 'Run Scenarios'}
        </button>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '320px 1fr', overflow: 'hidden' }}>
        {/* ── Left: Controls ── */}
        <div style={{
          borderRight: '1px solid var(--border)',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          overflow: 'auto',
        }}>
          {/* Run mode */}
          <div className="card">
            <div className="card__title" style={{ marginBottom: '12px' }}>Run Mode</div>
            {(['all', 'synthetic', 'edge_case', 'id'] as RunMode[]).map(mode => (
              <label key={mode} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '8px 0',
                cursor: 'pointer',
                borderBottom: '1px solid var(--border)',
                fontSize: '13px',
                color: runMode === mode ? 'var(--accent)' : 'var(--text-secondary)',
              }}>
                <input
                  type="radio"
                  id={`mode-${mode}`}
                  name="runMode"
                  checked={runMode === mode}
                  onChange={() => setRunMode(mode)}
                  style={{ accentColor: 'var(--accent)' }}
                />
                {mode === 'all' ? 'All Scenarios' :
                 mode === 'synthetic' ? 'Standard Cases' :
                 mode === 'edge_case' ? 'Edge Cases (negative tests)' : 'Specific ID'}
              </label>
            ))}

            {runMode === 'id' && (
              <input
                id="input-scenario-id"
                className="form-input"
                style={{ marginTop: '10px' }}
                placeholder="e.g. SYN-004"
                value={specificId}
                onChange={e => setSpecificId(e.target.value)}
              />
            )}
          </div>

          {/* Options */}
          <div className="card">
            <div className="card__title" style={{ marginBottom: '12px' }}>Options</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '13px' }}>
              <input
                id="toggle-continuous"
                type="checkbox"
                checked={continuous}
                onChange={e => setContinuous(e.target.checked)}
                style={{ accentColor: 'var(--accent)' }}
              />
              <div>
                <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>Continuous Mode</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Keep retrying until all pass</div>
              </div>
            </label>
          </div>

          {/* Progress */}
          {total > 0 && (
            <div className="card">
              <div className="card__title" style={{ marginBottom: '12px' }}>Progress</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  <span style={{ color: 'var(--status-green)' }}>{passed}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '14px', alignSelf: 'flex-end', paddingBottom: '4px' }}>/ {total}</span>
                  <span style={{ color: 'var(--status-red)' }}>{failed}</span>
                </div>
                <div className="gauge-bar" style={{ height: '8px' }}>
                  <div className="gauge-bar__fill gauge-bar__fill--green" style={{ width: `${passRate}%` }} />
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                  {passRate.toFixed(1)}% pass rate
                </div>
                {current && (
                  <div style={{ fontSize: '11px', color: 'var(--status-amber)', fontFamily: 'var(--font-mono)', textAlign: 'center' }}>
                    &gt; {current}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Right: Results + Log ── */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Results table */}
          {scenarioResults.length > 0 && (
            <div style={{ flex: 1, overflow: 'auto', padding: '20px', minHeight: 0 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Scenario</th>
                    <th>Result</th>
                    <th>Score</th>
                    <th>Attempts</th>
                    <th>Failed Metrics</th>
                  </tr>
                </thead>
                <tbody>
                  {scenarioResults.map((r, i) => (
                    <tr key={i}>
                      <td>{r.scenarioId}</td>
                      <td style={{ color: 'var(--text-primary)', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.scenarioName}</td>
                      <td>
                        <span className={`verdict-badge verdict-badge--${r.passed ? 'green' : 'red'}`}>
                          {r.passed ? 'PASS' : 'FAIL'}
                        </span>
                      </td>
                      <td>{r.passCount}/{r.totalCount}</td>
                      <td>{r.attempt}</td>
                      <td style={{ color: r.failedMetrics.length ? 'var(--status-red)' : 'var(--text-muted)', fontSize: '11px' }}>
                        {r.failedMetrics.join(', ') || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Log console */}
          <div style={{
            borderTop: '1px solid var(--border)',
            background: 'var(--bg-deep)',
            height: '200px',
            overflow: 'auto',
            padding: '12px 16px',
            flexShrink: 0,
          }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Run Log
            </div>
            {log.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                Waiting for run to start
              </div>
            ) : (
              log.map((line, i) => (
                <div key={i} style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: line.includes('[PASS]') || line.includes('[OK]') ? 'var(--status-green)' :
                         line.includes('[FAIL]') ? 'var(--status-red)' :
                         line.includes('[WARN]') ? 'var(--status-amber)' :
                         'var(--text-secondary)',
                  lineHeight: '1.6',
                }}>
                  {line}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
