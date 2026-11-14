# Statisticians Workbench

A modern, extensible web application for data analysis, database management, and AI integration. Built with Next.js, shadcn/ui, Tailwind CSS, PostgreSQL, and NextAuth.js.

## Open Source vs Commercial

The installation instructions below apply **only** to the Open Source version of the Statisticians Workbench — building and running it from this repository's source code.

The **commercial versions are packaged differently**: they ship as pre-built installers with their own database provisioning, services and upgrade path, and are installed from those packages, not from source. These instructions will **not** work for a commercial version. If you are installing a commercial version, follow the documentation that ships with that package instead.

## Features

- User authentication – Self Registration, login, session management, and persistent error messages.

- Admin panel – Manage users, grant/revoke admin rights, delete accounts.

- Database connection manager – Test and save connections to PostgreSQL and MySQL (other drivers can be added). Multiple connection credentials are stored per user.

- AI connection manager – Test and save connections to a local Ollama, remote OpenAI and many other AI providers. Multiple connection credentials are stored per user.

- User profile – Update name, email (read‑only), and preferences (dark mode, email notifications, interface language choice).

- PostgreSQL backend

- Responsive sidebar – Navigation, user avatar, logout, and admin‑only links.

## Technology Stack

- Frontend: React, Next.js (App Router), shadcn/ui, Tailwind CSS, lucide‑react

- Forms & Validation: react‑hook‑form, Zod

- Authentication: NextAuth.js (credentials provider) with bcryptjs

- Database: PostgreSQL

- Backend: Python (FastAPI)

- Testing: API endpoints for database connectivity (pg, mysql2)

- Language: TypeScript

## Getting Started

### Prerequisites

- Node.js 20 or newer (and npm)

- pnpm (install with npm install -g pnpm)

- Python 3.x (for the backend)

- PostgreSQL (a running server)

- Git

### Installation

1. Clone the repository:
git clone [https://github.com/ronohara/statisticians-workbench.git](https://github.com/ronohara/statisticians-workbench.git)
cd statisticians-workbench

2. Install frontend dependencies:
cd frontend
pnpm install

3. Generate the environment files:
../scripts/generate-env-files.sh
Then review the generated .env and hand-edit as needed — set DATABASE\_URL to your PostgreSQL database and NEXTAUTH\_SECRET to a random secret.

4. Set up the database — create the workbench database and apply the SQL migrations in db/migrations/ using psql.

5. Start the backend:
../scripts/start-backend.sh

6. Build and start the frontend (production build — this project does not use a dev server):
pnpm build
pnpm start
Then open http://localhost:3000 in your browser.

## Usage Guide

- Login / Register – Access via the sidebar or directly at /login and /register. Error messages stay on screen until corrected.

- Settings Hub – Use the sidebar to reach Profile, Database, and AI settings.

- Database Connection – Select PostgreSQL or MySQL, enter credentials, test the connection (persistent result message), and save. Saved connections are stored per user.

- Admin Panel – Only visible to users with isAdmin=true. Manage all registered users, promote/demote admins, or delete accounts.

- AI Settings – Placeholder for future LLM integration (API keys, model selection, etc.).

## Project Structure

- frontend/ – Next.js application

- backend/ – Python (FastAPI) backend

- db/ – database schema and migrations

- scripts/ – build, run, and maintenance scripts

- config/ – configuration templates

## Development Notes

- The application uses PostgreSQL by default. We no longer rely on SQLite.

- Dark mode and other preferences are stored in a PostgreSQL database called 'workbench'

- All API endpoints that require admin privileges are protected with a server‑side requireAdmin() check.

## Troubleshooting

- pnpm approve-builds – If you see build‑script warnings, run this command and select all packages.

## Licensing

### MIT License (Open Source)

The source code in this repository is released under the MIT License, with the
exceptions listed below. See the LICENCE.md file for full terms.

### Documentation

All documentation — including README files, changelogs, design notes, installation
guides, FAQ documents, and any content delivered in `.pdf`, `.md`, or `.html`
format — is **excluded** from the MIT License. Documentation is copyright Ron O'Hara
(all rights reserved) and is available for reading under fair use. We retain
control of the documentation to encourage contributions to this central repository
rather than uncoordinated forks — though forking the code remains permitted under MIT.

### Corporate Features and Feature Gating

This repository includes a **golden screwdriver** feature-gating mechanism. Corporate-tier
features such as the audit log, SSO integration, advanced analytics, and
session management are:

- **Present in the source code** — you can read, inspect, and understand how they work.
- **Gated by a signed licence file** — they do not activate without a valid licence.
- **Not covered by the MIT License** — the gating mechanism, licence verification
  logic, and the specific features it controls are proprietary (all rights reserved).

The remaining code — all open-source tier features — remains fully MIT-licensed.
Removing or bypassing the gating mechanism to activate corporate features without
a licence is not permitted under the terms of this repository.

### Summary

| Component | License |
|---|---|
| Open-source features (datasets, recipes, AI chat, visualisation, etc.) | MIT |
| Corporate features (audit log, SSO, session management, etc.) | Proprietary — all rights reserved |
| Feature-gating mechanism (licence verification, `FeatureGate` component) | Proprietary — all rights reserved |
| Documentation (README, changelogs, guides, FAQ) | Copyright Ron O'Hara — all rights reserved |

## Acknowledgments

- shadcn/ui for accessible component primitives.

- Next.js for the React framework.

- NextAuth.js for authentication.

Last updated: 15th November 2026
