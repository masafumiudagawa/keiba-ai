import { useState, useEffect } from 'react'
import PredictionTable from './pages/PredictionTable'
import RaceSimulation from './pages/RaceSimulation'
import BettingOptimizer from './pages/BettingOptimizer'

interface RaceInfo { id: string; name: string; date: string; venue: string; distance: number; surface: string; grade: string }

const TABS = [
  { id: 'prediction', label: '予測一覧', icon: '📊' },
  { id: 'simulation', label: 'シミュレーション', icon: '🏇' },
  { id: 'betting', label: '買い目最適化', icon: '💰' },
] as const
type TabId = typeof TABS[number]['id']

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('prediction')
  const [races, setRaces] = useState<RaceInfo[]>([])
  const [activeRace, setActiveRace] = useState<string>('takarazuka_2026')
  const [showAddRace, setShowAddRace] = useState(false)
  const [newRace, setNewRace] = useState({ name: '', date: '', venue: '', distance: 2000, surface: '芝', grade: 'G1' })

  useEffect(() => {
    fetch('/api/races').then(r => r.json()).then(d => {
      setRaces(d.races || [])
      if (d.races?.length > 0 && !d.races.find((r: RaceInfo) => r.id === activeRace)) {
        setActiveRace(d.races[0].id)
      }
    }).catch(() => {})
  }, [])

  const currentRace = races.find(r => r.id === activeRace)

  const addRace = async () => {
    if (!newRace.name) return
    // IDを自動生成: レース名+年 → ローマ字化
    const autoId = (newRace.name + '_' + (newRace.date?.slice(0, 4) || '2026'))
      .replace(/[^a-zA-Z0-9\u3040-\u9fff]/g, '_').toLowerCase()
    await fetch('/api/races', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ ...newRace, id: autoId, trends: {} }),
    })
    const res = await fetch('/api/races')
    const d = await res.json()
    setRaces(d.races || [])
    setActiveRace(autoId)
    setShowAddRace(false)
    setNewRace({ name: '', date: '', venue: '', distance: 2000, surface: '芝', grade: 'G1' })
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800">
      {/* Header */}
      <header className="bg-gradient-to-r from-slate-800 via-blue-900 to-indigo-900 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="text-2xl sm:text-3xl">🐴</div>
            <h1 className="text-lg sm:text-xl font-bold tracking-tight">競馬予想AI</h1>
          </div>

          {/* Race Selector */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {races.map(race => (
              <button key={race.id} onClick={() => setActiveRace(race.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  activeRace === race.id
                    ? 'bg-white text-blue-900'
                    : 'bg-white/10 text-white/80 hover:bg-white/20'
                }`}>
                <span className="bg-red-600 text-white px-1.5 py-0.5 rounded text-[10px] mr-1.5">{race.grade}</span>
                {race.name}
                <span className="text-[10px] ml-1 opacity-60">{race.venue}{race.surface}{race.distance}m</span>
              </button>
            ))}
            <button onClick={() => setShowAddRace(!showAddRace)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/10 text-white/80 hover:bg-white/20 whitespace-nowrap">
              + レース追加
            </button>
          </div>

          {/* Add Race Form */}
          {showAddRace && (
            <div className="mt-2 bg-white/10 rounded-lg p-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
              <input placeholder="レース名（例: 有馬記念）" value={newRace.name} onChange={e => setNewRace({ ...newRace, name: e.target.value })}
                className="bg-white/20 rounded px-2 py-1 text-xs text-white placeholder-white/50" />
              <input type="date" value={newRace.date} onChange={e => setNewRace({ ...newRace, date: e.target.value })}
                className="bg-white/20 rounded px-2 py-1 text-xs text-white" />
              <input placeholder="競馬場" value={newRace.venue} onChange={e => setNewRace({ ...newRace, venue: e.target.value })}
                className="bg-white/20 rounded px-2 py-1 text-xs text-white placeholder-white/50" />
              <input type="number" placeholder="距離" value={newRace.distance} onChange={e => setNewRace({ ...newRace, distance: Number(e.target.value) })}
                className="bg-white/20 rounded px-2 py-1 text-xs text-white" />
              <select value={newRace.surface} onChange={e => setNewRace({ ...newRace, surface: e.target.value })}
                className="bg-white/20 rounded px-2 py-1 text-xs text-white">
                <option value="芝">芝</option><option value="ダート">ダート</option>
              </select>
              <select value={newRace.grade} onChange={e => setNewRace({ ...newRace, grade: e.target.value })}
                className="bg-white/20 rounded px-2 py-1 text-xs text-white">
                <option>G1</option><option>G2</option><option>G3</option><option>OP</option><option>L</option><option>条件</option>
              </select>
              <button onClick={addRace} className="bg-white text-blue-900 rounded px-3 py-1 text-xs font-bold hover:bg-blue-50">
                追加
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Current Race Info */}
      {currentRace && (
        <div className="bg-white border-b border-slate-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-3 sm:px-4 py-2 flex items-center gap-3 text-sm text-slate-600">
            <span className="bg-red-600 text-white px-2 py-0.5 rounded text-xs font-bold">{currentRace.grade}</span>
            <span className="font-bold text-slate-800">{currentRace.name}</span>
            <span>{currentRace.venue} {currentRace.surface}{currentRace.distance}m</span>
            {currentRace.date && <span>{currentRace.date}</span>}
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm overflow-x-auto">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 flex gap-0 min-w-max">
          {TABS.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`px-3 sm:px-6 py-2 sm:py-2.5 text-xs sm:text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
                activeTab === tab.id ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}>
              <span className="mr-1">{tab.icon}</span>{tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-2 sm:px-4 py-4 sm:py-6">
        {activeTab === 'prediction' && <PredictionTable raceId={activeRace} />}
        {activeTab === 'simulation' && <RaceSimulation raceId={activeRace} />}
        {activeTab === 'betting' && <BettingOptimizer raceId={activeRace} />}
      </main>
    </div>
  )
}
