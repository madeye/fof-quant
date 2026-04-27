import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { auth, signOut } from "@/auth";

export const metadata: Metadata = {
  title: "fof-quant 看板",
  description: "fof-quant 实验回测结果浏览与对比。",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await auth();
  return (
    <html lang="zh-CN">
      <body className="bg-slate-50 text-slate-900 min-h-screen">
        <header className="border-b bg-white">
          <div className="mx-auto max-w-6xl px-4 py-3 flex items-center gap-6">
            <Link href="/" className="font-semibold text-lg">
              fof-quant
            </Link>
            <nav className="text-sm text-slate-600 flex gap-4">
              <Link href="/" className="hover:text-slate-900">
                实验列表
              </Link>
            </nav>
            {session?.user && (
              <div className="ml-auto flex items-center gap-3 text-sm text-slate-600">
                <span>{session.user.email}</span>
                <form
                  action={async () => {
                    "use server";
                    await signOut({ redirectTo: "/login" });
                  }}
                >
                  <button
                    type="submit"
                    className="rounded border bg-white px-2 py-1 hover:bg-slate-100"
                  >
                    退出登录
                  </button>
                </form>
              </div>
            )}
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
