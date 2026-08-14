import React, { useEffect } from 'react'
import { useAppStore } from './store/appStore'

// Page imports
import DashboardPage from './pages/Dashboard'
import DispatchDesignerPage from './pages/MissionDesigner'
import CouncilViewerPage from './pages/CouncilViewer'
import FleetMapPage from './pages/TrajectoryViewer'
import ScenarioRunnerPage from './pages/ScenarioRunner'
import KnowledgeBasePage from './pages/KnowledgeBase'
import HardwarePanelPage from './pages/HardwarePanel'
import SettingsPage from './pages/Settings'
import VRSafetyViewPage from './pages/VRSafetyView'
import PolicyProposalsPage from './pages/PolicyProposals'
import IncidentForensicsPage from './pages/IncidentForensics'

// Component imports
import RightPanel from './components/RightPanel'

// Icons (inline SVG)
const Icons = {
  Dashboard:   () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1 2a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1H2a1 1 0 01-1-1V2zm7 0a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1H9a1 1 0 01-1-1V2zM1 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H2a1 1 0 01-1-1v-4zm7-1a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H9a1 1 0 01-1-1V9z"/></svg>,
  Mission:     () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0a8 8 0 100 16A8 8 0 008 0zm.5 4.5a.5.5 0 00-1 0V8a.5.5 0 00.146.354l3 3a.5.5 0 00.708-.708L8.5 7.793V4.5z"/></svg>,
  Council:     () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1H7zm4-6a3 3 0 100-6 3 3 0 000 6zM5.216 14A2.238 2.238 0 015 13c0-1.355.68-2.75 1.936-3.72A6.325 6.325 0 005 9c-4 0-5 3-5 4s1 1 1 1h4.216z"/></svg>,
  Trajectory:  () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0a8 8 0 100 16A8 8 0 008 0zM5 7.5a2.5 2.5 0 115 0 2.5 2.5 0 01-5 0z"/></svg>,
  Scenarios:   () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M14 1a1 1 0 011 1v8a1 1 0 01-1 1H4.414L2 13.414V2a1 1 0 011-1h11zm-2.5 5a.5.5 0 100-1 .5.5 0 000 1zm-3.5 0a.5.5 0 100-1 .5.5 0 000 1zm-3.5 0a.5.5 0 100-1 .5.5 0 000 1z"/></svg>,
  Knowledge:   () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1 2.828c.885-.37 2.154-.769 3.388-.893 1.33-.134 2.458.063 3.112.752v9.746c-.935-.53-2.12-.603-3.213-.493-1.18.12-2.37.461-3.287.811V2.828zm7.5-.141c.654-.689 1.782-.886 3.112-.752 1.234.124 2.503.523 3.388.893v9.966c-.918-.35-2.107-.692-3.287-.81-1.094-.111-2.278-.039-3.213.492V2.687zM8 1.783C7.015.936 5.587.81 4.287.94c-1.514.153-3.042.672-3.994 1.105A.5.5 0 000 2.5v11a.5.5 0 00.707.455c.882-.4 2.303-.881 3.68-1.02 1.409-.142 2.59.087 3.223.877a.5.5 0 00.78 0c.633-.79 1.814-1.019 3.222-.877 1.378.139 2.8.62 3.681 1.02A.5.5 0 0016 13.5v-11a.5.5 0 00-.293-.455c-.952-.433-2.48-.952-3.994-1.105C10.413.809 8.985.936 8 1.783z"/></svg>,
  Hardware:    () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M6 1a1 1 0 011 1v1h2V2a1 1 0 112 0v1h.5A1.5 1.5 0 0113 4.5V5h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v.5a1.5 1.5 0 01-1.5 1.5H11v1a1 1 0 11-2 0v-1H7v1a1 1 0 11-2 0v-1h-.5A1.5 1.5 0 013 11.5V11H2a1 1 0 110-2h1V7H2a1 1 0 110-2h1v-.5A1.5 1.5 0 014.5 3H5V2a1 1 0 011-1zm-1 4.5v5h6v-5H5z"/></svg>,
  Settings:    () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M9.405 1.05c-.413-1.4-2.397-1.4-2.81 0l-.1.34a1.464 1.464 0 01-2.105.872l-.31-.17c-1.283-.698-2.686.705-1.987 1.987l.169.311c.446.82.023 1.841-.872 2.105l-.34.1c-1.4.413-1.4 2.397 0 2.81l.34.1a1.464 1.464 0 01.872 2.105l-.17.31c-.698 1.283.705 2.686 1.987 1.987l.311-.169a1.464 1.464 0 012.105.872l.1.34c.413 1.4 2.397 1.4 2.81 0l.1-.34a1.464 1.464 0 012.105-.872l.31.17c1.283.698 2.686-.705 1.987-1.987l-.169-.311a1.464 1.464 0 01.872-2.105l.34-.1c1.4-.413 1.4-2.397 0-2.81l-.34-.1a1.464 1.464 0 01-.872-2.105l.17-.31c.698-1.283-.705-2.686-1.987-1.987l-.311.169a1.464 1.464 0 01-2.105-.872l-.1-.34zM8 10.93a2.929 2.929 0 110-5.86 2.929 2.929 0 010 5.858z"/></svg>,
  VR:          () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M3.5 4A1.5 1.5 0 002 5.5v5A1.5 1.5 0 003.5 12h1.586a1.5 1.5 0 001.06-.44L7.5 10.207a.5.5 0 01.707 0l1.353 1.353a1.5 1.5 0 001.06.44H12.5A1.5 1.5 0 0014 10.5v-5A1.5 1.5 0 0012.5 4h-9zM5 6.5a1 1 0 112 0 1 1 0 01-2 0zm5 0a1 1 0 112 0 1 1 0 01-2 0z"/></svg>,
  Policy:      () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0a1 1 0 01.933.638l.086.278a2.501 2.501 0 001.702 1.702l.278.086a1 1 0 010 1.866l-.278.086a2.501 2.501 0 00-1.702 1.702l-.086.278a1 1 0 01-1.866 0l-.086-.278a2.501 2.501 0 00-1.702-1.702l-.278-.086a1 1 0 010-1.866l.278-.086A2.501 2.501 0 007.048.916L7.134.638A1 1 0 018 0zM3 9a1 1 0 01.943.667 1.5 1.5 0 001.39 1.39A1 1 0 015 13a1.5 1.5 0 00-1.39 1.39A1 1 0 012.667 15a1.5 1.5 0 00-1.39-1.39A1 1 0 011 12a1.5 1.5 0 001.39-1.39A1 1 0 013 9z"/></svg>,
  Incident:    () => <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8.982 1.566a1.13 1.13 0 00-1.964 0L.165 13.233c-.457.778.091 1.767.982 1.767h13.706c.891 0 1.439-.99.982-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 01-1.1 0L7.1 5.995A.905.905 0 018 5zm.002 6a1 1 0 110 2 1 1 0 010-2z"/></svg>,
}

const PAGES = [
  { id: 'dashboard',   label: 'Ops Center',         Icon: Icons.Dashboard },
  { id: 'mission',     label: 'Dispatch Console',   Icon: Icons.Mission },
  { id: 'council',     label: 'Council Room',       Icon: Icons.Council },
  { id: 'incidents',   label: 'Incident Forensics', Icon: Icons.Incident },
  { id: 'policy',      label: 'Fleet Policy',       Icon: Icons.Policy },
  { id: 'trajectory',  label: 'Airspace Map',       Icon: Icons.Trajectory },
  { id: 'vr',          label: 'VR Safety View',     Icon: Icons.VR },
  { id: 'hardware',    label: 'Hardware',           Icon: Icons.Hardware },
  { id: 'scenarios',   label: 'Scenario Lab',       Icon: Icons.Scenarios },
  { id: 'knowledge',   label: 'Depot Network',      Icon: Icons.Knowledge },
  { id: 'settings',    label: 'Settings',           Icon: Icons.Settings },
]

const PAGE_COMPONENTS: Record<string, React.FC> = {
  dashboard:  DashboardPage,
  mission:    DispatchDesignerPage,
  council:    CouncilViewerPage,
  incidents:  IncidentForensicsPage,
  policy:     PolicyProposalsPage,
  trajectory: FleetMapPage,
  vr:         VRSafetyViewPage,
  hardware:   HardwarePanelPage,
  scenarios:  ScenarioRunnerPage,
  knowledge:  KnowledgeBasePage,
  settings:   SettingsPage,
}

export default function App() {
  const { activePage, setActivePage, apiConnected, setApiConnected, apiUrl } = useAppStore()

  // Real reachability check — previously nothing in the app ever called
  // setApiConnected, so the header badge stayed permanently "Offline" even
  // when every actual API call was succeeding. Pings the root endpoint on
  // mount and every 10s afterward so the badge reflects the real backend
  // state, including recovering if the API restarts mid-session.
  useEffect(() => {
    let cancelled = false
    const check = () => {
      fetch(`${apiUrl}/`)
        .then((r) => { if (!cancelled) setApiConnected(r.ok) })
        .catch(() => { if (!cancelled) setApiConnected(false) })
    }
    check()
    const interval = setInterval(check, 10000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [apiUrl, setApiConnected])

  const ActivePage = PAGE_COMPONENTS[activePage] || DashboardPage

  return (
    <div className="app-shell">
      {/* ── Top Header ── */}
      <header className="app-header">
        <div className="app-header__logo">
          <svg className="app-header__logo-icon" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="16" cy="16" r="13" strokeOpacity="0.35" />
            <circle cx="16" cy="16" r="8.5" strokeOpacity="0.6" />
            <circle cx="16" cy="16" r="1.8" fill="currentColor" stroke="none" />
            <path d="M16 16 L16 3" strokeOpacity="0.9" />
            <circle cx="23.5" cy="9" r="1.4" fill="currentColor" stroke="none" />
          </svg>
          <div>
            <div className="app-header__title">AeroFleet</div>
            <div className="app-header__subtitle">11-Agent Council · CBF-Gated Dispatch</div>
          </div>
        </div>

        <div className="app-header__spacer" />

        {/* Status indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div className={`status-indicator status-indicator--${apiConnected ? 'online' : 'offline'}`}>
            <div className="status-indicator__dot" />
            <span>API {apiConnected ? 'Connected' : 'Offline'}</span>
          </div>
        </div>

        <div className="app-header__status-dot" style={{ marginLeft: 16 }} />
      </header>

      {/* ── Left Sidebar ── */}
      <nav className="sidebar">
        <div className="sidebar__section-label">Navigation</div>
        {PAGES.map(({ id, label, Icon }) => (
          <button
            key={id}
            id={`nav-${id}`}
            className={`nav-item ${activePage === id ? 'active' : ''}`}
            onClick={() => setActivePage(id)}
          >
            <span className="nav-item__icon"><Icon /></span>
            {label}
          </button>
        ))}
      </nav>

      {/* ── Main Content ── */}
      <main className="main-content">
        <ActivePage />
      </main>

      {/* ── Right Panel ── */}
      <aside className="right-panel">
        <RightPanel />
      </aside>
    </div>
  )
}
