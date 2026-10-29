# Evidence v2 & Cryptographic Provenance 10/10 Plan

This document details how Sadskill's verification system evolves from local SHA-256 hash chains to enterprise-grade **SLSA Level 3 cryptographically signed provenance**.

---

## 🔗 Provenance Architecture Evolution

```
Local Evidence Record (.json)
           │
           ▼
[Canonical JSON Serialization] (RFC 8785)
           │
           ▼
[SHA-256 Digest Computation] -> Linked to `previous_record_hash` (Local Chain)
           │
           ▼
[Sigstore / Cosign Signing] (OIDC Identity binding)
           │
           ▼
[GitHub Artifact Attestation] -> Public verification via `gh attestation verify`
```

---

## 📋 SLSA Level 3 In-Toto Predicate Format

Every verification run emits an in-toto formatted predicate conforming to the SLSA Provenance v1.0 specification:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "sadskill-verification-evidence",
      "digest": {
        "sha256": "3a7b...8f"
      }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://sadskill.dev/evidence/v2",
      "externalParameters": {
        "command": "python3 -m unittest discover",
        "task_slug": "C1-01-nullable-bugfix"
      },
      "internalParameters": {
        "exit_code": 0,
        "worktree_dirty": false
      }
    },
    "runDetails": {
      "builder": {
        "id": "https://github.com/Prarohi/sadskill/.github/workflows/ci.yml"
      },
      "metadata": {
        "invocationId": "https://github.com/Prarohi/sadskill/actions/runs/40746032880",
        "startedOn": "2026-10-29T01:30:00Z",
        "finishedOn": "2026-10-29T01:32:00Z"
      }
    }
  }
}
```

---

## 🔑 GitHub Artifact Attestation Integration

In the GitHub Actions CI pipeline (`.github/workflows/ci.yml`), use the official GitHub Actions attestation action to cryptographically bind release artifacts and benchmark summaries:

```yaml
- name: Generate Artifact Attestation
  uses: actions/attest-build-provenance@v1
  with:
    subject-path: |
      dist/sadskill-*.tar.gz
      dist/sadskill-*.zip
      .sad/benchmark-latest.json
```

### Public Verification Command
Anyone in the world can independently verify that the release or benchmark artifact was generated directly by the audited GitHub Actions workflow without tampering:

```bash
gh attestation verify dist/sadskill-0.5.0.tar.gz \
  --repo Prarohi/sadskill
```
