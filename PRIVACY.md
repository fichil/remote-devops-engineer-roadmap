# Privacy Policy for Learning Evidence

This project intentionally separates a public learning trail from a private job-search trail.

## Public by design

- Daily learning plans and completion evidence
- Sanitized command output and lab notes
- Portfolio code, runbooks, architecture decisions, and demos
- Weekly learning metrics without employer or compensation data

## Private by design

Store the following only under the ignored `private/` directory or another private system:

- employer and recruiter names;
- email addresses, phone numbers, and personal contacts;
- compensation, invoices, contracts, and financial details;
- job application status and private interview feedback;
- credentials, account identifiers, internal hostnames, and private repository names.

Before publishing, run `python scripts/privacy_scan.py` and manually review the diff. A passing scanner is not permission to publish and does not replace human review.
