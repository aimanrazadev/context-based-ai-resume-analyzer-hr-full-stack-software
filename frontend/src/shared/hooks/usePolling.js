import { useEffect, useRef } from "react";

export function usePolling({
  enabled,
  intervalMs = 1000,
  maxAttempts = Infinity,
  request,
  stopWhen,
  onSuccess,
  onError,
}) {
  const requestRef = useRef(request);
  const stopWhenRef = useRef(stopWhen);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    requestRef.current = request;
    stopWhenRef.current = stopWhen;
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
  }, [request, stopWhen, onSuccess, onError]);

  useEffect(() => {
    if (!enabled) return undefined;

    let attempts = 0;
    let cancelled = false;
    let timer = null;

    const stop = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };

    const tick = async () => {
      attempts += 1;
      try {
        const result = await requestRef.current?.();
        if (cancelled) return;
        onSuccessRef.current?.(result, attempts);
        if (stopWhenRef.current?.(result, attempts) || attempts >= maxAttempts) {
          stop();
        }
      } catch (error) {
        if (cancelled) return;
        onErrorRef.current?.(error, attempts);
        if (attempts >= maxAttempts) {
          stop();
        }
      }
    };

    tick();
    timer = setInterval(tick, intervalMs);

    return () => {
      cancelled = true;
      stop();
    };
  }, [enabled, intervalMs, maxAttempts]);
}
