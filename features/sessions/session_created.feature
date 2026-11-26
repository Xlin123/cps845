# CPS845 Project 1, topic CM. Use case: Session Created (actor Coach).
# Decisions (docs/decisions.md, 2026-11-25): "Session collisions and
# overwrite", "Coaches set each session's price and length", "Session
# notices are queued, and Coaches send them", "Coaches change only future
# sessions", "Coaches share one calendar"; "Sign-in, field rules, bounds and
# sending" item 5 (bounds).

Feature: Session Created

  A Coach chooses Create Session and enters a date, a start time, a length
  and a price. The length defaults to 60 minutes and is 15 to 480 minutes.
  The price is 0.00 to 1,000.00 dollars. The session must start in the
  future and within 365 days. Creating it queues a session-created notice,
  which a Coach sends from Notify Members, and returns the Coach to the main
  menu.

  The club has one venue, so a session collides with any session that has
  not ended and overlaps it. Sessions that only touch, one ending as the
  next starts, do not collide. On a collision the Coach is asked to
  overwrite or cancel. Overwrite deletes every colliding session exactly as
  Session Deleted does, then creates the new one, in one transaction. It is
  offered only when every colliding session is still in the future; a
  collision with a session in progress can only be cancelled. Any Coach can
  overwrite any Coach's session.

  A session records the Coach who created it, taken from the signed-in
  profile.

  Versions. The app ships as one version: the API and the frontend are
  built into one image, so there is no older client to support.

  Threats. Each class has a tagged scenario below, except denial of
  service.
  Races (@race): two Coaches creating overlapping sessions at once leave
  one; an overwrite names the sessions it was shown, and is asked again if
  they have changed.
  Replay (@replay): a create request sent again collides with the session
  it created, so it never makes a duplicate.
  Denial of service: only Coaches can create sessions, and every field is
  bounded; no scenario.
  Forgery and impersonation (@forgery, @impersonation): only a Coach can
  create a session, and the creator is always the signed-in Coach.

  Background:
    Given "colm@example.com" is a Coach named Colm
    And "cora@example.com" is a Coach named Cora
    And "cara@example.com" is a confirmed Customer named Cara
    And the time is 2026-12-01 09:00
    And Colm is signed in

  Scenario: A Coach creates a session and a session-created notice is queued
    When Colm creates a session on 2026-12-03 at 18:00 for 60 minutes at 15.00
    Then the session on 2026-12-03 18:00 to 19:00 exists with price 15.00, created by Colm
    And a session-created notice for it is queued
    And Colm is back at the main menu

  Scenario: A session's length defaults to 60 minutes
    When Colm opens Create Session
    Then the length is 60 minutes

  Scenario: Cancelling Create Session creates nothing
    When Colm opens Create Session, enters 2026-12-03 at 18:00 and cancels
    Then no session exists on 2026-12-03
    And no notice is queued

  Scenario: An overlapping session asks the Coach to overwrite or cancel
    Given a session exists on 2026-12-03 from 18:00 to 19:00
    When Colm creates a session on 2026-12-03 at 18:30 for 60 minutes at 15.00
    Then Colm is asked to overwrite the session on 2026-12-03 18:00 or cancel

  Scenario: Overwriting replaces the colliding session
    Given a session exists on 2026-12-03 from 18:00 to 19:00
    When Colm creates a session on 2026-12-03 at 18:30 for 60 minutes at 20.00 and chooses overwrite
    Then the session on 2026-12-03 18:00 no longer exists
    And the session on 2026-12-03 18:30 to 19:30 exists with price 20.00
    And the deletion of the 18:00 session is logged against Colm

  Scenario: Cancelling at the collision prompt changes nothing
    Given a session exists on 2026-12-03 from 18:00 to 19:00
    When Colm creates a session on 2026-12-03 at 18:30 for 60 minutes and cancels at the collision prompt
    Then only the session on 2026-12-03 18:00 exists that day
    And no notice is queued

  Scenario: Sessions that only touch do not collide
    Given a session exists on 2026-12-03 from 18:00 to 19:00
    When Colm creates a session on 2026-12-03 at 19:00 for 60 minutes at 15.00
    Then both sessions exist

  Scenario: A collision with a session in progress can only be cancelled
    Given a session exists on 2026-12-01 from 08:30 to 10:00
    When Colm creates a session on 2026-12-01 at 09:30 for 60 minutes
    Then Colm is told it collides with the session in progress and can only cancel

  Scenario: A Coach can overwrite another Coach's session
    Given Cora created a session on 2026-12-03 from 18:00 to 19:00
    When Colm creates a session on 2026-12-03 at 18:00 for 90 minutes and chooses overwrite
    Then Cora's session no longer exists
    And the deletion of Cora's session is logged against Colm

  Scenario Outline: A session outside the bounds is refused
    When Colm creates a session on <date> at <time> for <length> minutes at <price>
    Then Colm sees the error "<error>"
    And no session is created

    Examples:
      | date       | time  | length | price   | error                                       |
      | 2026-12-01 | 08:00 | 60     | 15.00   | A session must start in the future          |
      | 2027-12-02 | 18:00 | 60     | 15.00   | A session must start within 365 days        |
      | 2026-12-03 | 18:00 | 14     | 15.00   | A session lasts 15 to 480 minutes           |
      | 2026-12-03 | 18:00 | 481    | 15.00   | A session lasts 15 to 480 minutes           |
      | 2026-12-03 | 18:00 | 60     | -1.00   | A price is 0.00 to 1,000.00                 |
      | 2026-12-03 | 18:00 | 60     | 1000.01 | A price is 0.00 to 1,000.00                 |
      | 2026-12-03 | 18:00 | 60     | 15.005  | A price is 0.00 to 1,000.00                 |

  @race
  Scenario: Two overlapping sessions created at once leave one
    When Colm and Cora each create a session on 2026-12-03 at 18:00 at the same moment
    Then exactly one session exists on 2026-12-03 at 18:00
    And the other Coach is asked to overwrite it or cancel

  @race
  Scenario: An overwrite is asked again when the colliding sessions have changed
    Given a session exists on 2026-12-03 from 18:00 to 19:00
    And Colm is asked to overwrite it or cancel for a session at 18:30 for 90 minutes
    And Cora then creates a session on 2026-12-03 from 19:30 to 20:00
    When Colm chooses overwrite
    Then Colm is asked again, naming both the 18:00 and the 19:30 sessions
    And both sessions still exist

  @replay
  Scenario: A create request sent again does not make a duplicate
    Given Colm created a session on 2026-12-03 at 18:00 for 60 minutes
    When the same create request is sent again
    Then Colm is asked to overwrite the session on 2026-12-03 18:00 or cancel
    And exactly one session exists on 2026-12-03

  @forgery
  Scenario: A Customer cannot create a session
    Given Cara is signed in
    When she sends a request to create a session on 2026-12-03 at 18:00
    Then it is refused as not permitted
    And no session is created

  @impersonation
  Scenario: A session records the signed-in Coach, whatever the request names
    When Colm sends a create request for 2026-12-03 at 18:00 that names Cora as its creator
    Then the session on 2026-12-03 18:00 is created by Colm
