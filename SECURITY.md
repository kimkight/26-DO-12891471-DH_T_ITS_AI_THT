# Security Policy

## Status of this project

This is a **prototype**. It is not authorized for operational use, it has no
authentication, and it must not be used with real application data or with any
sensitive information. See
[docs/06_SECURITY_AND_COMPLIANCE.md](docs/06_SECURITY_AND_COMPLIANCE.md) for the
full posture, threat model, and the production path for each limitation.

## Reporting a vulnerability

Report suspected vulnerabilities through GitHub's private vulnerability
reporting on this repository, under the Security tab.

**Do not open a public issue for a suspected vulnerability.**

Please include what you did, what happened, what you expected, and the commit
SHA. Do not include credentials, account identifiers, or personal data in a
report.

## Scope

In scope: the application code in `backend/` and `frontend/`, the container
definition, and the CI and deployment workflows.

Out of scope: findings that follow directly from documented prototype
limitations. These are known, deliberate, and recorded:

- No authentication. Anyone who can reach the service can use it (Decision D-9).
- No rate limiting or WAF.
- No persistence, therefore no audit trail (Decision D-9).
- Container base images pinned by tag rather than by digest.

Reports that identify a *new* consequence of one of these, or a way to escalate
beyond it, are in scope.

## Handling of data

The application persists nothing. Uploaded images and form data exist only in
process memory for the lifetime of the request, and are not written to disk, a
database, object storage, or a cache. Logs contain no image content and no
extracted field values. See NFR-6.

## Secrets

No secret, credential, or account identifier belongs in this repository.
`.env` is git-ignored, `.env.example` documents configuration shape only, and a
`detect-private-key` pre-commit hook guards commits. Deployment authenticates to
AWS through GitHub OIDC; there are no static access keys.

If you believe a secret has been committed, treat it as compromised: rotate it
first, then report it.
