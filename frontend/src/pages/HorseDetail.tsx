import { useMemo, useState } from 'react'

const FIN_BG: Record<number, string> = { 1: 'bg-red-600 text-white', 2: 'bg-blue-600 text-white', 3: 'bg-green-600 text-white' }
const Fin = ({v}:{v:number|string}) => { const n=typeof v==='number'?v:parseInt(String(v)); if(!n||isNaN(n)) return <span className="text-slate-400">-</span>; return <span className={`w-6 h-6 rounded-full ${FIN_BG[n]||'bg-slate-200 text-slate-600'} text-xs font-bold inline-flex items-center justify-center`}>{n}</span> }

interface Props {
  horse: any
  weights: Record<string, number>
  onBack: () => void
  weightCategories: { key: string; label: string }[]
}

const DETAIL_TABS = [
  { id: 'profile', label: 'プロフィール' },
  { id: 'results', label: '競走成績' },
  { id: 'pedigree', label: '血統' },
  { id: 'analysis', label: 'AI分析' },
]

export default function HorseDetail({ horse: h, weights, onBack, weightCategories }: Props) {
  const [tab, setTab] = useState('profile')

  const scoreItems = useMemo(() =>
    weightCategories.map(c => ({
      ...c,
      raw: h.scores[c.key] || 0,
      weighted: (h.scores[c.key] || 0) * (weights[c.key] ?? 1),
    })).sort((a, b) => b.weighted - a.weighted)
  , [h, weights, weightCategories])

  return (
    <div>
      {/* Back Button */}
      <button onClick={onBack} className="text-blue-600 text-sm mb-3 hover:underline">← 出馬表に戻る</button>

      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-4">
        <div className="bg-gradient-to-r from-slate-800 to-blue-900 text-white p-4">
          <div className="flex items-center gap-3">
            {/* Horse Icon (large waku badge) */}
            <div className={`w-16 h-16 rounded-xl flex flex-col items-center justify-center text-lg font-bold
              ${({1:'bg-white text-slate-800',2:'bg-gray-700',3:'bg-red-500',4:'bg-blue-500',5:'bg-yellow-400 text-gray-900',6:'bg-green-500',7:'bg-orange-400',8:'bg-pink-400'} as Record<number,string>)[h.post_position as number] || 'bg-slate-400'}`}>
              <div className="text-xs opacity-70">{h.post_position}枠</div>
              <div className="text-2xl">{h.gate_number}</div>
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold">{h.horse_name}</h2>
              <div className="text-blue-200 text-sm">
                {h.english_name && h.english_name !== 'nan' && <span>{h.english_name} | </span>}
                {h.sex}{h.age} {h.coat_color && h.coat_color !== 'nan' ? h.coat_color : ''}
              </div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold font-mono">{(h.prob * 100).toFixed(1)}%</div>
              <div className="text-blue-200 text-xs">AI勝率予測</div>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 sm:grid-cols-5 border-t border-slate-100 text-center text-xs">
          <div className="p-2 border-r border-slate-100">
            <div className="text-slate-400">オッズ</div>
            <div className="font-bold text-lg font-mono">{h.raw.win_odds || '-'}</div>
            {h.raw.popularity > 0 && <div className={`text-[10px] font-bold ${h.raw.popularity <= 3 ? 'text-red-600' : 'text-slate-500'}`}>{h.raw.popularity}人気</div>}
          </div>
          <div className="p-2 border-r border-slate-100">
            <div className="text-slate-400">成績</div>
            <div className="font-bold text-sm">{h.career}</div>
          </div>
          <div className="p-2 border-r border-slate-100">
            <div className="text-slate-400">能力値</div>
            <div className="font-bold text-lg font-mono text-blue-700">{h.raw.speed_figure || '-'}</div>
          </div>
          <div className="p-2 border-r border-slate-100 hidden sm:block">
            <div className="text-slate-400">上がり3F</div>
            <div className="font-bold text-lg font-mono">{h.raw.best_last3f || '-'}</div>
          </div>
          <div className="p-2">
            <div className="text-slate-400">脚質</div>
            <div className="font-bold text-sm">{h.running_style_label}</div>
          </div>
        </div>
      </div>

      {/* Detail Tabs */}
      <div className="flex gap-1 mb-3 overflow-x-auto">
        {DETAIL_TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-xs font-medium whitespace-nowrap border ${tab === t.id ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-600 border-slate-200'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">

        {/* ── Profile ── */}
        {tab === 'profile' && (
          <div className="p-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="space-y-2">
                <div><span className="text-slate-400 text-xs block">騎手</span><span className="font-medium">{h.jockey}</span>{h.raw.jockey_g1 > 0 && <span className="text-xs text-slate-400 ml-1">G1: {h.raw.jockey_g1}勝</span>}</div>
                <div><span className="text-slate-400 text-xs block">調教師</span><span className="font-medium">{h.trainer && h.trainer !== 'nan' ? h.trainer : '-'}</span></div>
                <div><span className="text-slate-400 text-xs block">馬主</span><span>{h.owner && h.owner !== 'nan' ? h.owner : '-'}</span></div>
                <div><span className="text-slate-400 text-xs block">馬体重</span><span>{h.weight && h.weight !== 'nan' ? h.weight + 'kg' : '-'}</span></div>
              </div>
              <div className="space-y-2">
                <div><span className="text-slate-400 text-xs block">父</span><span className="font-medium">{h.sire && h.sire !== 'nan' ? h.sire : '-'}</span></div>
                <div><span className="text-slate-400 text-xs block">母父</span><span>{h.dam_sire && h.dam_sire !== 'nan' ? h.dam_sire : '-'}</span></div>
                <div><span className="text-slate-400 text-xs block">獲得賞金</span><span>{h.total_prize && h.total_prize !== 'nan' && h.total_prize !== '' ? Number(h.total_prize).toLocaleString() + '万円' : '-'}</span></div>
                <div><span className="text-slate-400 text-xs block">G1勝利</span><span className="font-bold">{h.raw.g1_wins || 0}勝</span> <span className="text-slate-400 text-xs">(複勝 {h.raw.g1_place || 0}回)</span></div>
              </div>
            </div>

            {/* YouTube / News Scores */}
            <div className="mt-4 pt-3 border-t border-slate-100">
              <div className="text-xs text-slate-400 mb-2">世論スコア</div>
              <div className="flex gap-4 text-sm">
                <div>YouTube: <span className="font-bold text-blue-700">{h.raw.yt_score || 0}</span></div>
                <div>ニュース: <span className="font-bold text-purple-700">{h.raw.news_score || 0}</span></div>
                <div>調教評価: <span className="font-bold text-emerald-700">{h.raw.training || 3}/5</span></div>
              </div>
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {tab === 'results' && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
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
                    <td className="px-2 py-1.5 text-slate-500">{r.date}</td>
                    <td className="px-2 py-1.5">{r.venue}</td>
                    <td className="px-2 py-1.5 font-medium">{r.race} {r.grade && <span className="text-red-500 text-[10px]">{r.grade}</span>}</td>
                    <td className="px-2 py-1.5 text-right font-mono">{r.dist}m</td>
                    <td className="px-2 py-1.5 text-center"><Fin v={r.finish} /></td>
                    <td className="px-2 py-1.5 text-right font-mono text-slate-500">{r.time && r.time !== 'nan' && r.time !== '' ? r.time : '-'}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-blue-600">{r.last3f && r.last3f !== 'nan' && r.last3f !== '' ? r.last3f : '-'}</td>
                    <td className="px-2 py-1.5 text-slate-400">{r.passing && r.passing !== 'nan' && r.passing !== '' ? r.passing : '-'}</td>
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
            <div className="flex items-center justify-center">
              <div className="border border-slate-200 rounded-lg overflow-hidden text-sm">
                <div className="flex">
                  <div className="bg-blue-50 border-r border-slate-200 p-3 w-36 flex items-center justify-center font-bold text-blue-800">
                    {h.sire && h.sire !== 'nan' ? h.sire : '父'}
                  </div>
                  <div className="flex flex-col">
                    <div className="bg-slate-50 border-b border-slate-200 p-2 px-4 text-xs text-slate-500">父の父</div>
                    <div className="bg-slate-50 p-2 px-4 text-xs text-slate-500">父の母</div>
                  </div>
                </div>
                <div className="flex border-t border-slate-200">
                  <div className="bg-pink-50 border-r border-slate-200 p-3 w-36 flex items-center justify-center font-bold text-pink-800">
                    母
                  </div>
                  <div className="flex flex-col">
                    <div className="bg-slate-50 border-b border-slate-200 p-2 px-4 text-xs font-medium">{h.dam_sire && h.dam_sire !== 'nan' ? h.dam_sire : '母の父'}</div>
                    <div className="bg-slate-50 p-2 px-4 text-xs text-slate-500">母の母</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── AI Analysis ── */}
        {tab === 'analysis' && (
          <div className="p-4">
            <div className="text-xs text-slate-400 mb-3">AIスコア内訳（ウェイト適用後）</div>
            <div className="space-y-2">
              {scoreItems.map(s => (
                <div key={s.key} className="flex items-center gap-2 text-sm">
                  <span className="w-16 text-slate-500 text-xs shrink-0">{s.label}</span>
                  <div className="flex-1 bg-slate-200 rounded-full h-2.5">
                    <div className="bg-blue-600 h-2.5 rounded-full transition-all" style={{ width: `${Math.min(s.weighted / 2, 100)}%` }} />
                  </div>
                  <span className="w-10 text-right font-mono text-xs text-slate-600">{s.weighted.toFixed(0)}</span>
                  {(weights[s.key] ?? 1) !== 1 && <span className="text-[10px] text-blue-600">×{(weights[s.key] ?? 1).toFixed(1)}</span>}
                </div>
              ))}
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 text-right">
              <span className="text-slate-400 text-xs">合計スコア: </span>
              <span className="font-mono font-bold text-lg">{h.total.toFixed(0)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
