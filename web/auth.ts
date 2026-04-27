import NextAuth, { type NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

function allowedEmails(): Set<string> {
  const raw = process.env.ALLOWED_USERS ?? "";
  return new Set(
    raw
      .split(/[,\s]+/)
      .map((entry) => entry.trim().toLowerCase())
      .filter(Boolean)
  );
}

export const config: NextAuthConfig = {
  providers: [Google],
  pages: {
    signIn: "/login",
  },
  session: { strategy: "jwt" },
  callbacks: {
    async signIn({ user }) {
      const email = (user.email ?? "").toLowerCase();
      const allowed = allowedEmails();
      if (allowed.size === 0) {
        // Fail closed when no allowlist is configured — the deployer must opt
        // someone in explicitly. Returning false sends the user to the
        // /login page with ?error=AccessDenied.
        return false;
      }
      return allowed.has(email);
    },
    async jwt({ token, user }) {
      if (user?.email) token.email = user.email;
      return token;
    },
    async session({ session, token }) {
      if (token.email && session.user) {
        session.user.email = token.email as string;
      }
      return session;
    },
  },
  trustHost: true,
};

export const { handlers, signIn, signOut, auth } = NextAuth(config);
