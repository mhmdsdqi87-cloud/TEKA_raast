# Security Policy

## Reporting

Report vulnerabilities via GitHub Security Advisories ("Report a vulnerability" on the Security tab) or by contacting the repository owner through GitHub. Do not open public issues for security reports.

Expected response: acknowledgment within 7 days, assessment within 30 days.

## Scope

RAAST is a developer tool. Threat models that matter:

- **Supply chain**: the CLI has zero runtime dependencies by design; the browser suite pins versions. Report any dependency drift immediately.
- **Content injection**: `raast fix` rewrites files in place (with backups). Malicious repos could craft content that exploits naive regex rewriting — if you find a path where a fix corrupts or injects code beyond its documented transformation, that is a security bug.
- **Credentials**: the CLI never reads env vars beyond standard PATH resolution and never sends network requests. If any command attempts network access, file a security report — it should not exist.

## Non-scope

- The Skills are Markdown documents; executing their code snippets in your agent is subject to your agent's own security model.
