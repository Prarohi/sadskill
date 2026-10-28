# Vercel tasks

Use for Vercel builds, project configuration, environment variables, preview deployments, promotion, and rollback. Discover the framework, package manager, monorepo root, output directory, runtime, and existing Git integration first. Vercel hosting does not imply Next.js or authorize a framework migration.

## Environment and execution boundary

Identify the exact project/team, requested environment, and operations already authorized by the task. Inspect which Git branch triggers production: merging a PR can trigger deployment when a Git integration is active. A request to fix code or add documentation is not itself a request to create a project, change billing, deploy, or promote.

- Keep Development, Preview and Production configuration separate. Use disposable data and non-production credentials in previews, including branch-specific variables when needed.
- Treat public framework prefixes such as `VITE_` and `NEXT_PUBLIC_` as client-visible. Never put a server secret behind a public prefix.
- Stored Secret/sensitive variables are still readable by code executing with those variables. Masking a dashboard value does not make an untrusted PR build safe to receive it.
- Run untrusted PR checks without production secrets or a privileged repository token. Inspect dependency/install/build scripts before a credential-bearing step; use least-privilege, scoped credentials only where needed.
- Keep downloaded `.env` files, authentication state and secret-bearing traces out of commits and published artifacts. Let the owner configure credentials directly in the service or protected environment.

## Build, verify and promote

Use the repository's actual build and test commands. Check environment compatibility, routes, assets and affected server functions; a successful build is not full application verification. Consult current CLI help and official docs for the requested action.

For an authorized release that must promote the tested artifact, stage a production-target deployment without assigning production domains, test that staged deployment, then promote it. A preview promoted to production can rebuild with production variables, so do not claim the preview bytes were the released artifact. With prebuilt output, verify the documented runtime and environment limitations before choosing that workflow.

Record the commit, deployment ID, environment, checks and previous working production deployment. Verify service behavior after promotion. A rollback can disable automatic production-domain assignment; inspect that setting before the next release. Use protected preview access already configured for the task and preserve access controls when inspecting a deployment.

## Official sources

Reviewed 2026-10-28; refresh relevant documentation when implementing a task.

- [Environments](https://vercel.com/docs/deployments/environments)
- [Environment variables](https://vercel.com/docs/environment-variables)
- [Deploy CLI](https://vercel.com/docs/cli/deploy)
- [Promotion](https://vercel.com/docs/cli/promote)
- [Rollback](https://vercel.com/docs/cli/rollback)
- [Research and external content](../protocols/research.md)
