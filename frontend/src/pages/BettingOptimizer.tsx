import { useState, useEffect } from 'react'
import type { BettingResponse, PredictionResponse } from '../types'

const BET_TYPES = [
  { id: 'win', label: '単勝' },
  { id: 'place', label: '複勝' },
  { id: 'quinella', label: '馬連' },
  { id: 'wide', label: 'ワイド' },
  { id: 'trio', label: '三連複' },
]

const MODES = [
  { id: 'auto', label: 'AI自動', icon: '🤖' },
  { id: 'pivot', label: '軸馬流し', icon: '🎯' },
  { id: 'formation', label: 'フォーメーション', icon: '📐' },
  { id: 'box', label: 'ボックス', icon: '📦' },
]

type Mode = 'auto' | 'pivot' | 'formation' | 'box'

export default function BettingOptimizer() {
  const [mode, setMode] = useState<Mode>('auto')
  const [horses, setHorses] = useState<string[]>([])
  const [budget, setBudget] = useState(10000)
  const [risk, setRisk] = useState<'low' | 'medium' | 'high'>('medium')
  const [betTypes, setBetTypes] = useState(['win', 'quinella', 'wide', 'trio'])
  const [pivotHorses, setPivotHorses] = useState<string[]>([])
  const [formation, setFormation] = useState<{ first: string[]; second: string[]; third: string[] }>({ first: [], second: [], third: [] })
  const [boxHorses, setBoxHorses] = useState<string[]>([])
  const [boxBetType, setBoxBetType] = useState('trio')
  const [result, setResult] = useState<BettingResponse | null>(null)
  const [formationResult, setFormationResult] = useState<any>(null)
  const [boxResult, setBoxResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  // 収支シミュレーション
  const [simFirst, setSimFirst] = useState('')
  const [simSecond, setSimSecond] = useState('')
  const [simThird, setSimThird] = useState('')
  const [simResult, setSimResult] = useState<any>(null)

  // 馬名リスト取得
  useEffect(() => {
    fetch('/api/predictions').then(r => r.json()).then((d: PredictionResponse) => {
      setHorses(d.predictions.map(p => p.horse_name))
    }).catch(() => {})
  }, [])

  const toggleList = (list: string[], item: string) =>
    list.includes(item) ? list.filter(x => x !== item) : [...list, item]

  // ── AI自動 / 軸馬流し ──
  const runOptimize = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/betting/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({
          budget, risk_level: risk, bet_types: betTypes,
          odds: {}, excluded_horses: [],
          pivot_horses: mode === 'pivot' ? pivotHorses : [],
        }),
      })
      setResult(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  // ── フォーメーション ──
  const runFormation = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/betting/formation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ bet_type: 'trio', ...formation, amount_per_bet: 100 }),
      })
      setFormationResult(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  // ── ボックス ──
  const runBox = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/betting/box', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ bet_type: boxBetType, horses: boxHorses, amount_per_bet: 100 }),
      })
      setBoxResult(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  // ── 収支シミュレーション ──
  const runSimulate = async () => {
    if (!result || !simFirst) return
    const res = await fetch('/api/betting/simulate-result', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        bets: result.recommendations.map(r => ({ type: r.bet_type, selection: r.selection, amount: r.amount, odds: r.odds })),
        result_first: simFirst, result_second: simSecond, result_third: simThird,
      }),
    })
    setSimResult(await res.json())
  }

  // ── 馬選択ボタン群 ──
  const HorsePicker = ({ selected, onToggle, label }: { selected: string[]; onToggle: (h: string) => void; label: string }) => (
    <div className="mb-3">
      <div className="text-xs text-slate-500 mb-1 font-medium">{label}</div>
      <div className="flex flex-wrap gap-1">
        {horses.map(h => (
          <button key={h} onClick={() => onToggle(h)}
            className={`px-2 py-1 rounded text-xs font-medium border transition-colors ${
              selected.includes(h) ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-100'}`}>
            {h.slice(0, 5)}
          </button>
        ))}
      </div>
    </div>
  )

  return (
    <div>
      {/* Mode tabs */}
      <div className="flex gap-1 mb-4 overflow-x-auto">
        {MODES.map(m => (
          <button key={m.id} onClick={() => setMode(m.id as Mode)}
            className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap border ${
              mode === m.id ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}>
            <span className="mr-1">{m.icon}</span>{m.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* ── 設定パネル ── */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200 space-y-4">

          {/* AI自動モード */}
          {mode === 'auto' && <>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">投資金額</label>
              <input type="number" step={1000} min={1000} value={budget} onChange={e => setBudget(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-base font-mono focus:border-blue-500 focus:outline-none" />
              <div className="flex gap-1.5 mt-1.5">
                {[3000, 5000, 10000, 30000, 50000].map(v => (
                  <button key={v} onClick={() => setBudget(v)}
                    className={`px-2 py-1 rounded text-xs border ${budget === v ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-500 border-slate-300'}`}>
                    {v >= 10000 ? `${v / 10000}万` : `${v / 1000}千`}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">リスク許容度</label>
              <div className="flex gap-1.5">
                {([['low', '低（堅実）'], ['medium', '中'], ['high', '高（大穴）']] as const).map(([v, l]) => (
                  <button key={v} onClick={() => setRisk(v)}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium border ${risk === v ? 'bg-blue-700 text-white border-blue-700' : 'bg-white text-slate-600 border-slate-300'}`}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">馬券種別</label>
              <div className="flex flex-wrap gap-1.5">
                {BET_TYPES.map(bt => (
                  <button key={bt.id} onClick={() => setBetTypes(toggleList(betTypes, bt.id))}
                    className={`px-3 py-1.5 rounded text-xs font-medium border ${betTypes.includes(bt.id) ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-300'}`}>
                    {bt.label}
                  </button>
                ))}
              </div>
            </div>
            <button onClick={runOptimize} disabled={loading}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white py-2.5 rounded-lg font-bold text-sm">
              {loading ? '計算中...' : '買い目を最適化'}
            </button>
          </>}

          {/* 軸馬流しモード */}
          {mode === 'pivot' && <>
            <HorsePicker selected={pivotHorses} onToggle={h => setPivotHorses(toggleList(pivotHorses, h))}
              label={`軸馬を選択（${pivotHorses.length}/2頭）`} />
            <div>
              <label className="text-xs text-slate-500 mb-1 block">投資金額</label>
              <input type="number" step={1000} min={1000} value={budget} onChange={e => setBudget(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 font-mono focus:border-blue-500 focus:outline-none" />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">馬券種別</label>
              <div className="flex flex-wrap gap-1.5">
                {BET_TYPES.filter(b => ['quinella', 'wide', 'trio'].includes(b.id)).map(bt => (
                  <button key={bt.id} onClick={() => setBetTypes(toggleList(betTypes, bt.id))}
                    className={`px-3 py-1.5 rounded text-xs font-medium border ${betTypes.includes(bt.id) ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-300'}`}>
                    {bt.label}
                  </button>
                ))}
              </div>
            </div>
            <button onClick={runOptimize} disabled={loading || pivotHorses.length === 0}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white py-2.5 rounded-lg font-bold text-sm">
              {loading ? '計算中...' : `${pivotHorses.length}軸で流し買い生成`}
            </button>
          </>}

          {/* フォーメーションモード */}
          {mode === 'formation' && <>
            <HorsePicker selected={formation.first} onToggle={h => setFormation({ ...formation, first: toggleList(formation.first, h) })}
              label="1着候補" />
            <HorsePicker selected={formation.second} onToggle={h => setFormation({ ...formation, second: toggleList(formation.second, h) })}
              label="2着候補" />
            <HorsePicker selected={formation.third} onToggle={h => setFormation({ ...formation, third: toggleList(formation.third, h) })}
              label="3着候補" />
            <button onClick={runFormation} disabled={loading || formation.first.length === 0}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white py-2.5 rounded-lg font-bold text-sm">
              {loading ? '計算中...' : '三連複フォーメーション計算'}
            </button>
          </>}

          {/* ボックスモード */}
          {mode === 'box' && <>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">馬券種別</label>
              <div className="flex gap-1.5">
                {['quinella', 'wide', 'trio'].map(bt => (
                  <button key={bt} onClick={() => setBoxBetType(bt)}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium border ${boxBetType === bt ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-300'}`}>
                    {{ quinella: '馬連', wide: 'ワイド', trio: '三連複' }[bt]}
                  </button>
                ))}
              </div>
            </div>
            <HorsePicker selected={boxHorses} onToggle={h => setBoxHorses(toggleList(boxHorses, h))}
              label={`BOX馬を選択（${boxHorses.length}頭）`} />
            <button onClick={runBox} disabled={loading || boxHorses.length < (boxBetType === 'trio' ? 3 : 2)}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white py-2.5 rounded-lg font-bold text-sm">
              {loading ? '計算中...' : 'ボックス計算'}
            </button>
          </>}
        </div>

        {/* ── 結果パネル ── */}
        <div className="lg:col-span-2 space-y-4">

          {/* AI自動 / 軸馬 結果 */}
          {(mode === 'auto' || mode === 'pivot') && result && <>
            {/* サマリー */}
            <div className="grid grid-cols-3 gap-2">
              {[
                ['合計投資', `${result.total_budget.toLocaleString()}円`, ''],
                ['期待回収', `${result.expected_return.toLocaleString()}円`, result.expected_return > result.total_budget ? 'text-emerald-600' : 'text-red-600'],
                ['回収率', `${(result.expected_roi * 100).toFixed(1)}%`, result.expected_roi >= 1 ? 'text-emerald-600' : 'text-red-600'],
              ].map(([label, val, color]) => (
                <div key={label as string} className="bg-white rounded-lg p-2 sm:p-3 text-center shadow-sm border border-slate-200">
                  <div className="text-slate-500 text-xs">{label}</div>
                  <div className={`text-base sm:text-xl font-bold font-mono ${color}`}>{val}</div>
                </div>
              ))}
            </div>

            {/* 買い目リスト */}
            <div className="space-y-2">
              {result.recommendations.map((r, i) => (
                <div key={i} className="bg-white rounded-lg border border-slate-200 p-3 flex flex-wrap items-center gap-2 sm:gap-4">
                  <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-xs font-medium">{r.bet_type_ja}</span>
                  <span className="font-medium text-slate-800 text-sm flex-1 min-w-0 truncate">{r.selection}</span>
                  <span className="font-mono font-bold text-emerald-600 text-sm">{r.amount.toLocaleString()}円</span>
                  <span className="font-mono text-slate-500 text-xs">{r.odds}倍</span>
                  <span className="font-mono text-slate-500 text-xs">的中{(r.hit_prob * 100).toFixed(1)}%</span>
                  <span className={`font-mono text-xs font-bold ${r.expected_value >= 1 ? 'text-emerald-600' : 'text-slate-400'}`}>
                    EV{r.expected_value.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>

            {/* 収支シミュレーション */}
            <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
              <h3 className="text-sm font-bold text-slate-700 mb-2">収支シミュレーション</h3>
              <p className="text-xs text-slate-400 mb-2">着順を入力すると的中馬券と払い戻しを計算</p>
              <div className="flex flex-wrap gap-2 mb-3">
                {['1着', '2着', '3着'].map((label, idx) => (
                  <div key={label} className="flex-1 min-w-[100px]">
                    <label className="text-xs text-slate-500">{label}</label>
                    <select className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm bg-white"
                      value={[simFirst, simSecond, simThird][idx]}
                      onChange={e => [setSimFirst, setSimSecond, setSimThird][idx](e.target.value)}>
                      <option value="">選択</option>
                      {horses.map(h => <option key={h} value={h}>{h}</option>)}
                    </select>
                  </div>
                ))}
                <button onClick={runSimulate}
                  className="bg-slate-700 hover:bg-slate-800 text-white px-4 py-1.5 rounded text-sm self-end">
                  計算
                </button>
              </div>
              {simResult && (
                <div className={`p-3 rounded-lg text-sm ${simResult.profit > 0 ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'}`}>
                  <div className="flex flex-wrap gap-4 font-mono">
                    <div>投資: {simResult.total_invested?.toLocaleString()}円</div>
                    <div>回収: <strong className={simResult.profit > 0 ? 'text-emerald-700' : 'text-red-700'}>{simResult.total_return?.toLocaleString()}円</strong></div>
                    <div>収支: <strong className={simResult.profit > 0 ? 'text-emerald-700' : 'text-red-700'}>{simResult.profit > 0 ? '+' : ''}{simResult.profit?.toLocaleString()}円</strong></div>
                  </div>
                  {simResult.hit_bets?.length > 0 && (
                    <div className="mt-2 text-xs text-slate-600">
                      的中: {simResult.hit_bets.map((b: any) => `${b.selection} (${b.payout?.toLocaleString()}円)`).join(' / ')}
                    </div>
                  )}
                  {simResult.hit_bets?.length === 0 && <div className="mt-1 text-xs text-red-600">的中なし</div>}
                </div>
              )}
            </div>
          </>}

          {/* フォーメーション結果 */}
          {mode === 'formation' && formationResult && (
            <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
              <div className="flex gap-4 mb-3 text-sm font-bold">
                <span>三連複フォーメーション</span>
                <span className="text-blue-700">{formationResult.total_bets}点</span>
                <span className="text-emerald-600">{formationResult.total_cost?.toLocaleString()}円</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {formationResult.combinations?.map((c: any, i: number) => (
                  <div key={i} className="bg-slate-50 rounded px-2 py-1 text-xs text-slate-700 font-mono">{c.selection}</div>
                ))}
              </div>
            </div>
          )}

          {/* ボックス結果 */}
          {mode === 'box' && boxResult && (
            <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
              <div className="flex gap-4 mb-3 text-sm font-bold">
                <span>{{ quinella: '馬連', wide: 'ワイド', trio: '三連複' }[boxBetType]} BOX</span>
                <span className="text-blue-700">{boxResult.total_bets}点</span>
                <span className="text-emerald-600">{boxResult.total_cost?.toLocaleString()}円</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {boxResult.combinations?.map((c: any, i: number) => (
                  <div key={i} className="bg-slate-50 rounded px-2 py-1 text-xs text-slate-700 font-mono">{c.selection}</div>
                ))}
              </div>
            </div>
          )}

          {/* 未実行時メッセージ */}
          {!result && !formationResult && !boxResult && (
            <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
              設定を入力して計算ボタンを押してください
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
