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
    <div className="fixed top-0 right-0 bottom-0 left-64 w-[calc(100%-256px)] h-full -z-50 bg-[#090b14]">
      {images.map((src, i) => (
        <div
          key={src}
          className="absolute inset-0 w-full h-full bg-[length:100%_100%] bg-no-repeat bg-center transition-opacity duration-[2000ms] ease-in-out saturate-[1.5] contrast-[1.15] brightness-[1.1]"
          style={{
            backgroundImage: `url('${src}')`,
            opacity: i === currentIndex ? 1 : 0,
          }}
        />
      ))}
      {/* Glossy overlay to ensure everything looks super good */}
      <div className="absolute inset-0 w-full h-full bg-gradient-to-br from-black/40 via-transparent to-[#00d4ff]/10 pointer-events-none mix-blend-overlay" />
    </div>
  );
}
