# Security Policy

## Supported Versions

Only the latest release on the `main` branch receives security fixes. We do not backport patches to older releases.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues by email to: **giovanni.scafetta@gmail.com**

Include the following in your report:

- A clear description of the vulnerability
- Steps to reproduce or a proof-of-concept (if safe to share)
- The potential impact (data exposure, privilege escalation, etc.)
- Your name / handle if you want to be credited in the fix

### Response Timeline

| Step | Target |
|---|---|
| Initial acknowledgement | Within 48 hours |
| Severity assessment | Within 5 business days |
| Fix released (critical) | Within 14 days |
| Fix released (medium/low) | Within 60 days |

We follow responsible disclosure: we will coordinate with you on a public disclosure date after the fix is released.

---

## Security Design Notes

For a full description of the security architecture, see [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

Key points:

- **Passwords** are hashed with bcrypt (cost factor ≥ 12).
- **Refresh tokens** are stored as bcrypt hashes — the raw token is never persisted.
- **JWTs** are short-lived (30 min default) and signed with HS256.
- **TOTP 2FA** secrets are stored encrypted in the database.
- **Rate limiting** is enforced per-IP on all auth endpoints.
- **Host header injection** is blocked via FastAPI's `TrustedHostMiddleware`.
- All containers run with `no-new-privileges: true`.
- The backend is never directly exposed to the internet — it is only reachable through the Nginx reverse proxy.

---

## Scope

The following are **in scope** for vulnerability reports:

- Authentication and authorization bypasses
- Data leakage between users or accounts
- SQL injection, XSS, CSRF
- Privilege escalation (User → Superadmin)
- Secrets exposure via API responses or logs

The following are **out of scope**:

- Vulnerabilities in third-party dependencies that already have public CVEs (please open a regular issue to request a dependency update)
- Denial-of-service attacks requiring abnormal traffic volumes
- Issues affecting only non-production (development) configurations
