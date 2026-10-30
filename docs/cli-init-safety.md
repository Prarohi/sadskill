# `.sad` filesystem safety

`sad init` opens the selected project and `.sad/` through directory file
descriptors, refuses symlinked or non-directory managed paths, and creates
templates relative to the pinned `.sad/` descriptor. Exclusive, no-follow
template creation prevents overwriting user files or following a replacement
symlink at the leaf. Existing regular template files are preserved.

Project memory also opens `.sad/`, `events/`, and `archive/` relative to pinned
directory descriptors. It rejects symlinked, non-regular, and hard-linked
memory files. Event records are staged and published atomically without
overwriting an existing event; readers recognize a matching staging link after
a crash, and the next locked write or compaction removes that link. Archive
rewrites are staged, fsynced, and atomically renamed; compaction removes source
events only after the archive is durable. A malformed archive causes compaction
to stop while retaining source events.

The selected project's final path component is checked with `O_NOFOLLOW`
*before* canonicalizing the project itself. This prevents an explicit
`--project-root` symlink from redirecting `sad init`, event writes, reads,
search, or compaction into another project. The selected project's parent
may still resolve ordinary platform directory aliases (such as macOS
`/var`); this is not a guarantee that every ancestor is symlink-free.
Existing hard-linked init templates are rejected for consistency with memory
file checks. Regression tests exercise both direct APIs and the memory CLI.

These guards prevent redirection through pre-existing paths and reduce
path-swap races. They are not an OS sandbox against a hostile process with the
same user's filesystem permissions; a same-user process can rename an already
opened directory outside the selected tree. Use an external disposable
workspace with appropriate OS permission boundaries for malicious repositories.

On platforms without `O_NOFOLLOW`, directory-descriptor operations, and the
required file-locking support, initialization or memory operations fail closed.
The native Windows memory CLI is not yet validated. Run agents that handle
malicious repositories in a sandbox with appropriate OS permission boundaries.

New tests use only temporary project folders; no real user profile is edited.
These checks harden the `.sad` path boundary; they do not replace PR #4's
installer data-preservation repair or PR #9's runtime sandbox.
