# IIITDMJ Auto Pool (Django prototype v2)

"One Campus. Shared Rides. Lower Fares." Students at IIITDM Jabalpur (Dumna campus, 12-15 km from the
station) find or post auto-rickshaw rides and split the fare.

## 1. Setup (Windows, VS Code, PowerShell)
Open the folder that contains `manage.py`, then in the terminal:

    python -m pip install -r requirements.txt
    python manage.py makemigrations rides
    python manage.py migrate
    python manage.py seed_demo
    python manage.py runserver

Open http://127.0.0.1:8000. If `pip.exe` is blocked on your laptop, always use `python -m pip`. No virtual env needed.

### Upgrading from the earlier version
Copy these files over your old folder (keep your `db.sqlite3`), then run `makemigrations rides` and `migrate`.
It adds new columns and tables without deleting your data. If anything breaks, delete `db.sqlite3` and
`rides/migrations/` (keep `__init__.py` there if it exists) and run the 4 setup commands again.

### Demo logins (password `demo12345`)
aarav@, rohan@, diya@ (female), meera@ (female) + `iiitdmj.ac.in`.

### Admin
    python manage.py createsuperuser
Open /admin/ to suspend students, read reports and resolve them. Use a student account for the app itself.

### Run the tests
    python manage.py test

### Settings you may want to change (config/settings.py)
- UI_THEME = "light" (green + mint like the PDF) or "dark"
- EMAIL_VERIFICATION_REQUIRED = True. Real sign-ups must click a link. With no mail server, the email is printed
  in the terminal and the check-email page shows a "Verify now" shortcut (only when DEBUG = True).
  Set to False to skip verification during quick demos.

## 2. What the app does
Sign up with @iiitdmj.ac.in only (verified by email link) -> post a ride (direction, city point, meeting point,
date/time, seats, luggage, female-only, fare, notes) -> others see rides within +-45 minutes with a free seat ->
Request to join -> creator Accepts -> WhatsApp button unlocks (wa.me link, no paid API).
Fare per person = total fare / (3 - seats_available). One tap "+30 min" when a train is late.
Also: cancel request, leave ride, cancel ride, mark completed, in-app updates, report a student, admin
suspension, automatic expiry of unfilled rides 30 min after departure, landing page.

## 3. Review of the PDF specification
| PDF feature | In this Django app |
|---|---|
| @iiitdmj.ac.in only (UI, API, DB trigger) | Yes: form check + email-verification link; domain also checked at login |
| +-45 min matching, luggage, female-only | Yes (feed filters; female-only rides hidden from non-female students) |
| Dynamic fare split | Yes |
| Atomic seat locking (FOR UPDATE) | Yes: `select_for_update` inside transactions (real row locks on PostgreSQL, serialized writes on SQLite) |
| Privacy: phones hidden until accepted | Yes (checked by an automated test) |
| Cancel request / leave / cancel / complete / delay | Yes |
| 5-minute expiry cron | Lazy expiry whenever the feed or My rides loads |
| Reports + admin suspend | Yes, via Django admin |
| Notifications | In-app only (the "Updates" panel + badge) |
| Pickup points, notes, 6 destinations | Yes |
| WhatsApp bot (Meta Cloud API), WhatsApp OTP linking | Not included: needs a Meta Business account, tokens and a public HTTPS webhook |
| React + Node + Supabase stack | Replaced by Django + SQLite so it runs locally with one command |

### Problems found in the PDF itself
- It says all 26 files are included "without truncation", but most code blocks stop mid-file (for example the
  schema ends inside `ride_requests`, and `ride.service.ts`, `notification.service.ts`, `auth.routes.ts` are cut off).
  The Supabase/Node/React project cannot be rebuilt from the PDF alone.
- The test matrix lists 23 cases, but only 7 automated tests are shown as run; 6-17 are "awaiting credentials".
- `admin.routes.ts` imports `requireAdmin` and the routes use `leave_ride_atomic`, but neither is shown in the PDF.
- `FareCalculatorService` allows 0-3 co-riders, while the schema allows `max_seats` 1-3 *plus* the creator,
  which makes a 4-person auto; a standard auto seats 3 in total. This app uses 3 total (creator + up to 2).
- "Fare estimates" are not binding: the final price is agreed with the driver (the PDF says so too).

## 4. Known limits
- No real email server, SMS or WhatsApp messages. Notifications are in-app.
- SQLite is for demos; use PostgreSQL for real use.
- Set `DEBUG = False`, a real `SECRET_KEY` and `ALLOWED_HOSTS` before any public deployment.
- Not tested in a browser by the author. Please run `python manage.py test` and the demo once before presenting.

## 5. Project layout
    manage.py, requirements.txt
    config/      settings, urls, wsgi
    accounts/    register, login, email verification
    rides/       models, views, forms, admin, notify, middleware, tests, seed_demo command
    templates/   base, registration/, rides/ (landing, feed, card, create, my_rides, report)
    static/css/  autopool.css (base), theme-light.css (green/mint override)
