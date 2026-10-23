"use client";

import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";

interface ApexTwinProps {
  riskBand: string;
  streaming: boolean;
  selectedOrgan?: string | null;
}

const PALETTE: Record<string, { primary: string; glow: string; emissive: string; alert: string }> = {
  high: { primary: "#ef4444", glow: "#fca5a5", emissive: "#dc2626", alert: "#ef4444" },
  moderate: { primary: "#f59e0b", glow: "#fde68a", emissive: "#d97706", alert: "#f59e0b" },
  low: { primary: "#0284c7", glow: "#bae6fd", emissive: "#0369a1", alert: "#0284c7" },
  above_threshold: { primary: "#f43f5e", glow: "#fecdd3", emissive: "#e11d48", alert: "#f43f5e" },
  unknown: { primary: "#0284c7", glow: "#bae6fd", emissive: "#0369a1", alert: "#0284c7" },
};

/** Floating Quantum Biometric Particles orbiting the twin in pure light mode */
function QuantumBioParticles({ color }: { color: string }) {
  const pointsRef = useRef<THREE.Points>(null);
  const count = 380;

  const [positions] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const radius = 0.22 + Math.random() * 0.72;
      const y = (Math.random() - 0.5) * 2.3;
      pos[i * 3] = Math.cos(theta) * radius;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = Math.sin(theta) * radius;
    }
    return [pos];
  }, []);

  useFrame(({ clock }) => {
    if (!pointsRef.current) return;
    pointsRef.current.rotation.y = clock.getElapsedTime() * 0.09;
    const pos = pointsRef.current.geometry.attributes.position.array as Float32Array;
    const t = clock.getElapsedTime();
    for (let i = 0; i < count; i++) {
      pos[i * 3 + 1] += Math.sin(t * 1.5 + i) * 0.0008;
    }
    pointsRef.current.geometry.attributes.position.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.016}
        color={color}
        transparent
        opacity={0.7}
        depthWrite={false}
      />
    </points>
  );
}

/** Dual laser sweeping rings - High-precision medical optic scan */
function PrecisionMedicalScan({ color }: { color: string }) {
  const ringA = useRef<THREE.Group>(null);
  const ringB = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (ringA.current) {
      ringA.current.position.y = Math.sin(t * 1.4) * 1.05 + 0.05;
      ringA.current.rotation.z = t * 0.5;
    }
    if (ringB.current) {
      ringB.current.position.y = Math.cos(t * 1.4) * 1.05 + 0.05;
      ringB.current.rotation.z = -t * 0.35;
    }
  });

  return (
    <>
      <group ref={ringA}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.58, 0.006, 16, 64]} />
          <meshBasicMaterial color={color} transparent opacity={0.85} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <circleGeometry args={[0.575, 48]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.06}
            side={THREE.DoubleSide}
          />
        </mesh>
      </group>

      <group ref={ringB}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.52, 0.003, 16, 64]} />
          <meshBasicMaterial color="#0284c7" transparent opacity={0.6} />
        </mesh>
      </group>
    </>
  );
}

/** Precision Clean Floor Reticle - Pure White Lab Instrument style */
function PrecisionFloorReticle({ color }: { color: string }) {
  const g1 = useRef<THREE.Group>(null);
  const g2 = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (g1.current) g1.current.rotation.z = t * 0.12;
    if (g2.current) g2.current.rotation.z = -t * 0.18;
  });

  return (
    <group position={[0, -1.02, 0]}>
      {/* Outer measurement ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.2, 1.25, 64]} />
        <meshBasicMaterial
          color="#cbd5e1"
          wireframe
          transparent
          opacity={0.4}
          depthWrite={false}
        />
      </mesh>

      {/* Tilted subtle telemetry rings */}
      <group ref={g1} rotation={[-Math.PI / 2, 0, 0]}>
        <mesh>
          <ringGeometry args={[0.96, 0.975, 48, 1, 0, Math.PI * 1.5]} />
          <meshBasicMaterial color={color} transparent opacity={0.65} side={THREE.DoubleSide} />
        </mesh>
      </group>

      <group ref={g2} rotation={[-Math.PI / 2, 0, 0]}>
        <mesh>
          <ringGeometry args={[0.82, 0.835, 40, 1, Math.PI * 0.4, Math.PI * 1.2]} />
          <meshBasicMaterial color="#0284c7" transparent opacity={0.5} side={THREE.DoubleSide} />
        </mesh>
      </group>
    </group>
  );
}

/** Internal Anatomical Nodes: Pancreas, Sensor, Liver, Cardiac Core */
function BiometricInternalNodes({ color }: { color: string }) {
  const pulseRef = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!pulseRef.current) return;
    const s = 1 + Math.sin(clock.getElapsedTime() * 3.5) * 0.3;
    pulseRef.current.scale.set(s, s, s);
  });

  return (
    <group>
      {/* 1. Pancreatic Islets (Beta cells endocrine core) */}
      <group position={[0.05, 0.16, 0.11]}>
        <mesh>
          <sphereGeometry args={[0.026, 20, 20]} />
          <meshStandardMaterial
            color="#f59e0b"
            emissive="#d97706"
            emissiveIntensity={3.0}
            roughness={0.1}
          />
        </mesh>
        <group ref={pulseRef}>
          <mesh>
            <sphereGeometry args={[0.048, 16, 16]} />
            <meshBasicMaterial color="#f59e0b" wireframe transparent opacity={0.45} />
          </mesh>
        </group>
      </group>

      {/* 2. Dexcom CGM Sensor Patch (Arm) */}
      <group position={[-0.34, 0.38, 0.05]}>
        <mesh>
          <sphereGeometry args={[0.028, 20, 20]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={3.5}
            roughness={0.1}
          />
        </mesh>
        <mesh>
          <sphereGeometry args={[0.045, 14, 14]} />
          <meshBasicMaterial color={color} wireframe transparent opacity={0.5} />
        </mesh>
      </group>

      {/* 3. Hepatic Glycogen Center (Liver) */}
      <group position={[-0.11, 0.22, 0.09]}>
        <mesh>
          <sphereGeometry args={[0.022, 18, 18]} />
          <meshStandardMaterial
            color="#0284c7"
            emissive="#0369a1"
            emissiveIntensity={2.5}
            roughness={0.15}
          />
        </mesh>
      </group>

      {/* 4. Heart / Cardiac Perfusion Node */}
      <group position={[0.03, 0.38, 0.12]}>
        <mesh>
          <sphereGeometry args={[0.024, 18, 18]} />
          <meshStandardMaterial
            color="#ef4444"
            emissive="#dc2626"
            emissiveIntensity={2.8}
            roughness={0.15}
          />
        </mesh>
      </group>
    </group>
  );
}

/** Apex Clinical Twin - Single Master 3D Model in Pure Luxury White Studio */
export default function ApexClinicalTwin({ riskBand, streaming }: ApexTwinProps) {
  const modelGroup = useRef<THREE.Group>(null);
  const gltf = useGLTF("/geometries/human_body.glb");
  const p = PALETTE[riskBand] ?? PALETTE.unknown;

  // Ultra-Premium Ceramic + Glass Morphism Shader
  const clonedScene = useMemo(() => {
    const scene = gltf.scene.clone(true);

    scene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        // Luxury Pearlescent Optical Ceramic Glass material
        mesh.material = new THREE.MeshPhysicalMaterial({
          color: new THREE.Color("#f8fafc"),
          roughness: 0.18,
          metalness: 0.05,
          transmission: 0.72, // Frosted optical refraction
          thickness: 0.85,
          ior: 1.48, // Medical borosilicate glass IOR
          clearcoat: 0.95,
          clearcoatRoughness: 0.08,
          emissive: new THREE.Color(p.primary),
          emissiveIntensity: 0.28,
          sheen: 0.8,
          sheenColor: new THREE.Color("#e0f2fe"),
          transparent: true,
          opacity: 0.88,
        });
      }
    });

    return scene;
  }, [gltf, p.primary]);

  // Breathing simulation & slow 360 cinematic rotation
  useFrame(({ clock }, delta) => {
    if (!modelGroup.current) return;
    modelGroup.current.rotation.y += delta * 0.22;
    if (streaming) {
      const t = clock.getElapsedTime();
      const s = 1 + Math.sin(t * 1.8) * 0.01;
      modelGroup.current.scale.set(0.95 * s, 0.95, 0.95 * s);
    }
  });

  return (
    <group>
      {/* 1. Real Downloaded 3D Human Anatomy Model with Optical Ceramic Glass Shader */}
      <group ref={modelGroup} position={[0, -0.98, 0]} scale={0.95}>
        <primitive object={clonedScene} />
      </group>

      {/* 2. Internal Biometric Nodes: Pancreas, Sensor, Liver, Cardiac Core */}
      <BiometricInternalNodes color={p.primary} />

      {/* 3. Dual Sweeping Laser Diagnostic Scanner */}
      <PrecisionMedicalScan color={p.primary} />

      {/* 4. Floor Precision Reticle */}
      <PrecisionFloorReticle color={p.primary} />

      {/* 5. Quantum Bio-particles */}
      <QuantumBioParticles color={p.primary} />
    </group>
  );
}

useGLTF.preload("/geometries/human_body.glb");
