import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { getBackendErrorResponse } from "@/lib/backend-error";
import { proxyAuthHeaders } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

async function proxyRequest(
  req: NextRequest,
  method: string,
): Promise<NextResponse> {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const url = new URL(req.url);
    const path = url.pathname.replace("/api/notebooks", "");
    const backendUrl = `${BACKEND_URL}/api/notebooks${path}${url.search}`;

    // For file uploads (multipart), forward the raw body with original Content-Type
    const reqContentType = req.headers.get("content-type") || "";
    const isMultipart = reqContentType.includes("multipart/form-data");

    const headers: Record<string, string> = {
      ...proxyAuthHeaders(req),
    };
    if (isMultipart) {
      // Preserve the original Content-Type with its boundary
      headers["Content-Type"] = reqContentType;
    }

    const fetchOptions: RequestInit = {
      method,
      headers,
    };

    if (method !== "GET" && method !== "HEAD") {
      if (isMultipart) {
        // Forward the raw body bytes as-is to preserve multipart boundary
        fetchOptions.body = Buffer.from(await req.arrayBuffer());
      } else {
        fetchOptions.body = await req.text();
        fetchOptions.body = fetchOptions.body || undefined;
      }
    }

    const response = await fetch(backendUrl, fetchOptions);

    // Forward binary responses as-is, parse JSON responses normally
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/pdf")) {
      const buffer = await response.arrayBuffer();
      return new NextResponse(buffer, {
        status: response.status,
        headers: { "Content-Type": contentType },
      });
    }

    const text = await response.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: response.status });
    } catch {
      return NextResponse.json(
        { detail: text.substring(0, 500) || "Backend error" },
        { status: response.status }
      );
    }
  } catch (error) {
    const { status, body } = getBackendErrorResponse(error);
    return NextResponse.json(body, { status });
  }
}

export async function GET(req: NextRequest) {
  return proxyRequest(req, "GET");
}

export async function POST(req: NextRequest) {
  return proxyRequest(req, "POST");
}

export async function PUT(req: NextRequest) {
  return proxyRequest(req, "PUT");
}

export async function PATCH(req: NextRequest) {
  return proxyRequest(req, "PATCH");
}

export async function DELETE(req: NextRequest) {
  return proxyRequest(req, "DELETE");
}
