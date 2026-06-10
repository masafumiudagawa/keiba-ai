import { useEffect, useState, useMemo } from 'react'

const MARK_COLORS: Record<string, string> = { '◎': 'text-red-600', '○': 'text-blue-600', '▲': 'text-amber-600', '△': 'text-slate-500' }
const WAKU_BG: Record<number, string> = { 1: 'bg-white border border-slate-300 text-slate-800', 2: 'bg-gray-900 text-white', 3: 'bg-red-600 text-white', 4: 'bg-blue-600 text-white', 5: 'bg-yellow-400 text-gray-900', 6: 'bg-green-600 text-white', 7: 'bg-orange-500 text-white', 8: 'bg-pink-500 text-white' }
const FIN_BG: Record<number, string> = { 1: 'bg-red-600 text-white', 2: 'bg-blue-600 text-white', 3: 'bg-green-600 text-white' }

const WEIGHT_CATEGORIES = [
  { key: 'age', label: '馬齢' }, { key: 'recent_form', label: '近走' }, { key: 'g1_record', label: 'G1' },
  { key: 'jockey', label: '騎手' }, { key: 'last_3f', label: '3F' }, { key: 'speed_figure', label: '能力' },
  { key: 'pedigree', label: '血統' }, { key: 'public_opinion', label: '世論' }, { key: 'training', label: '調教' },
  { key: 'running_style', label: '脚質' }, { key: 'head_to_head', label: '対戦' }, { key: 'rest', label: '休養' },
  { key: 'trainer', label: '厩舎' }, { key: 'weight_trend', label: '体重' },
]
const PRESETS: Record<string, Record<string, number>> = {
  standard: Object.fromEntries(WEIGHT_CATEGORIES.map(c => [c.key, 1.0])),
  data: { age:1,recent_form:1.3,g1_record:1.3,jockey:1,last_3f:1.5,speed_figure:1.5,pedigree:1,public_opinion:0.3,training:0.8,running_style:1,head_to_head:1.2,rest:1,trainer:0.8,weight_trend:1 },
  upset: { age:0.5,recent_form:0.5,g1_record:0.3,jockey:0.5,last_3f:2,speed_figure:1.5,pedigree:1.2,public_opinion:0.2,training:1.5,running_style:1.5,head_to_head:0.5,rest:1.2,trainer:0.5,weight_trend:1 },
}

interface Recent { date:string;venue:string;race:string;dist:number;finish:number|string;grade:string;time:string;last3f:string;passing:string }
interface Horse { horse_name:string;jockey:string;age:number;sex:string;sire:string;dam_sire:string;trainer:string;gate_number:number;post_position:number;weight:string;running_style_label:string;career:string;owner:string;coat_color:string;english_name:string;total_prize:string;netkeiba_id:string;recent_5:Recent[];scores:Record<string,number>;raw:Record<string,any> }

const Fin = ({v}:{v:number|string}) => { const n = typeof v==='number'?v:parseInt(String(v)); if(!n||isNaN(n)) return <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-400 text-[10px] inline-flex items-center justify-center">-</span>; return <span className={`w-5 h-5 rounded-full ${FIN_BG[n]||'bg-slate-300 text-slate-600'} text-[10px] font-bold inline-flex items-center justify-center`}>{n}</span> }
const Waku = ({p,g}:{p:number;g:number}) => p ? <div className={`w-7 h-8 rounded flex flex-col items-center justify-center text-[10px] font-bold leading-tight ${WAKU_BG[p]||'bg-slate-200'}`}><div className="text-[8px] opacity-70">{p}</div><div className="text-xs">{g}</div></div> : null

export default function PredictionTable({ raceId }: { raceId: string }) {
  const [features, setFeatures] = useState<Horse[]>([])
  const [config, setConfig] = useState<any>(null)
  const [weather, setWeather] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [weights, setWeights] = useState<Record<string, number>>(PRESETS.standard)
  const [showWeights, setShowWeights] = useState(false)
  const [expanded, setExpanded] = useState<string|null>(null)

  useEffect(() => { setLoading(true); fetch(`/api/races/${raceId}/features`).then(r=>r.json()).then(d=>{setFeatures(d.features||[]);setConfig(d.config||{});setWeather(d.weather||null)}).catch(()=>{}).finally(()=>setLoading(false)) }, [raceId])

  const ranked = useMemo(() => {
    if(!features.length) return []
    const scored = features.map(h=>{const total=Object.entries(h.scores).reduce((s,[k,v])=>s+v*(weights[k]??1),0);return{...h,total}})
    const mn=Math.min(...scored.map(s=>s.total)),mx=Math.max(...scored.map(s=>s.total)),rng=mx-mn||1
    const wp=scored.map(s=>({...s,prob:(s.total-mn)/rng}))
    const ps=wp.reduce((s,h)=>s+h.prob,0)||1
    const f=wp.map(s=>({...s,prob:s.prob/ps})).sort((a,b)=>b.prob-a.prob)
    const marks=['◎','○','▲','△','△']
    return f.map((h,i)=>({...h,rank:i+1,mark:marks[i]||''}))
  }, [features,weights])

  if(loading) return <div className="text-center py-20 text-slate-400">読み込み中...</div>
  if(!features.length) return <div className="text-center py-20 text-slate-400">出走馬データがありません</div>

  const tc:Record<string,string>={'良':'text-emerald-600','稍重':'text-amber-600','重':'text-orange-600','不良':'text-red-600'}
  const nkLink = (id:string) => id ? `https://db.netkeiba.com/horse/${id}/` : ''

  return (
    <div>
      {/* Race Info + Weather */}
      {(config||weather)&&<div className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-xl p-3 mb-3 text-white shadow">
        <div className="flex flex-wrap gap-x-3 gap-y-1 items-center text-xs sm:text-sm">
          {config?.grade&&<span className="bg-red-600 px-2 py-0.5 rounded-full text-xs font-bold">{config.grade}</span>}
          <span className="font-bold">{config?.name}</span>
          <span className="text-blue-200">{config?.venue} {config?.surface}{config?.distance}m</span>
          {config?.date&&<span className="text-blue-200">{config.date}</span>}
          {config?.post_time&&<span className="text-blue-200">{config.post_time}発走</span>}
        </div>
        {weather?.forecast&&<div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-blue-100">
          <span>天気:<strong className="text-white ml-0.5">{weather.forecast}</strong></span>
          {weather.temperature_low!=null&&<span>{weather.temperature_low}〜{weather.temperature_high}℃</span>}
          {weather.precipitation_mm!=null&&<span>降水:{weather.precipitation_mm}mm</span>}
          {weather.predicted_track_condition&&<span>馬場:<strong className={`${tc[weather.predicted_track_condition]||''} bg-white/20 px-1 rounded`}>{weather.predicted_track_condition}</strong></span>}
        </div>}
      </div>}

      {/* Weight */}
      <div className="mb-3">
        <button onClick={()=>setShowWeights(!showWeights)} className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${showWeights?'bg-blue-700 text-white border-blue-700':'bg-white text-slate-600 border-slate-200'}`}>⚙ ウェイト {showWeights?'▲':'▼'}</button>
      </div>
      {showWeights&&<div className="bg-white rounded-xl border border-slate-200 p-3 mb-3 shadow-sm">
        <div className="flex flex-wrap gap-1.5 mb-2 pb-2 border-b border-slate-100">
          {[['standard','標準'],['data','データ重視'],['upset','穴馬発掘']].map(([k,l])=>(<button key={k} onClick={()=>setWeights(PRESETS[k])} className="px-2 py-1 rounded text-xs bg-slate-50 border border-slate-200 hover:bg-blue-50">{l}</button>))}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
          {WEIGHT_CATEGORIES.map(c=>(<div key={c.key} className="flex items-center gap-1"><span className="text-[10px] text-slate-500 w-8 shrink-0">{c.label}</span><input type="range" min="0" max="2" step="0.1" value={weights[c.key]??1} onChange={e=>setWeights({...weights,[c.key]:parseFloat(e.target.value)})} className="flex-1 h-2 accent-blue-600"/><span className={`text-[10px] font-mono w-6 text-right ${(weights[c.key]??1)!==1?'text-blue-700 font-bold':'text-slate-400'}`}>{(weights[c.key]??1).toFixed(1)}</span></div>))}
        </div>
      </div>}

      {/* ═══ Horse Cards (All Breakpoints) ═══ */}
      <div className="space-y-1.5">
        {ranked.map(h=>{
          const isExp = expanded===h.horse_name
          return (
          <div key={h.horse_name} className={`bg-white rounded-lg shadow-sm border overflow-hidden ${h.rank<=3?'border-l-4 border-l-blue-500 border-slate-200':'border-slate-200'}`}>
            {/* Main Row */}
            <div className="flex items-stretch cursor-pointer" onClick={()=>setExpanded(isExp?null:h.horse_name)}>
              {/* Waku + Mark */}
              <div className="flex items-center gap-1.5 px-2 py-2 shrink-0">
                <Waku p={h.post_position} g={h.gate_number}/>
                <span className={`text-xl leading-none ${MARK_COLORS[h.mark]||''}`}>{h.mark}</span>
              </div>

              {/* Horse Info */}
              <div className="flex-1 min-w-0 py-1.5 pr-2">
                <div className="flex items-baseline gap-1 flex-wrap">
                  <span className={`font-bold text-sm ${h.rank===1?'text-red-600':h.rank<=3?'text-blue-700':''}`}>{h.horse_name}</span>
                  <span className="text-[10px] text-slate-400">{h.sex}{h.age} {h.coat_color&&h.coat_color!=='nan'?h.coat_color:''}</span>
                  <span className="text-[10px] bg-slate-100 text-slate-500 px-1 rounded">{h.running_style_label}</span>
                  {h.netkeiba_id&&h.netkeiba_id!=='nan'&&h.netkeiba_id!==''&&
                    <a href={nkLink(h.netkeiba_id)} target="_blank" rel="noopener noreferrer" onClick={e=>e.stopPropagation()}
                      className="text-[10px] text-blue-500 hover:text-blue-700">↗詳細</a>}
                </div>
                <div className="text-[10px] text-slate-400 leading-snug">
                  <span className="font-medium text-slate-500">{h.jockey}</span>
                  <span className="mx-1">|</span>
                  {h.sire&&h.sire!=='nan'?h.sire:''}{h.dam_sire&&h.dam_sire!=='nan'&&h.dam_sire!==''?`×${h.dam_sire}`:''}
                </div>
                <div className="text-[10px] text-slate-400 leading-snug">
                  {h.trainer&&h.trainer!=='nan'?h.trainer:''}
                  {h.weight&&h.weight!=='nan'?` ${h.weight}kg`:''}
                  <span className="mx-1">|</span>
                  {h.career}
                  {h.owner&&h.owner!=='nan'?` | ${h.owner}`:''}
                  {h.total_prize&&h.total_prize!=='nan'&&h.total_prize!==''?` | ${Number(h.total_prize).toLocaleString()}万`:''}
                </div>
              </div>

              {/* Odds + AI */}
              <div className="flex flex-col items-end justify-center px-2 shrink-0 border-l border-slate-100">
                {h.raw.win_odds>0&&<div className="font-mono font-bold text-sm">{h.raw.win_odds}倍</div>}
                {h.raw.popularity>0&&<span className={`text-[10px] px-1.5 rounded-full font-bold ${h.raw.popularity<=3?'bg-red-100 text-red-700':'bg-slate-100 text-slate-500'}`}>{h.raw.popularity}人気</span>}
                <div className="font-mono font-bold text-sm text-blue-700 mt-0.5">{(h.prob*100).toFixed(1)}%</div>
              </div>
            </div>

            {/* Recent 5 (always visible) */}
            {h.recent_5?.length>0&&<div className="px-3 pb-2 border-t border-slate-50">
              <div className="flex gap-1.5 overflow-x-auto py-1">
                {h.recent_5.map((r,i)=>(
                  <div key={i} className="flex flex-col items-center shrink-0 min-w-[44px]">
                    <Fin v={r.finish}/>
                    <span className="text-[8px] text-slate-400 leading-tight mt-0.5">{r.race}</span>
                    {r.time&&r.time!=='nan'&&r.time!==''&&<span className="text-[8px] text-slate-400 font-mono">{r.time}</span>}
                    {r.last3f&&r.last3f!=='nan'&&r.last3f!==''&&<span className="text-[8px] text-blue-500 font-mono">{r.last3f}</span>}
                    {r.passing&&r.passing!=='nan'&&r.passing!==''&&<span className="text-[7px] text-slate-300">{r.passing}</span>}
                  </div>
                ))}
              </div>
            </div>}

            {/* Probability Bar */}
            <div className="px-3 pb-1.5">
              <div className="bg-slate-200 rounded-full h-1.5">
                <div className="bg-blue-600 h-1.5 rounded-full" style={{width:`${h.prob*100}%`}}/>
              </div>
            </div>

            {/* Expanded: Score Breakdown */}
            {isExp&&<div className="bg-slate-50 px-3 py-2 border-t border-slate-100">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1">
                {WEIGHT_CATEGORIES.map(c=>{const w=(h.scores[c.key]||0)*(weights[c.key]??1);return(
                  <div key={c.key} className="flex items-center gap-1 text-[10px]">
                    <span className="w-8 text-slate-400 shrink-0">{c.label}</span>
                    <div className="flex-1 bg-slate-200 rounded-full h-1"><div className="bg-blue-500 h-1 rounded-full" style={{width:`${Math.min(w/2,100)}%`}}/></div>
                    <span className="w-5 text-right font-mono text-slate-600">{w.toFixed(0)}</span>
                  </div>
                )})}
              </div>
              {h.english_name&&h.english_name!=='nan'&&<div className="text-[10px] text-slate-400 mt-1">{h.english_name}</div>}
            </div>}
          </div>
        )})}
      </div>
    </div>
  )
}
