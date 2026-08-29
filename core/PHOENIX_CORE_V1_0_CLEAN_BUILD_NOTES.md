# Phoenix Core V1.0 — Clean Build

## Current fix
The login API was succeeding, but the browser remained on "LOGGING IN...".
The authenticated session loader referenced `userInfo` without declaring it.
That caused a JavaScript ReferenceError after authentication, the catch block
then restored the login screen.

## Fix
`userInfo` is now explicitly bound to `#userInfo` before `loadSession()` can run.

## Expected authentication
1. Initial `/api/session` may return 401 when logged out.
2. `POST /api/login` returns 200.
3. `/api/session` returns 200.
4. Login screen is hidden.
5. Core application is shown.

## Package cleanup
Old patch-history files and unused login visual asset were removed from this
runnable build. Core source files, database, baseline/policy documentation,
branding assets, and application modules remain.
