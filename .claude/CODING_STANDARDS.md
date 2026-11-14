# Coding Standards

## Principles
- Prefer clarity over cleverness; use explicit interfaces and control flow.
- Give each function, file, and module one responsibility with a cohesive boundary.
- Fail fast and loudly at invalid states; surface actionable errors safely.
- Follow established project patterns; record new patterns and rationale in
  `state/DECISIONS_LOG.md` before spreading them.

## Naming
- Follow the ecosystem's idiom once known; keep naming consistent throughout a module.
- Use descriptive verb-noun function names and `UPPER_SNAKE_CASE` constants as the
  general starting convention, specializing with the confirmed language's conventions.
- Prefix booleans with `is`, `has`, `should`, or `can`; choose names that state intent.

## Error Handling
- Never swallow errors; propagate or handle them at a clear ownership boundary.
- Log enough safe context to reproduce (operation, error class, correlation ID),
  without configuration values, secrets, tokens, or personal data.
- Return generic errors to users; never expose stack traces or internal details.

## Testing
- Every feature has tests; every bug fix has a regression test.
- Provide one command for the full test suite; use isolated, deterministic fixtures.
- Cover security-relevant negative cases: unauthenticated, forbidden, malformed,
  oversized, cross-tenant/object access, and fail-closed configuration where applicable.
- Verify behavior with development and production configuration in isolated local
  tests using fake/dedicated test credentials, never production systems or data.
- Preserve the existing passing baseline and all checks; diagnose failures honestly.

## Quality Tooling
- Configure a formatter, linter, and type checker where the language supports one
  during foundation setup; reference their actual configuration paths here.
- Run checks before declaring done; report unsupported checks as N/A with a reason.
- Commit dependency lockfiles and use reproducible installs; follow the Security Gate.

## Documentation
- Document public functions/interfaces and their contracts in the ecosystem's style.
- Explain non-obvious decisions with a *why* comment; keep comments accurate.
- Update affected contracts, operational docs, and `.env.example` alongside changes.

## Version Control
- Only commit/push at user request; make commits small, focused, and clearly described.
- Keep unrelated changes out of a commit; review intended files and checks first.
- Never bypass verification hooks or rewrite existing work/history without approval.

## Self-Update
When the stack is confirmed, specialize these standards with concrete language and
framework conventions, formatter/linter/type-check configuration references, and
observed implementation patterns citing representative file paths. None exist yet;
record verified paths when created rather than inventing examples of project code.
