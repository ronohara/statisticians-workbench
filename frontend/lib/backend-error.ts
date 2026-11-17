/**
 * Shared utility for handling backend proxy errors.
 * Returns a user-friendly error message with a translation key
 * that the frontend can display and the user can report to a help desk.
 */

export function getBackendErrorResponse(error: unknown) {
  const errorMessage = error instanceof Error ? error.message : String(error);
  const cause = (error as any)?.cause;

  // Detect backend connection failures
  if (
    cause?.code === "ECONNREFUSED" ||
    cause?.code === "ENOTFOUND" ||
    cause?.code === "ECONNRESET" ||
    errorMessage.includes("ECONNREFUSED") ||
    errorMessage.includes("fetch failed")
  ) {
    console.error("Backend connection error:", errorMessage);
    return {
      status: 503,
      body: {
        error: "api.backend.unavailable",
        message:
          "The backend analysis service is not running. " +
          "Please start it with: cd backend && source venv/bin/activate && " +
          "uvicorn main:app --host 0.0.0.0 --port 8000. " +
          "If the problem persists, contact the help desk.",
      },
    };
  }

  // General proxy error
  console.error("Backend proxy error:", errorMessage);
  return {
    status: 502,
    body: {
      error: "api.backend.proxy_error",
      message:
        "The backend analysis service returned an unexpected error. " +
        "Please try again. If the problem persists, contact the help desk.",
    },
  };
}
