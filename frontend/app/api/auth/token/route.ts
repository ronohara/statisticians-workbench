import { getToken } from "next-auth/jwt";
import { NextResponse, NextRequest } from "next/server";
import jwt from "jsonwebtoken";

export async function GET(req: NextRequest) {
  const sessionToken = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  if (!sessionToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendToken = jwt.sign(
    {
      id: sessionToken.id,
      email: sessionToken.email,
      isAdmin: sessionToken.isAdmin,
    },
    process.env.NEXTAUTH_SECRET!,
    { expiresIn: "1h" }
  );

  return NextResponse.json({ token: backendToken });
}