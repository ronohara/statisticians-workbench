import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { getBackendErrorResponse } from "@/lib/backend-error";
import { proxyAuthHeaders } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const url = new URL(req.url);
    const path = url.pathname.replace("/api/dbdesign", "");
    const backendUrl = `${BACKEND_URL}/api/dbdesign${path}${url.search}`;

    // 15-minute timeout for AI-augmented analysis (Node.js undici defaults to 5 min
    // body timeout; AbortSignal.timeout applies to the full request including the stream)
    const response = await fetch(backendUrl, {
      headers: {
        ...proxyAuthHeaders(req),
        "Accept": "text/event-stream, application/json",
      },
      signal: AbortSignal.timeout(900_000),
    });

    // Stream SSE responses without buffering
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      return new NextResponse(response.body, {
        status: response.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
        },
      });
    }

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    const { status, body } = getBackendErrorResponse(error);
    return NextResponse.json(body, { status });
  }
}

export async function POST(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const url = new URL(req.url);
    const path = url.pathname.replace("/api/dbdesign", "");
    const backendUrl = `${BACKEND_URL}/api/dbdesign${path}`;

    const body = await req.text();
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: proxyAuthHeaders(req),
      body: body || undefined,
    });

    // Forward binary responses (PDF) as-is, parse JSON responses normally
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/pdf")) {
      const pdfBuffer = await response.arrayBuffer();
      return new NextResponse(pdfBuffer, {
        status: response.status,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": response.headers.get("content-disposition") || "attachment",
        },
      });
    }

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    const { status, body } = getBackendErrorResponse(error);
    return NextResponse.json(body, { status });
  }
}
