import { useRef, useCallback } from "react";

const LONG_PRESS_MS = 500;

/**
 * Rileva un long-press su un elemento touch.
 * `didFire()` restituisce true se il timer è scattato, così `onClick` può
 * ignorare il click successivo e non aprire il modal due volte.
 */
export function useLongPress(callback: () => void) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const movedRef = useRef(false);
  const firedRef = useRef(false);

  const start = useCallback(() => {
    movedRef.current = false;
    firedRef.current = false;
    timerRef.current = setTimeout(() => {
      if (!movedRef.current) {
        firedRef.current = true;
        callback();
      }
    }, LONG_PRESS_MS);
  }, [callback]);

  const cancel = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const onMove = useCallback(() => {
    movedRef.current = true;
    cancel();
  }, [cancel]);

  /** Ritorna true se il long-press è già scattato (usare in onClick per evitare doppio trigger) */
  const didFire = useCallback(() => firedRef.current, []);

  return {
    onTouchStart: start,
    onTouchEnd:   cancel,
    onTouchMove:  onMove,
    didFire,
  };
}
