import { NextResponse } from "next/server";
import { Client } from "pg";
import mysql from "mysql2/promise";
import { proxyAuthHeaders } from "@/lib/api";

export async function POST(req: Request) {
  const body = await req.json();
  const { type, host, port, database, username, password } = body;

  if (type === "postgresql") {
    const client = new Client({ host, port, database, user: username, password });
    try {
      await client.connect();
      await client.end();
      return NextResponse.json({ success: true });
    } catch (err: any) {
      return NextResponse.json({ success: false, error: err.message }, { status: 400 });
    }
  }

  if (type === "mysql") {
    try {
      const connection = await mysql.createConnection({
        host,
        port: port || 3306,
        database,
        user: username,
        password,
        connectTimeout: 10000,
      });
      await connection.end();
      return NextResponse.json({ success: true });
    } catch (err: any) {
      return NextResponse.json({ success: false, error: err.message }, { status: 400 });
    }
  }

  if (type === "mssql") {
    try {
      const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${backend}/api/datasets/test-mssql`, {
        method: "POST",
        headers: proxyAuthHeaders(req),
        body: JSON.stringify({ host, port, database, username, password }),
      });
      const data = await res.json();
      return NextResponse.json(data);
    } catch (err: any) {
      return NextResponse.json({ success: false, message: err.message }, { status: 500 });
    }
  }

  if (type === "access") {
    // Delegate to Python backend which has psycopg2 for msaccess-endpoint-ng
    try {
      const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${backend}/api/access/test`, {
        method: "POST",
        headers: proxyAuthHeaders(req),
        body: JSON.stringify({ file_path: database, host, port, user: username, password }),
      });
      const data = await res.json();
      return NextResponse.json(data);
    } catch (err: any) {
      return NextResponse.json({ success: false, message: err.message }, { status: 500 });
    }
  }

  return NextResponse.json({ success: false, error: `Unsupported database type: ${type}` }, { status: 400 });
}
