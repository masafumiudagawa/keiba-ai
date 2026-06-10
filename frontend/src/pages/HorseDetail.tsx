import { useMemo, useState } from 'react'

const FIN_BG: Record<number, string> = { 1: 'bg-red-600 text-white', 2: 'bg-blue-600 text-white', 3: 'bg-green-600 text-white' }
const Fin = ({v}:{v:number|string}) => { const n=typeof v==='number'?v:parseInt(String(v)); if(!n||isNaN(n)) return <span className="text-slate-400">-</span>; return <span className={`w-6 h-6 rounded-full ${FIN_BG[n]||'bg-slate-200 text-slate-600'} text-xs font-bold inline-flex items-center justify-center`}>{n}</span> }

interface Props { horse: any; weights: Record<string, number>; onBack: () => void; weightCategories: { key: string; label: string }[] }

const TABS = [
  { id: 'profile', label: 'プロフィール' },
  { id: 'results', label: '競走成績' },
  { id: 'pedigree', label: '血統' },
  { id: 'analysis', label: 'AI分析' },
]

const v = (x: any) => x && x !== 'nan' && x !== '' && x !== 'undefined' ? x : null

export default function HorseDetail({ horse: h, weights, onBack, weightCategories }: Props) {
  const [tab, setTab] = useState('profile')

  const scoreItems = useMemo(() =>
    weightCategories.map(c => ({
      ...c, raw: h.scores[c.key] || 0,
      weighted: (h.scores[c.key] || 0) * (weights[c.key] ?? 1),
    })).sort((a, b) => b.weighted - a.weighted)
  , [h, weights, weightCategories])

  const wakuColor = ({1:'bg-white text-slate-800 border-2 border-slate-300',2:'bg-gray-800',3:'bg-red-600',4:'bg-blue-600',5:'bg-yellow-400 text-gray-900',6:'bg-green-600',7:'bg-orange-500',8:'bg-pink-500'} as Record<number,string>)[h.post_position as number] || 'bg-slate-400'

  return (
    <div>
      <button onClick={onBack} className="text-blue-600 text-sm mb-3 hover:underline">← 出馬表に戻る</button>

      {/* ═══ Header ═══ */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-4">
        <div className="bg-gradient-to-r from-slate-800 to-blue-900 text-white p-4">
          <div className="flex items-center gap-4">
            {/* Large Waku Badge = 馬のビジュアル代替 */}
            <div className={`w-20 h-20 sm:w-24 sm:h-24 rounded-2xl flex flex-col items-center justify-center text-white shadow-lg ${wakuColor}`}>
              <div className="text-[10px] opacity-70">{h.post_position}枠</div>
              <div className="text-3xl sm:text-4xl font-black">{h.gate_number}</div>
              <div className="text-[9px] opacity-60">{v(h.coat_color) || ''}</div>
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-xl sm:text-2xl font-bold truncate">{h.horse_name}</h2>
              <div className="text-blue-200 text-sm">
                {v(h.english_name) && <span>{h.english_name}</span>}
              </div>
              <div className="text-blue-200 text-xs mt-0.5">
                {h.sex}{h.age} | {v(h.coat_color) || '-'} | {h.running_style_label}
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-3xl sm:text-4xl font-bold font-mono">{(h.prob * 100).toFixed(1)}<span className="text-lg">%</span></div>
              <div className="text-blue-300 text-[10px]">AI勝率</div>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 sm:grid-cols-6 text-center text-xs border-t border-slate-100">
          {[
            ['オッズ', h.raw.win_odds ? `${h.raw.win_odds}倍` : '-', h.raw.popularity > 0 ? `${h.raw.popularity}人気` : ''],
            ['成績', h.career, `G1: ${h.raw.g1_wins || 0}勝`],
            ['能力値', h.raw.speed_figure || '-', ''],
            ['上がり3F', h.raw.best_last3f || '-', ''],
            ['調教', `${h.raw.training || 3}/5`, ''],
            ['賞金', v(h.total_prize) ? `${Number(h.total_prize).toLocaleString()}万` : '-', ''],
          ].map(([label, val, sub], i) => (
            <div key={i} className="p-2 border-r border-b border-slate-100 last:border-r-0">
              <div className="text-slate-400 text-[10px]">{label}</div>
              <div className="font-bold text-sm font-mono">{val}</div>
              {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
            </div>
          ))}
        </div>
      </div>

      {/* ═══ Tabs ═══ */}
      <div className="flex gap-1 mb-3 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-xs font-medium whitespace-nowrap border ${tab === t.id ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-600 border-slate-200'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">

        {/* ── Profile ── */}
        {tab === 'profile' && (
          <div className="p-4">
            {/* 基本情報を明確なラベル付きで */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <h3 className="text-xs font-bold text-slate-500 mb-2 border-b border-slate-100 pb-1">基本情報</h3>
                <dl className="space-y-1.5 text-sm">
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">馬名</dt><dd className="font-bold">{h.horse_name}</dd></div>
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">性齢</dt><dd>{h.sex}{h.age}</dd></div>
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">毛色</dt><dd>{v(h.coat_color) || '-'}</dd></div>
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">脚質</dt><dd>{h.running_style_label}</dd></div>
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">馬体重</dt><dd>{v(h.weight) ? h.weight + 'kg' : '-'}</dd></div>
                </dl>
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-500 mb-2 border-b border-slate-100 pb-1">関係者</h3>
                <dl className="space-y-1.5 text-sm">
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">騎手</dt><dd className="font-medium">{h.jockey}{h.raw.jockey_g1 > 0 && <span className="text-xs text-slate-400 ml-1">(G1: {h.raw.jockey_g1}勝)</span>}</dd></div>
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">調教師</dt><dd>{v(h.trainer) || '-'}</dd></div>
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">馬主</dt><dd>{v(h.owner) || '-'}</dd></div>
                  <div className="flex"><dt className="text-slate-400 w-20 shrink-0">獲得賞金</dt><dd>{v(h.total_prize) ? Number(h.total_prize).toLocaleString() + '万円' : '-'}</dd></div>
                </dl>
              </div>
            </div>

            {/* 血統（プロフィール内にも簡易表示） */}
            <div className="mt-4 pt-3 border-t border-slate-100">
              <h3 className="text-xs font-bold text-slate-500 mb-2">血統</h3>
              <div className="flex gap-6 text-sm">
                <div><span className="text-slate-400 text-xs">父: </span><span className="font-bold">{v(h.sire) || '-'}</span></div>
                <div><span className="text-slate-400 text-xs">母の父: </span><span className="font-bold">{v(h.dam_sire) || '-'}</span></div>
              </div>
            </div>

            {/* 世論 */}
            <div className="mt-4 pt-3 border-t border-slate-100">
              <h3 className="text-xs font-bold text-slate-500 mb-2">世論・調教評価</h3>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-blue-50 rounded-lg p-2">
                  <div className="text-[10px] text-blue-400">YouTube</div>
                  <div className="font-bold text-blue-700 text-lg">{h.raw.yt_score || 0}</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-2">
                  <div className="text-[10px] text-purple-400">ニュース</div>
                  <div className="font-bold text-purple-700 text-lg">{h.raw.news_score || 0}</div>
                </div>
                <div className="bg-emerald-50 rounded-lg p-2">
                  <div className="text-[10px] text-emerald-400">追い切り</div>
                  <div className="font-bold text-emerald-700 text-lg">{h.raw.training || 3}<span className="text-xs font-normal">/5</span></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {tab === 'results' && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[500px]">
              <thead>
                <tr className="bg-slate-100 text-slate-600">
                  <th className="px-2 py-2 text-left">日付</th>
                  <th className="px-2 py-2 text-left">開催</th>
                  <th className="px-2 py-2 text-left">レース</th>
                  <th className="px-2 py-2 text-right">距離</th>
                  <th className="px-2 py-2 text-center">着順</th>
                  <th className="px-2 py-2 text-right">タイム</th>
                  <th className="px-2 py-2 text-right">上がり</th>
                  <th className="px-2 py-2 text-left">通過</th>
                </tr>
              </thead>
              <tbody>
                {h.recent_5?.map((r: any, i: number) => (
                  <tr key={i} className="border-t border-slate-100 hover:bg-blue-50">
                    <td className="px-2 py-2 text-slate-500">{r.date}</td>
                    <td className="px-2 py-2">{r.venue}</td>
                    <td className="px-2 py-2 font-medium">{r.race} {r.grade && <span className="text-red-500 text-[10px] ml-0.5">{r.grade}</span>}</td>
                    <td className="px-2 py-2 text-right font-mono">{r.dist}m</td>
                    <td className="px-2 py-2 text-center"><Fin v={r.finish} /></td>
                    <td className="px-2 py-2 text-right font-mono text-slate-500">{v(r.time) || '-'}</td>
                    <td className="px-2 py-2 text-right font-mono text-blue-600 font-bold">{v(r.last3f) || '-'}</td>
                    <td className="px-2 py-2 text-slate-400">{v(r.passing) || '-'}</td>
                  </tr>
                ))}
                {(!h.recent_5 || h.recent_5.length === 0) && (
                  <tr><td colSpan={8} className="px-2 py-8 text-center text-slate-400">競走成績データなし</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Pedigree ── */}
        {tab === 'pedigree' && (
          <div className="p-4">
            <div className="max-w-md mx-auto">
              {/* 3代血統表 */}
              <div className="border border-slate-200 rounded-lg overflow-hidden text-sm">
                {/* 父系 */}
                <div className="flex border-b border-slate-200">
                  <div className="bg-blue-50 border-r border-slate-200 p-3 w-32 sm:w-40 flex flex-col items-center justify-center">
                    <div className="text-[10px] text-blue-400">父</div>
                    <div className="font-bold text-blue-800 text-center">{v(h.sire) || '-'}</div>
                  </div>
                  <div className="flex-1 flex flex-col text-xs">
                    <div className="border-b border-slate-100 p-2 px-3 text-slate-400 bg-slate-50">
                      <span className="text-[9px] text-slate-300">父の父</span>
                    </div>
                    <div className="p-2 px-3 text-slate-400 bg-slate-50">
                      <span className="text-[9px] text-slate-300">父の母</span>
                    </div>
                  </div>
                </div>
                {/* 母系 */}
                <div className="flex">
                  <div className="bg-pink-50 border-r border-slate-200 p-3 w-32 sm:w-40 flex flex-col items-center justify-center">
                    <div className="text-[10px] text-pink-400">母</div>
                    <div className="font-bold text-pink-800 text-center">-</div>
                  </div>
                  <div className="flex-1 flex flex-col text-xs">
                    <div className="border-b border-slate-100 p-2 px-3 bg-slate-50">
                      <span className="text-[9px] text-slate-300">母の父（BMS）</span>
                      <div className="font-medium text-slate-700">{v(h.dam_sire) || '-'}</div>
                    </div>
                    <div className="p-2 px-3 text-slate-400 bg-slate-50">
                      <span className="text-[9px] text-slate-300">母の母</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-3 text-center text-[10px] text-slate-400">※ 父・母の父のみ表示（3代以降は未取得）</div>
            </div>
          </div>
        )}

        {/* ── AI Analysis ── */}
        {tab === 'analysis' && (
          <div className="p-4">
            <div className="text-xs text-slate-400 mb-3">AIスコア内訳（ウェイト適用後 / 大きい順）</div>
            <div className="space-y-2">
              {scoreItems.map(s => (
                <div key={s.key} className="flex items-center gap-2">
                  <span className="w-14 text-slate-500 text-xs shrink-0">{s.label}</span>
                  <div className="flex-1 bg-slate-100 rounded-full h-3">
                    <div className="bg-blue-600 h-3 rounded-full transition-all" style={{ width: `${Math.min(s.weighted / 2, 100)}%` }} />
                  </div>
                  <span className="w-10 text-right font-mono text-xs font-bold text-slate-700">{s.weighted.toFixed(0)}</span>
                  {(weights[s.key] ?? 1) !== 1 && <span className="text-[10px] text-blue-600 w-8">×{(weights[s.key] ?? 1).toFixed(1)}</span>}
                </div>
              ))}
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex justify-between items-center">
              <span className="text-slate-400 text-xs">合計スコア</span>
              <span className="font-mono font-bold text-xl text-blue-800">{h.total.toFixed(0)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
