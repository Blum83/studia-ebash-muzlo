import { useEffect, useState } from 'react'
import { api, type Config, type Params } from './api'
import { fmt } from './util'

const EMPTY: Params = {
  title: '',
  idea: '',
  caption: '',
  lyrics: '',
  duration: 120,
  seed: -1,
  instrumental: false,
  vocal_language: 'ru',
}

const STYLE_CHIPS = [
  'russian hip hop', 'pop punk', 'synthwave', 'indie rock', 'lofi chill', 'trap',
  'folk', 'acoustic', 'melancholic', 'energetic',
]

// ACE-Step has no voice presets; the voice is described in the caption.
const VOICE_CHIPS: [string, string][] = [
  ['Женский воздушный', 'female vocal, breathy, airy, soft'],
  ['Женский мощный', 'female vocal, powerful belting, soulful'],
  ['Женский рэп', 'female rap, fast flow, confident'],
  ['Мужской баритон', 'male vocal, deep baritone, warm'],
  ['Мужской хриплый', 'male vocal, raspy, smoky, gritty'],
  ['Мужской высокий', 'male vocal, high tenor, bright, falsetto'],
  ['Мужской рэп', 'male rap, laid-back flow, charismatic'],
  ['Дуэт М+Ж', 'male-female duet, call and response'],
  ['Хор', 'choir, gang vocals, layered harmonies'],
  ['Шёпот', 'whispered vocal, intimate, close-mic'],
  ['Автотюн', 'autotune vocal, melodic'],
]

const LANGS = [
  ['ru', 'Русский'],
  ['uk', 'Українська'],
  ['en', 'English'],
  ['unknown', 'Авто'],
]

type Props = {
  config: Config | null
  draft: Params | null // "Reuse" from the library loads here
  onSubmitted: () => void
}

export function CreatePanel({ config, draft, onSubmitted }: Props) {
  const [mode, setMode] = useState<'simple' | 'advanced'>('simple')
  const [p, setP] = useState<Params>(EMPTY)
  const [open, setOpen] = useState({ lyrics: true, styles: true, more: false })
  const [busy, setBusy] = useState<'' | 'writing' | 'submitting'>('')
  const [simpleVoice, setSimpleVoice] = useState('')
  const [error, setError] = useState('')
  const claude = !!config?.lyrics_enabled

  useEffect(() => {
    if (draft) {
      setP(draft)
      setMode('advanced')
    }
  }, [draft])

  const set = <K extends keyof Params>(k: K, v: Params[K]) => setP((x) => ({ ...x, [k]: v }))

  const addTags = (tags: string) =>
    set('caption', p.caption.trim() ? `${p.caption.trim()}, ${tags}` : tags)

  // One voice at a time: picking a voice replaces the previously picked one.
  const toggleVoice = (tags: string) => {
    let c = p.caption
    const wasOn = c.includes(tags)
    for (const [, t] of VOICE_CHIPS) c = c.replace(t, '')
    c = c.split(',').map((s) => s.trim()).filter(Boolean).join(', ')
    set('caption', wasOn ? c : c ? `${c}, ${tags}` : tags)
  }

  async function write(base: Params): Promise<Params> {
    setBusy('writing')
    const song = await api.writeSong({
      idea: base.idea,
      style: base.caption,
      lyrics: '',
      language: base.vocal_language,
      instrumental: base.instrumental,
      duration: base.duration,
    })
    return { ...base, title: base.title || song.title, caption: song.caption, lyrics: song.lyrics }
  }

  async function run(fn: () => Promise<void>) {
    setError('')
    try {
      await fn()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy('')
    }
  }

  const onWrite = () => run(async () => setP(await write(p)))

  const onCreate = () =>
    run(async () => {
      let params = p
      if (mode === 'simple') {
        if (!p.idea.trim()) throw new Error('Опиши песню')
        params = await write({ ...p, caption: simpleVoice, lyrics: '', title: '' })
        setP(params) // so Advanced shows what was generated
      } else if (!p.caption.trim()) {
        throw new Error('Заполни стиль')
      }
      setBusy('submitting')
      await api.generate(params)
      onSubmitted()
    })

  return (
    <section className="create">
      <div className="tabs">
        <button className={mode === 'simple' ? 'on' : ''} onClick={() => setMode('simple')}>
          Simple
        </button>
        <button className={mode === 'advanced' ? 'on' : ''} onClick={() => setMode('advanced')}>
          Advanced
        </button>
        <span className="badge">{config?.engine ?? '…'} 1.5</span>
      </div>

      {mode === 'simple' ? (
        <div className="card">
          <label className="label">Описание песни</label>
          <textarea
            rows={6}
            placeholder="песня про ночную электричку и недосып, в стиле русского инди"
            value={p.idea}
            onChange={(e) => set('idea', e.target.value)}
          />
          <span className="label">Голос</span>
          <div className="chips">
            <button className={simpleVoice ? 'chip' : 'chip on'} onClick={() => setSimpleVoice('')}>
              Авто
            </button>
            {VOICE_CHIPS.map(([name, tags]) => (
              <button
                key={name}
                className={simpleVoice === tags ? 'chip on' : 'chip'}
                title={tags}
                onClick={() => setSimpleVoice(tags)}
              >
                {name}
              </button>
            ))}
          </div>
          {!claude && (
            <p className="hint">
              Claude не подключён — залогинься в <code>claude</code> или задай ANTHROPIC_API_KEY, либо
              используй Advanced.
            </p>
          )}
        </div>
      ) : (
        <>
          <Section title="Lyrics" open={open.lyrics} toggle={() => setOpen({ ...open, lyrics: !open.lyrics })}>
            <input
              placeholder="Идея для Claude (необязательно)"
              value={p.idea}
              onChange={(e) => set('idea', e.target.value)}
            />
            <textarea
              rows={12}
              placeholder={'[Verse]\nТекст куплета…\n\n[Chorus]\nПрипев…'}
              value={p.lyrics}
              disabled={p.instrumental}
              onChange={(e) => set('lyrics', e.target.value)}
            />
            {claude && (
              <button className="ghost" disabled={!!busy} onClick={onWrite}>
                {busy === 'writing' ? 'Claude пишет…' : '✨ Написать с Claude'}
              </button>
            )}
          </Section>

          <Section title="Styles" open={open.styles} toggle={() => setOpen({ ...open, styles: !open.styles })}>
            <textarea
              rows={3}
              placeholder="russian hip hop, raspy male vocal, funky boom bap, 95 bpm"
              value={p.caption}
              onChange={(e) => set('caption', e.target.value)}
            />
            <div className="chips">
              {STYLE_CHIPS.map((c) => (
                <button key={c} className="chip" onClick={() => addTags(c)}>
                  {c}
                </button>
              ))}
            </div>
            <span className="label">Голос</span>
            <div className="chips">
              {VOICE_CHIPS.map(([name, tags]) => (
                <button
                  key={name}
                  className={p.caption.includes(tags) ? 'chip on' : 'chip'}
                  title={tags}
                  onClick={() => toggleVoice(tags)}
                >
                  {name}
                </button>
              ))}
            </div>
          </Section>
        </>
      )}

      <Section title="More Options" open={open.more} toggle={() => setOpen({ ...open, more: !open.more })}>
        <div className="row">
          <label className="label">Длительность: {fmt(p.duration)}</label>
          <input
            type="range"
            min={10}
            max={600}
            step={5}
            value={p.duration}
            onChange={(e) => set('duration', Number(e.target.value))}
          />
        </div>
        <div className="grid2">
          <label>
            <span className="label">Язык вокала</span>
            <select value={p.vocal_language} onChange={(e) => set('vocal_language', e.target.value)}>
              {LANGS.map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="label">Seed (-1 = случайный)</span>
            <input
              type="number"
              min={-1}
              value={p.seed}
              onChange={(e) => set('seed', Math.max(-1, Math.trunc(Number(e.target.value) || 0)))}
            />
          </label>
        </div>
        <label className="toggle">
          <input
            type="checkbox"
            checked={p.instrumental}
            onChange={(e) => set('instrumental', e.target.checked)}
          />
          Инструментал (без вокала)
        </label>
      </Section>

      {mode === 'advanced' && (
        <div className="card">
          <input
            placeholder="♪ Название (необязательно — возьмётся из припева)"
            value={p.title}
            onChange={(e) => set('title', e.target.value)}
          />
        </div>
      )}

      {error && <p className="error">{error}</p>}
      <button
        className="create-btn"
        disabled={!!busy || (mode === 'simple' && !claude)}
        onClick={onCreate}
      >
        {busy === 'writing' ? 'Claude пишет текст…' : busy === 'submitting' ? 'Отправляю…' : '♫ Create'}
      </button>
    </section>
  )
}

function Section(props: { title: string; open: boolean; toggle: () => void; children: React.ReactNode }) {
  return (
    <div className="card">
      <button className="section-head" onClick={props.toggle} aria-expanded={props.open}>
        <span className={props.open ? 'caret open' : 'caret'}>›</span> {props.title}
      </button>
      {props.open && <div className="section-body">{props.children}</div>}
    </div>
  )
}
