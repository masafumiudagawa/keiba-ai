import { useEffect, useState, useMemo } from 'react'

const MARK_COLORS: Record<string, string> = { '◎': 'text-red-600', '○': 'text-blue-600', '▲': 'text-amber-600', '△': 'text-slate-500' }

const WEIGHT_CATEGORIES = [
  { key: 'age', label: '馬齢' },
  { key: 'recent_form', label: '直近成績' },
  { key: 'g1_record', label: 'G1実績' },
  { key: 'jockey', label: '騎手力' },
  { key: 'last_3f', label: '上がり3F' },
  { key: 'speed_figure', label: 'スピード指数' },
  { key: 'pedigree', label: '血統適性' },
  { key: 'public_opinion', label: '世論(YT+News)' },
  { key: 'training', label: '調教' },
  { key: 'running_style', label: '脚質' },
  { key: 'head_to_head', label: '対戦成績' },
  { key: 'rest', label: '休養' },
  { key: 'trainer', label: '調教師' },
  { key: 'weight_trend', label: '体重' },
]

const PRESETS: Record<string, Record<string, number>> = {
  standard: Object.fromEntries(WEIGHT_CATEGORIES.map(c => [c.key, 1.0])),
  data_focused: { age: 1.0, recent_form: 1.3, g1_record: 1.3, jockey: 1.0, last_3f: 1.5, speed_figure: 1.5, pedigree: 1.0, public_opinion: 0.3, training: 0.8, running_style: 1.0, head_to_head: 1.2, rest: 1.0, trainer: 0.8, weight_trend: 1.0 },
  public_focused: { age: 0.8, recent_form: 0.8, g1_record: 0.8, jockey: 1.0, last_3f: 0.8, speed_figure: 0.8, pedigree: 0.8, public_opinion: 1.5, training: 1.3, running_style: 0.8, head_to_head: 0.8, rest: 0.8, trainer: 0.8, weight_trend: 0.8 },
  pedigree_focused: { age: 0.8, recent_form: 0.8, g1_record: 0.8, jockey: 0.8, last_3f: 1.0, speed_figure: 1.0, pedigree: 2.0, public_opinion: 0.5, training: 0.8, running_style: 1.2, head_to_head: 0.8, rest: 1.0, trainer: 0.8, weight_trend: 1.0 },
  upset_hunter: { age: 0.5, recent_form: 0.5, g1_record: 0.3, jockey: 0.5, last_3f: 2.0, speed_figure: 1.5, pedigree: 1.2, public_opinion: 0.2, training: 1.5, running_style: 1.5, head_to_head: 0.5, rest: 1.2, trainer: 0.5, weight_trend: 1.0 },
}

interface Horse {
  horse_name: string; jockey: string; age: number; sex: string; sire: string; career: string
  scores: Record<string, number>; raw: Record<string, any>
}

export default function PredictionTable({ raceId }: { raceId: string }) {
  const [features, setFeatures] = useState<Horse[]>([])
  const [_config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [weights, setWeights] = useState<Record<string, number>>(PRESETS.standard)
  const [showWeights, setShowWeights] = useState(false)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/races/${raceId}/features`).then(r => r.json()).then(d => {
      setFeatures(d.features || [])
      setConfig(d.config || {})
    }).catch(() => {}).finally(() => setLoading(false))
  }, [raceId])

  // フロントエンドでリアルタイムスコア再計算
  const ranked = useMemo(() => {
    if (!features.length) return []
    const scored = features.map(h => {
      const total = Object.entries(h.scores).reduce((sum, [k, v]) => sum + v * (weights[k] ?? 1.0), 0)
      return { ...h, total }
    })
    const min = Math.min(...scored.map(s => s.total))
    const max = Math.max(...scored.map(s => s.total))
    const range = max - min || 1
    const withProb = scored.map(s => ({ ...s, prob: (s.total - min) / range }))
    const probSum = withProb.reduce((s, h) => s + h.prob, 0) || 1
    const final = withProb.map(s => ({ ...s, prob: s.prob / probSum }))
    final.sort((a, b) => b.prob - a.prob)
    const marks = ['◎', '○', '▲', '△', '△']
    return final.map((h, i) => ({ ...h, rank: i + 1, mark: marks[i] || '' }))
  }, [features, weights])

  if (loading) return <div className="text-center py-20 text-slate-400">読み込み中...</div>
  if (!features.length) return <div className="text-center py-20 text-slate-400">出走馬データがありません</div>

  return (
    <div>
      {/* Weight Toggle */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => setShowWeights(!showWeights)}
          className={`px-4 py-2 rounded-lg text-sm font-medium border ${showWeights ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-600 border-slate-200'}`}>
          ⚙ ウェイト調整 {showWeights ? '▲' : '▼'}
        </button>
        {showWeights && (
          <div className="flex gap-1.5 overflow-x-auto">
            {[['standard', '標準'], ['data_focused', 'データ重視'], ['public_focused', '世論重視'], ['pedigree_focused', '血統重視'], ['upset_hunter', '穴馬発掘']].map(([k, l]) => (
              <button key={k} onClick={() => setWeights(PRESETS[k])}
                className="px-2.5 py-1 rounded text-xs font-medium bg-white border border-slate-200 hover:bg-blue-50 whitespace-nowrap">
                {l}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Weight Sliders */}
      {showWeights && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 shadow-sm">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-2">
            {WEIGHT_CATEGORIES.map(cat => (
              <div key={cat.key} className="flex items-center gap-2">
                <span className="text-xs text-slate-500 w-20 shrink-0">{cat.label}</span>
                <input type="range" min="0" max="2" step="0.1" value={weights[cat.key] ?? 1}
                  onChange={e => setWeights({ ...weights, [cat.key]: parseFloat(e.target.value) })}
                  className="flex-1 h-1.5 accent-blue-600" />
                <span className={`text-xs font-mono w-8 text-right ${(weights[cat.key] ?? 1) !== 1 ? 'text-blue-700 font-bold' : 'text-slate-400'}`}>
                  {(weights[cat.key] ?? 1).toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Desktop Table */}
      <div className="hidden md:block overflow-x-auto bg-white rounded-xl shadow border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-white text-xs">
              <th className="px-3 py-2 text-left">#</th><th className="px-3 py-2">印</th>
              <th className="px-3 py-2 text-left">馬名</th><th className="px-3 py-2 text-left">騎手</th>
              <th className="px-3 py-2 text-right">勝率</th><th className="px-3 py-2 text-right">AI指数</th>
              <th className="px-3 py-2 text-right">3F</th><th className="px-3 py-2 text-right">SP</th>
              <th className="px-3 py-2 text-right">G1</th><th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {ranked.map(h => (
              <>
                <tr key={h.horse_name} className={`border-b border-slate-100 hover:bg-blue-50 ${h.rank <= 3 ? 'bg-blue-50/50' : ''}`}>
                  <td className="px-3 py-2 font-bold text-slate-700">{h.rank}</td>
                  <td className={`px-3 py-2 text-lg text-center ${MARK_COLORS[h.mark] || ''}`}>{h.mark}</td>
                  <td className={`px-3 py-2 font-semibold ${h.rank === 1 ? 'text-red-600' : h.rank <= 3 ? 'text-blue-700' : ''}`}>
                    {h.horse_name} <span className="text-slate-400 text-xs">{h.sex}{h.age}</span>
                  </td>
                  <td className="px-3 py-2 text-slate-600 text-xs">{h.jockey}</td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <div className="w-16 bg-slate-200 rounded-full h-1.5">
                        <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${h.prob * 100}%` }} />
                      </div>
                      <span className="font-mono font-bold text-xs">{(h.prob * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className={`px-3 py-2 text-right font-mono font-bold text-xs ${h.total > 300 ? 'text-red-600' : h.total > 200 ? 'text-amber-600' : 'text-slate-500'}`}>
                    {h.total.toFixed(0)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-500">{h.raw.best_last3f || '-'}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-500">{h.raw.speed_figure || '-'}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-500">{h.raw.g1_wins || 0}</td>
                  <td className="px-3 py-2">
                    <button onClick={() => setExpandedRow(expandedRow === h.horse_name ? null : h.horse_name)}
                      className="text-slate-400 hover:text-blue-600 text-xs">{expandedRow === h.horse_name ? '▼' : '▶'}</button>
                  </td>
                </tr>
                {expandedRow === h.horse_name && (
                  <tr className="bg-slate-50"><td colSpan={10} className="px-4 py-3">
                    <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                      <div><span className="text-slate-400">戦績:</span> {h.career}</div>
                      <div><span className="text-slate-400">父:</span> {h.sire}</div>
                      <div><span className="text-slate-400">脚質:</span> {h.raw.running_style}</div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
                      {WEIGHT_CATEGORIES.map(cat => {
                        const base = h.scores[cat.key] || 0
                        const weighted = base * (weights[cat.key] ?? 1)
                        return (
                          <div key={cat.key} className="flex items-center gap-1 text-[11px]">
                            <span className="w-16 text-slate-400 shrink-0">{cat.label}</span>
                            <div className="flex-1 bg-slate-200 rounded-full h-1">
                              <div className="bg-blue-500 h-1 rounded-full" style={{ width: `${Math.min(weighted / 2, 100)}%` }} />
                            </div>
                            <span className="w-8 text-right font-mono text-slate-600">{weighted.toFixed(0)}</span>
                          </div>
                        )
                      })}
                    </div>
                  </td></tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Cards */}
      <div className="md:hidden space-y-2">
        {ranked.map(h => (
          <div key={h.horse_name}
            className={`bg-white rounded-lg shadow-sm border border-slate-200 p-3 ${h.rank <= 3 ? 'border-l-4 border-l-blue-500' : ''}`}
            onClick={() => setExpandedRow(expandedRow === h.horse_name ? null : h.horse_name)}>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-slate-700 w-6">{h.rank}</span>
              <span className={`text-xl ${MARK_COLORS[h.mark] || ''}`}>{h.mark}</span>
              <div className="flex-1 min-w-0">
                <div className={`font-bold truncate ${h.rank === 1 ? 'text-red-600' : h.rank <= 3 ? 'text-blue-700' : ''}`}>
                  {h.horse_name} <span className="text-slate-400 text-xs">{h.sex}{h.age}</span>
                </div>
                <div className="text-xs text-slate-500">{h.jockey} / {h.sire}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-mono font-bold text-sm">{(h.prob * 100).toFixed(1)}%</div>
                <div className="text-[10px] text-slate-400">3F:{h.raw.best_last3f} SP:{h.raw.speed_figure}</div>
              </div>
            </div>
            <div className="mt-1.5 bg-slate-200 rounded-full h-1.5">
              <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${h.prob * 100}%` }} />
            </div>
            {expandedRow === h.horse_name && (
              <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
                {WEIGHT_CATEGORIES.map(cat => {
                  const w = (h.scores[cat.key] || 0) * (weights[cat.key] ?? 1)
                  return (
                    <div key={cat.key} className="flex items-center gap-1 text-[10px]">
                      <span className="w-16 text-slate-400">{cat.label}</span>
                      <div className="flex-1 bg-slate-200 rounded-full h-1"><div className="bg-blue-500 h-1 rounded-full" style={{ width: `${Math.min(w / 2, 100)}%` }} /></div>
                      <span className="w-6 text-right font-mono">{w.toFixed(0)}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
