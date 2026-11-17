import { NextRequest, NextResponse } from "next/server";
import mysql from "mysql2/promise";

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

    const connection = await mysql.createConnection({
      host,
      port: Number(port),
      database,
      user: username,
      password,
      connectTimeout: 5000,
    });

    // Check if user has CREATE DATABASE rights
    let canCreateDatabase = false;
    try {
      const [rows] = await connection.query("SHOW GRANTS FOR CURRENT_USER");
      const grants = (rows as any[]).map((r: any) => Object.values(r)[0] as string).join(" ");
      canCreateDatabase = /CREATE DATABASE/i.test(grants) || /ALL PRIVILEGES/i.test(grants) || /\*\.\*/i.test(grants);
    } catch {
      // If we can't check, assume false
    }
    // Check if user has CREATE TABLE rights (test in current database)
    let canCreateTables = false;
    try {
      await connection.query("CREATE TABLE IF NOT EXISTS _nb_test (id INT)");
      await connection.query("DROP TABLE IF EXISTS _nb_test");
      canCreateTables = true;
    } catch {
      try { await connection.query("DROP TABLE IF EXISTS _nb_test"); } catch {}
    }
    await connection.end();
    return NextResponse.json({ success: true, canCreateDatabase, canCreateTables });
  } catch (error: any) {
    console.error("MySQL test connection error:", error);
    
    // Extract a clean user-facing error message
    let userMessage = "Unknown error";
    if (error.message) {
      // MySQL errors often include the user-facing message in the message string
      // Try to extract the most relevant part
      const msg = error.message;
      // Look for common MySQL error patterns
      const match = msg.match(/ER_[A-Z_]+\s*:\s*(.+)/i);
      if (match) {
        userMessage = match[1].trim();
      } else {
        // Fall back to the full message but clean it up
        userMessage = msg.split("(")[0].trim() || msg;
      }
    }
    
    return NextResponse.json(
      { success: false, error: userMessage },
      { status: 500 }
    );
  }
}