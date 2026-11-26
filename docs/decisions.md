# Decisions

## 2026-11-25: Stack and mail handling (human)

- Frontend: React with TypeScript, built by Vite.
- Backend: FastAPI (Python), managed with `uv`.
- Storage: SQLite, accessed through SQLAlchemy. SQLAlchemy gives typed
  models and migrations-friendly schema definitions over the stdlib
  `sqlite3` module, at the cost of one extra dependency, which is a
  reasonable trade for a project with several related tables (profiles,
  sessions, payments, notifications).
- Packaging: one Docker image. A multi-stage build compiles the frontend,
  then copies the static output into a slim Python image that serves both
  the API (under `/api`) and the built frontend (at `/`).
- Emails (profile confirmation, session and payment notices) are written to
  a local outbox table and the server log instead of being sent, so the
  project runs with no mail service.

## 2026-11-25: Roles and accounts

Context: Create Profile lists Customer and Coach as actors. If anyone could
sign up as a Coach, anyone could create and delete sessions. Notify Members
needs to know each user's permissions.

Decision (human): Create Profile makes a Customer's profile. A visitor who
enters the club's coach code, set on the server, gets a Coach's profile.
One Treasurer is created on the server with a command. Each profile has
exactly one role.

Consequences: with no coach code set, no Coach profile can be created. The
role comes from the coach code, never from the request. The Treasurer
cannot be created or promoted to from the app.

## 2026-11-25: Customers pay in the app

Context: no use case says how a session gets paid, yet Club Finances shows
the funds the club has accumulated and Check Unpaid Sessions shows the
money owed.

Decision (human): Check Unpaid Sessions has a Pay button. It settles every
unpaid session the Customer owes for (simulated: no card) and adds the
amount to the club's funds.

Consequences: the club's funds are the sum of payments less the sum of
withdrawals. A Customer's balance in Club Finances is what they owe.

## 2026-11-25: Check In is to the session in progress

Context: Check In is one button, but Check Unpaid Sessions lists dated,
priced sessions, so a check-in must belong to a session.

Decision (human): a check-in is to the session in progress, from 15
minutes before its start to its end. With no session in that window, the
check-in is refused with a message.

Consequences: a Customer's check-in makes them owe that session's price. A
Coach's check-in is recorded and costs nothing. One check-in per member per
session.

## 2026-11-25: Session collisions and overwrite

Context: Session Created re-prompts on a collision to overwrite or cancel,
without saying what collides or what overwrite does.

Decision (human): sessions have a start and a length. Any overlap with
another session that has not ended collides, as the club has one venue.
Overwrite deletes the colliding sessions exactly as Session Deleted does,
then creates the new one, in one transaction.

Consequences: sessions that only touch (one ends as the next starts) do
not collide. Overwrite is offered only when every colliding session is a
future one (see "Coaches change only future sessions").

## 2026-11-25: Coaches set each session's price and length

Decision (human): Create Session asks for the date, start time, length
(default 60 minutes) and price.

Consequences: "cost per class" in Check Unpaid Sessions can differ between
sessions. A check-in owes the price of its session.

## 2026-11-25: Session notices are queued, and Coaches send them

Context: Session Created "updates a queue of notifications", and Notify
Members has the Coach send notices about sessions created and deleted.

Decision (human): creating or deleting a session queues a notice. A Coach
sends the queue from Notify Members. Deleting a session whose
session-created notice has not been sent drops that notice and queues no
session-deleted notice, as no one heard of the session.

Consequences: Notify Members options b and c send whatever is queued; an
empty queue sends nothing.

## 2026-11-25: Coaches change only future sessions

Decision (human): a Coach can delete or overwrite only sessions that have
not started. Past and in-progress sessions carry check-ins and money owed,
so they stay.

## 2026-11-25: Coaches share one calendar

Decision (human): any Coach can delete or overwrite any Coach's session.
Each change is recorded against the Coach who made it.

Consequences: a session records the Coach who created it; a deleted
session leaves a log entry naming the Coach who deleted it and when.

## 2026-11-25: Sign-in, field rules, bounds and sending

Context: the use cases leave these open. The architect recommended each;
the feature files in `features/` follow them.

Decision (human, by approving the feature files): as follows.

1. Signing in. Email address and password. A signed-in session is a random
   256-bit token in an HttpOnly, SameSite=Strict cookie (Secure when served
   over HTTPS), stored only as its SHA-256 hash, and ends at sign-out or 7
   days after sign-in. Passwords are hashed with the standard library's
   `hashlib.scrypt` (n=2^14, r=8, p=1, a 16-byte random salt per password,
   64-byte output) and compared in constant time. Touches cryptography:
   needs human review.
2. Profile fields. Name 1 to 100 characters. Email address at most 254
   characters, one "@" with text either side and a dot after it, compared
   without regard to case. Phone number 7 to 15 digits, with optional
   spaces, hyphens, brackets and a leading "+". Password 12 to 128
   characters, no other rule (NIST SP 800-63B).
3. Confirmation links. A random 256-bit token, stored hashed, valid once,
   for 4 days. Pending profiles more than 4 days old are deleted at start-up
   and every hour after; a link is refused after 4 days even before the
   sweep runs. A sign-up with an address that already has a profile,
   pending or confirmed, gets the same answer as any sign-up and changes
   nothing, so sign-up does not reveal who is a member.
4. Throttling. A client address with 10 failed sign-ins, or 10 wrong coach
   codes, in 15 minutes is refused further attempts of that kind until the
   15 minutes pass. Per address rather than per email address, so no one can
   lock a member out by guessing at their address.
5. Money and bounds. Amounts are whole cents in Canadian dollars. A price is
   0.00 to 1,000.00. A length is 15 to 480 minutes. A session starts in the
   future and within 365 days. A withdrawal is more than 0.00 and at most the
   club's funds.
6. Stale totals. Pay sends the total the Customer saw, and Lower funds sends
   the funds the Treasurer saw. If the figure has changed, the request is
   refused and the screen refreshed. This also stops a resent request from
   paying or withdrawing twice.
7. Warnings for unpaid sessions. One email per Customer, with the amount
   owed when it is sent. A Customer warned in the last 24 hours is skipped
   and shown as skipped.
8. Sending session notices. Each confirmed Customer gets one email listing
   every queued notice of the kind chosen; pending profiles get none. The
   queue is read and emptied in one transaction, so a notice queued during a
   send waits for the next one.
9. Deleting sessions. Deleting is all or nothing: if any selected session
   has started or no longer exists when the Coach confirms, nothing is
   deleted and the Coach is told which. At most 100 sessions per delete.
