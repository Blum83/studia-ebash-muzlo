import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Config, type Job, type Params, type Track } from './api'
import { CreatePanel } from './CreatePanel'
import { Player } from './Player'
import { TrackList } from './TrackList'

export default function App() {
  const [view, setView] = useState<'create' | 'library'>('create')
  const [config, setConfig] = useState<Config | null>(null)
  const [tracks, setTracks] = useState<Track[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [current, setCurrent] = useState<Track | null>(null)
  const [playing, setPlaying] = useState(false)
  const [toggle, setToggle] = useState(0)
  const [draft, setDraft] = useState<Params | null>(null)
  const [offline, setOffline] = useState(false)
  const activeCount = useRef(0)

  const refresh = useCallback(async () => {
    try {
      const [c, j] = await Promise.all([api.config(), api.jobs()])
      const active = j.filter((x) => x.status !== 'error').length
      // A job left the active list -> it finished; reload the library.
      if (active < activeCount.current || tracks.length === 0) setTracks(await api.tracks())
      activeCount.current = active
      setConfig(c)
      setJobs(j)
      setOffline(false)
    } catch {
      setOffline(true)
    }
  }, [tracks.length])

  const busy = jobs.some((j) => j.status !== 'error') || !config?.engine_ready
  useEffect(() => {
    refresh()
  }, [refresh])
  useEffect(() => {
    const t = setInterval(refresh, busy ? 2000 : 10000)
    return () => clearInterval(t)
  }, [refresh, busy])

  const submitted = () => {
    activeCount.current += 1
    refresh()
  }

  const remix = async (p: Params) => {
    await api.generate(p)
    submitted()
  }

  const reuse = (p: Params) => {
    setDraft({ ...p })
    setView('create')
  }

  const del = async (t: Track) => {
    await api.deleteTrack(t.id)
    if (current?.id === t.id) setCurrent(null)
    setTracks(await api.tracks())
  }

  const play = (t: Track) => (current?.id === t.id ? setToggle((n) => n + 1) : setCurrent(t))

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="logo">songgen</div>
        <button className={view === 'create' ? 'nav on' : 'nav'} onClick={() => setView('create')}>
          ♫ Create
        </button>
        <button className={view === 'library' ? 'nav on' : 'nav'} onClick={() => setView('library')}>
          ▤ Library
        </button>
        <div className="status">
          {offline ? (
            <span className="dot red">Бэкенд недоступен</span>
          ) : config?.engine_error ? (
            <span className="dot red" title={config.engine_error}>Модель не загрузилась</span>
          ) : config?.engine_ready ? (
            <span className="dot green">Модель готова</span>
          ) : (
            <span className="dot yellow">Модель загружается…</span>
          )}
          <span className={config?.lyrics_enabled ? 'dot green' : 'dot grey'}>
            Claude {config?.lyrics_enabled ? 'подключён' : 'не подключён'}
          </span>
        </div>
      </nav>

      <main className={view === 'create' ? 'main two' : 'main'}>
        {view === 'create' && <CreatePanel config={config} draft={draft} onSubmitted={submitted} />}
        <TrackList
          tracks={tracks}
          jobs={jobs}
          current={current}
          playing={playing}
          onPlay={play}
          onRemix={remix}
          onReuse={reuse}
          onDelete={del}
          onDismiss={async (j) => {
            await api.dismissJob(j.id)
            refresh()
          }}
        />
      </main>

      <Player track={current} onPlayingChange={setPlaying} toggleSignal={toggle} />
    </div>
  )
}
