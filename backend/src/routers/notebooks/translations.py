"""
Translation keys for the Notebooks router.
"""

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


NOTEBOOKS = {
    "notebooks.delete_error": TranslationKey(
        "notebooks.delete_error",
        "Failed to delete import: {error}"
    ),
    "notebooks.example_blocked": TranslationKey(
        "notebooks.example_blocked",
        "Example users cannot import notebooks."
    ),
    "notebooks.example_blocked_2": TranslationKey(
        "notebooks.example_blocked_2",
        "Example users cannot modify notebook sharing."
    ),
    "notebooks.example_blocked_3": TranslationKey(
        "notebooks.example_blocked_3",
        "Example users cannot delete notebooks."
    ),
    "notebooks_storage.failed_create_table": TranslationKey(
        "notebooks_storage.failed_create_table",
        "Failed to create table {table}: {error}"
    ),
    "notebooks_storage.failed_create_table_mssql": TranslationKey(
        "notebooks_storage.failed_create_table_mssql",
        "Failed to create table: {error}"
    ),
    "notebooks.import_failed": TranslationKey(
        "notebooks.import_failed",
        "Notebook import failed: {error}"
    ),
    "notebooks.import_failed_2": TranslationKey(
        "notebooks.import_failed_2",
        "Failed to list imports: {error}"
    ),
    "notebooks.import_failed_3": TranslationKey(
        "notebooks.import_failed_3",
        "Import not found"
    ),
    "notebooks.import_failed_4": TranslationKey(
        "notebooks.import_failed_4",
        "Failed to fetch import: {error}"
    ),
    "notebooks.invalid_format_2": TranslationKey(
        "notebooks.invalid_format_2",
        "Invalid notebook format. Only .ipynb files are accepted."
    ),
    "notebooks.no_connection": TranslationKey(
        "notebooks.no_connection",
        "Please select a database connection."
    ),
    "notebooks_storage.no_connection_details": TranslationKey(
        "notebooks_storage.no_connection_details",
        "No connection details provided"
    ),
    "notebooks_storage.no_connection_details_short": TranslationKey(
        "notebooks_storage.no_connection_details_short",
        "No connection details"
    ),
    "notebooks_storage.no_data_pool": TranslationKey(
        "notebooks_storage.no_data_pool",
        "Data database pool is not initialised"
    ),
    "notebooks.no_dataframes": TranslationKey(
        "notebooks.no_dataframes",
        "No DataFrames found in this notebook"
    ),
    "notebooks.no_db_rights": TranslationKey(
        "notebooks.no_db_rights",
        "This connection does not have database creation rights."
    ),
    "notebooks.no_table_rights": TranslationKey(
        "notebooks.no_table_rights",
        "This connection cannot create tables \u2014 import denied."
    ),
    "notebooks.share_error": TranslationKey(
        "notebooks.share_error",
        "Only the owner can change sharing settings."
    ),
    "notebooks.share_error_2": TranslationKey(
        "notebooks.share_error_2",
        "Failed to update sharing: {error}"
    ),
    "notebooks.system_db_blocked": TranslationKey(
        "notebooks.system_db_blocked",
        "Cannot import into system database '{db}'. Please use a different database or create a new one."
    ),
    "notebooks_storage.unsupported_storage_type": TranslationKey(
        "notebooks_storage.unsupported_storage_type",
        "Unsupported storage type: {type}"
    ),
    # ---- Parser error keys (returned by parser.py, translated by router.py) ----
    "notebooks.file_too_large": TranslationKey(
        "notebooks.file_too_large",
        "Notebook file is too large. Maximum size is {max_size} MB."
    ),
    "notebooks.invalid_json": TranslationKey(
        "notebooks.invalid_json",
        "Invalid JSON: {error}"
    ),
    "notebooks.missing_cells": TranslationKey(
        "notebooks.missing_cells",
        "Invalid notebook format: missing 'cells' key"
    ),
    "notebooks.cells_not_list": TranslationKey(
        "notebooks.cells_not_list",
        "Invalid notebook format: 'cells' is not a list"
    ),
    "notebooks.too_many_cells": TranslationKey(
        "notebooks.too_many_cells",
        "Too many cells ({count}). Max: {max_cells}"
    ),
    "notebooks.unknown_error": TranslationKey(
        "notebooks.unknown_error",
        "Unknown error"
    ),
    "notebooks.untitled": TranslationKey(
        "notebooks.untitled",
        "Untitled"
    ),
}
