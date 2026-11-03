import { useState } from 'react'
import type { Job, Params, Track } from './api'
import { coverStyle, fmt } from './util'

type Props = {
  tracks: Track[]
  jobs: Job[]
  current: Track | null
  playing: boolean
  onPlay: (t: Track) => void
  onRemix: (p: Params) => void
  onReuse: (p: Params) => void
  onDelete: (t: Track) => void
  onDismiss: (j: Job) => void
}

export function TrackList(props: Props) {
  const [q, setQ] = useState('')
  const [menu, setMenu] = useState<string | null>(null)
  const needle = q.trim().toLowerCase()
  const shown = props.tracks.filter(
    (t) => !needle || `${t.title} ${t.caption} ${t.lyrics}`.toLowerCase().includes(needle),
  )

  const groups: [string, Track[]][] = []
  for (const t of shown) {
    const day = dayLabel(t.created_at)
    const last = groups[groups.length - 1]
    if (last?.[0] === day) last[1].push(t)
    else groups.push([day, [t]])
  }

  return (
    <section className="library" onClick={() => setMenu(null)}>
      <div className="lib-head">
        <input
          className="search"
          placeholder="🔍 Поиск по названию, стилю, тексту"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="count">{props.tracks.length} треков</span>
      </div>

      {props.jobs.length > 0 && <h3 className="day">В работе</h3>}
      {props.jobs.map((j) => (
        <div key={j.id} className={`track pending ${j.status}`}>
          <div className="cover" style={coverStyle(j.id)}>
            {j.status === 'error' ? <span className="cover-icon">!</span> : <span className="spinner" />}
          </div>
          <div className="info">
            <div className="title">{j.params.title || j.params.idea || 'Без названия'}</div>
            <div className="caption">
              {j.status === 'error'
                ? `Ошибка: ${j.error}`
                : j.status === 'running'
                  ? `Генерируется… (${fmt(j.params.duration)})`
                  : j.position > 0
                    ? `В очереди, перед тобой: ${j.position}`
                    : 'В очереди'}
            </div>
          </div>
          {j.status === 'error' && (
            <div className="actions">
              <button className="pill" onClick={() => props.onReuse(j.params)}>Исправить</button>
              <button className="icon" title="Убрать" onClick={() => props.onDismiss(j)}>✕</button>
            </div>
          )}
        </div>
      ))}

      {groups.map(([day, list]) => (
        <div key={day}>
          <h3 className="day">{day}</h3>
          {list.map((t) => {
            const isCur = props.current?.id === t.id
            return (
              <div key={t.id} className={isCur ? 'track current' : 'track'}>
                <button className="cover" style={coverStyle(t.id)} onClick={() => props.onPlay(t)} title="Play">
                  <span className="cover-icon">{isCur && props.playing ? '❚❚' : '▶'}</span>
                  <span className="dur">{fmt(t.duration)}</span>
                </button>
                <div className="info">
                  <div className="title">
                    {t.title} <span className="tag">{t.params.vocal_language.toUpperCase()}</span>
                    {t.meta.bpm ? <span className="tag">{t.meta.bpm} BPM</span> : null}
                    {t.meta.keyscale ? <span className="tag">{t.meta.keyscale}</span> : null}
                  </div>
                  <div className="caption" title={t.caption}>{t.caption}</div>
                </div>
                <div className="actions" onClick={(e) => e.stopPropagation()}>
                  <button className="pill" title="Те же настройки, новый seed" onClick={() => props.onRemix({ ...t.params, seed: -1 })}>
                    ⟳ Remix
                  </button>
                  <a className="icon" href={t.mp3_url} download={`${t.title}.mp3`} title="Скачать MP3">⤓</a>
                  <div className="menu-wrap">
                    <button className="icon" onClick={() => setMenu(menu === t.id ? null : t.id)}>⋯</button>
                    {menu === t.id && (
                      <div className="menu">
                        <button onClick={() => props.onReuse(t.params)}>Открыть в редакторе</button>
                        <button onClick={() => props.onRemix({ ...t.params, seed: t.seed })}>
                          Повторить точно (seed {t.seed})
                        </button>
                        <a href={t.wav_url} download={`${t.title}.wav`}>Скачать WAV</a>
                        <button
                          className="danger"
                          onClick={() => confirmDelete(t) && props.onDelete(t)}
                        >
                          Удалить
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ))}

      {props.tracks.length === 0 && props.jobs.length === 0 && (
        <p className="empty">Пока пусто. Опиши песню слева и нажми Create.</p>
      )}
    </section>
  )
}

function confirmDelete(t: Track) {
  return window.confirm(`Удалить «${t.title}»? Файлы будут стёрты.`)
}

function dayLabel(iso: string) {
  const d = new Date(iso)
  const today = new Date()
  const y = new Date()
  y.setDate(today.getDate() - 1)
  if (d.toDateString() === today.toDateString()) return 'Сегодня'
  if (d.toDateString() === y.toDateString()) return 'Вчера'
  return d.toLocaleDateString('ru', { weekday: 'long', day: 'numeric', month: 'long' })
}
