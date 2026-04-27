import { signIn } from "@/auth";

const ERRORS: Record<string, string> = {
  AccessDenied: "该 Google 账号没有访问权限。请联系管理员将邮箱加入 ALLOWED_USERS。",
  Configuration: "服务器未配置 Google OAuth；请检查 .env 中的 AUTH_GOOGLE_ID / AUTH_GOOGLE_SECRET。",
  Verification: "登录链接已过期，请重试。",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string; error?: string }>;
}) {
  const { callbackUrl = "/", error } = await searchParams;
  const errorMessage = error ? (ERRORS[error] ?? `登录失败：${error}`) : null;

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <form
        action={async () => {
          "use server";
          await signIn("google", { redirectTo: callbackUrl });
        }}
        className="w-full max-w-sm space-y-4 rounded border bg-white p-6 shadow-sm"
      >
        <h1 className="text-lg font-semibold">登录 fof-quant 看板</h1>
        <p className="text-sm text-slate-600">
          仅允许白名单内的 Google 账号登录。
        </p>
        {errorMessage && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {errorMessage}
          </div>
        )}
        <button
          type="submit"
          className="flex w-full items-center justify-center gap-2 rounded border bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
        >
          <GoogleMark />
          使用 Google 账号登录
        </button>
      </form>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#4285F4"
        d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
      />
    </svg>
  );
}
