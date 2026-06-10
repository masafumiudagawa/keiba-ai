import { useEffect, useState, useMemo } from 'react'

const MARK_COLORS: Record<string, string> = { '◎': 'text-red-600', '○': 'text-blue-600', '▲': 'text-amber-600', '△': 'text-slate-500' }
const WAKU_COLORS: Record<number, string> = { 1: 'bg-white border border-slate-300 text-slate-800', 2: 'bg-gray-900 text-white', 3: 'bg-red-600 text-white', 4: 'bg-blue-600 text-white', 5: 'bg-yellow-400 text-gray-900', 6: 'bg-green-600 text-white', 7: 'bg-orange-500 text-white', 8: 'bg-pink-500 text-white' }
const FINISH_COLORS: Record<number, string> = { 1: 'bg-red-600 text-white', 2: 'bg-blue-600 text-white', 3: 'bg-green-600 text-white' }

const WEIGHT_CATEGORIES = [
  { key: 'age', label: '馬齢' }, { key: 'recent_form', label: '直近成績' }, { key: 'g1_record', label: 'G1実績' },
  { key: 'jockey', label: '騎手力' }, { key: 'last_3f', label: '上がり3F' }, { key: 'speed_figure', label: '能力値' },
  { key: 'pedigree', label: '血統' }, { key: 'public_opinion', label: '世論' }, { key: 'training', label: '調教' },
  { key: 'running_style', label: '脚質' }, { key: 'head_to_head', label: '対戦' }, { key: 'rest', label: '休養' },
  { key: 'trainer', label: '調教師' }, { key: 'weight_trend', label: '体重' },
]

const PRESETS: Record<string, Record<string, number>> = {
  standard: Object.fromEntries(WEIGHT_CATEGORIES.map(c => [c.key, 1.0])),
  data_focused: { age: 1.0, recent_form: 1.3, g1_record: 1.3, jockey: 1.0, last_3f: 1.5, speed_figure: 1.5, pedigree: 1.0, public_opinion: 0.3, training: 0.8, running_style: 1.0, head_to_head: 1.2, rest: 1.0, trainer: 0.8, weight_trend: 1.0 },
  public_focused: { age: 0.8, recent_form: 0.8, g1_record: 0.8, jockey: 1.0, last_3f: 0.8, speed_figure: 0.8, pedigree: 0.8, public_opinion: 1.5, training: 1.3, running_style: 0.8, head_to_head: 0.8, rest: 0.8, trainer: 0.8, weight_trend: 0.8 },
  upset_hunter: { age: 0.5, recent_form: 0.5, g1_record: 0.3, jockey: 0.5, last_3f: 2.0, speed_figure: 1.5, pedigree: 1.2, public_opinion: 0.2, training: 1.5, running_style: 1.5, head_to_head: 0.5, rest: 1.2, trainer: 0.5, weight_trend: 1.0 },
}

interface Recent { date: string; venue: string; race: string; dist: number; finish: number | string; grade: string }
interface Horse {
  horse_name: string; jockey: string; age: number; sex: string; sire: string; dam_sire: string; trainer: string
  gate_number: number; post_position: number; weight: string; running_style_label: string; career: string
  recent_5: Recent[]; scores: Record<string, number>; raw: Record<string, any>
}

const FinishBadge = ({ finish }: { finish: number | string }) => {
  const n = typeof finish === 'number' ? finish : parseInt(String(finish))
  if (!n || isNaN(n)) return <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-400 text-[10px] flex items-center justify-center">-</span>
  const color = FINISH_COLORS[n] || 'bg-slate-300 text-slate-600'
  return <span className={`w-5 h-5 rounded-full ${color} text-[10px] font-bold flex items-center justify-center`}>{n}</span>
}

const WakuBadge = ({ post, gate }: { post: number; gate: number }) => {
  if (!post) return null
  return (
    <div className={`w-8 h-10 rounded flex flex-col items-center justify-center text-xs font-bold ${WAKU_COLORS[post] || 'bg-slate-200'}`}>
      <div className="text-[9px] opacity-70">{post}枠</div>
      <div className="text-sm">{gate}</div>
    </div>
  )
}

export default function PredictionTable({ raceId }: { raceId: string }) {
  const [features, setFeatures] = useState<Horse[]>([])
  const [config, setConfig] = useState<any>(null)
  const [weather, setWeather] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [weights, setWeights] = useState<Record<string, number>>(PRESETS.standard)
  const [showWeights, setShowWeights] = useState(false)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/races/${raceId}/features`).then(r => r.json()).then(d => {
      setFeatures(d.features || [])
      setConfig(d.config || {})
      setWeather(d.weather || null)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [raceId])

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

  const trackColor: Record<string, string> = { '良': 'text-emerald-600', '稍重': 'text-amber-600', '重': 'text-orange-600', '不良': 'text-red-600' }

  return (
    <div>
      {/* Race Info + Weather */}
      {(config || weather) && (
        <div className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-xl p-3 mb-4 text-white shadow">
          <div className="flex flex-wrap gap-x-4 gap-y-1 items-center text-xs sm:text-sm">
            {config?.grade && <span className="bg-red-600 px-2 py-0.5 rounded-full text-xs font-bold">{config.grade}</span>}
            {config?.name && <span className="font-bold">{config.name}</span>}
            {config?.venue && <span className="text-blue-200">{config.venue} {config.surface}{config.distance}m</span>}
            {config?.date && <span className="text-blue-200">{config.date}</span>}
            {config?.post_time && <span className="text-blue-200">{config.post_time}発走</span>}
          </div>
          {weather?.forecast && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-blue-100 items-center">
              <span>天気: <strong className="text-white">{weather.forecast}</strong></span>
              {weather.temperature_low != null && <span>{weather.temperature_low}〜{weather.temperature_high}℃</span>}
              {weather.precipitation_mm != null && <span>降水: {weather.precipitation_mm}mm</span>}
              {weather.predicted_track_condition && (
                <span>馬場: <strong className={`${trackColor[weather.predicted_track_condition] || 'text-white'} bg-white/20 px-1.5 py-0.5 rounded`}>
                  {weather.predicted_track_condition}
                </strong></span>
              )}
              <span className="text-blue-300 text-[10px]">({weather.fetched_at}更新)</span>
            </div>
          )}
        </div>
      )}

      {/* Weight Toggle + Presets */}
      <div className="mb-3">
        <button onClick={() => setShowWeights(!showWeights)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${showWeights ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-600 border-slate-200'}`}>
          ⚙ ウェイト調整 {showWeights ? '▲' : '▼'}
        </button>
      </div>
      {showWeights && (
        <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 shadow-sm">
          <div className="flex flex-wrap gap-1.5 mb-3 pb-2 border-b border-slate-100">
            {[['standard', '標準'], ['data_focused', 'データ重視'], ['public_focused', '世論重視'], ['upset_hunter', '穴馬発掘']].map(([k, l]) => (
              <button key={k} onClick={() => setWeights(PRESETS[k])}
                className="px-2.5 py-1 rounded text-xs font-medium bg-slate-50 border border-slate-200 hover:bg-blue-50">{l}</button>
            ))}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {WEIGHT_CATEGORIES.map(cat => (
              <div key={cat.key} className="flex items-center gap-2 py-0.5">
                <span className="text-xs text-slate-500 w-14 shrink-0">{cat.label}</span>
                <input type="range" min="0" max="2" step="0.1" value={weights[cat.key] ?? 1}
                  onChange={e => setWeights({ ...weights, [cat.key]: parseFloat(e.target.value) })}
                  className="flex-1 h-2 accent-blue-600" />
                <span className={`text-xs font-mono w-7 text-right ${(weights[cat.key] ?? 1) !== 1 ? 'text-blue-700 font-bold' : 'text-slate-400'}`}>
                  {(weights[cat.key] ?? 1).toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ PC Table (netkeiba風) ═══ */}
      <div className="hidden lg:block bg-white rounded-xl shadow border border-slate-200 overflow-hidden">
        {ranked.map(h => (
          <div key={h.horse_name} className={`border-b border-slate-100 hover:bg-blue-50/50 ${h.rank <= 3 ? 'bg-blue-50/30' : ''}`}>
            <div className="flex items-stretch">
              {/* 枠色+馬番 */}
              <div className="w-14 flex items-center justify-center shrink-0 border-r border-slate-100">
                <WakuBadge post={h.post_position} gate={h.gate_number} />
              </div>

              {/* 印+順位 */}
              <div className="w-12 flex flex-col items-center justify-center shrink-0 border-r border-slate-100">
                <span className={`text-lg ${MARK_COLORS[h.mark] || ''}`}>{h.mark}</span>
                <span className="text-[10px] text-slate-400">{h.rank}位</span>
              </div>

              {/* 馬名+血統+調教師 */}
              <div className="flex-1 min-w-0 p-2 border-r border-slate-100 cursor-pointer"
                onClick={() => setExpandedRow(expandedRow === h.horse_name ? null : h.horse_name)}>
                <div className="flex items-baseline gap-1.5">
                  <span className={`font-bold text-sm ${h.rank === 1 ? 'text-red-600' : h.rank <= 3 ? 'text-blue-700' : 'text-slate-800'}`}>
                    {h.horse_name}
                  </span>
                  <span className="text-[10px] text-slate-400">{h.sex}{h.age}</span>
                  <span className="text-[10px] bg-slate-100 text-slate-500 px-1 rounded">{h.running_style_label}</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  {h.sire && h.sire !== 'nan' ? h.sire : ''}{h.dam_sire && h.dam_sire !== 'nan' && h.dam_sire !== '' ? ` × ${h.dam_sire}` : ''}
                </div>
                <div className="text-[10px] text-slate-400">
                  {h.trainer && h.trainer !== 'nan' ? h.trainer : ''} {h.weight && h.weight !== 'nan' ? h.weight + 'kg' : ''} {h.career}
                </div>
              </div>

              {/* 騎手 */}
              <div className="w-16 flex items-center justify-center text-xs text-slate-700 shrink-0 border-r border-slate-100">
                {h.jockey}
              </div>

              {/* オッズ+人気 */}
              <div className="w-20 flex flex-col items-center justify-center shrink-0 border-r border-slate-100">
                <span className="font-mono font-bold text-sm">{h.raw.win_odds || '-'}</span>
                {h.raw.popularity > 0 && (
                  <span className={`text-[10px] px-1.5 rounded-full font-bold ${h.raw.popularity <= 3 ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-500'}`}>
                    {h.raw.popularity}人気
                  </span>
                )}
              </div>

              {/* 勝率 */}
              <div className="w-20 flex flex-col items-center justify-center shrink-0 border-r border-slate-100">
                <span className="font-mono font-bold text-sm">{(h.prob * 100).toFixed(1)}%</span>
                <div className="w-14 bg-slate-200 rounded-full h-1 mt-0.5">
                  <div className="bg-blue-600 h-1 rounded-full" style={{ width: `${h.prob * 100}%` }} />
                </div>
              </div>

              {/* 直近5走 */}
              <div className="w-36 flex items-center justify-center gap-1 shrink-0 px-2">
                {h.recent_5?.length > 0 ? h.recent_5.map((r, i) => (
                  <div key={i} className="flex flex-col items-center">
                    <FinishBadge finish={r.finish} />
                    <span className="text-[8px] text-slate-400 mt-0.5 leading-none">{r.race?.slice(0, 3)}</span>
                  </div>
                )) : <span className="text-[10px] text-slate-300">データなし</span>}
              </div>
            </div>

            {/* Expanded Detail */}
            {expandedRow === h.horse_name && (
              <div className="bg-slate-50 px-4 py-3 border-t border-slate-100">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
                  {WEIGHT_CATEGORIES.map(cat => {
                    const w = (h.scores[cat.key] || 0) * (weights[cat.key] ?? 1)
                    return (
                      <div key={cat.key} className="flex items-center gap-1 text-[11px]">
                        <span className="w-14 text-slate-400">{cat.label}</span>
                        <div className="flex-1 bg-slate-200 rounded-full h-1">
                          <div className="bg-blue-500 h-1 rounded-full" style={{ width: `${Math.min(w / 2, 100)}%` }} />
                        </div>
                        <span className="w-6 text-right font-mono text-slate-600">{w.toFixed(0)}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ═══ Tablet/Small Desktop ═══ */}
      <div className="hidden md:block lg:hidden space-y-1">
        {ranked.map(h => (
          <div key={h.horse_name} className={`bg-white rounded-lg shadow-sm border border-slate-200 p-2.5 ${h.rank <= 3 ? 'border-l-4 border-l-blue-500' : ''}`}
            onClick={() => setExpandedRow(expandedRow === h.horse_name ? null : h.horse_name)}>
            <div className="flex items-center gap-2">
              <WakuBadge post={h.post_position} gate={h.gate_number} />
              <span className={`text-lg ${MARK_COLORS[h.mark] || ''}`}>{h.mark}</span>
              <div className="flex-1 min-w-0">
                <div className={`font-bold text-sm truncate ${h.rank === 1 ? 'text-red-600' : h.rank <= 3 ? 'text-blue-700' : ''}`}>
                  {h.horse_name} <span className="text-slate-400 text-xs">{h.sex}{h.age} {h.running_style_label}</span>
                </div>
                <div className="text-[10px] text-slate-500">{h.jockey} / {h.sire && h.sire !== 'nan' ? h.sire : ''} / {h.trainer && h.trainer !== 'nan' ? h.trainer : ''}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-mono font-bold text-sm">{(h.prob * 100).toFixed(1)}%</div>
                <div className="text-[10px] text-slate-500">{h.raw.win_odds ? `${h.raw.win_odds}倍` : ''} {h.raw.popularity ? `${h.raw.popularity}人気` : ''}</div>
              </div>
              <div className="flex gap-0.5 shrink-0">
                {h.recent_5?.slice(0, 5).map((r, i) => <FinishBadge key={i} finish={r.finish} />)}
              </div>
            </div>
            {expandedRow === h.horse_name && (
              <div className="mt-2 pt-2 border-t border-slate-100 grid grid-cols-3 gap-1">
                {WEIGHT_CATEGORIES.map(cat => {
                  const w = (h.scores[cat.key] || 0) * (weights[cat.key] ?? 1)
                  return (
                    <div key={cat.key} className="flex items-center gap-1 text-[10px]">
                      <span className="w-10 text-slate-400">{cat.label}</span>
                      <div className="flex-1 bg-slate-200 rounded-full h-1"><div className="bg-blue-500 h-1 rounded-full" style={{ width: `${Math.min(w / 2, 100)}%` }} /></div>
                      <span className="w-5 text-right font-mono">{w.toFixed(0)}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ═══ Mobile Cards ═══ */}
      <div className="md:hidden space-y-1.5">
        {ranked.map(h => (
          <div key={h.horse_name}
            className={`bg-white rounded-lg shadow-sm border border-slate-200 p-2.5 ${h.rank <= 3 ? 'border-l-4 border-l-blue-500' : ''}`}
            onClick={() => setExpandedRow(expandedRow === h.horse_name ? null : h.horse_name)}>
            <div className="flex items-center gap-2">
              <WakuBadge post={h.post_position} gate={h.gate_number} />
              <span className={`text-lg ${MARK_COLORS[h.mark] || ''} shrink-0`}>{h.mark}</span>
              <div className="flex-1 min-w-0">
                <div className={`font-bold truncate ${h.rank === 1 ? 'text-red-600' : h.rank <= 3 ? 'text-blue-700' : ''}`}>
                  {h.horse_name} <span className="text-slate-400 text-xs">{h.sex}{h.age}</span>
                </div>
                <div className="text-[10px] text-slate-500 truncate">{h.jockey} / {h.sire && h.sire !== 'nan' ? h.sire : ''}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-mono font-bold text-sm">{(h.prob * 100).toFixed(1)}%</div>
                <div className="text-[10px] text-slate-500">{h.raw.win_odds ? `${h.raw.win_odds}倍` : ''}</div>
              </div>
            </div>

            {/* 馬柱 */}
            <div className="flex items-center gap-1 mt-1.5">
              <span className="text-[10px] text-slate-400 w-8 shrink-0">近走:</span>
              {h.recent_5?.length > 0 ? h.recent_5.map((r, i) => (
                <div key={i} className="flex flex-col items-center">
                  <FinishBadge finish={r.finish} />
                  <span className="text-[7px] text-slate-400 leading-none mt-0.5">{r.race?.slice(0, 2)}</span>
                </div>
              )) : <span className="text-[10px] text-slate-300">-</span>}
              <span className="ml-auto text-[10px] bg-slate-100 text-slate-500 px-1 rounded">{h.running_style_label}</span>
            </div>

            {/* バー */}
            <div className="mt-1 bg-slate-200 rounded-full h-1.5">
              <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${h.prob * 100}%` }} />
            </div>

            {/* Expanded */}
            {expandedRow === h.horse_name && (
              <div className="mt-2 pt-2 border-t border-slate-100 text-[10px] space-y-1.5">
                <div className="grid grid-cols-2 gap-1">
                  <div><span className="text-slate-400">調教師:</span> {h.trainer && h.trainer !== 'nan' ? h.trainer : '-'}</div>
                  <div><span className="text-slate-400">馬体重:</span> {h.weight && h.weight !== 'nan' ? h.weight + 'kg' : '-'}</div>
                  <div><span className="text-slate-400">母父:</span> {h.dam_sire && h.dam_sire !== 'nan' ? h.dam_sire : '-'}</div>
                  <div><span className="text-slate-400">能力値:</span> {h.raw.speed_figure || '-'}</div>
                </div>
                <div className="space-y-0.5">
                  {WEIGHT_CATEGORIES.map(cat => {
                    const w = (h.scores[cat.key] || 0) * (weights[cat.key] ?? 1)
                    return (
                      <div key={cat.key} className="flex items-center gap-1">
                        <span className="w-10 text-slate-400">{cat.label}</span>
                        <div className="flex-1 bg-slate-200 rounded-full h-1"><div className="bg-blue-500 h-1 rounded-full" style={{ width: `${Math.min(w / 2, 100)}%` }} /></div>
                        <span className="w-5 text-right font-mono">{w.toFixed(0)}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
