import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { auth, signOut } from "@/auth";
import ThemeToggle from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: "fof-quant 看板",
  description: "fof-quant 实验回测结果浏览与对比。",
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
          <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:gap-6">
            <Link href="/" className="text-lg font-semibold text-slate-950 dark:text-slate-50">
              fof-quant
            </Link>
            <nav className="flex gap-4 text-sm text-slate-600 dark:text-slate-300">
              <Link href="/" className="hover:text-slate-950 dark:hover:text-white">
                实验列表
              </Link>
            </nav>
            <div className="sm:ml-auto">
              <ThemeToggle />
            </div>
            {session?.user && (
              <div className="flex min-w-0 items-center gap-3 text-sm text-slate-600 dark:text-slate-300">
                <span className="min-w-0 truncate">{session.user.email}</span>
                <form
                  action={async () => {
                    "use server";
                    await signOut({ redirectTo: "/login" });
                  }}
                >
                  <button
                    type="submit"
                    className="btn min-h-9 px-3 py-1.5"
                  >
                    退出登录
                  </button>
                </form>
              </div>
            )}
          </div>
        </header>
        <main className="page-shell">{children}</main>
      </body>
    </html>
  );
}
