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
    <div className="fixed inset-0 w-full h-full -z-50 bg-[#04060a]">
      {images.map((src, i) => (
        <div
          key={src}
          className="absolute inset-0 w-full h-full bg-[length:100%_100%] bg-no-repeat bg-center transition-opacity duration-[2000ms] ease-in-out saturate-[1.5] contrast-[1.15] brightness-[1.1] opacity-40"
          style={{
            backgroundImage: `url('${src}')`,
            opacity: i === currentIndex ? 0.45 : 0,
          }}
        />
      ))}
      
      {/* Liquid morphing gradient blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-gradient-to-br from-[#00d4ff]/15 to-[#2f7fff]/15 blur-[120px] animate-liquid-blob pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] rounded-full bg-gradient-to-tr from-[#8a2be2]/12 to-[#4d9fff]/12 blur-[150px] animate-liquid-blob-reverse pointer-events-none mix-blend-screen" />
      <div className="absolute top-[30%] left-[40%] w-[35vw] h-[35vw] rounded-full bg-gradient-to-tr from-[#00ffd4]/10 to-[#2f7fff]/10 blur-[130px] animate-liquid-blob pointer-events-none mix-blend-screen" style={{ animationDelay: "-8s" }} />

      {/* Glossy overlay to ensure everything looks super good */}
      <div className="absolute inset-0 w-full h-full bg-gradient-to-br from-black/40 via-transparent to-[#00d4ff]/10 pointer-events-none mix-blend-overlay" />
    </div>
  );
}
