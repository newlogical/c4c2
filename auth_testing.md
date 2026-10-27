# Auth testing (outside access)
See /app/memory/test_credentials.md "Outside access accounts".
1. LAN: PIN 1234 unlocks as before; `/api/bootstrap` → remote:false.
2. Remote (header `X-Smith-Remote: 1`): /api/state 401; /api/auth/demo 404; create user via LAN session; /api/remote/login enroll → TOTP code → done; PIN unlock; /api/state 200; logout keeps sign-in (pin_ok false).
3. Mongo: db.remote_users password_hash starts with `$2b$`; indexes remote_users.username (unique), login_attempts.identifier.
4. Lockout: 5 bad passwords → 429.
