import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";
import jwt from "jsonwebtoken";

export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;

  // Public paths that don't require authentication
  const publicPaths = [
    "/login",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/verify-email",
    "/resend-verification",
    "/api/auth",
    "/api/translations",
    "/api/languages",
    "/api/version",
    "/api/public-settings",
    "/api/register",
  ];

  // Check if the path is public
  const isPublicPath = publicPaths.some(
    (p) => path === p || path.startsWith(`${p}/`)
  );

  // Get the session token
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET,
  });

  // Redirect to login if not authenticated and trying to access protected path
  if (!token && !isPublicPath) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", path);
    return NextResponse.redirect(loginUrl);
  }

  // Auth bridge: mint a backend-shaped Bearer from the validated session
  // and attach it to authenticated API requests (strip any incoming first).
  // Layer-2 handlers ignore this header (they authenticate by session
  // cookie); the :8000 backend expects it. Same token shape and secret as
  // /api/auth/token. Revert = delete this block.
  let requestHeaders: Headers | undefined;
  if (token && token.id && path.startsWith("/api")) {
    const backendToken = jwt.sign(
      { id: token.id, email: token.email, isAdmin: token.isAdmin },
      process.env.NEXTAUTH_SECRET!,
      { expiresIn: "1h" }
    );
    requestHeaders = new Headers(request.headers);
    requestHeaders.delete("authorization");
    requestHeaders.set("authorization", `Bearer ${backendToken}`);
  }

  // Role authorization lives in the route handlers (fresh DB checks), not
  // here: the middleware's job is session validation + the Bearer bridge.
  return NextResponse.next(requestHeaders ? { request: { headers: requestHeaders } } : undefined);
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};