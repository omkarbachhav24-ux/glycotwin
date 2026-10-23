/*
  Procedural human geometry.

  The figure is built from lofted elliptical cross sections rather than stacked
  primitives, which is what gives it a continuous silhouette and smooth shading
  across the shoulders, waist and limbs. Proportions follow the usual drawing
  canon of roughly seven and a half head heights, with the model standing
  1.75 units tall and the feet on y = 0.

  Nothing here is anatomically exact. It is a believable body, not a medical
  reference, and the console says so beside it.
*/

import * as THREE from "three";

export interface Ring {
  y: number;
  rx: number;
  rz: number;
  cx?: number;
  cz?: number;
}

/** Loft a closed surface through elliptical rings stacked along y. */
export function loftRings(rings: Ring[], radialSegments = 48, smooth = 4): THREE.BufferGeometry {
  const dense = resample(rings, smooth);
  const positions: number[] = [];
  const indices: number[] = [];

  for (let i = 0; i < dense.length; i++) {
    const r = dense[i];
    for (let s = 0; s < radialSegments; s++) {
      const a = (s / radialSegments) * Math.PI * 2;
      positions.push(
        (r.cx ?? 0) + Math.cos(a) * r.rx,
        r.y,
        (r.cz ?? 0) + Math.sin(a) * r.rz,
      );
    }
  }

  for (let i = 0; i < dense.length - 1; i++) {
    for (let s = 0; s < radialSegments; s++) {
      const a = i * radialSegments + s;
      const b = i * radialSegments + ((s + 1) % radialSegments);
      const c = (i + 1) * radialSegments + s;
      const d = (i + 1) * radialSegments + ((s + 1) % radialSegments);
      indices.push(a, c, b, b, c, d);
    }
  }

  // Caps, so the surface is closed and does not show its interior.
  const capStart = positions.length / 3;
  const first = dense[0];
  positions.push(first.cx ?? 0, first.y, first.cz ?? 0);
  for (let s = 0; s < radialSegments; s++) {
    indices.push(capStart, (s + 1) % radialSegments, s);
  }
  const capEnd = positions.length / 3;
  const last = dense[dense.length - 1];
  const base = (dense.length - 1) * radialSegments;
  positions.push(last.cx ?? 0, last.y, last.cz ?? 0);
  for (let s = 0; s < radialSegments; s++) {
    indices.push(capEnd, base + s, base + ((s + 1) % radialSegments));
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

/** Catmull-Rom resampling so a handful of control rings reads as a smooth body. */
function resample(rings: Ring[], factor: number): Ring[] {
  if (factor <= 1 || rings.length < 3) return rings;
  const curveY = new THREE.CatmullRomCurve3(rings.map((r) => new THREE.Vector3(0, r.y, 0)));
  const curveR = new THREE.CatmullRomCurve3(
    rings.map((r) => new THREE.Vector3(r.rx, r.rz, r.cz ?? 0)));
  const curveC = new THREE.CatmullRomCurve3(
    rings.map((r) => new THREE.Vector3(r.cx ?? 0, 0, 0)));
  const n = (rings.length - 1) * factor;
  const out: Ring[] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const y = curveY.getPoint(t).y;
    const r = curveR.getPoint(t);
    out.push({ y, rx: Math.max(r.x, 0.001), rz: Math.max(r.y, 0.001), cx: curveC.getPoint(t).x, cz: r.z });
  }
  return out;
}

/** A tube along a curve whose radius varies, used for limbs. */
export function taperedTube(
  curve: THREE.Curve<THREE.Vector3>,
  radii: number[],
  tubularSegments = 44,
  radialSegments = 24,
  flatten = 1,
): THREE.BufferGeometry {
  const frames = (curve as THREE.CatmullRomCurve3).computeFrenetFrames(tubularSegments, false);
  const positions: number[] = [];
  const indices: number[] = [];
  const radiusAt = (t: number) => {
    const x = t * (radii.length - 1);
    const i = Math.min(Math.floor(x), radii.length - 2);
    const f = x - i;
    return radii[i] * (1 - f) + radii[i + 1] * f;
  };

  for (let i = 0; i <= tubularSegments; i++) {
    const t = i / tubularSegments;
    const p = curve.getPoint(t);
    const N = frames.normals[i];
    const B = frames.binormals[i];
    const r = radiusAt(t);
    for (let s = 0; s < radialSegments; s++) {
      const a = (s / radialSegments) * Math.PI * 2;
      const sin = Math.sin(a) * r * flatten;
      const cos = Math.cos(a) * r;
      positions.push(
        p.x + cos * N.x + sin * B.x,
        p.y + cos * N.y + sin * B.y,
        p.z + cos * N.z + sin * B.z,
      );
    }
  }
  for (let i = 0; i < tubularSegments; i++) {
    for (let s = 0; s < radialSegments; s++) {
      const a = i * radialSegments + s;
      const b = i * radialSegments + ((s + 1) % radialSegments);
      const c = (i + 1) * radialSegments + s;
      const d = (i + 1) * radialSegments + ((s + 1) % radialSegments);
      indices.push(a, c, b, b, c, d);
    }
  }

  const startCentre = curve.getPoint(0);
  const capA = positions.length / 3;
  positions.push(startCentre.x, startCentre.y, startCentre.z);
  for (let s = 0; s < radialSegments; s++) {
    indices.push(capA, (s + 1) % radialSegments, s);
  }
  const endCentre = curve.getPoint(1);
  const capB = positions.length / 3;
  const base = tubularSegments * radialSegments;
  positions.push(endCentre.x, endCentre.y, endCentre.z);
  for (let s = 0; s < radialSegments; s++) {
    indices.push(capB, base + s, base + ((s + 1) % radialSegments));
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

// --------------------------------------------------------------- the body

/** Torso from pelvis to neck. Waist narrows, chest and shoulders widen. */
export const TORSO_RINGS: Ring[] = [
  { y: 0.86, rx: 0.120, rz: 0.090 },
  { y: 0.91, rx: 0.158, rz: 0.104 },
  { y: 0.96, rx: 0.170, rz: 0.108 },
  { y: 1.02, rx: 0.156, rz: 0.100 },
  { y: 1.09, rx: 0.138, rz: 0.093 },
  { y: 1.15, rx: 0.142, rz: 0.097 },
  { y: 1.22, rx: 0.158, rz: 0.106 },
  { y: 1.29, rx: 0.176, rz: 0.113 },
  { y: 1.36, rx: 0.186, rz: 0.114 },
  { y: 1.42, rx: 0.192, rz: 0.110 },
  { y: 1.46, rx: 0.176, rz: 0.101 },
  { y: 1.49, rx: 0.120, rz: 0.088 },
  { y: 1.515, rx: 0.062, rz: 0.064 },
  { y: 1.545, rx: 0.053, rz: 0.055 },
  { y: 1.570, rx: 0.051, rz: 0.053 },
];

/** Head: cranium, face taper and jaw. */
export const HEAD_RINGS: Ring[] = [
  { y: 1.560, rx: 0.050, rz: 0.052 },
  { y: 1.582, rx: 0.059, rz: 0.066, cz: 0.006 },
  { y: 1.602, rx: 0.071, rz: 0.080, cz: 0.009 },
  { y: 1.624, rx: 0.081, rz: 0.090, cz: 0.008 },
  { y: 1.650, rx: 0.088, rz: 0.096, cz: 0.004 },
  { y: 1.676, rx: 0.092, rz: 0.098, cz: 0.000 },
  { y: 1.702, rx: 0.091, rz: 0.095, cz: -0.004 },
  { y: 1.728, rx: 0.084, rz: 0.086, cz: -0.008 },
  { y: 1.752, rx: 0.068, rz: 0.068, cz: -0.010 },
  { y: 1.770, rx: 0.044, rz: 0.043, cz: -0.010 },
  { y: 1.782, rx: 0.016, rz: 0.016, cz: -0.010 },
];

/*
  Poses.

  "relaxed" is the standing figure. The two Vitruvian poses are the ones
  Leonardo superimposed: arms level with the shoulders and feet together, and
  arms raised with the feet apart. Reach is tuned so the level pose touches the
  square and the raised pose touches the circle, which is the whole point of the
  drawing.
*/
export type ArmPose = "relaxed" | "level" | "raised";
export type LegPose = "relaxed" | "together" | "apart";

/** Circle centred on the navel, square on the standing height. */
export const VITRUVIAN = {
  navelY: 1.06,
  circleRadius: 0.95,
  squareHalf: 0.89,
  squareBottom: 0.0,
  squareTop: 1.78,
};

export function armCurvePosed(side: number, pose: ArmPose): THREE.CatmullRomCurve3 {
  if (pose === "relaxed") return armCurve(side);
  if (pose === "level") {
    // Fingertips reach the side of the square at shoulder height.
    return new THREE.CatmullRomCurve3([
      new THREE.Vector3(side * 0.110, 1.448, 0.004),
      new THREE.Vector3(side * 0.210, 1.452, 0.004),
      new THREE.Vector3(side * 0.370, 1.450, 0.002),
      new THREE.Vector3(side * 0.530, 1.447, 0.000),
      new THREE.Vector3(side * 0.690, 1.444, 0.000),
      new THREE.Vector3(side * 0.820, 1.442, 0.000),
    ]);
  }
  // Raised: fingertips land on the circle.
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(side * 0.110, 1.452, 0.004),
    new THREE.Vector3(side * 0.205, 1.496, 0.004),
    new THREE.Vector3(side * 0.350, 1.576, 0.002),
    new THREE.Vector3(side * 0.470, 1.650, 0.000),
    new THREE.Vector3(side * 0.580, 1.724, 0.000),
    new THREE.Vector3(side * 0.660, 1.776, 0.000),
  ]);
}

export function legCurvePosed(side: number, pose: LegPose): THREE.CatmullRomCurve3 {
  if (pose === "relaxed") return legCurve(side);
  if (pose === "together") {
    return new THREE.CatmullRomCurve3([
      new THREE.Vector3(side * 0.072, 0.965, 0),
      new THREE.Vector3(side * 0.066, 0.860, 0.002),
      new THREE.Vector3(side * 0.058, 0.660, 0.004),
      new THREE.Vector3(side * 0.052, 0.480, -0.002),
      new THREE.Vector3(side * 0.046, 0.260, -0.004),
      new THREE.Vector3(side * 0.042, 0.058, 0.004),
    ]);
  }
  // Apart: soles land on the circle.
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(side * 0.080, 0.960, 0),
    new THREE.Vector3(side * 0.130, 0.850, 0.002),
    new THREE.Vector3(side * 0.225, 0.650, 0.002),
    new THREE.Vector3(side * 0.300, 0.500, 0.000),
    new THREE.Vector3(side * 0.390, 0.330, 0.000),
    new THREE.Vector3(side * 0.455, 0.212, 0.002),
  ]);
}

/** Where a posed limb ends, so hands and feet can follow it. */
export function endOf(curve: THREE.CatmullRomCurve3): THREE.Vector3 {
  return curve.getPoint(1);
}

export function armCurve(side: number): THREE.CatmullRomCurve3 {
  // Shoulder, upper arm, elbow, forearm, wrist. A slight outward bow keeps the
  // arms off the torso so the silhouette stays readable from the front.
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(side * 0.120, 1.455, 0.004),
    new THREE.Vector3(side * 0.186, 1.408, 0.004),
    new THREE.Vector3(side * 0.233, 1.330, 0.004),
    new THREE.Vector3(side * 0.264, 1.180, -0.002),
    new THREE.Vector3(side * 0.274, 1.080, -0.004),
    new THREE.Vector3(side * 0.282, 0.960, 0.010),
    new THREE.Vector3(side * 0.288, 0.870, 0.022),
  ]);
}

export const ARM_RADII = [0.052, 0.062, 0.054, 0.044, 0.040, 0.035, 0.031];

export function legCurve(side: number): THREE.CatmullRomCurve3 {
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(side * 0.074, 0.965, 0),
    new THREE.Vector3(side * 0.082, 0.880, 0.002),
    new THREE.Vector3(side * 0.090, 0.760, 0.004),
    new THREE.Vector3(side * 0.094, 0.560, 0.002),
    new THREE.Vector3(side * 0.092, 0.480, -0.004),
    new THREE.Vector3(side * 0.090, 0.300, -0.006),
    new THREE.Vector3(side * 0.088, 0.058, 0.004),
  ]);
}

export const LEG_RADII = [0.088, 0.098, 0.090, 0.072, 0.062, 0.050, 0.040];
