# Security Policy

## Purpose and scope

Protect customer, employee, store, order, complaint, mailbox and shipping records, uploaded files, credentials, local caches and backups from unauthorized access, alteration and loss. Access is limited to authorized staff and necessary service providers under controlled accounts. No policy or software can guarantee absolute security.

This policy defines required controls; its presence does not prove that production settings meet them. See [Security and Backups](SECURITY_AND_BACKUPS.md) for the implementation and recovery guidance.

## Supported versions

Security fixes target the latest main branch and the production deployment built from it. Older deployments and desktop clients must be updated; there is no separate long-term support branch. Repository administrators own security triage and must designate a production incident owner.

## Reporting a vulnerability

Do not post customer information, credentials, exploitable details or production screenshots in public issues, pull requests or discussions.

Use GitHub's **Security > Advisories > Report a vulnerability** if private reporting is available:
https://github.com/mikemargs/Print-Orders/security/advisories

If the private reporting option is unavailable, contact the repository owner through an existing trusted private business channel. If no private channel is known, open an issue containing only a request for a private security contact. Do not include the vulnerability itself. Administrators must enable private reporting where available or establish a monitored private reporting channel; this file does not enable that setting.

Include affected version, impact, reproduction using fictional data, and redacted evidence. Test only systems you own or have explicit permission to test; do not access other customers' records, extract data, disrupt service or run unsolicited production scans. Response times depend on maintainer availability; no response-time guarantee is made.

## Required customer-data controls

- Require authenticated employee sessions for business records and files. Enforce company isolation and role/store permissions on the server for every read, mutation, export and signed-file request. Never rely on hidden buttons or unpredictable record IDs.
- Preserve intended company-wide staff reading and existing store-based editing rules; authorized cross-store access is not public access.
- Use individual employee PINs and promptly revoke departing staff. Protect the shared company credential and avoid shared administrator identities.
- Use HTTPS, secure HttpOnly session cookies, CSRF protection for browser mutations, bounded sessions, and login abuse controls. Application throttling must be supplemented by appropriate hosting/network controls.
- Keep database credentials, JWT secrets, service-role keys and mail-provider credentials exclusively in server-managed secrets. Never commit them or place them in frontend bundles, browser storage, logs or issue reports.
- Keep production records, uploads, exports and backups out of GitHub. Use synthetic fixtures for tests and redact logs; do not record full request bodies containing customer details.
- Collect only information needed for store operations. Do not store card numbers/CVV, passwords, government-ID images, medical records or other regulated information without separately reviewed controls.
- Define retention and approved deletion procedures for records, exports, uploads, caches and backups. Include incident and legal preservation requirements.

## Supabase and Render deployment requirements

Administrators must verify these controls in the actual production accounts; repository configuration alone is insufficient.

- Keep the artwork bucket private. Issue short-lived upload/download capabilities only after server authorization. Treat signed URLs as temporary bearer credentials; do not persist or expose them publicly.
- Audit Supabase Data API exposure for every table, view and function. Application employee sessions do not automatically protect direct Supabase REST/GraphQL access.
- Where the application does not require the Supabase Data API, evaluate disabling it after checking all integrations. Otherwise restrict exposed schemas, grants and RLS policies so anonymous or unrelated users cannot access business data. Review new migrations for exposure and verify with anonymous and low-privilege requests. Never use broad allow-all policies as a workaround.
- Service-role credentials bypass RLS and must remain server-side; RLS does not replace backend company/store authorization.
- Require verified TLS for database connections, least-privilege database access where supported, and appropriate network restrictions. Do not expose self-hosted database ports publicly. Validate any restriction against Render connectivity before applying it.
- Verify production HTTPS, secure-cookie settings, secret handling, and deployment permissions. Use MFA and least privilege on GitHub, Render, Supabase and email-provider administrator accounts.
- Minimize customer information in staff email notifications. Restrict recipient lists and review them when employees leave. Email creates additional copies subject to retention and access controls.

## Devices, caches and recovery

Browser offline mode intentionally retains a bounded work-order/customer cache. It is not a zero-local-data system. Use managed devices or protected OS/browser profiles, disk encryption and automatic screen locking. Sign out and verify cache clearing on shared devices. Customer Issues histories and artwork must not be added to persistent offline caching without security review.

Restrict exports and backup access, encrypt backup storage and transfers, and maintain documented retention. Restore-test database backups and separately validate artwork-object recovery; database metadata backups do not include storage object bytes. See SECURITY_AND_BACKUPS.md for the recovery process.

## Repository and release controls

- Require reviewed pull requests and successful relevant CI checks before production merge; investigate cancelled checks rather than bypassing them.
- Configure branch protection/rulesets, least-privilege collaborators, dependency alerts and secret scanning/push protection where supported by the account plan. These are separate GitHub settings, not enabled by this document.
- Review dependency and security alerts regularly and prioritize actively exploited flaws, credential exposure, authentication bypass and customer-data access.
- Test unauthenticated requests, cross-company record/file access, employee store write restrictions, admin-only endpoints, CSRF, session revocation and cache clearing with synthetic data before relevant releases.
- Do not treat passing CI as a penetration test or a production security certification.

## Incident response

1. Notify the designated incident owner privately. Preserve timestamps and redacted evidence with restricted access.
2. Contain the affected access path: revoke sessions, disable compromised accounts and rotate exposed secrets. Limit affected functionality when necessary.
3. Determine impacted records, files, providers, caches and backups. Avoid copying customer data into public tracking systems.
4. Fix and validate the cause, review access logs, and restore safely where needed.
5. Have the business owner obtain appropriate advice on notification obligations and communicate through approved channels.
6. Record lessons learned and verify remediation before restoring normal access.

## Production verification record

Before claiming deployment readiness, record the date, reviewer, deployed commit, account settings checked, test outcomes and unresolved risks in a restricted operational record. Do not store sensitive findings or live credentials in this public policy.

This change adds documentation only. Supabase RLS/grants, storage privacy, Render settings, GitHub security features, runtime authorization and production exposure still require independent verification.

## References

- https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/add-security-policy
- https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately
- https://supabase.com/docs/guides/database/secure-data
- https://supabase.com/docs/guides/api/securing-your-api
