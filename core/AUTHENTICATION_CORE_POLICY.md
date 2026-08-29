# Phoenix Core Authentication & User Administration v1.0

Authentication is a Phoenix Core capability.

## Included

- User accounts
- Username/email identity
- Roles and permissions
- Salted PBKDF2-SHA256 password hashing
- Login sessions
- First-login password change
- Admin password reset
- New-user temporary password workflow
- User listing and creation
- Authentication/security audit events

## First login

The bootstrap `admin` account is created with the development password:

`Admin123!`

For the development/test baseline, the bootstrap administrator is not forced to change this password on every fresh patch load. New users and administrator password resets still force a first-login password change.

On first login the application forces the user to the Core password-change
screen. A new password must be set before normal dashboard use.

New users created by an administrator are also flagged for a first-login
password change.

Administrator password resets invalidate the target user's active sessions
and force a new password at the next login.

## Password security

Minimum password length is 8 characters.

Passwords are never stored in plaintext. They are stored as salted
PBKDF2-SHA256 hashes.

## Future controlled security patches

- MFA
- SSO
- external identity providers
- password breach checking
- login rate limiting / lockout
- advanced session/device management
- production secret management
