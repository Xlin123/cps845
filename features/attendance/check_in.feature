# CPS845 Project 1, topic CM. Use case: Check In (actors Customer, Coach).
# Decisions (docs/decisions.md, 2026-11-25): "Check In is to the session in
# progress", "Coaches set each session's price and length".

Feature: Check In

  A Customer or Coach presses Check In on the main menu to say they have
  made it to a session. The check-in is to the session in progress: from 15
  minutes before its start to its end. With no session in that window, the
  check-in is refused with a message. The club has one venue and sessions
  never overlap, so at most one session is in progress.

  A check-in records the member, the session and the time, and adds one to
  the member's sessions attended. A Customer's check-in makes them owe the
  session's price; a Coach's costs nothing. Each member checks in to a
  session once. The Treasurer has no Check In.

  Versions. The app ships as one version: the API and the frontend are
  built into one image, so there is no older client to support.

  Threats. Each class has a tagged scenario below, except denial of
  service.
  Races (@race): two check-ins by one member at once record one.
  Replay (@replay): a check-in sent again is refused as already checked in.
  Denial of service: one check-in per member per session bounds what a
  member can record; no scenario.
  Forgery and impersonation (@forgery, @impersonation): a check-in is always
  for the signed-in member, and the Treasurer cannot check in.

  Background:
    Given "cara@example.com" is a confirmed Customer named Cara
    And "colm@example.com" is a Coach named Colm
    And a session exists on 2026-12-03 from 18:00 to 19:00 at 15.00

  Scenario: A Customer checks in to the session in progress
    Given the time is 2026-12-03 18:05
    And Cara is signed in with 4 sessions attended
    When she presses Check In
    Then she is checked in to the 2026-12-03 18:00 session at 18:05
    And she has 5 sessions attended
    And she owes 15.00 for the 2026-12-03 session

  Scenario: Check-in opens 15 minutes before the start
    Given the time is 2026-12-03 17:45
    And Cara is signed in
    When she presses Check In
    Then she is checked in to the 2026-12-03 18:00 session

  Scenario Outline: Check-in with no session in progress is refused
    Given the time is <time>
    And Cara is signed in
    When she presses Check In
    Then she sees "There is no session to check in to right now"
    And nothing is recorded

    Examples:
      | time             |
      | 2026-12-03 17:44 |
      | 2026-12-03 19:00 |
      | 2026-12-04 18:05 |

  Scenario: A Coach checks in and owes nothing
    Given the time is 2026-12-03 17:50
    And Colm is signed in
    When he presses Check In
    Then he is checked in to the 2026-12-03 18:00 session
    And he owes nothing for it

  @replay
  Scenario: Checking in twice to one session is refused
    Given the time is 2026-12-03 18:05
    And Cara is signed in and has checked in to the 2026-12-03 session
    When the same check-in is sent again
    Then she sees "You have already checked in to this session"
    And she owes 15.00 for the 2026-12-03 session, once

  @race
  Scenario: Two check-ins by one member at once record one
    Given the time is 2026-12-03 18:05
    And Cara is signed in
    When two check-ins from Cara arrive at the same moment
    Then exactly one check-in is recorded for Cara on the 2026-12-03 session

  @impersonation
  Scenario: A check-in is for the signed-in member, whatever the request names
    Given the time is 2026-12-03 18:05
    And Cara is signed in
    When she sends a check-in that names Colm
    Then Cara is checked in
    And Colm is not

  @forgery
  Scenario: The Treasurer cannot check in
    Given the time is 2026-12-03 18:05
    And "tess@example.com" is the Treasurer and is signed in
    When she sends a check-in request
    Then it is refused as not permitted
    And nothing is recorded
