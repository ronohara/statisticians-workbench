import { NextResponse } from "next/server";

export async function GET() {
  try {
    const res = await fetch("http://127.0.0.1:8000/api/health");
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json({ version: data.version });
    }
  } catch {
    // Fallback — backend unreachable
  }
  return NextResponse.json({ version: "unknown" });
}
