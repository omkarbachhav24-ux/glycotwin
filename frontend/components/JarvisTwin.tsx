"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import {
  ARM_RADII, HEAD_RINGS, LEG_RADII, TORSO_RINGS,
  armCurve, legCurve, loftRings, taperedTube,
} from "./humanGeometry";

interface JarvisTwinProps {
  color: string;
  streaming: boolean;
  scanActive?: boolean;
}

/** Hologram scan ring that sweeps vertically across the biological twin */
function HolographicScanner({ color }: { color: string }) {
  const ringRef = useRef<THREE.Group>(null);
  const ringMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(color),
        transparent: true,
        opacity: 0.85,
        wireframe: true,
      }),
    [color]
  );

  const glowDisk = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(color),
        transparent: true,
        opacity: 0.15,
        side: THREE.DoubleSide,
      }),
    [color]
  );

  useFrame(({ clock }) => {
    if (!ringRef.current) return;
    const t = clock.getElapsedTime() * 1.5;
    // Oscillate up and down across the full height of the body (-0.9 to 1.1)
    ringRef.current.position.y = Math.sin(t) * 1.0 + 0.1;
    ringRef.current.rotation.z = t * 0.4;
  });

  return (
    <group ref={ringRef}>
      <mesh material={ringMat} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.55, 0.008, 16, 64]} />
      </mesh>
      <mesh material={glowDisk} rotation={[Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.54, 32]} />
      </mesh>
    </group>
  );
}

/** Orbiting HUD data telemetry rings around the holographic twin */
function JarvisTelemetryRings({ color }: { color: string }) {
  const g1 = useRef<THREE.Group>(null);
  const g2 = useRef<THREE.Group>(null);
  const g3 = useRef<THREE.Group>(null);

  const matCyan = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color("#00f0ff"),
        transparent: true,
        opacity: 0.35,
        wireframe: true,
      }),
    []
  );

  const matStatus = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(color),
        transparent: true,
        opacity: 0.5,
      }),
    [color]
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (g1.current) {
      g1.current.rotation.z = t * 0.25;
      g1.current.rotation.x = Math.sin(t * 0.15) * 0.15;
    }
    if (g2.current) {
      g2.current.rotation.z = -t * 0.35;
      g2.current.rotation.y = Math.cos(t * 0.2) * 0.2;
    }
    if (g3.current) {
      g3.current.rotation.y = t * 0.4;
    }
  });

  return (
    <group position={[0, 0.05, 0]}>
      {/* Outer segmented radar ring */}
      <group ref={g1} rotation={[Math.PI / 2.3, 0, 0]}>
        <mesh material={matCyan}>
          <ringGeometry args={[0.95, 0.98, 48, 1, 0, Math.PI * 1.6]} />
        </mesh>
        <mesh material={matStatus}>
          <ringGeometry args={[1.02, 1.035, 32, 1, Math.PI * 0.8, Math.PI * 0.5]} />
        </mesh>
      </group>

      {/* Tilted orbital ring */}
      <group ref={g2} rotation={[Math.PI / 2.6, 0.3, 0]}>
        <mesh material={matStatus}>
          <ringGeometry args={[0.78, 0.8, 40, 1, 0, Math.PI * 1.8]} />
        </mesh>
      </group>

      {/* Floating biometric node sphere cluster */}
      <group ref={g3}>
        {[-0.6, 0.6].map((x, i) => (
          <mesh key={i} position={[x, 0.3, 0.4]} material={matStatus}>
            <sphereGeometry args={[0.018, 12, 12]} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

/** 3D Neural / Vascular node points along the spine and major organs */
function InternalNeuralNodes({ color }: { color: string }) {
  const nodes = useMemo(() => {
    return [
      { pos: [0, 0.68, 0.02], size: 0.022 }, // Brain stem / Cranial
      { pos: [0, 0.42, 0.05], size: 0.026 }, // Heart / Cardiac center
      { pos: [0.08, 0.26, 0.04], size: 0.03 }, // Pancreatic region (Endocrine / Glucose target)
      { pos: [-0.09, 0.30, 0.03], size: 0.028 }, // Hepatic (Liver glycogen)
      { pos: [0, 0.12, 0.02], size: 0.02 }, // Navel / Core
      { pos: [-0.28, 0.36, 0.02], size: 0.025 }, // Left arm CGM sensor site
    ];
  }, []);

  const matCore = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(color),
        emissive: new THREE.Color(color),
        emissiveIntensity: 3.5,
        roughness: 0.2,
      }),
    [color]
  );

  const matPulse = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(color),
        transparent: true,
        opacity: 0.4,
        wireframe: true,
      }),
    [color]
  );

  const pulseRef = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!pulseRef.current) return;
    const s = 1 + Math.sin(clock.getElapsedTime() * 4) * 0.25;
    pulseRef.current.scale.set(s, s, s);
  });

  return (
    <group>
      {nodes.map((n, i) => (
        <group key={i} position={n.pos as [number, number, number]}>
          <mesh material={matCore}>
            <sphereGeometry args={[n.size, 16, 16]} />
          </mesh>
          {i === 2 && ( // Highlight endocrine / pancreas with pulsing halo
            <group ref={pulseRef}>
              <mesh material={matPulse}>
                <sphereGeometry args={[n.size * 2.2, 12, 12]} />
              </mesh>
            </group>
          )}
        </group>
      ))}
    </group>
  );
}

export default function JarvisHologramTwin({ color, streaming }: JarvisTwinProps) {
  const chestRef = useRef<THREE.Mesh>(null);
  const glowHullRef = useRef<THREE.Mesh>(null);

  // Procedural geometries from the anatomical model
  const torso = useMemo(() => loftRings(TORSO_RINGS, 56, 6), []);
  const head = useMemo(() => loftRings(HEAD_RINGS, 48, 6), []);
  const arms = useMemo(
    () => [-1, 1].map((side) => taperedTube(armCurve(side), ARM_RADII, 48, 28, 0.92)),
    []
  );
  const legs = useMemo(
    () => [-1, 1].map((side) => taperedTube(legCurve(side), LEG_RADII, 48, 28, 0.94)),
    []
  );

  // Futuristic Hologram Shaders & Materials
  const holoWireMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: new THREE.Color("#00f0ff"),
      emissive: new THREE.Color("#004466"),
      emissiveIntensity: 0.8,
      wireframe: true,
      transparent: true,
      opacity: 0.45,
      roughness: 0.2,
      metalness: 0.9,
    });
  }, []);

  const holoGlassMaterial = useMemo(() => {
    return new THREE.MeshPhysicalMaterial({
      color: new THREE.Color("#051c24"),
      roughness: 0.1,
      metalness: 0.1,
      transparent: true,
      opacity: 0.45,
      transmission: 0.75,
      ior: 1.3,
      thickness: 0.5,
      emissive: new THREE.Color(color),
      emissiveIntensity: 0.35,
    });
  }, [color]);

  // Breathing simulation
  useFrame(({ clock }) => {
    if (!chestRef.current || !streaming) return;
    const t = clock.getElapsedTime();
    const s = 1 + Math.sin(t * 1.8) * 0.012;
    chestRef.current.scale.set(s, 1, s);
    if (glowHullRef.current) {
      glowHullRef.current.scale.set(s * 1.015, 1.01, s * 1.015);
    }
  });

  return (
    <group>
      {/* 1. Outer Hologram Wireframe Matrix */}
      <group>
        <mesh geometry={torso} material={holoWireMaterial} />
        <mesh geometry={head} material={holoWireMaterial} />
        {arms.map((g, i) => (
          <mesh key={`h-arm-${i}`} geometry={g} material={holoWireMaterial} />
        ))}
        {legs.map((g, i) => (
          <mesh key={`h-leg-${i}`} geometry={g} material={holoWireMaterial} />
        ))}
      </group>

      {/* 2. Inner Translucent Bio-Glass Core */}
      <group>
        <mesh ref={chestRef} geometry={torso} material={holoGlassMaterial} />
        <mesh geometry={head} material={holoGlassMaterial} />
        {arms.map((g, i) => (
          <mesh key={`g-arm-${i}`} geometry={g} material={holoGlassMaterial} />
        ))}
        {legs.map((g, i) => (
          <mesh key={`g-leg-${i}`} geometry={g} material={holoGlassMaterial} />
        ))}
      </group>

      {/* 3. Internal Neural & Endocrine Biometric Nodes */}
      <InternalNeuralNodes color={color} />

      {/* 4. Real-time Laser Scanner sweeping through the Twin */}
      <HolographicScanner color={color} />

      {/* 5. 3D JARVIS Telemetry Rings and Status Reticles */}
      <JarvisTelemetryRings color={color} />
    </group>
  );
}
