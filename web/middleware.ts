import { NextResponse } from "next/server";
import { auth } from "@/auth";

// PWA assets must load before login so the browser can install the app and
// the service worker can boot on the public /login route.
const PUBLIC_PATHS = ["/login", "/manifest.webmanifest", "/sw.js", "/icons"];

export default auth((req) => {
  const { pathname } = req.nextUrl;
  if (req.auth) return;
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return;
  }
  // For API requests, return 401 JSON so client fetches don't follow the
  // redirect into HTML and break their JSON parsing. The page-level
  // redirect-to-/login still happens for navigation requests.
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "未登录" }, { status: 401 });
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
