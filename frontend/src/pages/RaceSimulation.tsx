import { useState, useRef, useEffect, useCallback } from 'react'
import type { SimulationResponse } from '../types'

const GATE_COLORS = ['#ffffff','#111111','#dc2626','#2563eb','#eab308','#16a34a','#ea580c','#db2777']

export default function RaceSimulation({ raceId: _raceId }: { raceId: string }) {
  const [data, setData] = useState<SimulationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [speed, setSpeed] = useState(1)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const startTimeRef = useRef(0)
  const progressRef = useRef(0)

  const runSimulation = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ num_simulations: 500, track_condition: 'good' }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
      progressRef.current = 0
      setProgress(0)
      setPlaying(false)
    } catch (e) {
      console.error('Simulation error:', e)
      alert('シミュレーション実行に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const draw = useCallback((prog: number) => {
    const canvas = canvasRef.current
    if (!canvas || !data) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width, h = canvas.height
    const horses = data.representative_race.horses

    ctx.fillStyle = '#1e6b3a'
    ctx.fillRect(0, 0, w, h)

    const cx = w * 0.5, cy = h * 0.48
    const rx = w * 0.38, ry = h * 0.34

    // Track
    ctx.beginPath()
    ctx.ellipse(cx, cy, rx + 25, ry + 25, 0, 0, Math.PI * 2)
    ctx.fillStyle = '#2d8a4e'
    ctx.fill()

    ctx.beginPath()
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2)
    ctx.strokeStyle = '#c4a35a'
    ctx.lineWidth = 44
    ctx.stroke()

    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.ellipse(cx, cy, rx - 23, ry - 23, 0, 0, Math.PI * 2)
    ctx.stroke()
    ctx.beginPath()
    ctx.ellipse(cx, cy, rx + 23, ry + 23, 0, 0, Math.PI * 2)
    ctx.stroke()

    ctx.beginPath()
    ctx.ellipse(cx, cy, rx - 24, ry - 24, 0, 0, Math.PI * 2)
    ctx.fillStyle = '#1a5c30'
    ctx.fill()

    const goalAngle = Math.PI * 0.8
    const fs = Math.max(9, w * 0.014)

    // Distance markers
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.font = `${fs}px sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (let d = 400; d <= 2000; d += 400) {
      const a = goalAngle + (Math.PI * 2) * (d / 2200)
      ctx.fillText(`${2200 - d}m`, cx + (rx + 35) * Math.cos(a), cy + (ry + 35) * Math.sin(a))
    }
    ctx.fillStyle = '#fff'
    ctx.font = `bold ${Math.max(11, w * 0.016)}px sans-serif`
    ctx.fillText('GOAL', cx + (rx + 35) * Math.cos(goalAngle), cy + (ry + 35) * Math.sin(goalAngle))

    // Horses
    const dotR = Math.max(10, Math.min(16, w * 0.022))
    horses.forEach((horse, i) => {
      const nCp = horse.positions.length
      const cpFloat = prog * (nCp - 1)
      const cpIdx = Math.min(Math.floor(cpFloat), nCp - 2)
      const cpFrac = cpFloat - cpIdx
      const relPos = horse.positions[cpIdx] + (horse.positions[cpIdx + 1] - horse.positions[cpIdx]) * cpFrac

      // relPos 0=先頭, 1=最後方 → 角度オフセットに変換
      // 0.8ラジアン（約45度）分の差をつけて馬群を広げる
      const lagAngle = relPos * 0.8
      const angle = goalAngle + (Math.PI * 2) * prog - lagAngle
      // 内外のレーン分け（隣接馬が重ならないように）
      const lane = ((i % 4) - 1.5) * 7
      const hx = cx + (rx + lane) * Math.cos(angle)
      const hy = cy + (ry + lane) * Math.sin(angle)

      const gateIdx = Math.floor(((horse.gate_number || i + 1) - 1) / 2)
      const color = GATE_COLORS[gateIdx] || '#999'

      ctx.beginPath()
      ctx.arc(hx + 1, hy + 1, dotR, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(0,0,0,0.3)'
      ctx.fill()

      ctx.beginPath()
      ctx.arc(hx, hy, dotR, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()

      const textColor = ['#111111','#dc2626','#2563eb','#db2777'].includes(color) ? '#fff' : '#000'
      ctx.fillStyle = textColor
      ctx.font = `bold ${Math.max(8, Math.min(12, w * 0.016))}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(String(horse.gate_number || i + 1), hx, hy)
    })

    // HUD
    const remaining = Math.max(0, Math.round(2200 * (1 - prog)))
    ctx.fillStyle = 'rgba(0,0,0,0.6)'
    const hudW = Math.max(120, w * 0.18)
    ctx.fillRect(8, 8, hudW, 28)
    ctx.fillStyle = '#fff'
    ctx.font = `bold ${Math.max(13, w * 0.02)}px sans-serif`
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.fillText(`残り ${remaining}m  ${speed}x`, 14, 13)
  }, [data, speed])

  useEffect(() => {
    if (!playing || !data) return
    const duration = 15000 / speed
    startTimeRef.current = performance.now() - progressRef.current * duration
    const animate = (now: number) => {
      const p = Math.min((now - startTimeRef.current) / duration, 1)
      progressRef.current = p
      setProgress(p)
      draw(p)
      if (p < 1) animRef.current = requestAnimationFrame(animate)
      else setPlaying(false)
    }
    animRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animRef.current)
  }, [playing, data, speed, draw])

  useEffect(() => {
    if (data && !playing) draw(progressRef.current)
  }, [data, playing, draw])

  useEffect(() => {
    const resize = () => {
      const canvas = canvasRef.current
      if (!canvas?.parentElement) return
      const w = canvas.parentElement.clientWidth - 24
      canvas.width = w
      canvas.height = Math.min(w * 0.6, 420)
      if (data) draw(progressRef.current)
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [data, draw])

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button onClick={runSimulation} disabled={loading}
          className="bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 text-white px-4 py-2 rounded-lg font-medium text-sm">
          {loading ? '計算中...' : 'シミュレーション実行'}
        </button>
        {data && <>
          <button onClick={() => { if (!playing) startTimeRef.current = performance.now() - progressRef.current * (15000/speed); setPlaying(!playing) }}
            className="bg-slate-200 hover:bg-slate-300 text-slate-700 px-3 py-2 rounded text-sm">
            {playing ? '⏸' : '▶'}
          </button>
          <button onClick={() => { progressRef.current = 0; setProgress(0); setPlaying(false); draw(0) }}
            className="bg-slate-200 hover:bg-slate-300 text-slate-700 px-3 py-2 rounded text-sm">⏮</button>
          {[1, 2, 4].map(s => (
            <button key={s} onClick={() => setSpeed(s)}
              className={`px-2.5 py-1.5 rounded text-xs font-medium ${speed === s ? 'bg-blue-700 text-white' : 'bg-slate-200 text-slate-600'}`}>
              {s}x
            </button>
          ))}
        </>}
      </div>

      {data ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white rounded-xl shadow border border-slate-200 p-3">
            <canvas ref={canvasRef} className="w-full rounded-lg" />
            <div className="mt-2 bg-slate-200 rounded-full h-2 cursor-pointer"
              onClick={e => { const r = e.currentTarget.getBoundingClientRect(); const p = Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)); progressRef.current=p; setProgress(p); setPlaying(false); draw(p) }}>
              <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${progress * 100}%` }} />
            </div>
          </div>
          <div className="space-y-3">
            <div className="bg-white rounded-xl p-3 shadow border border-slate-200">
              <h3 className="text-xs font-semibold text-slate-500 mb-2">着順結果</h3>
              <div className="space-y-0.5 max-h-64 overflow-y-auto">
                {data.representative_race.horses.map((h, i) => (
                  <div key={h.horse_name} className={`flex items-center gap-1.5 text-xs py-0.5 px-1 rounded ${i < 3 ? 'bg-blue-50' : ''}`}>
                    <span className={`w-4 font-bold text-right ${i === 0 ? 'text-red-600' : i < 3 ? 'text-blue-600' : 'text-slate-400'}`}>{h.finish_position}</span>
                    <span className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold border border-slate-300 shrink-0"
                      style={{ backgroundColor: h.color, color: ['#111111','#dc2626','#2563eb','#db2777'].includes(h.color) ? '#fff' : '#000' }}>{h.gate_number}</span>
                    <span className="flex-1 truncate text-slate-700">{h.horse_name}</span>
                    <span className="text-slate-400 font-mono text-[9px]">{h.finish_time}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-xl p-3 shadow border border-slate-200">
              <h3 className="text-xs font-semibold text-slate-500 mb-1">1着回数 / {data.summary.num_simulations}回</h3>
              {Object.entries(data.summary.win_counts).sort((a,b) => b[1]-a[1]).slice(0,6).map(([name, count]) => (
                <div key={name} className="flex items-center gap-1.5 text-xs py-0.5">
                  <span className="w-20 truncate text-slate-600">{name}</span>
                  <div className="flex-1 bg-slate-200 rounded-full h-1.5">
                    <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${Math.min((count/data.summary.num_simulations)*300, 100)}%` }} />
                  </div>
                  <span className="w-10 text-right font-mono text-[9px] text-slate-500">{((count/data.summary.num_simulations)*100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
            <div className="bg-white rounded-xl p-3 shadow border border-slate-200 text-xs text-slate-600">
              <div className="flex flex-wrap gap-x-3">
                <span>前半1000m: <b className="font-mono">{data.representative_race.pace.first_1000m}秒</b></span>
                <span>上がり3F: <b className="font-mono">{data.representative_race.pace.last_600m}秒</b></span>
                <span className={`font-bold ${data.representative_race.pace.type === 'H' ? 'text-red-600' : data.representative_race.pace.type === 'S' ? 'text-blue-600' : 'text-emerald-600'}`}>
                  {data.representative_race.pace.type === 'H' ? 'ハイ' : data.representative_race.pace.type === 'S' ? 'スロー' : 'ミドル'}ペース
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : !loading && <div className="text-center py-16 text-slate-400 text-sm">「シミュレーション実行」を押してレース展開を生成</div>}
    </div>
  )
}
