import { useEffect, useState } from 'react'
import type { PredictionResponse, Prediction } from '../types'

const MARK_COLORS: Record<string, string> = {
  '◎': 'text-red-600',
  '○': 'text-blue-600',
  '▲': 'text-amber-600',
  '△': 'text-slate-500',
}

export default function PredictionTable() {
  const [data, setData] = useState<PredictionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<keyof Prediction>('rank')
  const [sortAsc, setSortAsc] = useState(true)

  useEffect(() => {
    fetch('/api/predictions')
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-20 text-slate-400">読み込み中...</div>
  if (!data) return <div className="text-center py-20 text-red-500">データ取得失敗</div>

  const sorted = [...data.predictions].sort((a, b) => {
    const av = a[sortKey] ?? 0
    const bv = b[sortKey] ?? 0
    if (av < bv) return sortAsc ? -1 : 1
    if (av > bv) return sortAsc ? 1 : -1
    return 0
  })

  const handleSort = (key: keyof Prediction) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(true) }
  }

  const ri = data.race_info

  return (
    <div>
      {/* Race Info Bar */}
      <div className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-xl p-4 mb-6 flex flex-wrap gap-4 items-center text-sm text-white shadow">
        <span className="bg-red-600 text-white px-3 py-1 rounded-full font-bold text-xs">{ri.grade}</span>
        <span className="font-semibold">{ri.name}</span>
        <span className="text-blue-300">|</span>
        <span className="text-blue-100">{ri.venue} {ri.surface}{ri.distance}m</span>
        <span className="text-blue-300">|</span>
        <span className="text-blue-100">馬場: <span className="font-bold text-emerald-300">{ri.track_condition}</span></span>
        <span className="text-blue-300">|</span>
        <span className="text-blue-100">{ri.field_size}頭</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto bg-white rounded-xl shadow border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-white">
              {([
                ['rank', '順位'],
                ['mark', '印'],
                ['gate_number', '馬番'],
                ['horse_name', '馬名'],
                ['jockey', '騎手'],
                ['win_probability', '勝率'],
                ['place_probability', '複勝率'],
                ['ai_score', 'AI指数'],
              ] as [keyof Prediction, string][]).map(([key, label]) => (
                <th
                  key={key}
                  className="px-3 py-3 text-left cursor-pointer hover:text-blue-200 select-none font-medium text-sm"
                  onClick={() => handleSort(key)}
                >
                  {label} {sortKey === key && (sortAsc ? '↑' : '↓')}
                </th>
              ))}
              <th className="px-3 py-3 text-left font-medium text-sm">詳細</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <>
                <tr
                  key={p.horse_name}
                  className={`border-b border-slate-100 hover:bg-blue-50 transition-colors ${
                    p.rank <= 3 ? 'bg-blue-50/60' : ''
                  }`}
                >
                  <td className="px-3 py-3 font-bold text-slate-700">{p.rank}</td>
                  <td className={`px-3 py-3 text-xl ${MARK_COLORS[p.mark] || ''}`}>{p.mark}</td>
                  <td className="px-3 py-3 text-center text-slate-600">{p.gate_number ?? '-'}</td>
                  <td className={`px-3 py-3 font-semibold ${p.rank === 1 ? 'text-red-600' : p.rank <= 3 ? 'text-blue-700' : 'text-slate-800'}`}>
                    {p.horse_name}
                    {p.sex && p.age && <span className="text-slate-400 text-xs ml-2">{p.sex}{p.age}</span>}
                  </td>
                  <td className="px-3 py-3 text-slate-600">{p.jockey ?? '-'}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-24 bg-slate-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{ width: `${Math.min(p.win_probability * 100, 100)}%` }}
                        />
                      </div>
                      <span className="font-mono font-bold text-slate-800 text-xs w-12">{(p.win_probability * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span className="font-mono text-slate-600">{(p.place_probability * 100).toFixed(1)}%</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`font-mono font-bold ${p.ai_score >= 80 ? 'text-red-600' : p.ai_score >= 60 ? 'text-amber-600' : 'text-slate-500'}`}>
                      {p.ai_score.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <button
                      onClick={() => setExpandedRow(expandedRow === p.horse_name ? null : p.horse_name)}
                      className="text-slate-400 hover:text-blue-600"
                    >
                      {expandedRow === p.horse_name ? '▼' : '▶'}
                    </button>
                  </td>
                </tr>
                {expandedRow === p.horse_name && (
                  <tr key={`${p.horse_name}-detail`} className="bg-slate-50">
                    <td colSpan={9} className="px-6 py-4">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                        <div>
                          <div className="text-slate-400 font-medium">父</div>
                          <div className="text-slate-700">{p.sire ?? '-'}</div>
                        </div>
                        <div>
                          <div className="text-slate-400 font-medium">前走</div>
                          <div className="text-slate-700">{p.prev_race ?? '-'} {p.prev_finish ? `${p.prev_finish}着` : ''}</div>
                        </div>
                        <div>
                          <div className="text-slate-400 font-medium">斤量</div>
                          <div className="text-slate-700">{p.weight_carried ?? '-'}kg</div>
                        </div>
                        <div>
                          <div className="text-slate-400 font-medium">G1勝利</div>
                          <div className="text-slate-700">{p.factors.g1_wins}勝</div>
                        </div>
                      </div>
                      <div className="mt-4 space-y-2">
                        <div className="text-slate-400 text-xs mb-1 font-medium">スコア内訳</div>
                        {([
                          ['近走成績', p.factors.recent_form, 'bg-emerald-500'],
                          ['コース適性', p.factors.course_aptitude, 'bg-blue-500'],
                          ['騎手力', p.factors.jockey_factor, 'bg-amber-500'],
                          ['世論(YT+News)', p.factors.public_opinion, 'bg-purple-500'],
                          ['調教', p.factors.training, 'bg-rose-500'],
                        ] as [string, number, string][]).map(([label, val, color]) => (
                          <div key={label} className="flex items-center gap-2 text-xs">
                            <span className="w-28 text-slate-500">{label}</span>
                            <div className="flex-1 bg-slate-200 rounded-full h-1.5">
                              <div className={`${color} h-1.5 rounded-full`} style={{ width: `${Math.min(val, 100)}%` }} />
                            </div>
                            <span className="w-10 text-right font-mono text-slate-600">{val.toFixed(0)}</span>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
