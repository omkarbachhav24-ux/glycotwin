"use client";

import { Canvas } from "@react-three/fiber";
import { ContactShadows, OrbitControls } from "@react-three/drei";
import { Suspense, useEffect } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import ApexClinicalTwin from "./ApexClinicalTwin";

/** Studio image-based environment generating warm crisp reflections on the white ceramic glass */
function StudioEnvironment() {
  return null;
}

function Scene({ band, streaming }: { band: string; streaming: boolean }) {
  const isHighRisk = band === "high" || band === "above_threshold";
  const lightColor = isHighRisk ? "#ef4444" : "#0284c7";

  return (
    <>
      {/* Crisp White Studio Key Lights */}
      <ambientLight intensity={1.2} />
      <directionalLight
        position={[3, 5, 4]}
        intensity={2.8}
        color="#ffffff"
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-near={0.5}
        shadow-camera-far={10}
        shadow-bias={-0.0008}
      />
      <directionalLight position={[-4, 2, -3]} intensity={1.5} color="#e0f2fe" />
      <pointLight position={[0, 2, 2.5]} intensity={2.2} distance={6} color={lightColor} />

      {/* The Single Master 3D Apex Twin */}
      <ApexClinicalTwin riskBand={band} streaming={streaming} />

      {/* Clean soft contact shadow on white podium */}
      <ContactShadows
        position={[0, -1.02, 0]}
        opacity={0.45}
        scale={4}
        blur={2.2}
        far={1.4}
        resolution={512}
        color="#64748b"
      />
    </>
  );
}

export default function TwinFigure({
  riskBand,
  streaming,
}: {
  riskBand: string;
  streaming: boolean;
  view?: string;
}) {
  return (
    <div style={{ height: 560, width: "100%", position: "relative", cursor: "grab" }}>
      <Canvas
        shadows
        camera={{ position: [0, 0.12, 3.1], fov: 35 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.05;
        }}
      >
        <Suspense fallback={null}>
          <Scene band={riskBand} streaming={streaming} />
          <OrbitControls
            enablePan={false}
            enableZoom
            target={[0, 0, 0]}
            minDistance={1.6}
            maxDistance={5.5}
            minPolarAngle={Math.PI / 4.5}
            maxPolarAngle={Math.PI / 1.9}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
