"use client";

/*
  The twin drawn as Leonardo's figure of proportion.

  Leonardo's Vitruvian Man is from about 1490 and is long out of copyright, so
  this is a reading of it rather than a copy of the sheet: the same idea, the
  two superimposed poses inside a circle and a square, rebuilt in three
  dimensions from the same body used by the anatomical view.

  The one modern element is the sensor on the upper arm, which keeps the colour
  of the current risk band. Everything else is ink.
*/

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import {
  ARM_RADII, HEAD_RINGS, LEG_RADII, TORSO_RINGS, VITRUVIAN,
  armCurvePosed, endOf, legCurvePosed, loftRings, taperedTube,
} from "./humanGeometry";

const INK = "#d9ae63";
const PARCHMENT = "#efe3cb";

function useInkMaterials(tint: string) {
  return useMemo(() => {
    const body = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(PARCHMENT),
      roughness: 0.82,
      metalness: 0,
      sheen: 0.4,
      sheenColor: new THREE.Color("#c9a877"),
      envMapIntensity: 0.45,
    });
    // The second pose is the one Leonardo drew over the first. Here it is held
    // back so the primary pose still reads as the figure.
    // Lit, so the held back pose still has form, and opaque enough that it
    // reads as pale ink on a dark page rather than as a shadow.
    const ghost = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color("#e4d8bd"),
      roughness: 0.86,
      metalness: 0,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
      envMapIntensity: 0.4,
    });
    const line = new THREE.MeshBasicMaterial({ color: new THREE.Color(INK) });
    const lineSoft = new THREE.MeshBasicMaterial({
      color: new THREE.Color(INK),
      transparent: true,
      opacity: 0.42,
    });
    const accent = new THREE.MeshStandardMaterial({
      color: new THREE.Color(tint),
      emissive: new THREE.Color(tint),
      emissiveIntensity: 1.6,
      roughness: 0.3,
    });
    return { body, ghost, line, lineSoft, accent };
  }, [tint]);
}

/** The circle on the navel and the square on the standing height. */
function Frame({ line, lineSoft }: { line: THREE.Material; lineSoft: THREE.Material }) {
  const { navelY, circleRadius, squareHalf, squareBottom, squareTop } = VITRUVIAN;
  const t = 0.0035;
  const side = squareTop - squareBottom;
  const midY = (squareTop + squareBottom) / 2;

  return (
    <group>
      <mesh position={[0, navelY, 0]} material={line}>
        <torusGeometry args={[circleRadius, t, 10, 220]} />
      </mesh>
      <mesh position={[0, squareTop, 0]} material={line}>
        <boxGeometry args={[squareHalf * 2, t * 2, t * 2]} />
      </mesh>
      <mesh position={[0, squareBottom, 0]} material={line}>
        <boxGeometry args={[squareHalf * 2, t * 2, t * 2]} />
      </mesh>
      <mesh position={[-squareHalf, midY, 0]} material={line}>
        <boxGeometry args={[t * 2, side, t * 2]} />
      </mesh>
      <mesh position={[squareHalf, midY, 0]} material={line}>
        <boxGeometry args={[t * 2, side, t * 2]} />
      </mesh>
      {/* The construction lines Leonardo ruled across the sheet. */}
      <mesh position={[0, navelY, -0.002]} material={lineSoft}>
        <boxGeometry args={[circleRadius * 2, t, t]} />
      </mesh>
      <mesh position={[0, midY, -0.002]} material={lineSoft}>
        <boxGeometry args={[t, side, t]} />
      </mesh>
    </group>
  );
}

export default function VitruvianBody({
  tint, streaming,
}: {
  tint: string;
  streaming: boolean;
}) {
  const mats = useInkMaterials(tint);
  const halo = useRef<THREE.Mesh>(null);

  const torso = useMemo(() => loftRings(TORSO_RINGS, 56, 6), []);
  const head = useMemo(() => loftRings(HEAD_RINGS, 48, 6), []);

  const level = useMemo(
    () => [-1, 1].map((s) => armCurvePosed(s, "level")), []);
  const raised = useMemo(
    () => [-1, 1].map((s) => armCurvePosed(s, "raised")), []);
  const together = useMemo(
    () => [-1, 1].map((s) => legCurvePosed(s, "together")), []);
  const apart = useMemo(
    () => [-1, 1].map((s) => legCurvePosed(s, "apart")), []);

  const geo = useMemo(() => ({
    levelArms: level.map((c) => taperedTube(c, ARM_RADII, 48, 24, 0.9)),
    raisedArms: raised.map((c) => taperedTube(c, ARM_RADII, 48, 24, 0.9)),
    togetherLegs: together.map((c) => taperedTube(c, LEG_RADII, 48, 24, 0.94)),
    apartLegs: apart.map((c) => taperedTube(c, LEG_RADII, 48, 24, 0.94)),
  }), [level, raised, together, apart]);

  useFrame(({ clock }) => {
    if (!halo.current) return;
    if (!streaming) {
      (halo.current.material as THREE.MeshBasicMaterial).opacity = 0;
      return;
    }
    const t = clock.getElapsedTime();
    halo.current.scale.setScalar(1 + Math.sin(t * 2) * 0.18);
    (halo.current.material as THREE.MeshBasicMaterial).opacity = 0.4 - Math.sin(t * 2) * 0.16;
  });

  const sensorAt = useMemo(() => {
    const p = armCurvePosed(-1, "level").getPoint(0.32);
    return new THREE.Vector3(p.x, p.y + 0.028, p.z - 0.018);
  }, []);

  return (
    <group>
      <Frame line={mats.line} lineSoft={mats.lineSoft} />

      <mesh geometry={torso} material={mats.body} />
      <mesh geometry={head} material={mats.body} />

      {/* Leonardo's figure has a face and long hair. These are the same
          features the standing view uses, in ink tones. */}
      <mesh material={mats.body} position={[0, 1.644, 0.092]} rotation={[0.42, 0, 0]}
            scale={[0.013, 0.026, 0.017]}>
        <sphereGeometry args={[1, 18, 14]} />
      </mesh>
      {[-1, 1].map((side) => (
        <mesh key={`vbrow-${side}`} material={mats.body}
              position={[side * 0.033, 1.672, 0.086]} rotation={[0, 0, side * -0.12]}
              scale={[0.022, 0.0065, 0.010]}>
          <sphereGeometry args={[1, 20, 12]} />
        </mesh>
      ))}
      {[-1, 1].map((side) => (
        <mesh key={`veye-${side}`} position={[side * 0.034, 1.656, 0.088]}
              scale={[0.0092, 0.0070, 0.007]}>
          <sphereGeometry args={[1, 18, 14]} />
          <meshBasicMaterial color="#6f5a3c" />
        </mesh>
      ))}
      <mesh position={[0, 1.609, 0.086]} scale={[0.018, 0.0045, 0.008]}>
        <sphereGeometry args={[1, 20, 14]} />
        <meshBasicMaterial color="#a9825a" />
      </mesh>
      {[-1, 1].map((side) => (
        <mesh key={`vear-${side}`} material={mats.body}
              position={[side * 0.088, 1.664, -0.004]} rotation={[0, side * 0.3, 0]}
              scale={[0.008, 0.021, 0.015]}>
          <sphereGeometry args={[1, 16, 14]} />
        </mesh>
      ))}
      <mesh position={[0, 1.694, -0.018]} scale={[0.101, 0.100, 0.106]}>
        <sphereGeometry args={[1, 40, 32, 0, Math.PI * 2, 0, Math.PI * 0.86]} />
        <meshPhysicalMaterial color="#8a6a42" roughness={0.78} envMapIntensity={0.35} />
      </mesh>

      {/* Primary pose: arms level, feet together. */}
      {geo.levelArms.map((g, i) => <mesh key={`la-${i}`} geometry={g} material={mats.body} />)}
      {geo.togetherLegs.map((g, i) => <mesh key={`tl-${i}`} geometry={g} material={mats.body} />)}

      {/* Superimposed pose: arms raised, feet apart. */}
      {geo.raisedArms.map((g, i) => <mesh key={`ra-${i}`} geometry={g} material={mats.ghost} />)}
      {geo.apartLegs.map((g, i) => <mesh key={`al-${i}`} geometry={g} material={mats.ghost} />)}

      {/* Hands and feet follow whichever pose they belong to. */}
      {[0, 1].map((i) => {
        const e = endOf(level[i]);
        return (
          <mesh key={`hand-${i}`} material={mats.body} position={[e.x + (i ? 0.03 : -0.03), e.y, e.z]}
                scale={[0.038, 0.026, 0.016]}>
            <sphereGeometry args={[1, 18, 14]} />
          </mesh>
        );
      })}
      {[0, 1].map((i) => {
        const e = endOf(raised[i]);
        return (
          <mesh key={`ghand-${i}`} material={mats.ghost}
                position={[e.x + (i ? 0.022 : -0.022), e.y + 0.022, e.z]}
                scale={[0.03, 0.034, 0.016]}>
            <sphereGeometry args={[1, 18, 14]} />
          </mesh>
        );
      })}
      {[0, 1].map((i) => {
        const e = endOf(together[i]);
        return (
          <group key={`foot-${i}`} position={[e.x, e.y - 0.022, e.z]}>
            <mesh material={mats.body} position={[0, 0, 0.056]} scale={[0.042, 0.03, 0.1]}>
              <sphereGeometry args={[1, 22, 16]} />
            </mesh>
            <mesh material={mats.body} position={[0, 0.012, -0.016]} scale={[0.04, 0.038, 0.04]}>
              <sphereGeometry args={[1, 20, 16]} />
            </mesh>
          </group>
        );
      })}
      {[0, 1].map((i) => {
        const e = endOf(apart[i]);
        return (
          <mesh key={`gfoot-${i}`} material={mats.ghost}
                position={[e.x + (i ? 0.03 : -0.03), e.y - 0.012, 0.03]}
                rotation={[0, 0, (i ? -1 : 1) * 0.5]}
                scale={[0.042, 0.03, 0.09]}>
            <sphereGeometry args={[1, 20, 16]} />
          </mesh>
        );
      })}

      {/* The one thing that is not from 1490. */}
      <group position={[sensorAt.x, sensorAt.y, sensorAt.z]} rotation={[Math.PI / 2, 0, 0]}>
        <mesh material={mats.accent}>
          <cylinderGeometry args={[0.019, 0.02, 0.012, 24]} />
        </mesh>
        <mesh ref={halo} rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.03, 0.055, 40]} />
          <meshBasicMaterial color={tint} transparent opacity={0} side={THREE.DoubleSide}
                             depthWrite={false} />
        </mesh>
      </group>
    </group>
  );
}
