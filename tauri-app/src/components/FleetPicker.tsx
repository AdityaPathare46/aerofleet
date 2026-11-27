// Shared fleet selector for Today's fleet, Spray register, Fleet trends, and Fleet Assurance.
// Fetches existing fleets from GET /api/v1/assurance/fleets, persists choice in localStorage,
// and smartly selects 'pune-agri' (or the first seeded fleet) when localStorage still holds 'default'.
import { useEffect, useState } from 'react'

interface FleetItem {
  fleet: string
  drones: number
  flights: number
  has_baseline: boolean
}

function token(): Record<string, string> {
  try { const t = localStorage.getItem('aerofleet_token') || ''; return t ? { Authorization: `Bearer ${t}` } : {} } catch { return {} }
}

export function initialFleet(): string {
  try { return localStorage.getItem('aerofleet_fleet') || 'pune-agri' } catch { return 'pune-agri' }
}

export function setSavedFleet(fleet: string) {
  try { localStorage.setItem('aerofleet_fleet', fleet) } catch { /* private window */ }
}

export default function FleetPicker({ apiUrl, fleet, onChange }: { apiUrl: string; fleet: string; onChange: (next: string) => void }) {
  const [fleets, setFleets] = useState<FleetItem[]>([])

  useEffect(() => {
    let active = true
    fetch(`${apiUrl}/api/v1/assurance/fleets`, { headers: token() })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { fleets?: FleetItem[]; default?: string } | null) => {
        if (!active || !data?.fleets) return
        setFleets(data.fleets)
        if (data.fleets.length > 0 && !data.fleets.some((f) => f.fleet === fleet) && (fleet === 'default' || fleet === 'pune-agri')) {
          const pick = data.default || data.fleets[0].fleet
          setSavedFleet(pick)
          onChange(pick)
        }
      })
      .catch(() => {})
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl])

  const options = fleets.some((f) => f.fleet === fleet)
    ? fleets
    : [{ fleet, drones: 0, flights: 0, has_baseline: false }, ...fleets]

  return (
    <select
      aria-label="Fleet"
      className="form-select"
      value={fleet}
      onChange={(e) => { setSavedFleet(e.target.value); onChange(e.target.value) }}
      style={{ width: 'auto', minWidth: 150, padding: '4px 8px', fontSize: 13 }}
    >
      {options.map((f) => (
        <option key={f.fleet} value={f.fleet}>
          {f.fleet}{f.drones > 0 ? ` (${f.drones} drones · ${f.flights} flights)` : ''}
        </option>
      ))}
    </select>
  )
}
