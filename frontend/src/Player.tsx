import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import type { Track } from './api'
import { coverStyle, fmt } from './util'

type Props = { track: Track | null; onPlayingChange: (playing: boolean) => void; toggleSignal: number }

export function Player({ track, onPlayingChange, toggleSignal }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const ws = useRef<WaveSurfer | null>(null)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    const w = WaveSurfer.create({
      container: el.current!,
      height: 40,
      waveColor: '#4a4a55',
      progressColor: '#f0f0f5',
      cursorColor: 'transparent',
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
    })
    w.on('timeupdate', setTime)
    w.on('play', () => setPlaying(true))
    w.on('pause', () => setPlaying(false))
    w.on('finish', () => setPlaying(false))
    ws.current = w
    return () => w.destroy()
  }, [])

  useEffect(() => onPlayingChange(playing), [playing, onPlayingChange])

  useEffect(() => {
    if (!track || !ws.current) return
    setTime(0)
    ws.current.load(track.mp3_url).then(() => ws.current?.play(), () => {})
  }, [track])

  // Clicking the current track's cover in the list toggles play/pause.
  useEffect(() => {
    if (toggleSignal) ws.current?.playPause()
  }, [toggleSignal])

  return (
    <footer className={track ? 'player' : 'player hidden'}>
      {track && <div className="cover small" style={coverStyle(track.id)} />}
      <div className="p-info">
        <div className="title">{track?.title ?? ''}</div>
        <div className="caption">{track ? `${fmt(time)} / ${fmt(track.duration)}` : ''}</div>
      </div>
      <button className="play" onClick={() => ws.current?.playPause()} aria-label="Play/Pause">
        {playing ? '❚❚' : '▶'}
      </button>
      <div className="wave" ref={el} />
    </footer>
  )
}
