# Feedback Log

This document records friction, observations, and findings during development.
It covers Nebius Token Factory, NVIDIA Nemotron models, and developer tooling.

---

## 1. Nebius Token Factory & NVIDIA Models

- Integration entries log observations during Phase X development.
- Nemotron inference endpoints follow standard OpenAI API request formats.
- JSON schema structured output requires explicit schema definitions in requests.
- Tool calling loops execute deterministically when schemas forbid extra properties.

---

## 2. Developer Experience & Tooling

- Initial scaffolding established strict pre-commit verification.
- Pre-commit secret scanning blocks accidental credential commits.
- FastAPI validates request bodies against strict Pydantic models.
- Next.js proxy rewrites protect internal backend endpoints from client exposure.
- In-memory JWT storage isolates access tokens from persistent browser storage.

---

## 3. Glossary

- **JWT:** JSON Web Token used for authenticated sessions.
- **Nemotron:** Family of language models developed by NVIDIA.
- **Token Factory:** Cloud AI inference service operated by Nebius.
