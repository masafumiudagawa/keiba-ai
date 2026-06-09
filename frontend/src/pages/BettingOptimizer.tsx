import { useState, useEffect } from 'react'
import type { BettingResponse, PredictionResponse } from '../types'

const BET_TYPES = [
  { id: 'win', label: '単勝' }, { id: 'place', label: '複勝' },
  { id: 'exacta', label: '馬単' }, { id: 'quinella', label: '馬連' },
  { id: 'wide', label: 'ワイド' }, { id: 'trio', label: '三連複' },
  { id: 'trifecta', label: '三連単' },
]

const MODES = [
  { id: 'compare', label: '3パターン比較', icon: '📊' },
  { id: 'auto', label: 'AI最適化', icon: '🤖' },
  { id: 'pivot', label: '軸馬流し', icon: '🎯' },
  { id: 'formation', label: 'フォーメーション', icon: '📐' },
  { id: 'box', label: 'ボックス', icon: '📦' },
] as const
type Mode = typeof MODES[number]['id']

export default function BettingOptimizer({ raceId: _raceId }: { raceId: string }) {
  const [mode, setMode] = useState<Mode>('compare')
  const [horses, setHorses] = useState<string[]>([])
  const [budget, setBudget] = useState(10000)
  const [risk, setRisk] = useState<'low' | 'medium' | 'high'>('medium')
  const [betTypes, setBetTypes] = useState(['win', 'quinella', 'wide', 'trio'])
  const [pivotHorses, setPivotHorses] = useState<string[]>([])
  const [formation, setFormation] = useState<{first:string[];second:string[];third:string[]}>({first:[],second:[],third:[]})
  const [boxHorses, setBoxHorses] = useState<string[]>([])
  const [boxBetType, setBoxBetType] = useState('trio')
  const [result, setResult] = useState<BettingResponse | null>(null)
  const [compareResult, setCompareResult] = useState<any>(null)
  const [formationResult, setFormationResult] = useState<any>(null)
  const [boxResult, setBoxResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [simFirst, setSimFirst] = useState(''); const [simSecond, setSimSecond] = useState(''); const [simThird, setSimThird] = useState('')
  const [simResult, setSimResult] = useState<any>(null)

  useEffect(() => {
    fetch('/api/predictions').then(r=>r.json()).then((d:PredictionResponse)=>{
      setHorses(d.predictions.map(p=>p.horse_name))
    }).catch(()=>{})
  }, [])

  const toggle = (list:string[], item:string) => list.includes(item) ? list.filter(x=>x!==item) : [...list,item]
  const post = async (url:string, body:any) => {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json;charset=utf-8'}, body:JSON.stringify(body)})
    return r.json()
  }

  const runCompare = async () => { setLoading(true); try { setCompareResult(await post('/api/betting/compare', {budget, bet_types:betTypes, odds:{}, excluded_horses:[]})) } finally { setLoading(false) } }
  const runOptimize = async () => { setLoading(true); try { setResult(await post('/api/betting/optimize', {budget, risk_level:risk, bet_types:betTypes, odds:{}, excluded_horses:[], pivot_horses: mode==='pivot' ? pivotHorses : []})) } finally { setLoading(false) } }
  const runFormation = async () => { setLoading(true); try { setFormationResult(await post('/api/betting/formation', {bet_type:'trio',...formation,amount_per_bet:100})) } finally { setLoading(false) } }
  const runBox = async () => { setLoading(true); try { setBoxResult(await post('/api/betting/box', {bet_type:boxBetType,horses:boxHorses,amount_per_bet:100})) } finally { setLoading(false) } }
  const runSim = async () => {
    if (!result || !simFirst) return
    setSimResult(await post('/api/betting/simulate-result', {
      bets: result.recommendations.map(r=>({type:r.bet_type,selection:r.selection,amount:r.amount,odds:r.odds})),
      result_first:simFirst, result_second:simSecond, result_third:simThird,
    }))
  }

  const HorsePicker = ({selected,onToggle,label}:{selected:string[];onToggle:(h:string)=>void;label:string}) => (
    <div className="mb-3">
      <div className="text-xs text-slate-500 mb-1 font-medium">{label}</div>
      <div className="flex flex-wrap gap-1">
        {horses.map(h=>(
          <button key={h} onClick={()=>onToggle(h)}
            className={`px-2 py-1 rounded text-xs font-medium border ${selected.includes(h)?'bg-blue-700 text-white border-blue-700':'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'}`}>
            {h.length>6?h.slice(0,5)+'…':h}
          </button>
        ))}
      </div>
    </div>
  )

  // ── サマリーカード ──
  const Summary = ({r}:{r:BettingResponse}) => (
    <div className="grid grid-cols-4 gap-2 mb-3">
      {[
        ['投資', `${r.total_budget.toLocaleString()}円`, ''],
        ['期待回収', `${r.expected_return.toLocaleString()}円`, r.expected_return>r.total_budget?'text-emerald-600':'text-red-600'],
        ['回収率', `${(r.expected_roi*100).toFixed(0)}%`, r.expected_roi>=1?'text-emerald-600':'text-red-600'],
        ['最高払戻', `${r.risk_metrics.best_case.toLocaleString()}円`, 'text-blue-700'],
      ].map(([l,v,c])=>(
        <div key={l as string} className="bg-slate-50 rounded-lg p-2 text-center border border-slate-200">
          <div className="text-[10px] text-slate-400">{l}</div>
          <div className={`text-sm sm:text-base font-bold font-mono ${c}`}>{v}</div>
        </div>
      ))}
    </div>
  )

  // ── 買い目テーブル（PC用） ──
  const BetTable = ({recs}:{recs:any[]}) => (
    <>
      <table className="hidden md:table w-full text-sm bg-white rounded-lg overflow-hidden border border-slate-200">
        <thead>
          <tr className="bg-slate-700 text-white text-xs">
            <th className="px-3 py-2 text-left">種別</th>
            <th className="px-3 py-2 text-left">買い目</th>
            <th className="px-3 py-2 text-right">金額</th>
            <th className="px-3 py-2 text-right">オッズ</th>
            <th className="px-3 py-2 text-right">的中率</th>
            <th className="px-3 py-2 text-right">的中時払戻</th>
            <th className="px-3 py-2 text-right">期待値</th>
          </tr>
        </thead>
        <tbody>
          {recs.map((r:any,i:number)=>(
            <tr key={i} className="border-t border-slate-100 hover:bg-blue-50">
              <td className="px-3 py-2"><span className="bg-slate-100 px-2 py-0.5 rounded text-xs">{r.bet_type_ja}</span></td>
              <td className="px-3 py-2 font-medium text-slate-800 text-xs">{r.selection}</td>
              <td className="px-3 py-2 text-right font-mono">{r.amount?.toLocaleString()}円</td>
              <td className="px-3 py-2 text-right font-mono text-slate-500">{r.odds}倍</td>
              <td className="px-3 py-2 text-right font-mono text-slate-500">{(r.hit_prob*100).toFixed(1)}%</td>
              <td className="px-3 py-2 text-right font-mono font-bold text-blue-700">{r.payout?.toLocaleString()}円</td>
              <td className={`px-3 py-2 text-right font-mono font-bold ${r.expected_value>=1?'text-emerald-600':'text-slate-400'}`}>{r.expected_value?.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {/* スマホ用カード */}
      <div className="md:hidden space-y-1.5">
        {recs.map((r:any,i:number)=>(
          <div key={i} className="bg-white rounded-lg border border-slate-200 p-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="bg-slate-100 px-2 py-0.5 rounded text-[10px] font-medium text-slate-600">{r.bet_type_ja}</span>
              <span className="font-mono font-bold text-emerald-600 text-sm">{r.amount?.toLocaleString()}円</span>
            </div>
            <div className="text-sm font-medium text-slate-800 mt-1 truncate">{r.selection}</div>
            <div className="flex gap-3 text-[11px] text-slate-500 mt-0.5">
              <span>{r.odds}倍</span>
              <span>的中{(r.hit_prob*100).toFixed(1)}%</span>
              <span className="text-blue-700 font-bold">払戻{r.payout?.toLocaleString()}円</span>
            </div>
          </div>
        ))}
      </div>
    </>
  )

  return (
    <div>
      {/* Mode tabs */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-1">
        {MODES.map(m=>(
          <button key={m.id} onClick={()=>setMode(m.id)}
            className={`px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap border ${mode===m.id?'bg-blue-700 text-white border-blue-700':'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}>
            <span className="mr-1">{m.icon}</span>{m.label}
          </button>
        ))}
      </div>

      {/* ═══ 3パターン比較 ═══ */}
      {mode === 'compare' && (
        <div>
          <div className="flex flex-wrap items-end gap-3 mb-3">
            <div>
              <label className="text-xs text-slate-500 block mb-1">予算</label>
              <input type="number" step={1000} value={budget} onChange={e=>setBudget(Number(e.target.value))}
                className="w-32 bg-white border border-slate-300 rounded px-3 py-1.5 font-mono text-sm"/>
            </div>
            <div className="flex gap-1">
              {[3000,5000,10000,30000].map(v=>(
                <button key={v} onClick={()=>setBudget(v)} className={`px-2 py-1.5 rounded text-xs border ${budget===v?'bg-blue-700 text-white border-blue-700':'bg-white text-slate-500 border-slate-300'}`}>
                  {v>=10000?`${v/10000}万`:`${v/1000}千`}
                </button>
              ))}
            </div>
            <button onClick={runCompare} disabled={loading}
              className="bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white px-5 py-1.5 rounded-lg font-bold text-sm">
              {loading?'計算中...':'3パターン比較'}
            </button>
          </div>
          <div className="flex flex-wrap gap-1 mb-4">
            {BET_TYPES.map(bt=>(
              <button key={bt.id} onClick={()=>setBetTypes(toggle(betTypes,bt.id))}
                className={`px-2.5 py-1 rounded text-xs font-medium border ${betTypes.includes(bt.id)?'bg-indigo-600 text-white border-indigo-600':'bg-white text-slate-500 border-slate-300'}`}>{bt.label}</button>
            ))}
          </div>
          {compareResult && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {['low','medium','high'].map(risk=>{
                const p = compareResult.patterns[risk]
                if(!p) return null
                return (
                  <div key={risk} className={`bg-white rounded-xl border-2 shadow-sm p-4 ${risk==='medium'?'border-blue-500':'border-slate-200'}`}>
                    <div className="flex items-center justify-between mb-3">
                      <span className={`text-sm font-bold ${risk==='low'?'text-blue-600':risk==='medium'?'text-amber-600':'text-red-600'}`}>
                        {p.label}
                      </span>
                      <span className="text-xs text-slate-400">{p.recommendations?.length}点</span>
                    </div>
                    {/* サマリー */}
                    <div className="grid grid-cols-2 gap-1.5 mb-3 text-xs">
                      <div className="bg-slate-50 rounded p-1.5 text-center">
                        <div className="text-slate-400">投資</div>
                        <div className="font-mono font-bold">{p.total_budget?.toLocaleString()}円</div>
                      </div>
                      <div className="bg-slate-50 rounded p-1.5 text-center">
                        <div className="text-slate-400">期待回収</div>
                        <div className={`font-mono font-bold ${p.expected_roi>=1?'text-emerald-600':'text-slate-700'}`}>{p.expected_return?.toLocaleString()}円</div>
                      </div>
                      <div className="bg-slate-50 rounded p-1.5 text-center">
                        <div className="text-slate-400">回収率</div>
                        <div className={`font-mono font-bold ${p.expected_roi>=1?'text-emerald-600':'text-slate-700'}`}>{(p.expected_roi*100).toFixed(0)}%</div>
                      </div>
                      <div className="bg-slate-50 rounded p-1.5 text-center">
                        <div className="text-slate-400">最高払戻</div>
                        <div className="font-mono font-bold text-blue-700">{p.risk_metrics?.best_case?.toLocaleString()}円</div>
                      </div>
                    </div>
                    {/* 買い目リスト */}
                    <div className="space-y-1">
                      {p.recommendations?.map((r:any,i:number)=>(
                        <div key={i} className="flex items-center gap-1.5 text-xs py-1 border-b border-slate-100 last:border-0">
                          <span className="bg-slate-100 px-1.5 py-0.5 rounded text-[10px] text-slate-600 shrink-0">{r.bet_type_ja}</span>
                          <span className="flex-1 truncate text-slate-700">{r.selection}</span>
                          <span className="font-mono text-slate-800 shrink-0">{r.amount?.toLocaleString()}円</span>
                          <span className="font-mono text-blue-600 shrink-0 font-bold">→{r.payout?.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          {!compareResult && !loading && <div className="text-center py-16 text-slate-400 text-sm">予算を設定して「3パターン比較」を押してください</div>}
        </div>
      )}

      {/* ═══ AI自動 / 軸馬流し ═══ */}
      {(mode === 'auto' || mode === 'pivot') && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* 設定 */}
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200 space-y-3">
            {mode === 'pivot' && (
              <HorsePicker selected={pivotHorses} onToggle={h=>setPivotHorses(toggle(pivotHorses,h))} label={`軸馬（${pivotHorses.length}/2頭）`}/>
            )}
            <div>
              <label className="text-xs text-slate-500 mb-1 block">予算</label>
              <input type="number" step={1000} value={budget} onChange={e=>setBudget(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 font-mono focus:border-blue-500 focus:outline-none"/>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">リスク</label>
              <div className="flex gap-1.5">
                {([['low','堅実'],['medium','中'],['high','大穴']] as const).map(([v,l])=>(
                  <button key={v} onClick={()=>setRisk(v)} className={`flex-1 py-1.5 rounded text-xs font-medium border ${risk===v?'bg-blue-700 text-white border-blue-700':'bg-white text-slate-600 border-slate-300'}`}>{l}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">馬券種別</label>
              <div className="flex flex-wrap gap-1">
                {BET_TYPES.map(bt=>(
                  <button key={bt.id} onClick={()=>setBetTypes(toggle(betTypes,bt.id))}
                    className={`px-2.5 py-1 rounded text-xs font-medium border ${betTypes.includes(bt.id)?'bg-indigo-600 text-white border-indigo-600':'bg-white text-slate-600 border-slate-300'}`}>{bt.label}</button>
                ))}
              </div>
            </div>
            <button onClick={runOptimize} disabled={loading || (mode==='pivot' && pivotHorses.length===0)}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white py-2 rounded-lg font-bold text-sm">
              {loading?'計算中...':mode==='pivot'?`${pivotHorses.length}軸流し`:'最適化実行'}
            </button>
          </div>

          {/* 結果 */}
          <div className="lg:col-span-3 space-y-3">
            {result ? <>
              <Summary r={result}/>
              <BetTable recs={result.recommendations}/>

              {/* 収支シミュレーション */}
              <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
                <h3 className="text-sm font-bold text-slate-700 mb-2">収支シミュレーション</h3>
                <div className="flex flex-wrap gap-2 mb-2">
                  {['1着','2着','3着'].map((l,idx)=>(
                    <div key={l} className="flex-1 min-w-[90px]">
                      <label className="text-[10px] text-slate-500">{l}</label>
                      <select className="w-full border border-slate-300 rounded px-2 py-1 text-sm bg-white"
                        value={[simFirst,simSecond,simThird][idx]} onChange={e=>[setSimFirst,setSimSecond,setSimThird][idx](e.target.value)}>
                        <option value="">-</option>
                        {horses.map(h=><option key={h} value={h}>{h}</option>)}
                      </select>
                    </div>
                  ))}
                  <button onClick={runSim} className="bg-slate-700 hover:bg-slate-800 text-white px-4 py-1 rounded text-sm self-end">計算</button>
                </div>
                {simResult && (
                  <div className={`p-2.5 rounded-lg text-sm font-mono ${simResult.profit>0?'bg-emerald-50 border border-emerald-200':'bg-red-50 border border-red-200'}`}>
                    <span>投資:{simResult.total_invested?.toLocaleString()}円</span>
                    <span className="mx-3">→</span>
                    <span className={`font-bold ${simResult.profit>0?'text-emerald-700':'text-red-700'}`}>
                      回収:{simResult.total_return?.toLocaleString()}円 ({simResult.profit>0?'+':''}{simResult.profit?.toLocaleString()}円)
                    </span>
                    {simResult.hit_bets?.length>0 && <div className="text-xs text-slate-500 mt-1">的中: {simResult.hit_bets.map((b:any)=>`${b.selection}(${b.payout?.toLocaleString()}円)`).join(', ')}</div>}
                    {simResult.hit_bets?.length===0 && <div className="text-xs text-red-500 mt-1">的中なし</div>}
                  </div>
                )}
              </div>
            </> : <div className="text-center py-16 text-slate-400 text-sm">設定して実行ボタンを押してください</div>}
          </div>
        </div>
      )}

      {/* ═══ フォーメーション ═══ */}
      {mode === 'formation' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <HorsePicker selected={formation.first} onToggle={h=>setFormation({...formation,first:toggle(formation.first,h)})} label="1着候補"/>
            <HorsePicker selected={formation.second} onToggle={h=>setFormation({...formation,second:toggle(formation.second,h)})} label="2着候補"/>
            <HorsePicker selected={formation.third} onToggle={h=>setFormation({...formation,third:toggle(formation.third,h)})} label="3着候補"/>
            <button onClick={runFormation} disabled={loading||formation.first.length===0}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white py-2 rounded-lg font-bold text-sm mt-2">
              三連複フォーメーション計算
            </button>
          </div>
          <div className="lg:col-span-2">
            {formationResult ? (
              <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
                <div className="flex flex-wrap gap-3 mb-3 text-sm items-center">
                  <span className="font-bold">三連複フォーメーション</span>
                  <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-bold">{formationResult.total_bets}点</span>
                  <span className="font-mono text-emerald-600 font-bold">{formationResult.total_cost?.toLocaleString()}円</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 text-xs">
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">的中率合計</div><div className="font-mono font-bold">{((formationResult.total_hit_prob||0)*100).toFixed(1)}%</div></div>
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">期待回収</div><div className="font-mono font-bold">{formationResult.expected_return?.toLocaleString()}円</div></div>
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">回収率</div><div className={`font-mono font-bold ${(formationResult.expected_roi||0)>=1?'text-emerald-600':'text-slate-700'}`}>{((formationResult.expected_roi||0)*100).toFixed(0)}%</div></div>
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">最高払戻</div><div className="font-mono font-bold text-blue-700">{formationResult.best_payout?.toLocaleString()}円</div></div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-1.5">
                  {formationResult.combinations?.map((c:any,i:number)=>(
                    <div key={i} className="bg-slate-50 rounded px-2 py-1.5 flex justify-between text-xs">
                      <span className="text-slate-700 font-mono">{c.selection}</span>
                      <span className="text-blue-600 font-mono font-bold ml-2">→{c.payout?.toLocaleString()}円</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : <div className="text-center py-16 text-slate-400 text-sm">候補を選んで計算してください</div>}
          </div>
        </div>
      )}

      {/* ═══ ボックス ═══ */}
      {mode === 'box' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <div className="mb-3">
              <label className="text-xs text-slate-500 mb-1 block">馬券種別</label>
              <div className="flex gap-1.5">
                {[['quinella','馬連'],['wide','ワイド'],['exacta','馬単'],['trio','三連複']].map(([v,l])=>(
                  <button key={v} onClick={()=>setBoxBetType(v)}
                    className={`flex-1 py-1.5 rounded text-xs font-medium border ${boxBetType===v?'bg-indigo-600 text-white border-indigo-600':'bg-white text-slate-600 border-slate-300'}`}>{l}</button>
                ))}
              </div>
            </div>
            <HorsePicker selected={boxHorses} onToggle={h=>setBoxHorses(toggle(boxHorses,h))} label={`BOX馬（${boxHorses.length}頭）`}/>
            <button onClick={runBox} disabled={loading||boxHorses.length<(boxBetType==='trio'?3:2)}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white py-2 rounded-lg font-bold text-sm mt-2">
              ボックス計算
            </button>
          </div>
          <div className="lg:col-span-2">
            {boxResult ? (
              <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
                <div className="flex flex-wrap gap-3 mb-3 text-sm items-center">
                  <span className="font-bold">{{quinella:'馬連',wide:'ワイド',trio:'三連複',exacta:'馬単'}[boxBetType]} BOX</span>
                  <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-bold">{boxResult.total_bets}点</span>
                  <span className="font-mono text-emerald-600 font-bold">{boxResult.total_cost?.toLocaleString()}円</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 text-xs">
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">的中率合計</div><div className="font-mono font-bold">{((boxResult.total_hit_prob||0)*100).toFixed(1)}%</div></div>
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">期待回収</div><div className="font-mono font-bold">{boxResult.expected_return?.toLocaleString()}円</div></div>
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">回収率</div><div className={`font-mono font-bold ${(boxResult.expected_roi||0)>=1?'text-emerald-600':'text-slate-700'}`}>{((boxResult.expected_roi||0)*100).toFixed(0)}%</div></div>
                  <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-400">最高払戻</div><div className="font-mono font-bold text-blue-700">{boxResult.best_payout?.toLocaleString()}円</div></div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-1.5">
                  {boxResult.combinations?.map((c:any,i:number)=>(
                    <div key={i} className="bg-slate-50 rounded px-2 py-1.5 flex justify-between text-xs">
                      <span className="text-slate-700 font-mono">{c.selection}</span>
                      <span className="text-blue-600 font-mono font-bold ml-2">→{c.payout?.toLocaleString()}円</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : <div className="text-center py-16 text-slate-400 text-sm">馬を選んで計算してください</div>}
          </div>
        </div>
      )}
    </div>
  )
}
