import { NextResponse } from "next/server";
import { auth } from "@/auth";

const PUBLIC_PATHS = ["/login"];

export default auth((req) => {
  const { pathname } = req.nextUrl;
  if (req.auth) return;
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return;
  }
  const loginUrl = new URL("/login", req.nextUrl);
  loginUrl.searchParams.set("callbackUrl", pathname + req.nextUrl.search);
  return NextResponse.redirect(loginUrl);
});

export const config = {
  // Match everything except Next.js internals, the NextAuth API routes, and
  // common static assets. The /api/auth/* path must stay open so the OAuth
  // round-trip can complete.
  matcher: ["/((?!api/auth|_next/static|_next/image|favicon.ico).*)"],
};
