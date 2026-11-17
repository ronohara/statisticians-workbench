import { NextRequest, NextResponse } from "next/server";
import { Client } from "pg";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { host, port, database, username, password } = body;

    if (!host || !port || !database || !username || !password) {
      return NextResponse.json(
        { success: false, error: "Missing required fields" },
        { status: 400 }
      );
    }

    const client = new Client({
      host,
      port: Number(port),
      database,
      user: username,
      password,
      connectionTimeoutMillis: 5000,
    });

    await client.connect();
    // Check if user has CREATE DATABASE rights
    let canCreateDatabase = false;
    try {
      const result = await client.query(
        "SELECT rolcreatedb FROM pg_catalog.pg_roles WHERE rolname = current_user"
      );
      canCreateDatabase = result.rows[0]?.rolcreatedb === true;
    } catch {
      // If we can't check, assume false
    }
    // Check if user has CREATE TABLE rights (test in public schema)
    let canCreateTables = false;
    try {
      await client.query("CREATE TABLE IF NOT EXISTS public._nb_test (id integer)");
      await client.query("DROP TABLE IF EXISTS public._nb_test");
      canCreateTables = true;
    } catch {
      // Try cleanup even on failure
      try { await client.query("DROP TABLE IF EXISTS public._nb_test"); } catch {}
    }
    await client.end();
    return NextResponse.json({ success: true, canCreateDatabase, canCreateTables });
  } catch (error: any) {
    console.error("PostgreSQL test connection error:", error);
    
    // Extract a clean user-facing error message
    let userMessage = "Unknown error";
    if (error.message) {
      // Try to extract the user-facing part from PostgreSQL errors
      // Errors like: error: database "bikeshop" does not exist
      // Or: error: connection refused
      const msg = error.message;
      // Look for common PostgreSQL error patterns
      const match = msg.match(/error:\s*(.+)/i);
      if (match) {
        userMessage = match[1].trim();
      } else {
        userMessage = msg;
      }
    }
    
    return NextResponse.json(
      { success: false, error: userMessage },
      { status: 500 }
    );
  }
}