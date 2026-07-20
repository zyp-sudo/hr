import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { MotionPathPlugin } from 'gsap/MotionPathPlugin';

gsap.registerPlugin(ScrollTrigger, MotionPathPlugin);

/* Detect reduced-motion preference once */
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/* Detect mobile once */
function isMobileViewport(): boolean {
  if (typeof window === 'undefined') return false;
  return window.innerWidth <= 768;
}

/**
 * Build a cubic-bezier SVG path string connecting two points with a rightward arc.
 * The path goes from start → slight right drift → accelerates up-right to end.
 */
function buildStarPath(
  sx: number, sy: number, // start (relative to container)
  ex: number, ey: number  // end (relative to container)
): string {
  const dx = ex - sx;
  const dy = ey - sy;
  const cp1x = sx + dx * 0.28;
  const cp1y = sy - Math.max(80, Math.abs(dy) * 1.4);
  const cp2x = ex - dx * 0.18;
  const cp2y = ey + Math.max(70, Math.abs(dy) * 1.1);
  return `M ${sx} ${sy} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${ex} ${ey}`;
}

/* Full right-to-left paths: enter, pass behind the title, emerge on the left,
   then curl around the lower edge to complete the surrounding gesture. */
function buildOrbitPaths(width: number, height: number): string[] {
  return [
    `M ${width * 1.04} ${height * 0.31} C ${width * 0.86} ${height * 0.23}, ${width * 0.70} ${height * 0.29}, ${width * 0.61} ${height * 0.39} C ${width * 0.52} ${height * 0.49}, ${width * 0.42} ${height * 0.50}, ${width * 0.32} ${height * 0.43} C ${width * 0.20} ${height * 0.34}, ${width * 0.10} ${height * 0.45}, ${width * 0.16} ${height * 0.62} C ${width * 0.27} ${height * 0.88}, ${width * 0.65} ${height * 0.83}, ${width * 0.86} ${height * 0.65} C ${width * 0.99} ${height * 0.54}, ${width * 0.98} ${height * 0.31}, ${width * 1.04} ${height * 0.22}`,
    `M ${width * 1.04} ${height * 0.37} C ${width * 0.85} ${height * 0.28}, ${width * 0.69} ${height * 0.34}, ${width * 0.60} ${height * 0.43} C ${width * 0.51} ${height * 0.53}, ${width * 0.41} ${height * 0.54}, ${width * 0.31} ${height * 0.47} C ${width * 0.19} ${height * 0.38}, ${width * 0.12} ${height * 0.49}, ${width * 0.18} ${height * 0.65} C ${width * 0.30} ${height * 0.84}, ${width * 0.63} ${height * 0.79}, ${width * 0.83} ${height * 0.63} C ${width * 0.96} ${height * 0.52}, ${width * 0.97} ${height * 0.36}, ${width * 1.04} ${height * 0.27}`,
    `M ${width * 1.04} ${height * 0.43} C ${width * 0.84} ${height * 0.34}, ${width * 0.68} ${height * 0.39}, ${width * 0.59} ${height * 0.48} C ${width * 0.50} ${height * 0.58}, ${width * 0.40} ${height * 0.59}, ${width * 0.30} ${height * 0.52} C ${width * 0.20} ${height * 0.44}, ${width * 0.14} ${height * 0.53}, ${width * 0.20} ${height * 0.67} C ${width * 0.33} ${height * 0.80}, ${width * 0.61} ${height * 0.75}, ${width * 0.80} ${height * 0.61} C ${width * 0.93} ${height * 0.51}, ${width * 0.96} ${height * 0.40}, ${width * 1.04} ${height * 0.33}`,
  ];
}

/* Visible foreground continuation after the stream emerges from the left. */
function buildOrbitFrontPaths(width: number, height: number): string[] {
  return [
    `M ${width * 0.32} ${height * 0.43} C ${width * 0.20} ${height * 0.34}, ${width * 0.10} ${height * 0.45}, ${width * 0.16} ${height * 0.62} C ${width * 0.27} ${height * 0.88}, ${width * 0.65} ${height * 0.83}, ${width * 0.86} ${height * 0.65} C ${width * 0.99} ${height * 0.54}, ${width * 0.98} ${height * 0.31}, ${width * 1.04} ${height * 0.22}`,
    `M ${width * 0.31} ${height * 0.47} C ${width * 0.19} ${height * 0.38}, ${width * 0.12} ${height * 0.49}, ${width * 0.18} ${height * 0.65} C ${width * 0.30} ${height * 0.84}, ${width * 0.63} ${height * 0.79}, ${width * 0.83} ${height * 0.63} C ${width * 0.96} ${height * 0.52}, ${width * 0.97} ${height * 0.36}, ${width * 1.04} ${height * 0.27}`,
    `M ${width * 0.30} ${height * 0.52} C ${width * 0.20} ${height * 0.44}, ${width * 0.14} ${height * 0.53}, ${width * 0.20} ${height * 0.67} C ${width * 0.33} ${height * 0.80}, ${width * 0.61} ${height * 0.75}, ${width * 0.80} ${height * 0.61} C ${width * 0.93} ${height * 0.51}, ${width * 0.96} ${height * 0.40}, ${width * 1.04} ${height * 0.33}`,
  ];
}

const ORBIT_SYMBOLS = [
  'c2a9f0ed8abe2da9359a6649b83b5784.png',
  '2a663dfd70bf6b896a5ad98a16de2e1c.png',
  'ac6492f04da764ee924c17473e6cd6a3.png',
  '547334c2d14bc0032617d066b700a88b.png',
  'd93af2ebb59f066502593ffaf0402a2e.png',
  'c2834536e9c3129faa25b8db3edfa05b.png',
  '6d37eddc6733dff79f2bd5e4a306e354.png',
  '626b0bd1a8d79678be34cc45f72ba8dc.png',
  '90571985e0bd82d99bf0fbbc7a66242b.png',
];

export function useHomeHeroMotion(
  heroRef: React.RefObject<HTMLDivElement | null>,
  isLoggedIn: boolean
) {
  const overlayDivRef = useRef<HTMLDivElement | null>(null);
  const starHeadRef = useRef<HTMLDivElement | null>(null);
  const trailPathRef = useRef<SVGPathElement | null>(null);
  const scrollTriggerRef = useRef<ScrollTrigger | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;

    const reducedMotion = prefersReducedMotion();
    const mobile = isMobileViewport();
    // Play whenever the authenticated homepage mounts. gsap.context cleanup
    // removes the first React StrictMode trial mount before the real one runs.
    const firstVisit = true;

    /* ── Add is-motion-ready class to document ── */
    document.documentElement.classList.add('is-motion-ready');

    /* ── Use gsap.context() for proper StrictMode cleanup ── */
    const ctx = gsap.context(() => {
      /* ── Set up side-scene ScrollTriggers (always, except reduced-motion) ── */
      const leftScene = hero.querySelector<HTMLDivElement>('.hero-side-scene--left');
      const rightScene = hero.querySelector<HTMLDivElement>('.hero-side-scene--right');

      if (!reducedMotion && !mobile && leftScene && rightScene) {
        // Set initial clip-path for growth effect on the figures
        const leftFig = leftScene.querySelector<HTMLElement>('.hero-showcase__visual');
        const rightFig = rightScene.querySelector<HTMLElement>('.hero-showcase__visual');

        const killSideTweens = () => {
          // Find and kill any active side-scene tweens in this context
          const tweens = gsap.getTweensOf([leftScene, rightScene, leftFig, rightFig].filter(Boolean));
          tweens.forEach(t => t.kill());
        };

        const animateSideEnter = (duration = 0.75) => {
          killSideTweens();
          const tl = gsap.timeline({ defaults: { overwrite: 'auto' } });

          tl.to(leftScene, {
            x: 0, opacity: 1, scale: 1, duration, ease: 'power3.out',
          }, 0);
          tl.to(rightScene, {
            x: 0, opacity: 1, scale: 1, duration, ease: 'power3.out',
          }, 0);

          if (leftFig) {
            tl.to(leftFig, {
              clipPath: 'inset(0% 0% 0% 0%)',
              WebkitClipPath: 'inset(0% 0% 0% 0%)',
              duration: duration * 1.1,
              ease: 'power3.out',
            }, 0);
          }
          if (rightFig) {
            tl.to(rightFig, {
              clipPath: 'inset(0% 0% 0% 0%)',
              WebkitClipPath: 'inset(0% 0% 0% 0%)',
              duration: duration * 1.1,
              ease: 'power3.out',
            }, 0);
          }

          // Add will-change during animation, remove after
          leftScene.style.willChange = 'transform, opacity';
          rightScene.style.willChange = 'transform, opacity';
          tl.eventCallback('onComplete', () => {
            leftScene.style.willChange = 'auto';
            rightScene.style.willChange = 'auto';
          });
          tl.eventCallback('onInterrupt', () => {
            leftScene.style.willChange = 'auto';
            rightScene.style.willChange = 'auto';
          });
        };

        const animateSideLeave = (duration = 0.5) => {
          killSideTweens();
          const tl = gsap.timeline({ defaults: { overwrite: 'auto' } });

          tl.to(leftScene, {
            x: -120, opacity: 0, scale: 0.97, duration, ease: 'power2.in',
          }, 0);
          tl.to(rightScene, {
            x: 120, opacity: 0, scale: 0.97, duration, ease: 'power2.in',
          }, 0);

          leftScene.style.willChange = 'transform, opacity';
          rightScene.style.willChange = 'transform, opacity';
          tl.eventCallback('onComplete', () => {
            leftScene.style.willChange = 'auto';
            rightScene.style.willChange = 'auto';
          });
          tl.eventCallback('onInterrupt', () => {
            leftScene.style.willChange = 'auto';
            rightScene.style.willChange = 'auto';
          });
        };

        // If not first visit, scenes start in their natural positions
        if (!firstVisit) {
          gsap.set([leftScene, rightScene], { clearProps: 'all' });
          if (leftFig) gsap.set(leftFig, { clearProps: 'clipPath,WebkitClipPath' });
          if (rightFig) gsap.set(rightFig, { clearProps: 'clipPath,WebkitClipPath' });
        }

        const st = ScrollTrigger.create({
          trigger: hero,
          start: 'top bottom-=10%',
          end: 'bottom top+=10%',
          onEnter: () => animateSideEnter(0.75),
          onLeave: () => animateSideLeave(0.5),
          onEnterBack: () => animateSideEnter(0.65),
          onLeaveBack: () => animateSideLeave(0.45),
        });

        scrollTriggerRef.current = st;

        // If first visit, disable ST until intro completes
        if (firstVisit) {
          st.disable();
        }
      }

      /* ── Star Trail Intro Animation ── */
      if (firstVisit && !reducedMotion && !mobile) {
        hero.setAttribute('data-intro', 'active');

        // Create overlay container
        const overlay = document.createElement('div');
        overlay.className = 'home-intro__overlay';
        overlay.setAttribute('aria-hidden', 'true');

        const backLayer = document.createElement('div');
        backLayer.className = 'home-intro__layer home-intro__layer--back';
        const frontLayer = document.createElement('div');
        frontLayer.className = 'home-intro__layer home-intro__layer--front';
        overlay.appendChild(backLayer);
        overlay.appendChild(frontLayer);

        // Create star head div
        const starHead = document.createElement('div');
        starHead.className = 'home-intro__star';
        frontLayer.appendChild(starHead);

        // Create SVG for trail
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'home-intro__trail-svg');
        const frontSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        frontSvg.setAttribute('class', 'home-intro__trail-svg home-intro__trail-svg--front');

        // Gradient for trail
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        const grad = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        grad.setAttribute('id', 'homeIntroTrailGrad');
        grad.setAttribute('x1', '0'); grad.setAttribute('y1', '1');
        grad.setAttribute('x2', '1'); grad.setAttribute('y2', '0');
        const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop1.setAttribute('offset', '0%');
        stop1.setAttribute('stop-color', '#6BC8E0');
        stop1.setAttribute('stop-opacity', '0');
        const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop2.setAttribute('offset', '65%');
        stop2.setAttribute('stop-color', '#3178C0');
        stop2.setAttribute('stop-opacity', '0.55');
        const stop3 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop3.setAttribute('offset', '100%');
        stop3.setAttribute('stop-color', '#FFFFFF');
        stop3.setAttribute('stop-opacity', '0.85');
        grad.appendChild(stop1);
        grad.appendChild(stop2);
        grad.appendChild(stop3);
        defs.appendChild(grad);
        svg.appendChild(defs);

        // Broad orbit ribbons behind the title. The symbols travel along the
        // exact same paths, so the visual reads as one continuous data stream.
        const orbitPaths = [0, 1, 2].map((index) => {
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('fill', 'none');
          path.setAttribute('stroke', index === 0 ? '#3948D8' : index === 1 ? '#5080D0' : '#00B8E0');
          path.setAttribute('stroke-width', index === 0 ? '5.5' : index === 1 ? '4.5' : '5');
          path.setAttribute('stroke-linecap', 'round');
          path.setAttribute('class', `home-intro__orbit-path home-intro__orbit-path--${index + 1}`);
          svg.appendChild(path);
          return path;
        });
        const frontOrbitPaths = [0, 1, 2].map((index) => {
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('fill', 'none');
          path.setAttribute('stroke', index === 0 ? '#3948D8' : index === 1 ? '#5080D0' : '#00B8E0');
          path.setAttribute('stroke-width', index === 0 ? '5.5' : index === 1 ? '4.5' : '5');
          path.setAttribute('stroke-linecap', 'round');
          path.setAttribute('class', `home-intro__orbit-path home-intro__orbit-path--front home-intro__orbit-path--${index + 1}`);
          frontSvg.appendChild(path);
          return path;
        });

        // Trail path
        const trailPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        trailPath.setAttribute('fill', 'none');
        trailPath.setAttribute('stroke', 'url(#homeIntroTrailGrad)');
        trailPath.setAttribute('stroke-width', '2');
        trailPath.setAttribute('stroke-linecap', 'round');
        svg.appendChild(trailPath);

        backLayer.appendChild(svg);
        frontLayer.appendChild(frontSvg);

        const orbitSymbols = ORBIT_SYMBOLS.map((asset, index) => {
          const symbol = document.createElement('img');
          symbol.className = 'home-intro__orbit-symbol';
          symbol.src = `/hero/orbit-elements/${asset}`;
          symbol.alt = '';
          symbol.draggable = false;
          symbol.style.width = index < 3 ? '48px' : `${16 + (index % 3) * 4}px`;
          frontLayer.appendChild(symbol);
          return symbol;
        });

        const orbitDots = Array.from({ length: 30 }, (_, index) => {
          const dot = document.createElement('span');
          dot.className = 'home-intro__orbit-dot';
          const size = 1.5 + (index % 4) * 0.8;
          dot.style.width = `${size}px`;
          dot.style.height = `${size}px`;
          dot.style.background = index % 3 === 2 ? '#00B8E0' : index % 2 ? '#4B6CB8' : '#1E3A8A';
          frontLayer.appendChild(dot);
          return dot;
        });

        // Insert overlay as first child of hero
        hero.insertBefore(overlay, hero.firstChild);
        overlayDivRef.current = overlay;
        starHeadRef.current = starHead;
        trailPathRef.current = trailPath;

        /* ── Compute star path coordinates ── */
        const computePath = () => {
          const heroRect = hero.getBoundingClientRect();
          if (heroRect.width === 0 || heroRect.height === 0) return null;

          const sx = heroRect.width * 1.04;
          const sy = heroRect.height * 0.42;
          const ex = heroRect.width * -0.04;
          const ey = heroRect.height * 0.56;

          return { sx, sy, ex, ey, heroW: heroRect.width, heroH: heroRect.height };
        };

        const pathData = computePath();
        if (!pathData) return;

        const { sx, sy, ex, ey } = pathData;
        const d = buildStarPath(sx, sy, ex, ey);
        const orbitDs = buildOrbitPaths(pathData.heroW, pathData.heroH);
        const frontOrbitDs = buildOrbitFrontPaths(pathData.heroW, pathData.heroH);
        trailPath.setAttribute('d', d);
        const pathLen = Math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2) * 1.3;
        trailPath.style.strokeDasharray = `${pathLen} ${pathLen}`;
        trailPath.style.strokeDashoffset = `${pathLen}`;

        orbitPaths.forEach((path, index) => {
          path.setAttribute('d', orbitDs[index]);
          const length = path.getTotalLength();
          path.style.strokeDasharray = `${length} ${length}`;
          path.style.strokeDashoffset = `${length}`;
        });
        frontOrbitPaths.forEach((path, index) => {
          path.setAttribute('d', frontOrbitDs[index]);
          const length = path.getTotalLength();
          path.style.strokeDasharray = `${length} ${length}`;
          path.style.strokeDashoffset = `${length}`;
        });

        // Position star head at start
        gsap.set(starHead, { x: sx - 7, y: sy - 7 });
        gsap.set(orbitSymbols, { opacity: 0, scale: 0.82, transformOrigin: '50% 50%' });
        gsap.set(orbitDots, { opacity: 0, scale: 0.65, transformOrigin: '50% 50%' });

        // Hide content containers initially for intro
        const titleEl = hero.querySelector<HTMLElement>('.home-hero__title');
        const descEl = hero.querySelector<HTMLElement>('.home-hero__desc');
        const actionsEl = hero.querySelector<HTMLElement>('.home-hero__actions');
        let introSettled = false;

        // Single source of truth for final settled positions.
        const symbolFinalProgress = (i: number) =>
          0.08 + (i / Math.max(1, orbitSymbols.length - 1)) * 0.82;
        const dotFinalProgress = (i: number) =>
          0.03 + (i / Math.max(1, orbitDots.length - 1)) * 0.92;

        const settleOrbitElements = (
          paths: string[],
          reposition: boolean,
        ) => {
          orbitSymbols.forEach((symbol, index) => {
            const trackIndex = index % paths.length;
            const progress = symbolFinalProgress(index);
            // Confirm correct layer
            (progress >= 0.18 && progress < 0.48 ? backLayer : frontLayer).appendChild(symbol);
            if (reposition) {
              // ResizeObserver path: move to new path coordinates
              gsap.set(symbol, {
                motionPath: {
                  path: paths[trackIndex],
                  alignOrigin: [0.5, 0.5],
                  autoRotate: true,
                  start: progress,
                  end: progress,
                },
                willChange: 'auto',
              });
            }
          });

          orbitDots.forEach((dot, index) => {
            const trackIndex = index % paths.length;
            const progress = dotFinalProgress(index);
            (progress >= 0.18 && progress < 0.48 ? backLayer : frontLayer).appendChild(dot);
            if (reposition) {
              gsap.set(dot, {
                motionPath: {
                  path: paths[trackIndex],
                  alignOrigin: [0.5, 0.5],
                  start: progress,
                  end: progress,
                },
                willChange: 'auto',
              });
            }
          });
        };

        /* ── Build GSAP timeline ── */
        const tl = gsap.timeline({
          onComplete: () => {
            if (overlayDivRef.current) {
              overlayDivRef.current.classList.add('home-intro__overlay--settled');
            }
            introSettled = true;
            // Lock elements at their exact final coordinates using the same paths
            // and progress values the animation used — no coordinate drift.
            settleOrbitElements(orbitDs, true);
            // Smooth opacity transition 240 ms (within 180–280 ms spec).
            // Only animate opacity here; position/rotation/scale stay locked.
            gsap.to(orbitSymbols, {
              opacity: (i: number) => i < 3 ? 0.62 : 0.48,
              duration: 0.24,
              stagger: 0.012,
              ease: 'power1.out',
            });
            gsap.to(orbitDots, {
              opacity: (i: number) => 0.22 + (i % 4) * 0.07,
              duration: 0.24,
              stagger: 0.008,
              ease: 'power1.out',
            });
            starHeadRef.current = null;
            // Remove intro attribute
            hero.removeAttribute('data-intro');
            // Clean up will-change on star
            starHead.style.willChange = 'auto';
            starHead.style.display = 'none';
            trailPath.style.display = 'none';
            // Enable scroll triggers
            if (scrollTriggerRef.current) {
              scrollTriggerRef.current.enable();
            }
          },
        });

        // The leading sparkle enters from the right and exits on the left.
        // Use the same path string for both star motion and trail SVG
        tl.to(starHead, {
          motionPath: {
            path: d,
            autoRotate: false,
          },
          duration: 1.45,
          ease: 'power3.inOut',
        }, 0.05);

        // Trail dashoffset animation (reveal trail as star flies)
        tl.to(trailPath, {
          strokeDashoffset: 0,
          duration: 1.25,
          ease: 'power3.inOut',
        }, 0.05);

        // Draw right-to-left ribbons across the entire hero.
        tl.to(orbitPaths, {
          strokeDashoffset: 0,
          duration: 0.92,
          stagger: 0.05,
          ease: 'power2.inOut',
        }, 0.04);
        tl.to(frontOrbitPaths, {
          strokeDashoffset: 0,
          duration: 0.90,
          stagger: 0.04,
          ease: 'power2.inOut',
        }, 0.62);

        // Recruitment/network symbols flow along the ribbons. Each symbol
        // starts from the right entrance (progress 0) and glides to its
        // unique final position — the very same position it keeps after settle.
        orbitSymbols.forEach((symbol, index) => {
          const trackIndex = index % orbitDs.length;
          const fp = symbolFinalProgress(index);
          const motionStart = 0.06 + index * 0.045;
          const motionDuration = 0.75 + fp * 1.05;

          tl.to(symbol, {
            opacity: index < 3 ? 0.88 : 0.70,
            scale: 1,
            duration: 0.12,
            ease: 'power1.out',
          }, motionStart);
          tl.to(symbol, {
            motionPath: {
              path: orbitDs[trackIndex],
              alignOrigin: [0.5, 0.5],
              autoRotate: true,
              start: 0,
              end: fp,
            },
            duration: motionDuration,
            ease: 'power2.inOut',
          }, motionStart);

          // Layer reparenting timed to actual finalProgress
          if (fp >= 0.18) {
            const backTime = motionStart + motionDuration * (0.18 / fp);
            tl.call(() => backLayer.appendChild(symbol), [], backTime);
          }
          if (fp >= 0.48) {
            const frontTime = motionStart + motionDuration * (0.48 / fp);
            tl.call(() => frontLayer.appendChild(symbol), [], frontTime);
          }
        });

        orbitDots.forEach((dot, index) => {
          const trackIndex = index % orbitDs.length;
          const fp = dotFinalProgress(index);
          const dotStart = 0.04 + index * 0.014;
          const dotDuration = 0.65 + fp * 1.0;

          tl.to(dot, {
            opacity: 0.32 + (index % 5) * 0.1,
            scale: 1,
            duration: 0.08,
          }, dotStart);
          tl.to(dot, {
            motionPath: {
              path: orbitDs[trackIndex],
              alignOrigin: [0.5, 0.5],
              start: 0,
              end: fp,
            },
            duration: dotDuration,
            ease: 'power1.inOut',
          }, dotStart);

          if (fp >= 0.18) {
            const backTime = dotStart + dotDuration * (0.18 / fp);
            tl.call(() => backLayer.appendChild(dot), [], backTime);
          }
          if (fp >= 0.48) {
            const frontTime = dotStart + dotDuration * (0.48 / fp);
            tl.call(() => frontLayer.appendChild(dot), [], frontTime);
          }
        });

        // Fade trail out near end
        tl.to(trailPath, {
          opacity: 0,
          duration: 0.15,
        }, 1.48);

        // ── 250~950ms: side scenes grow out ──
        if (leftScene && rightScene) {
          gsap.set(leftScene, { x: 70, opacity: 0, scale: 0.94 });
          gsap.set(rightScene, { x: -70, opacity: 0, scale: 0.94 });

          const leftFig = leftScene.querySelector<HTMLElement>('.hero-showcase__visual');
          const rightFig = rightScene.querySelector<HTMLElement>('.hero-showcase__visual');
          if (leftFig) {
            gsap.set(leftFig, { clipPath: 'inset(12% 28% 12% 28%)', WebkitClipPath: 'inset(12% 28% 12% 28%)' });
          }
          if (rightFig) {
            gsap.set(rightFig, { clipPath: 'inset(12% 28% 12% 28%)', WebkitClipPath: 'inset(12% 28% 12% 28%)' });
          }

          // Set will-change during the intro side scene animation
          leftScene.style.willChange = 'transform, opacity';
          rightScene.style.willChange = 'transform, opacity';

          const sideEnter = gsap.timeline({ defaults: { overwrite: 'auto' } });
          sideEnter.to(leftScene, { x: 0, opacity: 1, scale: 1, duration: 0.7, ease: 'power3.out' }, 0);
          sideEnter.to(rightScene, { x: 0, opacity: 1, scale: 1, duration: 0.7, ease: 'power3.out' }, 0);
          if (leftFig) {
            sideEnter.to(leftFig, {
              clipPath: 'inset(0% 0% 0% 0%)',
              WebkitClipPath: 'inset(0% 0% 0% 0%)',
              duration: 0.75, ease: 'power3.out',
            }, 0);
          }
          if (rightFig) {
            sideEnter.to(rightFig, {
              clipPath: 'inset(0% 0% 0% 0%)',
              WebkitClipPath: 'inset(0% 0% 0% 0%)',
              duration: 0.75, ease: 'power3.out',
            }, 0);
          }

          sideEnter.eventCallback('onComplete', () => {
            leftScene.style.willChange = 'auto';
            rightScene.style.willChange = 'auto';
          });

          tl.add(sideEnter, 0.25);
        }

        // ── 680~1180ms: title drops down ──
        if (titleEl) {
          tl.fromTo(titleEl,
            { opacity: 0, y: -24, scale: 0.985 },
            { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: 'power3.out' },
            0.68
          );
        }

        // ── 760~1280ms: description rises up ──
        if (descEl) {
          tl.fromTo(descEl,
            { opacity: 0, y: 22 },
            { opacity: 1, y: 0, duration: 0.48, ease: 'power3.out' },
            0.76
          );
        }

        // ── 900~1350ms: buttons float up ──
        if (actionsEl) {
          tl.fromTo(actionsEl,
            { opacity: 0, y: 12 },
            { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out' },
            0.90
          );
        }

        // ── 1350~1550ms: star fades out ──
        tl.to(starHead, { opacity: 0, scale: 0.6, duration: 0.2 }, 1.82);

        /* ── ResizeObserver to update trail SVG path on resize ── */
        const ro = new ResizeObserver(() => {
          if (!overlayDivRef.current || !trailPathRef.current) return;
          const updated = computePath();
          if (!updated) return;

          const newD = buildStarPath(updated.sx, updated.sy, updated.ex, updated.ey);
          const newOrbitDs = buildOrbitPaths(updated.heroW, updated.heroH);
          const newFrontOrbitDs = buildOrbitFrontPaths(updated.heroW, updated.heroH);
          trailPathRef.current.setAttribute('d', newD);
          const newLen = Math.sqrt(
            (updated.ex - updated.sx) ** 2 + (updated.ey - updated.sy) ** 2
          ) * 1.3;
          trailPathRef.current.style.strokeDasharray = `${newLen} ${newLen}`;
          orbitPaths.forEach((path, index) => {
            path.setAttribute('d', newOrbitDs[index]);
            const length = path.getTotalLength();
            path.style.strokeDasharray = `${length} ${length}`;
          });
          frontOrbitPaths.forEach((path, index) => {
            path.setAttribute('d', newFrontOrbitDs[index]);
            const length = path.getTotalLength();
            path.style.strokeDasharray = `${length} ${length}`;
          });
          if (introSettled) settleOrbitElements(newOrbitDs, true);
          // Note: The star's GSAP motionPath animation is not updated on resize.
          // The intro lasts only ~1.55s, so viewport resize during flight is
          // extremely rare. The trail SVG (the dominant visual) stays correct.
        });
        ro.observe(hero);
        resizeObserverRef.current = ro;
      }

    }, hero); // end gsap.context()

    /* ── Cleanup ── */
    return () => {
      ctx.revert(); // Kills all animations, ScrollTriggers, and reverts inline styles

      // Manual DOM cleanup (gsap.context doesn't manage manual DOM insertions)
      if (overlayDivRef.current) {
        overlayDivRef.current.remove();
        overlayDivRef.current = null;
      }
      starHeadRef.current = null;
      trailPathRef.current = null;

      // Disconnect ResizeObserver (not managed by GSAP context)
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
        resizeObserverRef.current = null;
      }

      // Remove data-intro attribute
      hero.removeAttribute('data-intro');

      // Clean up side scene will-change
      const ls = hero.querySelector<HTMLElement>('.hero-side-scene--left');
      const rs = hero.querySelector<HTMLElement>('.hero-side-scene--right');
      if (ls) ls.style.willChange = 'auto';
      if (rs) rs.style.willChange = 'auto';

      // Clear ScrollTrigger ref (already killed by ctx.revert())
      scrollTriggerRef.current = null;
    };
  }, [heroRef, isLoggedIn]);

  /* ── Handle visibility change: kill running tweens when tab hidden ── */
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden && heroRef.current) {
        // Kill all tweens targeting side scenes to prevent stale state on return
        const hero = heroRef.current;
        const leftScene = hero.querySelector<HTMLElement>('.hero-side-scene--left');
        const rightScene = hero.querySelector<HTMLElement>('.hero-side-scene--right');
        if (leftScene) {
          gsap.getTweensOf(leftScene).forEach(t => { if (t.isActive()) t.kill(); });
        }
        if (rightScene) {
          gsap.getTweensOf(rightScene).forEach(t => { if (t.isActive()) t.kill(); });
        }
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [heroRef]);
}
