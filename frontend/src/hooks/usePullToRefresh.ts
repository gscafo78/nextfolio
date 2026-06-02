import { useEffect, useRef, useState } from "react";

interface Options {
  onRefresh: () => Promise<void> | void;
  threshold?: number;   // px to pull before triggering
  resistance?: number;  // divisor to slow down the pull visual
}

export function usePullToRefresh({ onRefresh, threshold = 72, resistance = 2.5 }: Options) {
  const [pullY, setPullY] = useState(0);       // visual offset in px
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef<number | null>(null);
  const pulling = useRef(false);

  useEffect(() => {
    const el = document.documentElement;

    function onTouchStart(e: TouchEvent) {
      // Only activate when page is scrolled to the very top
      if (el.scrollTop > 0) return;
      startY.current = e.touches[0].clientY;
      pulling.current = true;
    }

    function onTouchMove(e: TouchEvent) {
      if (!pulling.current || startY.current === null) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy <= 0) { setPullY(0); return; }
      // Prevent native scroll while pulling
      if (el.scrollTop === 0 && dy > 8) e.preventDefault();
      setPullY(Math.min(dy / resistance, threshold * 1.4));
    }

    async function onTouchEnd() {
      if (!pulling.current) return;
      pulling.current = false;
      const y = pullY;
      setPullY(0);
      startY.current = null;
      if (y >= threshold / resistance && !refreshing) {
        setRefreshing(true);
        try { await onRefresh(); } finally { setRefreshing(false); }
      }
    }

    document.addEventListener("touchstart", onTouchStart, { passive: true });
    document.addEventListener("touchmove", onTouchMove, { passive: false });
    document.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      document.removeEventListener("touchstart", onTouchStart);
      document.removeEventListener("touchmove", onTouchMove);
      document.removeEventListener("touchend", onTouchEnd);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pullY, refreshing]);

  return { pullY, refreshing };
}
