import { useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";

const SWIPE_THRESHOLD = 60;   // px orizzontali minimi per scattare la navigazione
const SWIPE_MAX_Y    = 80;    // px verticali massimi — oltre = l'utente sta scrollando

/**
 * Rileva uno swipe orizzontale sull'area main e naviga tra le tab del BottomNav.
 * Attivare solo su mobile (non chiamare i gestori se md+ breakpoint).
 */
export function useSwipeNavigation(routes: string[]) {
  const navigate  = useNavigate();
  const location  = useLocation();
  const startX    = useRef<number | null>(null);
  const startY    = useRef<number | null>(null);

  // Trova l'indice della route corrente
  const currentIndex = routes.findIndex((r) =>
    r === "/" ? location.pathname === "/" : location.pathname.startsWith(r)
  );

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    startX.current = e.touches[0].clientX;
    startY.current = e.touches[0].clientY;
  }, []);

  const onTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      if (startX.current === null || startY.current === null) return;

      const dx = e.changedTouches[0].clientX - startX.current;
      const dy = e.changedTouches[0].clientY - startY.current;
      startX.current = null;
      startY.current = null;

      // Ignora gesti prevalentemente verticali (scroll)
      if (Math.abs(dy) > SWIPE_MAX_Y) return;
      // Ignora gesti troppo corti
      if (Math.abs(dx) < SWIPE_THRESHOLD) return;

      if (dx < 0 && currentIndex < routes.length - 1) {
        // Swipe sinistro → tab successiva
        navigate(routes[currentIndex + 1]);
      } else if (dx > 0 && currentIndex > 0) {
        // Swipe destro → tab precedente
        navigate(routes[currentIndex - 1]);
      }
    },
    [currentIndex, navigate, routes]
  );

  return { onTouchStart, onTouchEnd };
}
