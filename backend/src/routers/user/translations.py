# src/routers/user/translations.py
# ============================================================
# USER ROUTER TRANSLATIONS
# All translation keys used by the user router.
# ============================================================

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


USER = {
    # Error messages
    "api.auth.unauthorized": TranslationKey(
        "api.auth.unauthorized",
        "Unauthorized"
    ),
    "api.user.example_blocked": TranslationKey(
        "api.user.example_blocked",
        "Example users cannot perform this action"
    ),
    "api.user.connection_not_found": TranslationKey(
        "api.user.connection_not_found",
        "Connection not found"
    ),
    "api.user.connection_name_exists": TranslationKey(
        "api.user.connection_name_exists",
        "A connection with this name already exists"
    ),
    "api.user.provider_not_found": TranslationKey(
        "api.user.provider_not_found",
        'Provider "{provider}" not found'
    ),
    "api.user.api_key_required": TranslationKey(
        "api.user.api_key_required",
        "API key is required for this provider"
    ),
    "api.user.missing_fields": TranslationKey(
        "api.user.missing_fields",
        "Missing required fields"
    ),
    "api.user.invalid_name": TranslationKey(
        "api.user.invalid_name",
        "Name must be a string"
    ),
    "api.user.invalid_port": TranslationKey(
        "api.user.invalid_port",
        "Port must be an integer"
    ),
    "api.profile.invalid_name": TranslationKey(
        "api.profile.invalid_name",
        "Name must be a string"
    ),
    "api.profile.name_required": TranslationKey(
        "api.profile.name_required",
        "Name is required"
    ),
    "api.profile.update_failed": TranslationKey(
        "api.profile.update_failed",
        "Failed to update profile"
    ),
    "api.profile.fetch_failed": TranslationKey(
        "api.profile.fetch_failed",
        "Failed to fetch profile"
    ),
    "api.settings.invalid_default_ai_connection": TranslationKey(
        "api.settings.invalid_default_ai_connection",
        "Invalid default AI connection"
    ),
    "api.settings.example_blocked": TranslationKey(
        "api.settings.example_blocked",
        "Example users cannot edit settings"
    ),
    "api.settings.user_not_found": TranslationKey(
        "api.settings.user_not_found",
        "User not found"
    ),
    "api.settings.load_failed": TranslationKey(
        "api.settings.load_failed",
        "Failed to load settings"
    ),
    "api.settings.save_failed": TranslationKey(
        "api.settings.save_failed",
        "Failed to save settings"
    ),
    "api.settings.invalid_slow_threshold": TranslationKey(
        "api.settings.invalid_slow_threshold",
        "The slow-model limit must be a whole number of seconds, at least 1"
    ),
    "api.user.internal_error": TranslationKey(
        "api.user.internal_error",
        "Internal server error"
    ),
    "api.user.user_not_found": TranslationKey(
        "api.user.user_not_found",
        "User not found"
    ),
    "api.user.invalid_current_password": TranslationKey(
        "api.user.invalid_current_password",
        "Current password is incorrect"
    ),
    "api.auth.example_user_blocked": TranslationKey(
        "api.auth.example_user_blocked",
        "Password changes are disabled for example users"
    ),
    "api.auth.missing_fields": TranslationKey(
        "api.auth.missing_fields",
        "Missing fields"
    ),
    "api.auth.invalid_current_password": TranslationKey(
        "api.auth.invalid_current_password",
        "Current password is incorrect"
    ),
    "api.auth.internal_error": TranslationKey(
        "api.auth.internal_error",
        "Internal server error"
    ),
    "api.auth.user_not_found": TranslationKey(
        "api.auth.user_not_found",
        "User not found"
    ),
    # Library-string intercept (FastAPI's HTTPBearer "Not authenticated").
    "api.auth.not_authenticated": TranslationKey(
        "api.auth.not_authenticated",
        "Not authenticated"
    ),
    # Item-14 models/fetch dynamic provider errors (option b — English
    # fallback matches the frontend's exact bare string; {var} placeholders
    # are interpolated by t()).
    "user.unknown_provider": TranslationKey(
        "user.unknown_provider",
        "Unknown provider: {code}"
    ),
    "user.no_endpoint": TranslationKey(
        "user.no_endpoint",
        "No endpoint configured for this provider."
    ),
    "user.provider_returned": TranslationKey(
        "user.provider_returned",
        "Provider returned {status}: {text}"
    ),
    "user.connection_timeout_local": TranslationKey(
        "user.connection_timeout_local",
        "Connection timeout. Is {code} running at {baseUrl}?"
    ),
    "user.connection_timeout_remote": TranslationKey(
        "user.connection_timeout_remote",
        "Connection timeout for {code} at {baseUrl}"
    ),
    "user.api_key_required_fetch": TranslationKey(
        "user.api_key_required_fetch",
        "API key is required for this provider."
    ),
    "user.fetch_failed": TranslationKey(
        "user.fetch_failed",
        "fetch failed"
    ),
    # Item 31 — the discover route's success line. One key, parameterised, rather than
    # one per outcome kind: the counts are data, and the sentence that presents them is
    # translatable prose.
    "api.user.discovery_complete": TranslationKey(
        "api.user.discovery_complete",
        "Discovered {seen} model(s): {created} new here, {refreshed} already known, "
        "{pruned} no longer served."
    ),
    "api.user.model_not_served_by_connection": TranslationKey(
        "api.user.model_not_served_by_connection",
        'This connection does not serve "{model}". Its models may have changed — '
        'refresh the connection, or choose another model.'
    ),
    # Two keys were removed 2026-11-02, both reported as UNREFERENCED-KEY by
    # scripts/check-translations.py before removal rather than presumed dead:
    # `api.user.test_model_not_served` (superseded by
    # `api.user.model_not_served_by_connection`, which the route actually raises) and
    # `api.user.test_recording_unavailable` (which existed only for the interval when
    # the test route refused because the results store was being rebuilt — Item 22's
    # rewrite removed its last caller). Leaving either would keep a sentence in the
    # Translation table that no code path can reach.
    #
    # EIGHT MESSAGES, ONE PER FAILURE CLASS (plan Item 5 of
    # workbench-AI-timeout-policy-plan.html).
    #
    # `api.user.test_transport_failed` was retired rather than edited: it answered
    # every transport failure with one sentence, so a refused port, a dead host, a
    # bad hostname and an expired certificate all read the same — and none of them
    # told the user which fix applied. Leaving the key in place would let a stale row
    # in the Translation table resurrect the old sentence, so it is gone.
    #
    # Each says what was KEPT as well as what was withheld. Since Item 25 the
    # duration of a failed run is recorded on the connection — a connection that
    # takes 200 s to fail is slow in a way a user feels — so a message claiming
    # "nothing was recorded" would be false. What is withheld is the capability
    # verdict.
    "api.user.test_connect_refused": TranslationKey(
        "api.user.test_connect_refused",
        "Nothing is listening at that address — the server is reachable but no service "
        "answered. Check the port and that the AI server is running. No capability "
        "verdict was recorded; how long it took to fail was."
    ),
    "api.user.test_connect_timeout": TranslationKey(
        "api.user.test_connect_timeout",
        "The endpoint did not accept a connection in time. The host may be down, or a "
        "firewall may be dropping the request. No capability verdict was recorded; how "
        "long it took to fail was."
    ),
    "api.user.test_dns_failure": TranslationKey(
        "api.user.test_dns_failure",
        "The endpoint's hostname could not be resolved. Check the address for a typo, "
        "or for a name only this network can resolve. No capability verdict was "
        "recorded; how long it took to fail was."
    ),
    "api.user.test_tls_failure": TranslationKey(
        "api.user.test_tls_failure",
        "The secure connection could not be established — the endpoint may be plain "
        "http where https was expected, or its certificate may have expired. No "
        "capability verdict was recorded; how long it took to fail was."
    ),
    "api.user.test_read_timeout": TranslationKey(
        "api.user.test_read_timeout",
        "The model accepted the request but did not answer in time. It may be too slow "
        "for this host — a large model on a CPU can take several minutes. No capability "
        "verdict was recorded; how long it took to fail was."
    ),
    "api.user.test_http_status": TranslationKey(
        "api.user.test_http_status",
        "The provider answered, and its answer was an error: {detail}. No capability "
        "verdict was recorded; what the provider said is shown so the cause is clear."
    ),
    "api.user.test_budget_exhausted": TranslationKey(
        "api.user.test_budget_exhausted",
        "The model returned nothing because it used its whole output budget before "
        "reaching an answer. No capability verdict was recorded; the duration was."
    ),
    "api.user.test_other_failure": TranslationKey(
        "api.user.test_other_failure",
        "The model could not be reached, and the cause was not one this system "
        "recognises. No capability verdict was recorded: {detail}"
    ),
    # Timeouts on a connection (plan workbench-AI-timeout-policy-plan.html, Item 2).
    #
    # Three separate messages rather than one "invalid timeout", because an
    # administrator who typed a word, a decimal or a number above the ceiling is in
    # three different situations and fixes each differently.
    "api.user.invalid_connect_timeout": TranslationKey(
        "api.user.invalid_connect_timeout",
        "The connect timeout must be a whole number of seconds, at least 1 and "
        "at most {ceiling}"
    ),
    "api.user.invalid_probe_timeout": TranslationKey(
        "api.user.invalid_probe_timeout",
        "The test timeout must be a whole number of seconds, at least 1 and "
        "at most {ceiling}"
    ),
    "api.user.connect_timeout_exceeds_probe": TranslationKey(
        "api.user.connect_timeout_exceeds_probe",
        # States the pair, not just the rule: an administrator who has set one value
        # and is editing the other needs to see both numbers to know which to change.
        "The connect timeout ({connect}s) cannot be longer than the test timeout "
        "({probe}s) — a connection cannot be allowed to take longer to establish "
        "than the whole test may run"
    ),
    "api.user.test_not_implemented": TranslationKey(
        "api.user.test_not_implemented",
        'The test "{test}" is registered but has no probe yet'
    ),
    "user.no_models_returned": TranslationKey(
        "user.no_models_returned",
        "Provider returned no models; nothing was changed"
    ),
    # Item-18 database-connections (option b — English fallback = the
    # frontend's exact per-method string).
    "user.example_create_db": TranslationKey(
        "user.example_create_db",
        "Example users cannot create database connections"
    ),
    "user.example_update_db": TranslationKey(
        "user.example_update_db",
        "Example users cannot update database connections"
    ),
    "user.example_delete_db": TranslationKey(
        "user.example_delete_db",
        "Example users cannot delete database connections"
    ),
    "api.user.example_create_ai": TranslationKey(
        "api.user.example_create_ai",
        "Example users cannot create AI connections"
    ),
    "api.user.example_update_ai": TranslationKey(
        "api.user.example_update_ai",
        "Example users cannot update AI connections"
    ),
    "api.user.example_delete_ai": TranslationKey(
        "api.user.example_delete_ai",
        "Example users cannot delete AI connections"
    ),
    "api.user.connection_id_required": TranslationKey(
        "api.user.connection_id_required",
        "Connection id required"
    ),
    "api.user.invalid_connection_id": TranslationKey(
        "api.user.invalid_connection_id",
        "Invalid connection id"
    ),
    # Per-pair AI tuning (AI limits plan, Item 9).
    #
    # One 404 key for a connection the caller may not see OR that does not exist:
    # two keys would let a caller tell the cases apart, which is the disclosure the
    # 404 rule exists to prevent. The model miss has its own key because by then the
    # caller has already proved access to the connection.
    "api.user.tuning_connection_not_found": TranslationKey(
        "api.user.tuning_connection_not_found",
        "No such AI connection"
    ),
    "api.user.tuning_model_not_found": TranslationKey(
        "api.user.tuning_model_not_found",
        "No such model"
    ),
    "api.user.tuning_invalid_temperature": TranslationKey(
        "api.user.tuning_invalid_temperature",
        "Temperature must be a number between 0 and 2"
    ),
    "api.user.tuning_invalid_max_tokens": TranslationKey(
        "api.user.tuning_invalid_max_tokens",
        "The output limit must be a whole number of tokens, at least 1"
    ),
    "api.user.tuning_invalid_ai_timeout": TranslationKey(
        "api.user.tuning_invalid_ai_timeout",
        "The AI time limit must be a whole number of seconds, at least 1"
    ),
    "api.user.tuning_nothing_to_update": TranslationKey(
        "api.user.tuning_nothing_to_update",
        "Supply at least one of temperature, maxTokens or timeoutSeconds"
    ),
    "api.user.tuning_malformed_body": TranslationKey(
        "api.user.tuning_malformed_body",
        "The request body is not valid JSON"
    ),
    "user.auto_create_default_detail": TranslationKey(
        "user.auto_create_default_detail",
        "Dataset auto-creation failed. The database server may be unreachable."
    ),
    # Model suitability writer refusals (AI model suitability plan, Item 4).
    "api.user.model_not_found": TranslationKey(
        "api.user.model_not_found",
        'Model "{model}" not found for provider "{provider}"'
    ),
    "api.user.unknown_test_id": TranslationKey(
        "api.user.unknown_test_id",
        'Unknown test "{test}". Registered tests: {known}'
    ),
    "api.user.invalid_test_state": TranslationKey(
        "api.user.invalid_test_state",
        'Invalid test result "{state}". Allowed: {allowed}'
    ),
    "api.user.test_reason_required": TranslationKey(
        "api.user.test_reason_required",
        "A test result must record a reason"
    ),
    "api.user.test_attribution_required": TranslationKey(
        "api.user.test_attribution_required",
        "A test result must record who ran it"
    ),
}