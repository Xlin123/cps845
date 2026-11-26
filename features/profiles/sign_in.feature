# CPS845 Project 1, topic CM. Not a use case of its own: Club Finances
# starts "when the treasurer logs into the app", and Notify Members needs a
# signed-in user's permissions. Decisions (docs/decisions.md): "Roles and
# accounts" (2026-11-25), "Sign-in, field rules, bounds and sending" items 1
# (signing in) and 4 (throttling).

Feature: Sign In

  A member signs in with the email address and password of a confirmed
  profile. Signing in starts a session that lasts until the member signs
  out or for 7 days, whichever comes first. Every action is checked on the
  server against the signed-in profile's role; what the menu shows is never
  the check.

  After signing in, a Customer or Coach lands on the main menu and the
  Treasurer lands on Club Finances.

  The one Treasurer is created on the server with the command
  `cm create-treasurer`, which asks for the name, email address and
  password. The profile it creates is confirmed at once.

  Versions. The app ships as one version: the API and the frontend are
  built into one image, so there is no older client to support.

  Threats. Each class has a tagged scenario below, except races.
  Races: a request that crosses sign-out is answered either as signed in or
  as signed out, as each request reads its session once; no scenario.
  Replay (@replay): a session cookie stops working at sign-out and at
  expiry.
  Denial of service (@dos): failed sign-ins are throttled per client
  address, not per email address, so no one can lock a member out by
  guessing at their address.
  Forgery and impersonation (@forgery, @impersonation): a made-up session
  cookie is treated as signed out; a wrong password and an unknown address
  get the same answer; only one Treasurer can exist.

  Background:
    Given "cara@example.com" has a confirmed Customer profile with password "correct horse battery"
    And the time is 2026-12-01 09:00

  Scenario: A confirmed Customer signs in and lands on the main menu
    When they sign in with "cara@example.com" and "correct horse battery"
    Then they see the main menu

  Scenario: The Treasurer signs in and lands on Club Finances
    Given "tess@example.com" is the Treasurer with password "treasurer passphrase"
    When they sign in with "tess@example.com" and "treasurer passphrase"
    Then they see Club Finances

  Scenario: A pending profile cannot sign in
    Given a visitor signed up with email "pat@example.com" and password "pending passphrase" and has not confirmed
    When they sign in with "pat@example.com" and "pending passphrase"
    Then they see the error "Confirm your email address before signing in"

  @impersonation
  Scenario: A wrong password and an unknown email address get the same refusal
    When someone signs in with "cara@example.com" and "wrong passphrase"
    And someone signs in with "nobody@example.com" and "wrong passphrase"
    Then both see the error "Email address or password is wrong"

  @replay
  Scenario: Signing out ends the session
    Given Cara is signed in
    When she signs out
    And a request is sent with the session cookie she had
    Then the request is treated as signed out

  @replay
  Scenario: A session expires 7 days after sign-in
    Given Cara signed in at 2026-12-01 09:00
    When she opens the main menu at 2026-12-08 09:01
    Then she is asked to sign in

  @forgery
  Scenario: A request with a made-up session cookie is treated as signed out
    When a request to the main menu carries a session cookie the server never issued
    Then the request is treated as signed out

  @dos
  Scenario: Failed sign-ins from one client address are throttled
    Given 10 sign-ins from one client address failed in the last 15 minutes
    When that address signs in with "cara@example.com" and "correct horse battery"
    Then it sees the error "Too many attempts. Try again later"

  Scenario: Sign-ins from another client address are not throttled
    Given 10 sign-ins from one client address failed in the last 15 minutes
    When another address signs in with "cara@example.com" and "correct horse battery"
    Then they see the main menu

  Scenario: The Treasurer is created with the server command
    Given no Treasurer exists
    When the server command creates the Treasurer "Tess Okafor" with email "tess@example.com"
    Then a confirmed Treasurer profile exists for "tess@example.com"

  @impersonation
  Scenario: A second Treasurer cannot be created
    Given "tess@example.com" is the Treasurer
    When the server command tries to create a Treasurer with email "mallory@example.com"
    Then it fails with "A Treasurer already exists"
    And no profile exists for "mallory@example.com"
