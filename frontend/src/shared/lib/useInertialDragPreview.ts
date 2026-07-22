import { useCallback, useEffect, useRef } from "react";

type PreviewMotion = {
  active: boolean;
  initialized: boolean;
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  tilt: number;
  targetTilt: number;
  lift: number;
  targetLift: number;
  scale: number;
  targetScale: number;
  lastPointerX: number;
  lastPointerY: number;
  lastPointerTime: number;
};

export function useInertialDragPreview({ verticalOffset = 12, maxTilt = 7 } = {}) {
  const previewRef = useRef<HTMLDivElement>(null);
  const animationFrameRef = useRef<number | null>(null);
  const motionRef = useRef<PreviewMotion>(createPreviewMotion());

  const animatePreview = useCallback(function animate() {
    const motion = motionRef.current;
    const preview = previewRef.current;
    if (!motion.active) {
      animationFrameRef.current = null;
      return;
    }
    if (preview) {
      if (!motion.initialized) {
        motion.x = motion.targetX;
        motion.y = motion.targetY;
        motion.initialized = true;
      }
      motion.x += (motion.targetX - motion.x) * .42;
      motion.y += (motion.targetY - motion.y) * .42;
      motion.tilt += (motion.targetTilt - motion.tilt) * .24;
      motion.lift += (motion.targetLift - motion.lift) * .2;
      motion.scale += (motion.targetScale - motion.scale) * .2;
      motion.targetTilt *= .84;
      motion.targetLift *= .86;
      motion.targetScale += (1 - motion.targetScale) * .14;
      preview.style.transform = `translate3d(${motion.x - preview.offsetWidth / 2}px, ${motion.y + verticalOffset}px, 0)`;
      const surface = preview.firstElementChild as HTMLElement | null;
      surface?.style.setProperty("--drag-preview-tilt", `${motion.tilt.toFixed(2)}deg`);
      surface?.style.setProperty("--drag-preview-lift", `${motion.lift.toFixed(2)}px`);
      surface?.style.setProperty("--drag-preview-scale", motion.scale.toFixed(3));
    }
    animationFrameRef.current = requestAnimationFrame(animate);
  }, [verticalOffset]);

  const startPreview = useCallback((x: number, y: number) => {
    if (animationFrameRef.current !== null) cancelAnimationFrame(animationFrameRef.current);
    const motion = motionRef.current;
    Object.assign(motion, createPreviewMotion(), {
      active: true,
      targetX: x,
      targetY: y,
      lastPointerX: x,
      lastPointerY: y,
      lastPointerTime: performance.now(),
    });
    animationFrameRef.current = requestAnimationFrame(animatePreview);
  }, [animatePreview]);

  const movePreview = useCallback((x: number, y: number) => {
    const motion = motionRef.current;
    if (!motion.active) return;
    const now = performance.now();
    const elapsed = Math.max(8, now - motion.lastPointerTime);
    const velocityX = (x - motion.lastPointerX) / elapsed;
    const velocityY = (y - motion.lastPointerY) / elapsed;
    const speed = Math.hypot(velocityX, velocityY);
    motion.targetX = x;
    motion.targetY = y;
    motion.targetTilt = Math.max(-maxTilt, Math.min(maxTilt, velocityX * 5.2));
    motion.targetLift = -Math.min(2.4, speed * 1.15);
    motion.targetScale = 1 + Math.min(.028, speed * .012);
    motion.lastPointerX = x;
    motion.lastPointerY = y;
    motion.lastPointerTime = now;
  }, [maxTilt]);

  const stopPreview = useCallback(() => {
    motionRef.current.active = false;
    if (animationFrameRef.current !== null) cancelAnimationFrame(animationFrameRef.current);
    animationFrameRef.current = null;
  }, []);

  useEffect(() => stopPreview, [stopPreview]);

  return { previewRef, startPreview, movePreview, stopPreview };
}

function createPreviewMotion(): PreviewMotion {
  return {
    active: false,
    initialized: false,
    x: 0,
    y: 0,
    targetX: 0,
    targetY: 0,
    tilt: 0,
    targetTilt: 0,
    lift: 0,
    targetLift: 0,
    scale: 1,
    targetScale: 1,
    lastPointerX: 0,
    lastPointerY: 0,
    lastPointerTime: 0,
  };
}
