type Props = { onSignOut: () => void }

function ClubFinances({ onSignOut }: Props) {
  return (
    <section>
      <h2>Club Finances</h2>
      <button onClick={onSignOut}>Sign out</button>
    </section>
  )
}

export default ClubFinances
