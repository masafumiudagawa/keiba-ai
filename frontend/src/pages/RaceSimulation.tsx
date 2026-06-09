import { useState, useRef, useEffect, useCallback } from 'react'
import type { SimulationResponse, HorseRaceData } from '../types'

const GATE_COLORS = ['#fff','#000','#e74c3c','#3498db','#f1c40f','#2ecc71','#e67e22','#e91e63']

export default function RaceSimulation() {
  const [data, setData] = useState<SimulationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0) // 0 ~ 1
  const [speed, setSpeed] = useState(1)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const startTimeRef = useRef(0)

  const runSimulation = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ num_simulations: 1000, track_condition: '良' }),
      })
      const json = await res.json()
      setData(json)
      setProgress(0)
      setPlaying(false)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const drawTrack = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number, horses: HorseRaceData[], prog: number) => {
    ctx.clearRect(0, 0, w, h)

    // Track (ellipse)
    const cx = w * 0.45, cy = h * 0.5
    const rx = w * 0.35, ry = h * 0.35

    // Draw grass
    ctx.fillStyle = '#1a4d1a'
    ctx.fillRect(0, 0, w, h)

    // Outer track
    ctx.strokeStyle = '#2d7a2d'
    ctx.lineWidth = 50
    ctx.beginPath()
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2)
    ctx.stroke()

    // Track surface
    ctx.strokeStyle = '#8B6914'
    ctx.lineWidth = 40
    ctx.beginPath()
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2)
    ctx.stroke()

    // Inner rail
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.ellipse(cx, cy, rx - 22, ry - 22, 0, 0, Math.PI * 2)
    ctx.stroke()

    // Outer rail
    ctx.beginPath()
    ctx.ellipse(cx, cy, rx + 22, ry + 22, 0, 0, Math.PI * 2)
    ctx.stroke()

    // Start/Goal markers
    const goalAngle = Math.PI * 0.75 // bottom-left area
    const gx = cx + rx * Math.cos(goalAngle)
    const gy = cy + ry * Math.sin(goalAngle)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 12px sans-serif'
    ctx.fillText('GOAL', gx - 15, gy + 35)

    // Distance markers
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.font = '10px sans-serif'
    for (let d = 400; d <= 2000; d += 400) {
      const ratio = d / 2200
      const angle = goalAngle + Math.PI * 2 * ratio // clockwise (right turn)
      const mx = cx + (rx + 30) * Math.cos(angle)
      const my = cy + (ry + 30) * Math.sin(angle)
      ctx.fillText(`${2200 - d}m`, mx - 10, my)
    }

    // Draw horses
    const topN = horses.slice(0, 14) // max 14 for visibility
    topN.forEach((horse, i) => {
      // Position along track based on progress
      const checkpoints = horse.positions.length
      const cpIdx = Math.min(Math.floor(prog * (checkpoints - 1)), checkpoints - 2)
      const cpFrac = (prog * (checkpoints - 1)) - cpIdx
      const gap1 = horse.positions[cpIdx] || 0
      const gap2 = horse.positions[cpIdx + 1] || 0
      const gap = gap1 + (gap2 - gap1) * cpFrac

      // Leader is at 'prog' position, others are offset by gap
      const gapOffset = gap * 0.01 // scale gap to angle offset
      const angle = goalAngle + Math.PI * 2 * prog - gapOffset

      // Spread horses across track width
      const lane = (i % 4) * 6
      const hrx = rx + lane - 10
      const hry = ry + lane - 10

      const hx = cx + hrx * Math.cos(angle)
      const hy = cy + hry * Math.sin(angle)

      // Horse dot
      const gateColor = GATE_COLORS[Math.floor(((horse.gate_number || i + 1) - 1) / 2)] || '#999'
      ctx.beginPath()
      ctx.arc(hx, hy, 14, 0, Math.PI * 2)
      ctx.fillStyle = gateColor
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()

      // Gate number
      ctx.fillStyle = gateColor === '#000' || gateColor === '#e74c3c' ? '#fff' : '#000'
      ctx.font = 'bold 11px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(String(horse.gate_number || i + 1), hx, hy)
    })

    // Remaining distance
    const remaining = Math.max(0, Math.round(2200 * (1 - prog)))
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 20px sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.fillText(`残り ${remaining}m`, 20, 20)

    // Speed indicator
    ctx.font = '14px sans-serif'
    ctx.fillStyle = '#aaa'
    ctx.fillText(`${speed}x`, 20, 48)
  }, [speed])

  // Animation loop
  useEffect(() => {
    if (!playing || !data || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const duration = 15000 / speed // 15 seconds at 1x
    startTimeRef.current = performance.now() - progress * duration

    const animate = (now: number) => {
      const elapsed = now - startTimeRef.current
      const prog = Math.min(elapsed / duration, 1)
      setProgress(prog)

      drawTrack(ctx, canvas.width, canvas.height, data.representative_race.horses, prog)

      if (prog < 1) {
        animRef.current = requestAnimationFrame(animate)
      } else {
        setPlaying(false)
      }
    }

    animRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animRef.current)
  }, [playing, data, speed, drawTrack, progress])

  // Draw initial frame when data loads
  useEffect(() => {
    if (!data || !canvasRef.current) return
    const ctx = canvasRef.current.getContext('2d')
    if (ctx) drawTrack(ctx, canvasRef.current.width, canvasRef.current.height, data.representative_race.horses, progress)
  }, [data, drawTrack, progress])

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={runSimulation}
          disabled={loading}
          className="bg-rose-600 hover:bg-rose-700 disabled:bg-gray-700 text-white px-6 py-2 rounded-lg font-medium"
        >
          {loading ? 'シミュレーション中...' : 'シミュレーション実行 (1000回)'}
        </button>
      </div>

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Canvas */}
          <div className="lg:col-span-2 bg-gray-900 rounded-xl p-4">
            <canvas ref={canvasRef} width={700} height={450} className="w-full rounded-lg" />

            {/* Controls */}
            <div className="flex items-center gap-4 mt-4">
              <button
                onClick={() => { setPlaying(!playing) }}
                className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded text-sm"
              >
                {playing ? '⏸ 一時停止' : '▶ 再生'}
              </button>
              <button
                onClick={() => { setProgress(0); setPlaying(false) }}
                className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded text-sm"
              >
                ⏮ 最初から
              </button>
              {[1, 2, 4].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-3 py-1 rounded text-sm ${speed === s ? 'bg-rose-600' : 'bg-gray-800 hover:bg-gray-700'}`}
                >
                  {s}x
                </button>
              ))}

              {/* Progress bar */}
              <div className="flex-1 bg-gray-800 rounded-full h-2 cursor-pointer"
                onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect()
                  setProgress((e.clientX - rect.left) / rect.width)
                  setPlaying(false)
                }}
              >
                <div className="bg-rose-500 h-2 rounded-full transition-none" style={{ width: `${progress * 100}%` }} />
              </div>
            </div>
          </div>

          {/* Sidebar: Rankings + Stats */}
          <div className="space-y-4">
            {/* Live Rankings */}
            <div className="bg-gray-900 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-400 mb-3">着順 (シミュレーション結果)</h3>
              <div className="space-y-1">
                {data.representative_race.horses.map((h, i) => (
                  <div key={h.horse_name} className={`flex items-center gap-2 text-sm py-1 px-2 rounded ${i < 3 ? 'bg-gray-800/50' : ''}`}>
                    <span className={`w-6 font-bold ${i === 0 ? 'text-rose-400' : i < 3 ? 'text-blue-300' : 'text-gray-500'}`}>
                      {h.finish_position}
                    </span>
                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                      style={{ backgroundColor: h.color, color: h.color === '#000000' || h.color === '#e74c3c' ? '#fff' : '#000' }}
                    >
                      {h.gate_number}
                    </span>
                    <span className="flex-1 truncate">{h.horse_name}</span>
                    <span className="text-gray-500 font-mono text-xs">{h.finish_time}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Win counts */}
            <div className="bg-gray-900 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-400 mb-3">
                1着回数 / {data.summary.num_simulations}回
              </h3>
              {Object.entries(data.summary.win_counts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([name, count]) => (
                  <div key={name} className="flex items-center gap-2 text-sm py-1">
                    <span className="w-28 truncate">{name}</span>
                    <div className="flex-1 bg-gray-800 rounded-full h-2">
                      <div className="bg-rose-500 h-2 rounded-full"
                        style={{ width: `${(count / data.summary.num_simulations) * 400}%` }} />
                    </div>
                    <span className="w-16 text-right font-mono text-xs">{count}回 ({((count / data.summary.num_simulations) * 100).toFixed(1)}%)</span>
                  </div>
                ))}
            </div>

            {/* Pace */}
            <div className="bg-gray-900 rounded-xl p-4 text-sm">
              <h3 className="text-gray-400 font-semibold mb-2">ペース</h3>
              <div className="flex gap-4">
                <div>前半1000m: <span className="font-mono font-bold">{data.representative_race.pace.first_1000m}秒</span></div>
                <div>上がり3F: <span className="font-mono font-bold">{data.representative_race.pace.last_600m}秒</span></div>
                <div className={`font-bold ${data.representative_race.pace.type === 'H' ? 'text-rose-400' : data.representative_race.pace.type === 'S' ? 'text-blue-400' : 'text-emerald-400'}`}>
                  {data.representative_race.pace.type === 'H' ? 'ハイペース' : data.representative_race.pace.type === 'S' ? 'スローペース' : 'ミドル'}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {!data && !loading && (
        <div className="text-center py-20 text-gray-600">
          「シミュレーション実行」ボタンを押してレース展開を生成してください
        </div>
      )}
    </div>
  )
}
