// frontend/types/next-auth.d.ts
import "next-auth";

declare module "next-auth" {
  interface User {
    isAdmin?: boolean;
    isExampleUser?: boolean;
    language?: string;
  }
  interface Session {
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      isAdmin?: boolean;
      isExampleUser?: boolean;
      language?: string;
    };
  }
}