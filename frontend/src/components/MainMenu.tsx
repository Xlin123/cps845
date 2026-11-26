type Props = { onSignOut: () => void }

function MainMenu({ onSignOut }: Props) {
  return (
    <section>
      <h2>Main menu</h2>
      <button onClick={onSignOut}>Sign out</button>
    </section>
  )
}

export default MainMenu
