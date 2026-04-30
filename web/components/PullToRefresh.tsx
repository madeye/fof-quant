"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const TRIGGER_DISTANCE = 72;
const MAX_PULL = 112;

type PullState = "idle" | "pulling" | "ready" | "refreshing";

export default function PullToRefresh() {
  const router = useRouter();
  const startY = useRef(0);
  const startX = useRef(0);
  const tracking = useRef(false);
  const [distance, setDistance] = useState(0);
  const [state, setState] = useState<PullState>("idle");

  useEffect(() => {
    const reset = () => {
      tracking.current = false;
      setDistance(0);
      setState("idle");
    };

    const onTouchStart = (event: TouchEvent) => {
      if (
        event.touches.length !== 1 ||
        window.scrollY > 0 ||
        shouldIgnoreTarget(event.target)
      ) {
        tracking.current = false;
        return;
      }
      const touch = event.touches[0];
      startY.current = touch.clientY;
      startX.current = touch.clientX;
      tracking.current = true;
    };

    const onTouchMove = (event: TouchEvent) => {
      if (!tracking.current || event.touches.length !== 1 || state === "refreshing") return;
      const touch = event.touches[0];
      const deltaY = touch.clientY - startY.current;
      const deltaX = touch.clientX - startX.current;
      if (deltaY <= 0) {
        reset();
        return;
      }
      if (Math.abs(deltaX) > deltaY * 0.85) {
        tracking.current = false;
        return;
      }
      if (window.scrollY > 0) {
        reset();
        return;
      }

      event.preventDefault();
      const eased = Math.min(MAX_PULL, deltaY * 0.55);
      setDistance(eased);
      setState(eased >= TRIGGER_DISTANCE ? "ready" : "pulling");
    };

    const onTouchEnd = () => {
      if (!tracking.current) return;
      tracking.current = false;
      if (distance >= TRIGGER_DISTANCE) {
        setState("refreshing");
        setDistance(TRIGGER_DISTANCE);
        router.refresh();
        window.setTimeout(reset, 900);
      } else {
        reset();
      }
    };

    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("touchend", onTouchEnd);
    window.addEventListener("touchcancel", reset);
    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("touchcancel", reset);
    };
  }, [distance, router, state]);

  const visible = state !== "idle";
  const label =
    state === "refreshing"
      ? "刷新中"
      : state === "ready"
        ? "释放刷新"
        : "下拉刷新";

  return (
    <div
      aria-live="polite"
      className={
        "pointer-events-none fixed left-0 right-0 z-30 flex justify-center transition-opacity duration-150 " +
        (visible ? "opacity-100" : "opacity-0")
      }
      style={{
        top: "calc(var(--safe-top) + 0.35rem)",
        transform: `translateY(${Math.max(0, distance - 44)}px)`,
      }}
    >
      <div className="rounded-full border border-slate-200 bg-white/95 px-3 py-1 text-xs font-medium text-slate-700 shadow-sm backdrop-blur dark:border-slate-700 dark:bg-slate-900/95 dark:text-slate-200">
        {label}
      </div>
    </div>
  );
}

function shouldIgnoreTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  return Boolean(
    target.closest(
      "input, textarea, select, button, [contenteditable=true], .table-wrap, [data-no-pull-refresh]"
    )
  );
}
