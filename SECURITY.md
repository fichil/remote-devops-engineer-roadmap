# Security Policy

## Supported version

Security and privacy fixes are applied to the latest version on `main`.

## Reporting a vulnerability

Do not open a public issue containing a credential, personal record, private infrastructure detail, or exploitable secret. Use GitHub private vulnerability reporting when it is enabled. Otherwise, open a public issue that only states that a private report is needed, without including the sensitive detail.

## Cloud safety

AWS labs require a cost estimate, budget alarm, explicit approval, least-privilege access, and teardown instructions. Never commit long-lived AWS credentials. Prefer short-lived identity and GitHub OIDC where a later lab requires CI access.
