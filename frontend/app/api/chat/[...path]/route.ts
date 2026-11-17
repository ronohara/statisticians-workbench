import { NextRequest, NextResponse } from "next/server";
import { proxyAuthHeaders } from "@/lib/api";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.length > 0 ? path.join("/") : "";
  const backendUrl = `http://127.0.0.1:8000/chat/${pathStr}`;

  const response = await fetch(backendUrl, {
    headers: proxyAuthHeaders(req),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.length > 0 ? path.join("/") : "";
  const backendUrl = `http://127.0.0.1:8000/chat/${pathStr}`;

  const body = await req.json();
  const response = await fetch(backendUrl, {
    method: "POST",
    headers: proxyAuthHeaders(req),
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.length > 0 ? path.join("/") : "";
  const backendUrl = `http://127.0.0.1:8000/chat/${pathStr}`;

  const body = await req.json();
  const response = await fetch(backendUrl, {
    method: "PATCH",
    headers: proxyAuthHeaders(req),
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.length > 0 ? path.join("/") : "";
  const backendUrl = `http://127.0.0.1:8000/chat/${pathStr}`;

  const response = await fetch(backendUrl, {
    method: "DELETE",
    headers: proxyAuthHeaders(req),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}