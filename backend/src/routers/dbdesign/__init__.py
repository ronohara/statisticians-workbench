"""
Database Design Assistant router package.
"""

from . import schema, report, streaming, email_pdf
from .schema import router as schema_router
from .report import router as report_router
from .streaming import router as streaming_router
from .email_pdf import router as email_pdf_router
