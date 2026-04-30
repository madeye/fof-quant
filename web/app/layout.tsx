import "./globals.css";
import Link from "next/link";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { auth, signOut } from "@/auth";
import ThemeToggle from "@/components/ThemeToggle";
import ServiceWorkerRegistrar from "@/components/ServiceWorkerRegistrar";
import PullToRefresh from "@/components/PullToRefresh";

export const metadata: Metadata = {
  title: "fof-quant 看板",
  description: "fof-quant 实验回测结果浏览与对比。",
  applicationName: "fof-quant",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "fof-quant",
  },
  icons: {
    icon: [
      { url: "/icons/icon.svg", type: "image/svg+xml" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafc" },
    { media: "(prefers-color-scheme: dark)", color: "#0f172a" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await auth();
  const themeScript = `
    (() => {
      try {
        const stored = localStorage.getItem("fof-theme");
        const dark = stored ? stored === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
        document.documentElement.classList.toggle("dark", dark);
        document.documentElement.dataset.theme = dark ? "dark" : "light";
      } catch {}
    })();
  `;
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
          <div className="app-header-inner mx-auto flex max-w-6xl flex-row flex-wrap items-center gap-x-3 gap-y-1 sm:gap-x-6 sm:pb-3">
            <Link
              href="/"
              className="inline-flex min-h-9 items-center text-base font-semibold text-slate-950 dark:text-slate-50 sm:min-h-10 sm:text-lg"
            >
              fof-quant
            </Link>
            <nav className="flex min-w-0 flex-1 overflow-x-auto text-sm text-slate-600 dark:text-slate-300 sm:flex-none sm:overflow-visible">
              <Link
                href="/"
                className="inline-flex min-h-9 shrink-0 items-center rounded-md px-2 hover:text-slate-950 dark:hover:text-white sm:min-h-10"
              >
                实验列表
              </Link>
            </nav>
            <div className="ml-auto">
              <ThemeToggle />
            </div>
            {session?.user && (
              <div className="flex min-w-0 items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <span className="hidden min-w-0 truncate sm:inline">{session.user.email}</span>
                <form
                  action={async () => {
                    "use server";
                    await signOut({ redirectTo: "/login" });
                  }}
                >
                  <button
                    type="submit"
                    className="btn min-h-9 px-2 py-1 text-xs sm:min-h-10 sm:px-3 sm:text-sm"
                  >
                    退出登录
                  </button>
                </form>
              </div>
            )}
          </div>
        </header>
        <main className="page-shell">{children}</main>
        <PullToRefresh />
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
