import { useState } from 'react'
import PredictionTable from './pages/PredictionTable'
import RaceSimulation from './pages/RaceSimulation'
import BettingOptimizer from './pages/BettingOptimizer'

const TABS = [
  { id: 'prediction', label: '予測一覧', icon: '📊' },
  { id: 'simulation', label: 'レースシミュレーション', icon: '🏇' },
  { id: 'betting', label: '買い目最適化', icon: '💰' },
] as const

type TabId = typeof TABS[number]['id']

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('prediction')

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800">
      {/* Header */}
      <header className="bg-gradient-to-r from-slate-800 via-blue-900 to-indigo-900 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-5 flex items-center gap-3">
          <div className="text-3xl sm:text-4xl">🐴</div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
              競馬予想AI
            </h1>
            <p className="text-blue-200 text-xs sm:text-sm mt-0.5">
              宝塚記念 2026 | 阪神 芝2200m | 6/14(日)
            </p>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm overflow-x-auto">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 flex gap-0 min-w-max">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 sm:px-6 py-2.5 sm:py-3 text-xs sm:text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-2 sm:px-4 py-4 sm:py-6">
        {activeTab === 'prediction' && <PredictionTable />}
        {activeTab === 'simulation' && <RaceSimulation />}
        {activeTab === 'betting' && <BettingOptimizer />}
      </main>
    </div>
  )
}
