import { useEffect, useState } from 'react'
import type { PredictionResponse, Prediction } from '../types'

const MARK_COLORS: Record<string, string> = {
  '◎': 'text-red-600', '○': 'text-blue-600', '▲': 'text-amber-600', '△': 'text-slate-500',
}

export default function PredictionTable() {
  const [data, setData] = useState<PredictionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/predictions')
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-20 text-slate-400">読み込み中...</div>
  if (!data) return <div className="text-center py-20 text-red-500">データ取得失敗</div>

  const ri = data.race_info

  return (
    <div>
      {/* Race Info */}
      <div className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-xl p-3 sm:p-4 mb-4 flex flex-wrap gap-2 sm:gap-4 items-center text-xs sm:text-sm text-white shadow">
        <span className="bg-red-600 px-2 py-0.5 rounded-full font-bold">{ri.grade}</span>
        <span className="font-semibold">{ri.name}</span>
        <span className="text-blue-300 hidden sm:inline">|</span>
        <span className="text-blue-100">{ri.venue} {ri.surface}{ri.distance}m</span>
        <span className="text-blue-300 hidden sm:inline">|</span>
        <span className="text-blue-100">馬場: <span className="font-bold text-emerald-300">{ri.track_condition}</span></span>
        <span className="text-blue-100">{ri.field_size}頭</span>
      </div>

      {/* Desktop Table */}
      <div className="hidden md:block overflow-x-auto bg-white rounded-xl shadow border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-white">
              <th className="px-3 py-3 text-left">#</th>
              <th className="px-3 py-3 text-left">印</th>
              <th className="px-3 py-3 text-left">馬名</th>
              <th className="px-3 py-3 text-left">騎手</th>
              <th className="px-3 py-3 text-left">勝率</th>
              <th className="px-3 py-3 text-left">複勝率</th>
              <th className="px-3 py-3 text-left">AI指数</th>
              <th className="px-3 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {data.predictions.map((p) => (
              <>
                <tr key={p.horse_name}
                  className={`border-b border-slate-100 hover:bg-blue-50 ${p.rank <= 3 ? 'bg-blue-50/50' : ''}`}>
                  <td className="px-3 py-3 font-bold text-slate-700">{p.rank}</td>
                  <td className={`px-3 py-3 text-xl ${MARK_COLORS[p.mark] || ''}`}>{p.mark}</td>
                  <td className={`px-3 py-3 font-semibold ${p.rank === 1 ? 'text-red-600' : p.rank <= 3 ? 'text-blue-700' : 'text-slate-800'}`}>
                    {p.horse_name}
                    <span className="text-slate-400 text-xs ml-1">{p.sex}{p.age}</span>
                  </td>
                  <td className="px-3 py-3 text-slate-600">{p.jockey ?? '-'}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-20 bg-slate-200 rounded-full h-2">
                        <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${p.win_probability * 100}%` }} />
                      </div>
                      <span className="font-mono font-bold text-xs">{(p.win_probability * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-600">{(p.place_probability * 100).toFixed(1)}%</td>
                  <td className={`px-3 py-3 font-mono font-bold ${p.ai_score >= 80 ? 'text-red-600' : p.ai_score >= 60 ? 'text-amber-600' : 'text-slate-500'}`}>
                    {p.ai_score.toFixed(1)}
                  </td>
                  <td className="px-3 py-3">
                    <button onClick={() => setExpandedRow(expandedRow === p.horse_name ? null : p.horse_name)}
                      className="text-slate-400 hover:text-blue-600">
                      {expandedRow === p.horse_name ? '▼' : '▶'}
                    </button>
                  </td>
                </tr>
                {expandedRow === p.horse_name && <DetailRow p={p} />}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Cards */}
      <div className="md:hidden space-y-2">
        {data.predictions.map((p) => (
          <div key={p.horse_name}
            className={`bg-white rounded-lg shadow-sm border border-slate-200 p-3 ${p.rank <= 3 ? 'border-l-4 border-l-blue-500' : ''}`}
            onClick={() => setExpandedRow(expandedRow === p.horse_name ? null : p.horse_name)}>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-slate-700 w-6">{p.rank}</span>
              <span className={`text-xl ${MARK_COLORS[p.mark] || ''}`}>{p.mark}</span>
              <div className="flex-1 min-w-0">
                <div className={`font-bold truncate ${p.rank === 1 ? 'text-red-600' : p.rank <= 3 ? 'text-blue-700' : 'text-slate-800'}`}>
                  {p.horse_name}
                  <span className="text-slate-400 text-xs ml-1">{p.sex}{p.age}</span>
                </div>
                <div className="text-xs text-slate-500">{p.jockey ?? ''} {p.sire ? `/ ${p.sire}` : ''}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-mono font-bold text-sm">{(p.win_probability * 100).toFixed(1)}%</div>
                <div className={`font-mono text-xs font-bold ${p.ai_score >= 80 ? 'text-red-600' : p.ai_score >= 60 ? 'text-amber-600' : 'text-slate-400'}`}>
                  AI {p.ai_score.toFixed(0)}
                </div>
              </div>
            </div>

            {/* Progress bar */}
            <div className="mt-2 bg-slate-200 rounded-full h-1.5">
              <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${p.win_probability * 100}%` }} />
            </div>

            {/* Expanded detail */}
            {expandedRow === p.horse_name && (
              <div className="mt-3 pt-3 border-t border-slate-100 text-xs space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div><span className="text-slate-400">前走:</span> {p.prev_race ?? '-'} {p.prev_finish ? `${p.prev_finish}着` : ''}</div>
                  <div><span className="text-slate-400">複勝率:</span> {(p.place_probability * 100).toFixed(1)}%</div>
                  <div><span className="text-slate-400">斤量:</span> {p.weight_carried ?? '-'}kg</div>
                  <div><span className="text-slate-400">G1:</span> {p.factors.g1_wins}勝</div>
                </div>
                <div className="space-y-1">
                  {([
                    ['近走', p.factors.recent_form, 'bg-emerald-500'],
                    ['適性', p.factors.course_aptitude, 'bg-blue-500'],
                    ['騎手', p.factors.jockey_factor, 'bg-amber-500'],
                    ['世論', p.factors.public_opinion, 'bg-purple-500'],
                    ['調教', p.factors.training, 'bg-rose-500'],
                  ] as [string, number, string][]).map(([l, v, c]) => (
                    <div key={l} className="flex items-center gap-2">
                      <span className="w-8 text-slate-400">{l}</span>
                      <div className="flex-1 bg-slate-200 rounded-full h-1.5">
                        <div className={`${c} h-1.5 rounded-full`} style={{ width: `${Math.min(v, 100)}%` }} />
                      </div>
                      <span className="w-6 text-right font-mono text-slate-500">{v.toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function DetailRow({ p }: { p: Prediction }) {
  return (
    <tr className="bg-slate-50">
      <td colSpan={8} className="px-6 py-4">
        <div className="grid grid-cols-4 gap-4 text-xs">
          <div><span className="text-slate-400">父:</span> {p.sire ?? '-'}</div>
          <div><span className="text-slate-400">前走:</span> {p.prev_race ?? '-'} {p.prev_finish ? `${p.prev_finish}着` : ''}</div>
          <div><span className="text-slate-400">斤量:</span> {p.weight_carried ?? '-'}kg</div>
          <div><span className="text-slate-400">G1:</span> {p.factors.g1_wins}勝</div>
        </div>
        <div className="mt-3 space-y-1.5">
          {([
            ['近走成績', p.factors.recent_form, 'bg-emerald-500'],
            ['コース適性', p.factors.course_aptitude, 'bg-blue-500'],
            ['騎手力', p.factors.jockey_factor, 'bg-amber-500'],
            ['世論(YT+News)', p.factors.public_opinion, 'bg-purple-500'],
            ['調教', p.factors.training, 'bg-rose-500'],
          ] as [string, number, string][]).map(([l, v, c]) => (
            <div key={l} className="flex items-center gap-2 text-xs">
              <span className="w-28 text-slate-500">{l}</span>
              <div className="flex-1 bg-slate-200 rounded-full h-1.5">
                <div className={`${c} h-1.5 rounded-full`} style={{ width: `${Math.min(v, 100)}%` }} />
              </div>
              <span className="w-8 text-right font-mono text-slate-600">{v.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </td>
    </tr>
  )
}
