import { useState, type FormEvent } from 'react'
import { createSession, SessionCollisionError, type SessionCollision } from '../api'

type Props = { onDone: () => void }

function CreateSession({ onDone }: Props) {
  const [date, setDate] = useState('')
  const [startTime, setStartTime] = useState('')
  const [lengthMinutes, setLengthMinutes] = useState(60)
  const [price, setPrice] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [collisions, setCollisions] = useState<SessionCollision[] | null>(null)
  const [canOverwrite, setCanOverwrite] = useState(false)

  async function submit(overwriteIds?: number[]) {
    setError(null)
    try {
      await createSession({
        date,
        startTime,
        lengthMinutes,
        price: Number(price),
        overwriteIds,
      })
      onDone()
    } catch (err) {
      if (err instanceof SessionCollisionError) {
        setCollisions(err.collisions)
        setCanOverwrite(err.canOverwrite)
        setError(err.message)
      } else {
        setError(err instanceof Error ? err.message : 'Could not create the session')
      }
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    void submit()
  }

  function handleOverwrite() {
    void submit(collisions?.map((collision) => collision.id))
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Create Session</h2>
      <label>
        Date
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <label>
        Start time
        <input
          type="time"
          value={startTime}
          onChange={(e) => setStartTime(e.target.value)}
          required
        />
      </label>
      <label>
        Length (minutes)
        <input
          type="number"
          value={lengthMinutes}
          onChange={(e) => setLengthMinutes(Number(e.target.value))}
          required
        />
      </label>
      <label>
        Price
        <input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} required />
      </label>
      <button type="submit">Create</button>
      <button type="button" onClick={onDone}>
        Cancel
      </button>
      {error && <p role="alert">{error}</p>}
      {collisions && canOverwrite && (
        <button type="button" onClick={handleOverwrite}>
          Overwrite
        </button>
      )}
    </form>
  )
}

export default CreateSession
