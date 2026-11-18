# Licence

## 1. Scope

This repository — the Statisticians Workbench — contains three categories of intellectual property governed by different terms. Read this entire document. The MIT License (Section 2) applies only where explicitly stated; the exclusions (Section 1) override it.

### 1.1 Documentation — All Rights Reserved

All documentation in this repository, whatever its filename, including but not limited to:

- README files (`README.md`)
- The repository overview (`ABOUT.md`, `ABOUT.html`)
- The installation guide (`Installing.md`, `Installing.html`)
- Developer notes
- Any changelog, design note, FAQ document, or translation-key design document
- Any file inside a `docs/` directory
- Any other `.md` or `.html` content outside the frontend application

…is copyright &copy; 2026 Ron O'Hara, all rights reserved. Documentation is available for reading under fair use but may not be copied, modified, redistributed, or incorporated into derivative works without written permission.

### 1.2 Corporate Features — All Rights Reserved

The following features, where present in the source code, are proprietary and are **not** covered by the MIT License:

- Audit logging (`AuditLog` model, audit event recording, audit API endpoints)
- Session management (active session listing, admin session termination, session audit trail)
- SSO (Single Sign-On) integration
- Advanced analytics features designated as corporate-tier
- Priority support infrastructure

Where any of these features is present, it is **source-visible** — you may read and inspect the code — but it is not open source. Where present, it is gated by a signed licence file (the "golden screwdriver" mechanism), and it may not be used, activated, or operated without a valid licence issued by Ron O'Hara. Attempting to bypass or remove the gating mechanism to activate such a feature without a licence is not permitted.

### 1.3 Feature-Gating Mechanism — All Rights Reserved

The golden-screwdriver feature-gating mechanism — including but not limited to:

- Licence file verification logic
- Cryptographic signature validation
- The in-memory set of enabled features
- The `FeatureGate` React component
- The `GET /api/features` endpoint
- Any code that checks or enforces feature availability based on licence state

…is proprietary (all rights reserved). It is source-visible but not MIT-licensed. The mechanism exists to distinguish between open-source and corporate-tier capabilities within a single codebase. It may not be removed, disabled, bypassed, or repurposed to activate corporate features without a licence.

### 1.4 Excluded Files and Directories

The following specific files and directories are excluded from the MIT License and are instead governed by the terms above (all rights reserved, or the licence terms specified within them):

| Path | Status |
|---|---|
| `README.md`, `ABOUT.md`, `ABOUT.html`, `Installing.md`, `Installing.html` | Documentation — all rights reserved |
| Any file inside a `docs/` directory | Documentation — all rights reserved |
| Any other `.md` or `.html` file outside the frontend application | Documentation — all rights reserved |
| Corporate feature source code (see Section 1.2) | Proprietary — all rights reserved |
| Feature-gating source code (see Section 1.3) | Proprietary — all rights reserved |

This document itself is not documentation under Section 1.1: it states the terms that govern the rest of the repository, and it must be reproduced with copies of the code as Section 2 requires.

### 1.5 What *Is* MIT-Licensed

All source code in this repository that implements the **open-source tier** features of the Statisticians Workbench — datasets, recipes, AI chat, visualisation, notebook import, database connections, user management, authentication, and all supporting infrastructure not listed in Sections 1.1 through 1.4 — is released under the MIT License (Section 2 below).

---

## 2. MIT License

Copyright &copy; 2026 Ron O'Hara

Permission is hereby granted, free of charge, to any person obtaining a copy
of the open-source-tier source code in this repository (as defined in Section 1.5
above, and excluding the components listed in Sections 1.1 through 1.4), to deal
in that code without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the code, and to permit persons to whom the code is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the code.

THE CODE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE CODE OR THE USE OR OTHER DEALINGS IN THE
CODE.

---

## 3. Summary

| Component | Governing Terms |
|---|---|
| Open-source tier source code (datasets, recipes, AI chat, visualisation, auth, etc.) | MIT License (Section 2) |
| Corporate-tier features (audit log, SSO, session management, advanced analytics) | Proprietary — all rights reserved (Section 1.2) |
| Feature-gating mechanism (licence verification, `FeatureGate`, golden screwdriver) | Proprietary — all rights reserved (Section 1.3) |
| Documentation (README, ABOUT, Installing, `docs/`) | Copyright &copy; 2026 Ron O'Hara — all rights reserved (Section 1.1) |

If you are unsure whether a specific file or feature falls under the MIT License or the proprietary terms, contact the copyright holder for clarification before using, copying, or distributing it.

---

&copy; 2026 Ron O'Hara. Some rights reserved. See above.
