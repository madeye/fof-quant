import NextAuth, { type NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

const TEST_PROVIDER_ID = "test-token";

function allowedEmails(): Set<string> {
  const raw = process.env.ALLOWED_USERS ?? "";
  return new Set(
    raw
      .split(/[,\s]+/)
      .map((entry) => entry.trim().toLowerCase())
      .filter(Boolean)
  );
}

function testTokenEnv(): { token: string; email: string } | null {
  const token = process.env.AUTH_TEST_TOKEN ?? "";
  if (!token) return null;
  const email =
    (process.env.AUTH_TEST_EMAIL ?? "").trim() ||
    Array.from(allowedEmails())[0] ||
    "";
  if (!email) return null;
  return { token, email };
}

export const isTestLoginEnabled = (): boolean => testTokenEnv() !== null;

const providers: NextAuthConfig["providers"] = [Google];

const testEnv = testTokenEnv();
if (testEnv) {
  providers.push(
    Credentials({
      id: TEST_PROVIDER_ID,
      name: "Test Token",
      credentials: {
        token: { label: "Test token", type: "password" },
      },
      async authorize(credentials) {
        const provided = String(credentials?.token ?? "");
        // Constant-time comparison via Node's crypto would be ideal here, but
        // the token is checked once per login (not on every request) and we
        // already gate this provider behind a deploy-time env var, so a string
        // compare is acceptable for the test-only surface.
        if (provided && provided === testEnv.token) {
          return { id: testEnv.email, email: testEnv.email, name: "Test User" };
        }
        return null;
      },
    })
  );
}

export const config: NextAuthConfig = {
  providers,
  pages: {
    signIn: "/login",
  },
  session: { strategy: "jwt" },
  callbacks: {
    async signIn({ user, account }) {
      // The test-token provider has already validated the token via authorize();
      // skip the allowlist so headless tests can sign in regardless of which
      // email AUTH_TEST_EMAIL points at.
      if (account?.provider === TEST_PROVIDER_ID) return true;
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
