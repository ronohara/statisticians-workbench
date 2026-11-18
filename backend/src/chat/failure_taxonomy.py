"""
Failure taxonomy — the closed set of ways an AI request can fail.

This is the vocabulary, not the mapping. It says what a failure can *be*; the
provider layer decides which one happened (plan Item 5) and the probe decides
whether to try again (Item 6). Keeping the three apart is what lets the retry
rule be a table keyed by a declared value instead of a string test over an error
message.

WHY A CLOSED SET RATHER THAN A STRING

The code this replaces classified failures by searching the provider's error text
for digits — `_provider_says_no_such_model` returns true when any colon-separated
token is `404`. Measured consequence, 2026-11-02: OpenRouter answered
`OPENAI_HTTP_ERROR:400` with the body *"qwen2.5:7b-instruct is not a valid model
ID"*, and the route reported *"The model could not be reached"* — a provider that
answered clearly was described as unreachable. A token search cannot tell a status
code from a body that happens to contain one.

WHY THESE EIGHT AND NOT FEWER

Each one sends a user to a different fix, which is the test for whether a class
earns its place:

  connect_refused   something answered and said no. Wrong port, service stopped.
                    Fix: check the endpoint and start the service.
  connect_timeout   nothing answered at all. Dead host, firewall dropping SYN.
                    Fix: check the machine is up and the route is open.
  dns_failure       the name does not resolve. Typo, missing record, offline.
                    Fix: the hostname, not the server.
  tls_failure       connected, and the handshake failed. http where https was
                    meant, or an expired certificate.
                    Fix: the scheme or the certificate.
  read_timeout      connected, asked, and the answer never came. Slow or hung.
                    Fix: a smaller model, more time, or a different host.
  http_status       the provider answered with a status. The status travels
                    beside the class, because 402, 404 and 429 are different
                    problems with different owners.
  budget_exhausted  the model returned nothing because it spent its tokens.
                    A fact about the run, not about the model.
  other             none of the above, and the raw detail travels with it.

`budget_exhausted` is a class here and not a verdict key in
`probe_vocabulary.py`, and the two are not duplicates. There, `INCONCLUSIVE` is
what a probe *returns* when it has no answer; here, `budget_exhausted` is *why*
the request failed. A transport failure can be classified while still having no
outcome to record, which is exactly the combination Item 25 of
`workbench-AI-models-testing-plan-v2.html` needed and could not express.

SPELLED IDENTICALLY IN BOTH BACKENDS

These strings are compared across the port, so they are byte-identical to
`workbench-go/internal/llm/failures/failures.go` — the project's shared-identifier
rule. The Go suite parses this file's declarations and fails if the two sets
differ, so a change on one side cannot pass review on the other.
"""

import socket
import ssl

import httpx

# The eight classes. Flat module-level names, like the rest of this package's
# vocabulary, so a call site references one by name and never by a built string.
CONNECT_REFUSED = "connect_refused"
CONNECT_TIMEOUT = "connect_timeout"
DNS_FAILURE = "dns_failure"
TLS_FAILURE = "tls_failure"
READ_TIMEOUT = "read_timeout"
HTTP_STATUS = "http_status"
BUDGET_EXHAUSTED = "budget_exhausted"
OTHER = "other"

#: Every class, and nothing outside it. A frozenset rather than a list because
#: the question asked of it is membership, and because two classes with the same
#: value would be a declaration bug that a list would silently accept.
ALL = frozenset({
    CONNECT_REFUSED,
    CONNECT_TIMEOUT,
    DNS_FAILURE,
    TLS_FAILURE,
    READ_TIMEOUT,
    HTTP_STATUS,
    BUDGET_EXHAUSTED,
    OTHER,
})


class ProviderError(ValueError):
    """A provider call failed, and this says how.

    Subclasses `ValueError` deliberately. Every existing handler catches ValueError
    — the probe, the concierge, the route — and changing the base class would mean
    touching all of them at once. What changes is that the exception now CARRIES the
    class instead of being flattened to a string that a later regex has to guess at.

    That flattening is the defect this replaces. The code used to raise
    `ValueError("OLLAMA_ERROR:...")` and classify by searching the text for digits
    and the word TIMEOUT; measured 2026-11-02, OpenRouter answered
    `OPENAI_HTTP_ERROR:400` with a body saying "not a valid model ID" and the route
    reported "the model could not be reached".
    """

    def __init__(self, detail: str, failure_class: str = OTHER, http_status: int | None = None):
        if not is_known(failure_class):
            # A class outside the declared set would be invisible to every consumer
            # that switches on it, and would look like `other` without the honesty.
            raise ValueError(f"unknown failure class: {failure_class!r}")
        self.detail = detail
        self.failure_class = failure_class
        self.http_status = http_status
        super().__init__(detail)


def classify_exception(exc: BaseException) -> tuple[str, int | None]:
    """Which class `exc` represents, and the HTTP status if it carried one.

    Called by the provider where the exception is caught — the only point at which
    its TYPE is still available. Everything downstream sees a detail string, and a
    string cannot be classified reliably: that is F5.

    The chain is walked because httpx wraps the operating system's error as
    `__cause__`. A refused connection arrives as `httpx.ConnectError` whose cause is
    `ConnectionRefusedError`; a bad hostname as `ConnectError` caused by
    `socket.gaierror`. Reading only the outermost type would collapse all three
    connect-phase failures into one — which is the thing being fixed.

    `httpx.ConnectTimeout` and `httpx.ReadTimeout` are SIBLINGS under
    `httpx.TimeoutException` — neither is a subclass of the other, and neither is a
    builtin `TimeoutError`. Checked against the installed httpx 0.28.1:

        ConnectTimeout → TimeoutException → TransportError → RequestError → HTTPError

    So the two cannot be confused by ordering. The builtin `TimeoutError` is a
    separate hierarchy entirely — it is what `asyncio.timeout` raises — and it is
    checked last because it says nothing about which phase elapsed.
    """
    chain: list[BaseException] = []
    node: BaseException | None = exc
    while node is not None and len(chain) < 12:  # a cycle guard; cause chains are short
        chain.append(node)
        node = node.__cause__ or node.__context__

    for node in chain:
        if isinstance(node, httpx.HTTPStatusError):
            status = node.response.status_code if node.response is not None else None
            return HTTP_STATUS, status
        if isinstance(node, ConnectionRefusedError):
            return CONNECT_REFUSED, None
        if isinstance(node, socket.gaierror):
            return DNS_FAILURE, None
        if isinstance(node, ssl.SSLError):
            return TLS_FAILURE, None
        if isinstance(node, httpx.ConnectTimeout):
            return CONNECT_TIMEOUT, None
        if isinstance(node, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
            return READ_TIMEOUT, None

    # A bare TimeoutError is what our own `asyncio.timeout` raises, and it does not
    # say which phase it was in. Reported as a read timeout because the connect phase
    # has its own deadline and would have produced ConnectTimeout above.
    for node in chain:
        if isinstance(node, TimeoutError):
            return READ_TIMEOUT, None

    return OTHER, None


#: How many EXTRA attempts each class is worth, beyond the first.
#:
#: The principle, in one line: retry what is cheap and might be a blip; do not retry
#: what has already waited out a budget.
#:
#:   connect_refused  0  cheap to retry, but it will refuse again. Something answered
#:                       and said no; asking twice changes nothing.
#:   connect_timeout  1  cheap — the connect deadline is seconds, not minutes — and a
#:                       single dropped SYN is a real transient.
#:   dns_failure      1  likewise cheap, and a resolver can hiccup.
#:   tls_failure      0  a certificate or a scheme does not repair itself.
#:   read_timeout     0  the whole budget has already been spent. Retrying would
#:                       double the wait for a model that has shown it cannot answer
#:                       in time.
#:   budget_exhausted 0  a property of the model's output, not of the network.
#:   other            0  unknown means unknown; retrying an unexplained failure three
#:                       times is how a 20-minute wait happened.
#:
#: `http_status` is the one conditional entry and lives in `retry_attempts` below.
#:
#: DECLARED HERE, beside the classes, so the two cannot drift — a class added without
#: a retry policy would silently inherit `other`'s zero, and the test that walks ALL
#: fails if this table has no entry for a class.
RETRY_EXTRA_ATTEMPTS = {
    CONNECT_REFUSED: 0,
    CONNECT_TIMEOUT: 1,
    DNS_FAILURE: 1,
    TLS_FAILURE: 0,
    READ_TIMEOUT: 0,
    BUDGET_EXHAUSTED: 0,
    OTHER: 0,
}

#: A 5xx is the provider saying "I failed", which can be momentary; a 4xx is it saying
#: "your request is wrong", which will not change on a second identical request.
_HTTP_STATUS_RETRY = {5: 1}  # keyed by the hundred: 5xx → one retry, everything else → none


def retry_attempts(failure_class: str, http_status: int | None = None) -> int:
    """Extra attempts to allow after a failure of this class.

    Total attempts for a call is 1 + this value, capped by the probe's own ceiling.

    Unknown classes get 0 rather than a default of 1. An unrecognised failure is one
    nothing can reason about, and retrying it is what turned a silent-drop host into
    an eight-minute wait.
    """
    if failure_class == HTTP_STATUS:
        if http_status is None:
            return 0
        return _HTTP_STATUS_RETRY.get(http_status // 100, 0)
    return RETRY_EXTRA_ATTEMPTS.get(failure_class, 0)


def is_known(value: str) -> bool:
    """Whether `value` is one of the declared classes.

    A plain membership test rather than a `try` around a lookup, because callers
    of this ask the question directly — the retry table and the message table both
    need to know before they look anything up.
    """
    return value in ALL
