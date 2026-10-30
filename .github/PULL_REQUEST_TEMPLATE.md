## Problem and result

Closes #

Describe the concrete trigger and the resulting behavior. State the intended base/merge order if this PR is stacked.

## Evidence

- Before: reproduced failure or observable gap.
- After: exact commands, exit codes and relevant results for this head.
- Not run: checks that were unavailable and why.

For a behavioral fix, include a meaningful regression case. For documentation, check affected links and consistency. Keep static checks, fixture results and real-agent outcomes separate.

## Review and integration

- [ ] Scope matches the task; unrelated changes and local/private artifacts are excluded.
- [ ] Secrets, service access and new dependencies have been reviewed where affected.
- [ ] Request an independent reviewer; address findings and recheck CI after the final push.

State material risks and recovery steps. Required GitHub review and current CI must complete before merge; ticking this template does not replace them.

## Release and version impact

- [ ] If version metadata changes, verify `VERSION`, skill, README, plugin, CLI, CHANGELOG and security status are consistent.
- [ ] This PR does not create tags, publish releases, bypass protected status checks or silently alter existing release assets.
