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
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="bg-gradient-to-r from-gray-900 via-indigo-950 to-rose-950 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="text-rose-500">KEIBA</span> AI
          </h1>
          <p className="text-gray-400 mt-1">
            宝塚記念 2026 | 阪神 芝2200m | 6/14(日) 15:40
          </p>
        </div>
      </header>

      <nav className="bg-gray-900 border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === tab.id
                  ? 'border-rose-500 text-rose-400'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === 'prediction' && <PredictionTable />}
        {activeTab === 'simulation' && <RaceSimulation />}
        {activeTab === 'betting' && <BettingOptimizer />}
      </main>
    </div>
  )
}
