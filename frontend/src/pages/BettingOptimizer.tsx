import { useState } from 'react'
import type { BettingResponse } from '../types'

const BET_TYPE_OPTIONS = [
  { id: 'win', label: '単勝' },
  { id: 'place', label: '複勝' },
  { id: 'quinella', label: '馬連' },
  { id: 'wide', label: 'ワイド' },
  { id: 'trio', label: '三連複' },
]

export default function BettingOptimizer() {
  const [budget, setBudget] = useState(10000)
  const [risk, setRisk] = useState<'low' | 'medium' | 'high'>('medium')
  const [betTypes, setBetTypes] = useState(['win', 'quinella', 'wide', 'trio'])
  const [result, setResult] = useState<BettingResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const toggleBetType = (id: string) => {
    setBetTypes((prev) => prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id])
  }

  const optimize = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/betting/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ budget, risk_level: risk, bet_types: betTypes, odds: {}, excluded_horses: [] }),
      })
      setResult(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Input Form */}
      <div className="bg-gray-900 rounded-xl p-6 space-y-6">
        <h3 className="text-lg font-bold">投資設定</h3>

        <div>
          <label className="block text-sm text-gray-400 mb-1">投資金額</label>
          <input
            type="number" step={1000} min={1000}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-lg font-mono"
          />
          <div className="flex gap-2 mt-2">
            {[3000, 5000, 10000, 30000, 50000].map((v) => (
              <button key={v} onClick={() => setBudget(v)}
                className={`px-3 py-1 rounded text-xs ${budget === v ? 'bg-rose-600' : 'bg-gray-800 hover:bg-gray-700'}`}
              >
                {v >= 10000 ? `${v / 10000}万` : `${v / 1000}千`}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">リスク許容度</label>
          <div className="flex gap-2">
            {([
              ['low', '低（堅実）', 'bg-blue-600'],
              ['medium', '中', 'bg-amber-600'],
              ['high', '高（大穴）', 'bg-rose-600'],
            ] as const).map(([val, label, color]) => (
              <button key={val} onClick={() => setRisk(val)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium ${risk === val ? color : 'bg-gray-800 hover:bg-gray-700'}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">馬券種別</label>
          <div className="flex flex-wrap gap-2">
            {BET_TYPE_OPTIONS.map((bt) => (
              <button key={bt.id} onClick={() => toggleBetType(bt.id)}
                className={`px-4 py-2 rounded-lg text-sm ${betTypes.includes(bt.id) ? 'bg-indigo-600' : 'bg-gray-800 hover:bg-gray-700'}`}
              >
                {bt.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={optimize}
          disabled={loading || betTypes.length === 0}
          className="w-full bg-rose-600 hover:bg-rose-700 disabled:bg-gray-700 text-white py-3 rounded-lg font-bold text-lg"
        >
          {loading ? '最適化中...' : '買い目を最適化'}
        </button>
      </div>

      {/* Results */}
      <div className="lg:col-span-2">
        {result ? (
          <div className="space-y-4">
            {/* Summary Cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-gray-900 rounded-xl p-4 text-center">
                <div className="text-gray-500 text-sm">合計投資</div>
                <div className="text-2xl font-bold font-mono">{result.total_budget.toLocaleString()}円</div>
              </div>
              <div className="bg-gray-900 rounded-xl p-4 text-center">
                <div className="text-gray-500 text-sm">期待回収</div>
                <div className={`text-2xl font-bold font-mono ${result.expected_return > result.total_budget ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {result.expected_return.toLocaleString()}円
                </div>
              </div>
              <div className="bg-gray-900 rounded-xl p-4 text-center">
                <div className="text-gray-500 text-sm">期待回収率</div>
                <div className={`text-2xl font-bold font-mono ${result.expected_roi >= 1 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {(result.expected_roi * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Bet Table */}
            <div className="bg-gray-900 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-800 text-gray-400">
                    <th className="px-4 py-3 text-left">種別</th>
                    <th className="px-4 py-3 text-left">買い目</th>
                    <th className="px-4 py-3 text-right">金額</th>
                    <th className="px-4 py-3 text-right">オッズ</th>
                    <th className="px-4 py-3 text-right">的中率</th>
                    <th className="px-4 py-3 text-right">期待値</th>
                  </tr>
                </thead>
                <tbody>
                  {result.recommendations.map((r, i) => (
                    <tr key={i} className="border-t border-gray-800/50 hover:bg-gray-800/30">
                      <td className="px-4 py-3">
                        <span className="bg-gray-800 px-2 py-1 rounded text-xs">{r.bet_type_ja}</span>
                      </td>
                      <td className="px-4 py-3 font-medium">{r.selection}</td>
                      <td className="px-4 py-3 text-right font-mono font-bold text-emerald-400">
                        {r.amount.toLocaleString()}円
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{r.odds}倍</td>
                      <td className="px-4 py-3 text-right font-mono">{(r.hit_prob * 100).toFixed(1)}%</td>
                      <td className={`px-4 py-3 text-right font-mono font-bold ${r.expected_value >= 1 ? 'text-emerald-400' : 'text-gray-400'}`}>
                        {r.expected_value.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Risk */}
            <div className="bg-gray-900 rounded-xl p-4 flex gap-8 text-sm">
              <div>最悪ケース: <span className="text-rose-400 font-mono font-bold">{result.risk_metrics.worst_case.toLocaleString()}円</span></div>
              <div>最良ケース: <span className="text-emerald-400 font-mono font-bold">+{result.risk_metrics.best_case.toLocaleString()}円</span></div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-64 text-gray-600">
            左のフォームで設定して「買い目を最適化」を押してください
          </div>
        )}
      </div>
    </div>
  )
}
