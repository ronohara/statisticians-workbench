import "dotenv/config";
import { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import jwt from "jsonwebtoken";

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        language: { label: "Language", type: "text" }, // Add language field
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${backendUrl}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials?.email,
            password: credentials?.password,
            language: credentials?.language,
          }),
        });

        if (!res.ok) {
          let code = "INVALID_CREDENTIALS";
          let message = "Invalid email or password.";
          let language = "en";
          try {
            const data = await res.json();
            if (data && typeof data === "object") {
              if (data.error === "auth.email_not_verified") {
                code = "EMAIL_NOT_VERIFIED";
              } else if (data.error === "auth.account_deleted") {
                code = "ACCOUNT_DELETED";
              }
              if (typeof data.message === "string" && data.message) {
                message = data.message;
              }
              if (typeof data.language === "string" && data.language) {
                language = data.language;
              }
            }
          } catch {
            // Non-JSON error body — fall back to the defaults.
          }
          throw new Error(JSON.stringify({ code, message, language }));
        }

        const user = await res.json();
        return {
          id: user.id,
          email: user.email,
          name: user.name,
          isAdmin: user.isAdmin,
          isExampleUser: user.isExampleUser,
          // Store the language from credentials for Example Users
          language: user.isExampleUser
            ? credentials?.language || user.language
            : user.language,
        };
      },
    }),
  ],
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.isExampleUser = user.isExampleUser;
        // Store language in token for session
        token.language = user.language;
        token.id = user.id;
        token.isAdmin = user.isAdmin;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.isAdmin = token.isAdmin as boolean;
        session.user.isExampleUser = token.isExampleUser as boolean;
        // Pass language to session for Example Users
        session.user.language = token.language as string;
        // Refresh name/email from the backend on every session fetch: the JWT
        // caches them at sign-in and goes stale after a profile edit, which
        // made the /settings/profile name revert immediately after save.
        if (token.id) {
          try {
            const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
            const backendToken = jwt.sign(
              { id: token.id, email: token.email, isAdmin: token.isAdmin },
              process.env.NEXTAUTH_SECRET!,
              { expiresIn: "1h" }
            );
            const res = await fetch(`${backendUrl}/api/user/profile`, {
              headers: { Authorization: `Bearer ${backendToken}` },
            });
            if (res.ok) {
              const data = await res.json();
              if (data && typeof data.name === "string") {
                session.user.name = data.name;
              }
              if (data && typeof data.email === "string") {
                session.user.email = data.email;
              }
            }
          } catch {
            // Backend unreachable or profile fetch failed — keep the token's
            // cached name/email rather than failing the session.
          }
        }
      }
      return session;
    },
  },
};