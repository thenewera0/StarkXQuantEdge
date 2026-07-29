"use client";

import { useState, useEffect } from "react";

const images = [
  "/bg1.png",
  "/bg2.png",
  "/bg3.png",
  "/bg4.png",
  "/bg5.png"
];

export function BackgroundCarousel() {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    // Auto rotate every 1 minute (60000ms)
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % images.length);
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed inset-0 w-full h-full -z-50 carbon-mesh">
      {/* Spotlight spotlighting center dashboard */}
      <div className="absolute inset-0 w-full h-full bg-[radial-gradient(circle_at_50%_35%,transparent_10%,rgba(5,7,12,0.85)_85%)] pointer-events-none" />

      {images.map((src, i) => (
        <div
          key={src}
          className="absolute inset-0 w-full h-full bg-[length:100%_100%] bg-no-repeat bg-center transition-opacity duration-[2000ms] ease-in-out saturate-[1.2] contrast-[1.1] brightness-[0.8] mix-blend-overlay"
          style={{
            backgroundImage: `url('${src}')`,
            opacity: i === currentIndex ? 0.25 : 0,
          }}
        />
      ))}
      
      {/* Glare overlay simulating curved terminal glass reflection */}
      <div className="absolute inset-0 w-full h-full bg-[linear-gradient(135deg,rgba(255,255,255,0.02)_0%,rgba(255,255,255,0)_50%,rgba(255,255,255,0.01)_100%)] pointer-events-none" />
    </div>
  );
}
