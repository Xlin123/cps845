# CPS845 Project 1, topic CM. Use case: Create Profile (actors Customer,
# Coach). Decisions (docs/decisions.md): "Roles and accounts" (2026-11-25),
# "Sign-in, field rules, bounds and sending" items 2 (profile fields), 3
# (confirmation links), 4 (throttling).

Feature: Create Profile

  A visitor creates a profile with their name, email address, phone number
  and password. The profile stays pending until the visitor follows the
  confirmation link emailed to them, and a pending profile cannot sign in.
  A link not followed within 4 days expires, and the pending profile is
  deleted.

  A new profile is a Customer's. A visitor who enters the club's coach code
  gets a Coach's profile instead. The coach code is set on the server; with
  none set, no Coach profile can be created. The Treasurer is never created
  here (see Sign In).

  Emails are written to the outbox table and the server log; no mail is
  sent.

  Field rules. A name is 1 to 100 characters. An email address is at most
  254 characters, has one "@" with text either side and a dot after it, and
  is compared without regard to case. A phone number holds 7 to 15 digits,
  with optional spaces, hyphens, brackets and a leading "+". A password is
  12 to 128 characters, with no other rule.

  Versions. The app ships as one version: the API and the frontend are
  built into one image, so there is no older client to support.

  Threats. Each class has a tagged scenario below.
  Races (@race): two sign-ups with one email address at once leave one
  profile.
  Replay (@replay): a confirmation link works once, and not after it
  expires.
  Denial of service (@dos): wrong coach codes from one client address are
  throttled, and pending profiles are swept after 4 days, so abandoned
  sign-ups do not pile up.
  Forgery and impersonation (@forgery, @impersonation): the role comes from
  the coach code, never from a role the request names. A sign-up with an
  address that already has a profile gets the same answer as any other and
  changes nothing, so sign-up neither reveals nor takes over a member's
  profile.

  Background:
    Given the club's coach code is "TEST-COACH-CODE"
    And the time is 2026-12-01 09:00

  Scenario: A visitor creates a Customer profile and is sent a confirmation link
    When a visitor signs up as "Cara Diaz" with email "cara@example.com", phone "416-555-0101" and password "correct horse battery"
    Then they are told to check their email for a confirmation link
    And a pending Customer profile exists for "cara@example.com"
    And the outbox holds one confirmation email to "cara@example.com"

  Scenario: Following the confirmation link activates the profile
    Given a visitor signed up with email "cara@example.com"
    When they follow the confirmation link in their email at 2026-12-02 09:00
    Then the profile for "cara@example.com" is confirmed
    And they can sign in with "cara@example.com"

  Scenario Outline: An improperly formatted email address is refused
    When a visitor signs up with email "<email>"
    Then they see the error "Enter a valid email address"
    And no profile is created

    Examples:
      | email               |
      | cara.example.com    |
      | cara@               |
      | @example.com        |
      | cara@example        |
      | cara@@example.com   |

  Scenario Outline: An invalid password is refused
    When a visitor signs up with a password of <length> characters
    Then they see the error "Use a password of 12 to 128 characters"
    And no profile is created

    Examples:
      | length |
      | 0      |
      | 11     |
      | 129    |

  Scenario Outline: An invalid phone number is refused
    When a visitor signs up with phone "<phone>"
    Then they see the error "Enter a phone number of 7 to 15 digits"
    And no profile is created

    Examples:
      | phone              |
      | 555-01             |
      | 1234567890123456   |
      | call me            |

  Scenario: A visitor with the coach code creates a Coach profile
    When a visitor signs up as "Colm Byrne" with email "colm@example.com" and coach code "TEST-COACH-CODE"
    Then a pending Coach profile exists for "colm@example.com"

  Scenario: A wrong coach code is refused and creates no profile
    When a visitor signs up with email "colm@example.com" and coach code "WRONG-CODE"
    Then they see the error "That coach code is not right"
    And no profile is created

  Scenario: With no coach code set, no Coach profile can be created
    Given the club has no coach code set
    When a visitor signs up with email "colm@example.com" and coach code "TEST-COACH-CODE"
    Then they see the error "That coach code is not right"
    And no profile is created

  @forgery
  Scenario: A sign-up that names a role still gets a Customer profile
    When a visitor sends a sign-up for "mallory@example.com" that names the role "Treasurer"
    Then a pending Customer profile exists for "mallory@example.com"

  @replay
  Scenario: A confirmation link works only once
    Given a visitor signed up with email "cara@example.com" and followed the confirmation link
    When the same link is followed again
    Then they see "This link has already been used or has expired"
    And the profile for "cara@example.com" is unchanged

  Scenario: An unconfirmed profile is deleted after 4 days
    Given a visitor signed up with email "cara@example.com" at 2026-12-01 09:00
    When the time is 2026-12-05 09:01 and the pending-profile sweep runs
    Then no profile exists for "cara@example.com"

  @replay
  Scenario: A confirmation link followed after 4 days is refused
    Given a visitor signed up with email "cara@example.com" at 2026-12-01 09:00
    And the pending-profile sweep has not run since
    When they follow the confirmation link at 2026-12-05 09:01
    Then they see "This link has already been used or has expired"
    And the profile for "cara@example.com" is not confirmed

  @impersonation
  Scenario: Signing up with a member's email address leaves their profile unchanged
    Given "cara@example.com" has a confirmed Customer profile
    When a visitor signs up with email "CARA@example.com" and password "a different passphrase"
    Then they are told to check their email for a confirmation link
    And the profile for "cara@example.com" keeps its password
    And no confirmation email is added to the outbox

  @impersonation
  Scenario: Signing up again with a pending email address changes nothing
    Given a visitor signed up with email "cara@example.com" and has not confirmed
    When another visitor signs up with email "cara@example.com" and password "a different passphrase"
    Then they are told to check their email for a confirmation link
    And the pending profile for "cara@example.com" keeps its password and its confirmation link

  @race
  Scenario: Two sign-ups with one email address at once create one profile
    When two visitors sign up with email "cara@example.com" at the same moment
    Then both are told to check their email for a confirmation link
    And exactly one pending profile exists for "cara@example.com"

  @dos
  Scenario: Wrong coach codes from one client address are throttled
    Given 10 sign-ups from one client address in the last 15 minutes had a wrong coach code
    When that address signs up with coach code "TEST-COACH-CODE"
    Then they see the error "Too many attempts. Try again later"
    And no profile is created
