# Phoenix Core V1.0 — Login Background Embedded-Asset Final Fix

## Why this patch exists
The server continued returning 404 for both `/phoenix_logo.png` and
`/phoenix_login_background.png` even though the files were present in the
application package. To remove the static-file serving dependency from the
login page entirely, both images are now embedded directly into `index.html`
as data URIs.

## Result
- The login page makes NO browser request for either Phoenix PNG.
- No image 404 can occur for the login logo/background.
- The physical PNG files remain in the package as master assets.
- Existing login/authentication behavior is preserved.
- Existing Core application functionality is preserved.

## Expected log
The next launch should no longer contain:
GET /phoenix_logo.png ... 404
GET /phoenix_login_background.png ... 404

The normal authentication sequence remains:
POST /api/login ... 200
GET /api/session ... 200
