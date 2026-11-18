# backend/src/version.py
# Single source of truth for the application version.
# Both the FastAPI title and the /api/health endpoint import from here.

VERSION = "0.12.2"

# Which implementation is answering. The Go port serves the same /api/health body
# with the same version string, so without this field the two are indistinguishable
# from outside — a probe, a support call or a parity run cannot tell them apart.
# A property of this codebase, not of the deployment: a compile-time constant.
BACKEND = "python"
