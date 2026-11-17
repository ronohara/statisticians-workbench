import { NextRequest, NextResponse } from "next/server";
import { proxyAuthHeaders } from "@/lib/api";

export async function GET(req: NextRequest) {
  const backendUrl = "http://127.0.0.1:8000/chat/";

  const response = await fetch(backendUrl, {
    headers: proxyAuthHeaders(req),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function POST(req: NextRequest) {
  const backendUrl = "http://127.0.0.1:8000/chat/";

  const body = await req.json();
  const response = await fetch(backendUrl, {
    method: "POST",
    headers: proxyAuthHeaders(req),
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}