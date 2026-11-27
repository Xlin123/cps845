# CPS845 Project 1, topic CM. Use case: Session Deleted (actor Coach).
# Decisions (docs/decisions.md, 2026-11-25): "Session notices are queued,
# and Coaches send them", "Coaches change only future sessions", "Coaches
# share one calendar"; "Sign-in, field rules, bounds and sending" item 9
# (deleting sessions).

Feature: Session Deleted

  A Coach chooses Delete Session and sees a table of the sessions that have
  not started, each of which can be selected or deselected. Pressing Delete
  asks "Are you sure you want to delete these?" and lists the selected
  sessions. Yes deletes them all and returns to the main menu; No returns to
  the main menu and deletes nothing. Cancel on the table also deletes
  nothing. A delete takes at most 100 sessions.

  Deleting is all or nothing. If any selected session has started or no
  longer exists when the Coach answers Yes, nothing is deleted and the Coach
  is told which.

  Notices. A deleted session whose session-created notice has not been sent
  takes that notice with it, and no session-deleted notice is queued, as no
  one heard of the session. A deleted session whose session-created notice
  was sent queues a session-deleted notice. Each deletion is logged with the
  session, the Coach who deleted it and when. Any Coach can delete any
  Coach's session.

  Versions. The app ships as one version: the API and the frontend are
  built into one image, so there is no older client to support.

  Threats. Each class has a tagged scenario below.
  Races (@race): a session that starts between being selected and the Yes
  is not deleted; two Coaches deleting one session at once delete it once.
  Replay (@replay): a delete request sent again finds the session gone and
  changes nothing.
  Denial of service (@dos): a delete takes at most 100 sessions.
  Forgery and impersonation (@forgery, @impersonation): only a Coach can
  delete, and the log names the signed-in Coach.

  Background:
    Given "colm@example.com" is a Coach named Colm
    And "cora@example.com" is a Coach named Cora
    And "cara@example.com" is a confirmed Customer named Cara
    And the time is 2026-12-01 09:00
    And sessions exist on 2026-12-03 at 18:00 and on 2026-12-05 at 18:00
    And Colm is signed in

  Scenario: The delete table lists only sessions that have not started
    Given a session exists on 2026-12-01 from 08:30 to 10:00
    And a session ended on 2026-11-28
    When Colm opens Delete Session
    Then the table lists the sessions on 2026-12-03 and 2026-12-05 only

  Scenario: Confirming deletes every selected session
    When Colm selects the sessions on 2026-12-03 and 2026-12-05 and presses Delete
    Then he is asked "Are you sure you want to delete these?" with both sessions listed
    When he answers Yes
    Then neither session exists
    And each deletion is logged against Colm
    And Colm is back at the main menu

  Scenario: Answering No deletes nothing and returns to the main menu
    When Colm selects the session on 2026-12-03, presses Delete and answers No
    Then the session on 2026-12-03 still exists
    And Colm is back at the main menu

  Scenario: Cancelling the delete table deletes nothing
    When Colm opens Delete Session and cancels
    Then both sessions still exist

  Scenario: Deleting a session whose notice is unsent drops the notice
    Given the session-created notice for 2026-12-03 has not been sent
    When Colm deletes the session on 2026-12-03
    Then no notice about the 2026-12-03 session is queued

  Scenario: Deleting a session whose notice was sent queues a session-deleted notice
    Given the session-created notice for 2026-12-03 has been sent
    When Colm deletes the session on 2026-12-03
    Then a session-deleted notice for the 2026-12-03 session is queued

  Scenario: A Coach can delete another Coach's session
    Given Cora created the session on 2026-12-05
    When Colm deletes the session on 2026-12-05
    Then it no longer exists
    And the deletion is logged against Colm

  @race
  Scenario: A selected session that starts before the Yes stops the whole delete
    Given Colm has selected the sessions on 2026-12-03 and 2026-12-05 and pressed Delete
    And the 2026-12-03 session starts before he answers
    When he answers Yes
    Then he is told the 2026-12-03 session has started and nothing was deleted
    And both sessions still exist

  @race
  Scenario: Two Coaches deleting one session at once delete it once
    When Colm and Cora each confirm deleting the session on 2026-12-03 at the same moment
    Then the session on 2026-12-03 no longer exists
    And exactly one deletion is logged
    And the other Coach is told the session no longer exists

  @replay
  Scenario: A delete request sent again changes nothing
    Given Colm deleted the session on 2026-12-03
    When the same delete request is sent again
    Then he is told the 2026-12-03 session no longer exists
    And the session on 2026-12-05 still exists
    And no further deletion is logged

  @dos
  Scenario: A delete of more than 100 sessions is refused
    Given 101 future sessions exist
    When Colm sends a request to delete all 101
    Then it is refused with "Delete at most 100 sessions at a time"
    And no session is deleted

  @forgery
  Scenario: A Customer cannot delete a session
    Given Cara is signed in
    When she sends a request to delete the session on 2026-12-03
    Then it is refused as not permitted
    And the session on 2026-12-03 still exists

  @impersonation
  Scenario: The deletion log names the signed-in Coach, whatever the request names
    When Colm sends a delete request for the 2026-12-03 session that names Cora as the deleter
    Then the deletion is logged against Colm
