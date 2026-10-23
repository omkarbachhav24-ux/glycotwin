"use client";

import React, { useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF, Float, Html } from "@react-three/drei";
import * as THREE from "three";

interface ModelProps {
  color: string;
  streaming: boolean;
  onSelectRegion?: (name: string) => void;
  selectedRegion?: string | null;
}

/** 3D Holographic Particle Matrix for realistic Iron Man HUD field */
function HologramParticleField({ color }: { color: string }) {
  const pointsRef = useRef<THREE.Points>(null);
  const count = 400;

  const [positions, scales] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const sc = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      // Cylindrical distribution around body
      const theta = Math.random() * Math.PI * 2;
      const radius = 0.25 + Math.random() * 0.75;
      const y = (Math.random() - 0.5) * 2.2;
      pos[i * 3] = Math.cos(theta) * radius;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = Math.sin(theta) * radius;
      sc[i] = Math.random();
    }
    return [pos, sc];
  }, []);

  useFrame(({ clock }) => {
    if (!pointsRef.current) return;
    pointsRef.current.rotation.y = clock.getElapsedTime() * 0.08;
    const pos = pointsRef.current.geometry.attributes.position.array as Float32Array;
    const t = clock.getElapsedTime();
    for (let i = 0; i < count; i++) {
      pos[i * 3 + 1] += Math.sin(t + i) * 0.001;
    }
    pointsRef.current.geometry.attributes.position.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.018}
        color={color}
        transparent
        opacity={0.6}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

/** Sweeping volumetric dual-laser diagnostic scanner */
function VolumetricDualScanner({ color }: { color: string }) {
  const ring1 = useRef<THREE.Group>(null);
  const ring2 = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (ring1.current) {
      ring1.current.position.y = Math.sin(t * 1.6) * 1.05 + 0.05;
      ring1.current.rotation.z = t * 0.6;
    }
    if (ring2.current) {
      ring2.current.position.y = Math.cos(t * 1.6) * 1.05 + 0.05;
      ring2.current.rotation.z = -t * 0.4;
    }
  });

  return (
    <>
      <group ref={ring1}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.62, 0.007, 16, 64]} />
          <meshBasicMaterial color={color} transparent opacity={0.9} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0, 0.61, 32]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.08}
            side={THREE.DoubleSide}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      </group>

      <group ref={ring2}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.55, 0.004, 16, 64]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.6} />
        </mesh>
      </group>
    </>
  );
}

/** Concentric orbital telemetry reticles and angle markers */
function OrbitalTelemetryHUD({ color }: { color: string }) {
  const gOuter = useRef<THREE.Group>(null);
  const gTilted = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (gOuter.current) gOuter.current.rotation.z = t * 0.15;
    if (gTilted.current) gTilted.current.rotation.z = -t * 0.22;
  });

  return (
    <group position={[0, -0.05, 0]}>
      {/* Horizontal floor pedestal radar grid */}
      <mesh position={[0, -1.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.2, 1.25, 48]} />
        <meshBasicMaterial
          color={color}
          wireframe
          transparent
          opacity={0.25}
          depthWrite={false}
        />
      </mesh>

      {/* Floating orbital HUD reticle rings */}
      <group ref={gOuter} rotation={[Math.PI / 2.2, 0.1, 0]}>
        <mesh>
          <ringGeometry args={[0.92, 0.94, 64, 1, 0, Math.PI * 1.5]} />
          <meshBasicMaterial color={color} transparent opacity={0.65} side={THREE.DoubleSide} />
        </mesh>
        <mesh>
          <ringGeometry args={[0.98, 0.99, 48, 1, Math.PI * 0.7, Math.PI * 0.4]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.5} side={THREE.DoubleSide} />
        </mesh>
      </group>

      <group ref={gTilted} rotation={[Math.PI / 2.6, -0.3, 0]}>
        <mesh>
          <ringGeometry args={[0.78, 0.795, 48, 1, 0, Math.PI * 1.8]} />
          <meshBasicMaterial color={color} transparent opacity={0.5} side={THREE.DoubleSide} />
        </mesh>
      </group>
    </group>
  );
}

/** Interactive anatomical organs & holographic markers */
function AnatomicalFocalPoints({
  color,
  onSelect,
  selected,
}: {
  color: string;
  onSelect?: (organ: string) => void;
  selected?: string | null;
}) {
  const organs = useMemo(
    () => [
      {
        id: "pancreas",
        name: "Pancreatic Islets (Beta Cells)",
        desc: "Endocrine target: Insulin secretion & glucose regulation",
        pos: [0.06, 0.16, 0.11] as [number, number, number],
        color: "#f59e0b",
      },
      {
        id: "cgm",
        name: "Dexcom G7 / Abbott FreeStyle CGM",
        desc: "Active Sensor: Interstitial fluid glucose readings at 5m rate",
        pos: [-0.34, 0.38, 0.05] as [number, number, number],
        color: color,
      },
      {
        id: "liver",
        name: "Hepatic Glycogen Buffer",
        desc: "Gluconeogenesis & hepatic glucose output dynamics",
        pos: [-0.11, 0.22, 0.09] as [number, number, number],
        color: "#38bdf8",
      },
      {
        id: "heart",
        name: "Cardiovascular Telemetry",
        desc: "Microvascular pressure & autonomic perfusion index",
        pos: [0.03, 0.38, 0.12] as [number, number, number],
        color: "#ff3366",
      },
    ],
    [color]
  );

  return (
    <group>
      {organs.map((organ) => {
        const isSelected = selected === organ.id;
        return (
          <group
            key={organ.id}
            position={organ.pos}
            onClick={(e) => {
              e.stopPropagation();
              onSelect?.(organ.id);
            }}
          >
            <mesh>
              <sphereGeometry args={[isSelected ? 0.035 : 0.024, 20, 20]} />
              <meshStandardMaterial
                color={organ.color}
                emissive={organ.color}
                emissiveIntensity={isSelected ? 4.5 : 2.2}
                roughness={0.15}
              />
            </mesh>
            <mesh>
              <sphereGeometry args={[isSelected ? 0.055 : 0.04, 16, 16]} />
              <meshBasicMaterial
                color={organ.color}
                wireframe
                transparent
                opacity={isSelected ? 0.8 : 0.35}
              />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

/** The Main Real 3D GLB Human Body loaded with Photorealistic Cybernetic Materials */
export default function RealHumanBodyModel({
  color,
  streaming,
  onSelectRegion,
  selectedRegion,
}: ModelProps) {
  const groupRef = useRef<THREE.Group>(null);
  const gltf = useGLTF("/geometries/human_body.glb");

  // Clone scene so we can customize materials independently without side effects
  const clonedScene = useMemo(() => {
    const scene = gltf.scene.clone(true);

    // Apply Jarvis Hologram Shader Materials: Deep translucent cyber glass + Fresnel wireframe
    scene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        // Custom cyber-holographic material
        mesh.material = new THREE.MeshPhysicalMaterial({
          color: new THREE.Color("#081c2c"),
          emissive: new THREE.Color(color),
          emissiveIntensity: 0.38,
          roughness: 0.15,
          metalness: 0.2,
          transparent: true,
          opacity: 0.72,
          transmission: 0.65,
          ior: 1.35,
          thickness: 0.45,
          clearcoat: 0.8,
          clearcoatRoughness: 0.1,
          wireframe: false,
        });
      }
    });

    return scene;
  }, [gltf, color]);

  // Subtle breathing and cybernetic pulse
  useFrame(({ clock }, delta) => {
    if (!groupRef.current) return;
    if (streaming) {
      const t = clock.getElapsedTime();
      const breath = 1 + Math.sin(t * 1.8) * 0.01;
      groupRef.current.scale.set(0.95 * breath, 0.95, 0.95 * breath);
    }
  });

  return (
    <group>
      {/* 1. Real Downloaded 3D Human Anatomy Model */}
      <group ref={groupRef} position={[0, -0.98, 0]} scale={0.95}>
        <primitive object={clonedScene} />
      </group>

      {/* 2. Floating Interactive Anatomical Target Nodes (Pancreas, CGM, Liver, Heart) */}
      <AnatomicalFocalPoints
        color={color}
        onSelect={onSelectRegion}
        selected={selectedRegion}
      />

      {/* 3. Dual Volumetric Laser Scanners sweeping the body */}
      <VolumetricDualScanner color={color} />

      {/* 4. Concentric Orbital Telemetry HUD Reticles & Floor Matrix */}
      <OrbitalTelemetryHUD color={color} />

      {/* 5. Volumetric Holographic Particle Cloud */}
      <HologramParticleField color={color} />
    </group>
  );
}

useGLTF.preload("/geometries/human_body.glb");
