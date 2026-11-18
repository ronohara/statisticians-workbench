"""
Model-facing text for the AI-test concierge.

Deliberately NOT routed through the translation system, and this is the one
place in the codebase where that is correct rather than drift: every string in
this module is read by a model, never rendered to a user. The system prompt goes
into the request; the tool results go back to the model as JSON. A translated
system prompt would change the instrument per language, which is the opposite of
what a measurement needs.

Anything a *user* reads about a test result lives in the endpoint's translation
keys (`user/translations.py`) and the page's own module, not here.
"""

# The test concierge's whole instruction set. Deliberately short: a long prompt
# would make the instrument measure prompt-following at length rather than
# whether the model can drive a tool loop, and it would drift as it was tuned.
SYSTEM_PROMPT = (
    "You are evaluating a dataset. Use the tools available to you: read the "
    "dataset's schema, run one aggregate query over it, then report a finding "
    "with the tool provided. Answer in one or two sentences, using the numbers "
    "the tools returned."
)

# The single request a turn is given. Fixed, so every model is asked the same
# question and results are comparable between runs.
USER_REQUEST = (
    "How many rows are in this dataset, and what is the mean of its main "
    "numeric column? Use the tools to find out, then report what you found."
)

# The name of the tools, in the order they are offered.
TOOL_NAMES = [
    "test_dataset_schema",
    "test_run_query",
    "test_report_finding",
]
