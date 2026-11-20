// Modelos 3D de las máquinas (machines.py): cada id de modelo tiene un constructor con el mismo id.
// Lo comparten gym space (ubicar máquinas) y gym path (recorrido); no contiene lógica de ninguna de las dos.
import * as THREE from 'three';

// =====================================================================
// Modelos 3D de máquinas. Unidades en metros; origen en el centro de la
// huella sobre el piso; el frente (acceso del usuario) mira hacia +z.
// =====================================================================
const BOX = new THREE.BoxGeometry(1, 1, 1);
const CYL = new THREE.CylinderGeometry(1, 1, 1, 20);
const UP = new THREE.Vector3(0, 1, 0);
export const MAT = {
  frame: new THREE.MeshStandardMaterial({ color: 0x2b3038, metalness: 0.55, roughness: 0.45 }),
  steel: new THREE.MeshStandardMaterial({ color: 0xc3c8cf, metalness: 0.9, roughness: 0.25 }),
  pad: new THREE.MeshStandardMaterial({ color: 0x1c1f25, roughness: 0.9 }),
  accent: new THREE.MeshStandardMaterial({ color: 0xb8322b, metalness: 0.2, roughness: 0.45 }),
  plate: new THREE.MeshStandardMaterial({ color: 0x141619, roughness: 0.6 }),
  stack: new THREE.MeshStandardMaterial({ color: 0x6b727c, metalness: 0.55, roughness: 0.35 }),
  rubber: new THREE.MeshStandardMaterial({ color: 0x24272c, roughness: 0.95 }),
  screen: new THREE.MeshStandardMaterial({ color: 0x0e2635, emissive: 0x0d4a6b, roughness: 0.3 }),
  belt: new THREE.MeshStandardMaterial({ color: 0x15171a, roughness: 0.95 }),
};
const CABLE = new THREE.LineBasicMaterial({ color: 0x9aa0a8 });

function box(g, w, h, d, x, y, z, m = MAT.frame, rx = 0, ry = 0, rz = 0) {
  const mesh = new THREE.Mesh(BOX, m);
  mesh.scale.set(w, h, d);
  mesh.position.set(x, y, z);
  mesh.rotation.set(rx, ry, rz);
  g.add(mesh);
  return mesh;
}
function tube(g, a, b, r = 0.03, m = MAT.frame) {
  const A = new THREE.Vector3(...a);
  const B = new THREE.Vector3(...b);
  const mesh = new THREE.Mesh(CYL, m);
  mesh.scale.set(r, A.distanceTo(B), r);
  mesh.position.copy(A).add(B).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(UP, B.clone().sub(A).normalize());
  g.add(mesh);
  return mesh;
}
function disc(g, r, length, x, y, z, axis = 'x', m = MAT.plate) {
  const mesh = new THREE.Mesh(CYL, m);
  mesh.scale.set(r, length, r);
  mesh.position.set(x, y, z);
  if (axis === 'x') mesh.rotation.z = Math.PI / 2;
  if (axis === 'z') mesh.rotation.x = Math.PI / 2;
  g.add(mesh);
  return mesh;
}
const plate = (g, x, y, z, r = 0.22, axis = 'x') => disc(g, r, 0.05, x, y, z, axis);
const roller = (g, x, y, z, length = 0.45, r = 0.06) => disc(g, r, length, x, y, z, 'x', MAT.pad);
function cable(g, points) {
  g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map((p) => new THREE.Vector3(...p))), CABLE));
}
function base(g, w, d, x = 0, z = 0) {
  box(g, w, 0.06, 0.08, x, 0.03, z - d / 2 + 0.04);
  box(g, w, 0.06, 0.08, x, 0.03, z + d / 2 - 0.04);
  box(g, 0.08, 0.06, d, x - w / 2 + 0.04, 0.03, z);
  box(g, 0.08, 0.06, d, x + w / 2 - 0.04, 0.03, z);
}
function seat(g, x, y, z, w = 0.45, d = 0.42) {
  box(g, w, 0.09, d, x, y, z, MAT.pad);
  tube(g, [x, 0.05, z], [x, y - 0.05, z], 0.035);
}
function back(g, x, y, z, h = 0.65, w = 0.42, tilt = -0.12) {
  box(g, w, h, 0.08, x, y, z, MAT.pad, tilt);
}
function stack(g, x, z, h = 1.6, w = 0.42) {
  tube(g, [x - w / 2 - 0.03, 0.05, z], [x - w / 2 - 0.03, h, z], 0.035);
  tube(g, [x + w / 2 + 0.03, 0.05, z], [x + w / 2 + 0.03, h, z], 0.035);
  tube(g, [x - 0.06, 0.1, z], [x - 0.06, h - 0.05, z], 0.01, MAT.steel);
  tube(g, [x + 0.06, 0.1, z], [x + 0.06, h - 0.05, z], 0.01, MAT.steel);
  for (let i = 0; i < 12; i += 1) box(g, w - 0.04, 0.035, 0.18, x, 0.12 + i * 0.042, z, MAT.stack);
  box(g, w + 0.14, 0.06, 0.32, x, h, z);
  box(g, w + 0.12, h * 0.55, 0.02, x, h * 0.62, z + 0.15, MAT.accent);
}
function handle(g, x, y, z, span = 0.5) {
  tube(g, [x - span / 2, y, z], [x + span / 2, y, z], 0.016, MAT.steel);
}
function grip(g, x, y, z) {
  tube(g, [x, y - 0.09, z], [x, y + 0.09, z], 0.02, MAT.rubber);
}
function barbell(g, x, y, z, length = 2.1, plates = 2) {
  tube(g, [x - length / 2, y, z], [x + length / 2, y, z], 0.016, MAT.steel);
  for (let i = 0; i < plates; i += 1) {
    plate(g, x - length / 2 + 0.25 + i * 0.055, y, z);
    plate(g, x + length / 2 - 0.25 - i * 0.055, y, z);
  }
}
function post(g, x, z, h, size = 0.08) { box(g, size, h, size, x, h / 2, z); }

const BUILDERS = {
  smith(g) {
    base(g, 2.1, 1.4);
    for (const x of [-1.0, 1.0]) for (const z of [-0.6, 0.6]) post(g, x, z, 2.25);
    for (const z of [-0.6, 0.6]) box(g, 2.08, 0.08, 0.08, 0, 2.25, z);
    for (const x of [-1.0, 1.0]) box(g, 0.08, 0.08, 1.28, x, 2.25, 0);
    for (const x of [-0.85, 0.85]) tube(g, [x, 0.06, 0], [x, 2.21, 0], 0.02, MAT.steel);
    barbell(g, 0, 1.35, 0, 2.15, 2);
    box(g, 0.3, 0.08, 1.1, 0, 0.45, 0.2, MAT.pad);
    tube(g, [0, 0.05, -0.2], [0, 0.41, -0.2], 0.03);
    tube(g, [0, 0.05, 0.6], [0, 0.41, 0.6], 0.03);
  },
  assisted(g) {
    base(g, 1.2, 1.5);
    for (const x of [-0.55, 0.55]) post(g, x, -0.5, 2.35);
    box(g, 1.18, 0.08, 0.08, 0, 2.35, -0.5);
    tube(g, [-0.55, 2.3, -0.5], [-0.4, 2.3, 0.15], 0.025, MAT.steel);
    tube(g, [0.55, 2.3, -0.5], [0.4, 2.3, 0.15], 0.025, MAT.steel);
    for (const x of [-0.28, 0.28]) tube(g, [x, 1.3, -0.45], [x, 1.3, 0.25], 0.025, MAT.steel);
    box(g, 0.42, 0.06, 0.32, 0, 0.92, 0.05, MAT.pad);
    tube(g, [0, 0.92, -0.1], [0, 0.6, -0.45], 0.03);
    for (const x of [-0.35, 0.35]) box(g, 0.25, 0.05, 0.25, x, 0.4, 0.45, MAT.rubber);
    stack(g, 0, -0.62, 1.9);
  },
  lat_pulldown(g) {
    base(g, 1.2, 1.5);
    box(g, 0.14, 2.3, 0.14, 0, 1.15, -0.45);
    box(g, 0.12, 0.12, 0.9, 0, 2.25, -0.05);
    disc(g, 0.07, 0.04, 0, 2.2, 0.32, 'x', MAT.steel);
    cable(g, [[0, 2.15, 0.32], [0, 1.85, 0.25]]);
    tube(g, [-0.6, 1.85, 0.25], [0.6, 1.85, 0.25], 0.016, MAT.steel);
    tube(g, [-0.6, 1.85, 0.25], [-0.68, 1.75, 0.25], 0.016, MAT.steel);
    tube(g, [0.6, 1.85, 0.25], [0.68, 1.75, 0.25], 0.016, MAT.steel);
    seat(g, 0, 0.5, 0.42);
    tube(g, [0, 0.45, 0.42], [0, 0.6, 0.2], 0.03);
    roller(g, 0, 0.75, 0.25, 0.5);
    stack(g, 0, -0.62, 2.0);
  },
  seated_row(g) {
    box(g, 0.24, 0.1, 2.1, 0, 0.05, 0.05);
    seat(g, 0, 0.45, 0.65, 0.38, 0.38);
    box(g, 0.5, 0.36, 0.05, 0, 0.3, 0.12, MAT.rubber, -0.45);
    stack(g, 0, -0.95, 1.5);
    disc(g, 0.06, 0.04, 0, 0.42, -0.72, 'x', MAT.steel);
    cable(g, [[0, 0.42, -0.72], [0, 0.45, 0.3]]);
    tube(g, [-0.07, 0.45, 0.32], [0.07, 0.45, 0.32], 0.02, MAT.rubber);
  },
  leg_press(g) {
    base(g, 1.3, 2.3);
    const angle = Math.atan2(1.25, 1.35);
    for (const x of [-0.38, 0.38]) tube(g, [x, 0.25, 0.35], [x, 1.5, -1.0], 0.04);
    for (const x of [-0.38, 0.38]) tube(g, [x, 0.05, -1.0], [x, 1.5, -1.0], 0.035);
    box(g, 0.85, 0.65, 0.06, 0, 1.0, -0.42, MAT.frame, angle);
    box(g, 0.8, 0.6, 0.02, 0, 1.0, -0.38, MAT.rubber, angle);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.45, 0.95, -0.5], [side * 0.62, 0.95, -0.5], 0.025, MAT.steel);
      plate(g, side * 0.55, 0.95, -0.5, 0.22);
      plate(g, side * 0.6, 0.95, -0.5, 0.22);
    }
    box(g, 0.5, 0.09, 0.45, 0, 0.42, 0.72, MAT.pad, 0.15);
    box(g, 0.5, 0.7, 0.09, 0, 0.75, 0.98, MAT.pad, -0.75);
    for (const x of [-0.35, 0.35]) tube(g, [x, 0.4, 0.75], [x, 0.4, 0.45], 0.02, MAT.rubber);
  },
  cable_station(g) {
    base(g, 1.4, 0.9);
    for (const x of [-0.66, 0.66]) post(g, x, -0.3, 2.3);
    box(g, 1.4, 0.08, 0.08, 0, 2.3, -0.3);
    tube(g, [-0.6, 2.25, 0.35], [0.6, 2.25, 0.35], 0.02, MAT.steel);
    for (const x of [-0.6, 0.6]) tube(g, [x, 2.3, -0.3], [x, 2.25, 0.35], 0.025);
    stack(g, 0, -0.3, 2.0, 0.36);
    for (const side of [-1, 1]) {
      const x = side * 0.5;
      tube(g, [x, 0.08, 0.05], [x, 2.2, 0.05], 0.03, MAT.steel);
      box(g, 0.12, 0.18, 0.12, x, 1.35, 0.1, MAT.accent);
      disc(g, 0.05, 0.03, x, 1.3, 0.2, 'x', MAT.steel);
      cable(g, [[x, 1.3, 0.22], [x, 1.1, 0.38]]);
      grip(g, x, 1.06, 0.38);
    }
  },
  belt_squat(g) {
    box(g, 1.0, 0.15, 0.9, 0, 0.075, 0.2, MAT.rubber);
    base(g, 1.3, 1.9);
    tube(g, [0, 0.35, -0.85], [0, 0.6, 0.3], 0.04);
    box(g, 0.3, 0.08, 0.2, 0, 0.58, 0.32, MAT.accent);
    disc(g, 0.03, 0.4, 0, 0.35, -0.85, 'x', MAT.steel);
    plate(g, 0.15, 0.4, -0.8);
    plate(g, -0.15, 0.4, -0.8);
    for (const x of [-0.6, 0.6]) {
      tube(g, [x, 0.05, 0.6], [x, 1.1, 0.6], 0.03);
      tube(g, [x, 1.1, 0.6], [x, 1.1, 0.25], 0.02, MAT.rubber);
    }
  },
  hack_squat(g) {
    base(g, 1.3, 2.1);
    for (const x of [-0.32, 0.32]) tube(g, [x, 0.15, 0.75], [x, 1.85, -0.75], 0.04);
    box(g, 0.75, 0.06, 0.55, 0, 0.17, 0.62, MAT.rubber, 0.35);
    box(g, 0.45, 0.85, 0.09, 0, 1.0, 0.05, MAT.pad, -0.85);
    for (const x of [-0.17, 0.17]) box(g, 0.13, 0.09, 0.22, x, 1.48, -0.25, MAT.pad, -0.85);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.35, 1.2, -0.25], [side * 0.6, 1.2, -0.25], 0.025, MAT.steel);
      plate(g, side * 0.52, 1.2, -0.25, 0.22);
    }
    for (const x of [-0.32, 0.32]) tube(g, [x, 0.05, -0.75], [x, 1.85, -0.75], 0.04);
  },
  leg_extension(g) {
    base(g, 1.0, 1.3);
    seat(g, 0, 0.5, 0.05);
    back(g, 0, 0.88, -0.22, 0.6, 0.42, -0.18);
    tube(g, [0.3, 0.5, 0.3], [0.3, 0.22, 0.48], 0.03);
    roller(g, 0.05, 0.22, 0.5, 0.42);
    for (const x of [-0.3, 0.3]) tube(g, [x, 0.55, 0.05], [x, 0.55, -0.15], 0.02, MAT.rubber);
    stack(g, -0.25, -0.5, 1.25, 0.32);
  },
  lying_leg_curl(g) {
    base(g, 0.9, 1.9);
    box(g, 0.36, 0.1, 0.85, 0, 0.72, -0.25, MAT.pad, 0.12);
    box(g, 0.36, 0.1, 0.45, 0, 0.68, 0.38, MAT.pad, -0.1);
    for (const z of [-0.55, 0.3]) tube(g, [0, 0.05, z], [0, 0.64, z], 0.035);
    tube(g, [0.25, 0.62, 0.58], [0.25, 0.62, 0.82], 0.03);
    roller(g, 0.05, 0.62, 0.82, 0.42);
    for (const x of [-0.25, 0.25]) tube(g, [x, 0.72, -0.62], [x, 0.85, -0.62], 0.02, MAT.rubber);
    stack(g, 0, -0.85, 1.1, 0.3);
  },
  seated_leg_curl(g) {
    base(g, 1.0, 1.3);
    seat(g, 0, 0.5, 0.0);
    back(g, 0, 0.88, -0.25, 0.6, 0.42, -0.25);
    roller(g, 0.05, 0.72, 0.3, 0.42);
    tube(g, [0.3, 0.6, 0.15], [0.3, 0.42, 0.5], 0.03);
    roller(g, 0.05, 0.42, 0.52, 0.42);
    stack(g, -0.25, -0.5, 1.25, 0.32);
  },
  hip_ab_adductor(g) {
    base(g, 1.1, 1.4);
    seat(g, 0, 0.55, 0.1, 0.5, 0.45);
    back(g, 0, 0.95, -0.2, 0.65, 0.48, -0.3);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.12, 0.45, 0.25], [side * 0.3, 0.45, 0.35], 0.03);
      box(g, 0.08, 0.32, 0.28, side * 0.32, 0.55, 0.38, MAT.pad);
      box(g, 0.16, 0.04, 0.24, side * 0.3, 0.3, 0.55, MAT.rubber);
    }
    stack(g, 0, -0.55, 1.3, 0.34);
  },
  hip_thrust(g) {
    base(g, 1.2, 1.7);
    box(g, 0.9, 0.1, 0.35, 0, 0.42, -0.45, MAT.pad, -0.2);
    tube(g, [0, 0.05, -0.45], [0, 0.38, -0.45], 0.04);
    box(g, 0.9, 0.05, 0.6, 0, 0.05, 0.45, MAT.rubber);
    for (const side of [-1, 1]) tube(g, [side * 0.5, 0.65, -0.7], [side * 0.38, 0.5, 0.0], 0.035);
    box(g, 0.7, 0.12, 0.22, 0, 0.5, 0.0, MAT.pad);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.5, 0.65, -0.7], [side * 0.68, 0.65, -0.7], 0.025, MAT.steel);
      plate(g, side * 0.62, 0.65, -0.7, 0.22);
    }
  },
  glute_machine(g) {
    base(g, 0.9, 1.4);
    box(g, 0.45, 0.4, 0.1, 0, 1.1, -0.35, MAT.pad, 0.35);
    for (const x of [-0.2, 0.2]) box(g, 0.14, 0.06, 0.3, x, 0.98, -0.15, MAT.pad);
    box(g, 0.4, 0.08, 0.35, 0, 0.5, -0.05, MAT.pad);
    tube(g, [0, 0.05, -0.05], [0, 0.46, -0.05], 0.035);
    tube(g, [0.25, 0.75, -0.4], [0.2, 0.45, 0.45], 0.03);
    box(g, 0.25, 0.25, 0.08, 0.1, 0.45, 0.5, MAT.pad);
    stack(g, -0.25, -0.55, 1.4, 0.3);
  },
  standing_calf(g) {
    base(g, 1.0, 1.0);
    for (const x of [-0.42, 0.42]) post(g, x, -0.38, 2.05);
    box(g, 0.92, 0.08, 0.08, 0, 2.05, -0.38);
    box(g, 0.5, 0.1, 0.3, 0, 1.6, -0.15, MAT.frame);
    for (const x of [-0.17, 0.17]) box(g, 0.16, 0.09, 0.26, x, 1.56, 0.02, MAT.pad);
    box(g, 0.6, 0.12, 0.24, 0, 0.12, 0.2, MAT.rubber);
    stack(g, 0, -0.42, 1.5, 0.32);
  },
  seated_calf(g) {
    base(g, 0.7, 1.2);
    seat(g, 0, 0.45, -0.25, 0.38, 0.38);
    box(g, 0.42, 0.1, 0.16, 0, 0.7, 0.12, MAT.pad);
    tube(g, [0, 0.7, 0.05], [0, 0.6, -0.5], 0.03);
    box(g, 0.45, 0.1, 0.18, 0, 0.12, 0.35, MAT.rubber);
    tube(g, [0.2, 0.7, 0.12], [0.36, 0.7, 0.12], 0.025, MAT.steel);
    plate(g, 0.32, 0.7, 0.12, 0.2);
  },
  pec_deck(g) {
    base(g, 1.3, 1.3);
    seat(g, 0, 0.52, 0.18);
    back(g, 0, 1.0, -0.06, 0.8, 0.4, -0.08);
    box(g, 0.14, 2.0, 0.14, 0, 1.0, -0.4);
    box(g, 0.7, 0.1, 0.14, 0, 1.95, -0.32);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.3, 1.9, -0.25], [side * 0.55, 1.9, 0.12], 0.03);
      tube(g, [side * 0.55, 1.9, 0.12], [side * 0.55, 1.45, 0.12], 0.03);
      box(g, 0.08, 0.5, 0.14, side * 0.55, 1.2, 0.12, MAT.pad);
      grip(g, side * 0.5, 1.5, 0.22);
    }
    stack(g, 0, -0.55, 1.8, 0.36);
  },
  chest_press(g) {
    base(g, 1.3, 1.4);
    seat(g, 0, 0.5, 0.22);
    back(g, 0, 0.98, -0.02, 0.72, 0.44, -0.12);
    for (const x of [-0.6, 0.6]) post(g, x, -0.35, 1.75);
    box(g, 1.28, 0.08, 0.08, 0, 1.75, -0.35);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.6, 1.7, -0.3], [side * 0.42, 1.18, 0.45], 0.03);
      tube(g, [side * 0.42, 1.18, 0.45], [side * 0.3, 1.18, 0.45], 0.022, MAT.steel);
      grip(g, side * 0.3, 1.18, 0.45);
    }
    stack(g, 0, -0.55, 1.6, 0.36);
  },
  shoulder_press(g) {
    base(g, 1.2, 1.3);
    seat(g, 0, 0.5, 0.15);
    back(g, 0, 1.02, -0.06, 0.85, 0.44, -0.06);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.5, 0.95, -0.45], [side * 0.36, 1.45, 0.05], 0.03);
      tube(g, [side * 0.36, 1.45, 0.05], [side * 0.26, 1.45, 0.12], 0.022, MAT.steel);
      grip(g, side * 0.26, 1.45, 0.12);
      post(g, side * 0.5, -0.45, 1.7);
    }
    stack(g, 0, -0.5, 1.7, 0.34);
  },
  lateral_raise(g) {
    base(g, 1.1, 1.1);
    seat(g, 0, 0.5, 0.25, 0.4, 0.35);
    box(g, 0.34, 0.45, 0.08, 0, 0.95, 0.02, MAT.pad);
    tube(g, [0, 0.72, 0.0], [0, 0.72, -0.35], 0.035);
    for (const side of [-1, 1]) {
      disc(g, 0.07, 0.05, side * 0.2, 1.15, 0.0, 'z', MAT.accent);
      box(g, 0.32, 0.08, 0.09, side * 0.38, 1.15, 0.05, MAT.pad, 0, 0, side * 0.25);
    }
    stack(g, 0, -0.42, 1.3, 0.3);
  },
  plate_row(g) {
    base(g, 1.4, 1.5);
    box(g, 0.4, 0.42, 0.1, 0, 1.15, 0.02, MAT.pad, 0.22);
    seat(g, 0, 0.55, 0.38, 0.4, 0.35);
    tube(g, [0, 0.8, 0.1], [0, 0.8, -0.3], 0.035);
    for (const x of [-0.55, 0.55]) post(g, x, -0.55, 1.7);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.55, 1.65, -0.55], [side * 0.32, 1.1, -0.15], 0.032);
      grip(g, side * 0.3, 1.1, -0.12);
      tube(g, [side * 0.55, 1.4, -0.45], [side * 0.75, 1.4, -0.45], 0.025, MAT.steel);
      plate(g, side * 0.68, 1.4, -0.45, 0.22);
    }
  },
  t_bar_row(g) {
    box(g, 0.2, 0.08, 2.0, 0, 0.04, 0);
    box(g, 0.4, 0.08, 0.75, 0, 0.92, 0.2, MAT.pad, 0.55);
    tube(g, [0, 0.05, 0.35], [0, 0.8, 0.3], 0.04);
    box(g, 0.55, 0.05, 0.32, 0, 0.25, 0.75, MAT.rubber, -0.3);
    tube(g, [0, 0.15, -0.95], [0, 0.55, 0.05], 0.035, MAT.steel);
    tube(g, [-0.28, 0.58, 0.08], [0.28, 0.58, 0.08], 0.018, MAT.rubber);
    tube(g, [-0.18, 0.45, -0.2], [0.18, 0.45, -0.2], 0.025, MAT.steel);
    plate(g, -0.13, 0.45, -0.2);
    plate(g, 0.13, 0.45, -0.2);
  },
  pullover(g) {
    base(g, 1.2, 1.3);
    seat(g, 0, 0.5, 0.2);
    back(g, 0, 1.0, -0.05, 0.8, 0.42, -0.1);
    for (const side of [-1, 1]) {
      post(g, side * 0.55, -0.35, 1.85);
      disc(g, 0.09, 0.05, side * 0.5, 1.5, -0.05, 'x', MAT.accent);
      tube(g, [side * 0.5, 1.5, -0.05], [side * 0.4, 1.95, 0.2], 0.03);
      box(g, 0.1, 0.25, 0.1, side * 0.42, 1.65, 0.12, MAT.pad);
    }
    tube(g, [-0.4, 1.95, 0.2], [0.4, 1.95, 0.2], 0.02, MAT.steel);
    stack(g, 0, -0.5, 1.7, 0.34);
  },
  preacher_curl(g) {
    base(g, 0.8, 1.1);
    seat(g, 0, 0.58, 0.28, 0.38, 0.35);
    box(g, 0.6, 0.06, 0.35, 0, 0.98, -0.05, MAT.pad, 0.7);
    tube(g, [0, 0.05, -0.15], [0, 0.9, -0.12], 0.04);
    tube(g, [-0.3, 1.02, -0.3], [0.3, 1.02, -0.3], 0.018, MAT.steel);
    for (const side of [-1, 1]) tube(g, [side * 0.3, 1.02, -0.3], [side * 0.34, 0.85, -0.45], 0.025);
    stack(g, 0, -0.42, 1.15, 0.28);
  },
  triceps_machine(g) {
    base(g, 1.1, 1.2);
    seat(g, 0, 0.5, 0.15);
    back(g, 0, 0.95, -0.1, 0.65, 0.42, -0.1);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.42, 1.15, -0.3], [side * 0.38, 0.85, 0.2], 0.03);
      grip(g, side * 0.36, 0.85, 0.22);
      post(g, side * 0.45, -0.35, 1.5);
    }
    stack(g, 0, -0.45, 1.4, 0.3);
  },
  back_extension(g) {
    box(g, 0.25, 0.08, 1.3, 0, 0.04, 0.05);
    tube(g, [0, 0.05, 0.55], [0, 0.95, -0.15], 0.04);
    box(g, 0.42, 0.1, 0.28, 0, 0.92, -0.05, MAT.pad, -0.8);
    box(g, 0.4, 0.04, 0.3, 0, 0.28, 0.5, MAT.rubber, -0.8);
    roller(g, 0, 0.42, 0.35, 0.38, 0.05);
    for (const side of [-1, 1]) tube(g, [side * 0.2, 0.9, -0.2], [side * 0.28, 1.05, -0.15], 0.02, MAT.rubber);
  },
  ab_machine(g) {
    base(g, 1.1, 1.2);
    seat(g, 0, 0.5, 0.18);
    back(g, 0, 0.9, -0.08, 0.55, 0.42, -0.08);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.3, 1.5, -0.15], [side * 0.2, 1.3, 0.2], 0.03);
      box(g, 0.1, 0.3, 0.1, side * 0.2, 1.2, 0.22, MAT.pad);
    }
    tube(g, [-0.3, 1.5, -0.15], [0.3, 1.5, -0.15], 0.03);
    stack(g, 0, -0.42, 1.5, 0.3);
  },
  shrug_machine(g) {
    base(g, 1.1, 1.1);
    box(g, 0.7, 0.05, 0.6, 0, 0.05, 0.15, MAT.rubber);
    for (const side of [-1, 1]) {
      post(g, side * 0.5, -0.35, 1.4);
      tube(g, [side * 0.5, 1.0, -0.35], [side * 0.35, 0.75, 0.15], 0.03);
      grip(g, side * 0.35, 0.75, 0.18);
    }
    stack(g, 0, -0.4, 1.35, 0.3);
  },
  power_tower(g) {
    base(g, 1.2, 1.1);
    for (const x of [-0.55, 0.55]) post(g, x, -0.35, 2.3);
    box(g, 1.18, 0.08, 0.08, 0, 2.3, -0.35);
    for (const x of [-0.55, 0.55]) tube(g, [x, 2.3, -0.35], [x, 2.25, 0.2], 0.025);
    tube(g, [-0.6, 2.25, 0.2], [0.6, 2.25, 0.2], 0.018, MAT.steel);
    for (const x of [-0.3, 0.3]) tube(g, [x, 1.3, -0.35], [x, 1.3, 0.25], 0.025, MAT.rubber);
    for (const x of [-0.26, 0.26]) box(g, 0.1, 0.06, 0.28, x, 1.42, -0.15, MAT.pad);
    box(g, 0.32, 0.5, 0.08, 0, 1.1, -0.3, MAT.pad);
  },
  treadmill(g) {
    box(g, 0.82, 0.18, 1.9, 0, 0.12, 0.1, MAT.frame);
    box(g, 0.56, 0.02, 1.7, 0, 0.22, 0.12, MAT.belt);
    for (const x of [-0.38, 0.38]) tube(g, [x, 0.2, -0.75], [x, 1.25, -0.88], 0.035);
    box(g, 0.8, 0.28, 0.2, 0, 1.3, -0.85, MAT.frame, -0.4);
    box(g, 0.45, 0.18, 0.02, 0, 1.33, -0.75, MAT.screen, -0.4);
    for (const x of [-0.38, 0.38]) tube(g, [x, 1.0, -0.85], [x, 1.0, -0.45], 0.02, MAT.rubber);
  },
  bike(g) {
    box(g, 0.5, 0.06, 0.08, 0, 0.03, -0.5);
    box(g, 0.5, 0.06, 0.08, 0, 0.03, 0.5);
    tube(g, [0, 0.05, -0.5], [0, 0.4, -0.35], 0.04);
    tube(g, [0, 0.05, 0.5], [0, 0.9, 0.3], 0.04);
    disc(g, 0.26, 0.06, 0, 0.42, -0.35, 'x', MAT.accent);
    tube(g, [0, 0.42, -0.35], [0, 0.42, 0.15], 0.035);
    box(g, 0.22, 0.06, 0.28, 0, 0.95, 0.3, MAT.pad);
    tube(g, [0, 0.42, -0.35], [0, 1.05, -0.3], 0.035);
    tube(g, [-0.22, 1.08, -0.25], [0.22, 1.08, -0.25], 0.02, MAT.rubber);
    for (const side of [-1, 1]) box(g, 0.08, 0.03, 0.12, side * 0.12, 0.42, 0.0, MAT.rubber);
  },
  elliptical(g) {
    box(g, 0.32, 0.08, 1.9, 0, 0.04, 0);
    disc(g, 0.3, 0.2, 0, 0.42, -0.72, 'x', MAT.accent);
    for (const side of [-1, 1]) {
      box(g, 0.16, 0.04, 0.38, side * 0.16, 0.35, 0.15, MAT.rubber, -0.1);
      tube(g, [side * 0.16, 0.35, 0.0], [side * 0.28, 1.65, -0.35], 0.025);
      grip(g, side * 0.28, 1.6, -0.33);
    }
    tube(g, [0, 0.05, -0.55], [0, 1.3, -0.6], 0.04);
    box(g, 0.4, 0.22, 0.1, 0, 1.35, -0.6, MAT.frame, -0.4);
    box(g, 0.28, 0.14, 0.02, 0, 1.37, -0.55, MAT.screen, -0.4);
  },
  rower(g) {
    tube(g, [0, 0.15, -0.9], [0, 0.4, 1.15], 0.05);
    box(g, 0.14, 0.05, 2.0, 0, 0.32, 0.15, MAT.steel, -0.12);
    disc(g, 0.28, 0.22, 0, 0.45, -0.95, 'x', MAT.accent);
    box(g, 0.32, 0.07, 0.3, 0, 0.42, 0.25, MAT.pad, -0.12);
    for (const side of [-1, 1]) box(g, 0.12, 0.25, 0.04, side * 0.1, 0.32, -0.55, MAT.rubber, 0.6);
    tube(g, [-0.25, 0.55, -0.7], [0.25, 0.55, -0.7], 0.018, MAT.rubber);
    box(g, 0.5, 0.06, 0.08, 0, 0.03, -0.9);
    box(g, 0.4, 0.06, 0.08, 0, 0.03, 1.15);
  },
  stair(g) {
    base(g, 0.9, 1.4);
    for (let i = 0; i < 6; i += 1) box(g, 0.6, 0.06, 0.24, 0, 0.15 + i * 0.2, 0.45 - i * 0.16, MAT.rubber);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.4, 0.05, 0.6], [side * 0.4, 1.9, -0.55], 0.03);
      tube(g, [side * 0.38, 1.1, 0.4], [side * 0.38, 1.2, -0.2], 0.02, MAT.rubber);
    }
    box(g, 0.5, 0.25, 0.1, 0, 1.75, -0.45, MAT.frame, -0.3);
    box(g, 0.35, 0.16, 0.02, 0, 1.77, -0.4, MAT.screen, -0.3);
  },
  ski_erg(g) {
    box(g, 0.7, 0.05, 1.0, 0, 0.025, 0.1, MAT.rubber);
    box(g, 0.16, 2.2, 0.16, 0, 1.1, -0.4);
    disc(g, 0.2, 0.18, 0, 1.95, -0.32, 'x', MAT.accent);
    box(g, 0.25, 0.18, 0.04, 0, 1.6, -0.3, MAT.screen);
    for (const side of [-1, 1]) {
      cable(g, [[side * 0.06, 2.0, -0.25], [side * 0.15, 1.7, -0.15]]);
      grip(g, side * 0.15, 1.62, -0.15);
    }
  },
  dumbbells(g) {
    for (const x of [-1.0, 1.0]) {
      tube(g, [x, 0.05, -0.65], [x, 0.9, -0.62], 0.035);
      tube(g, [x, 0.05, -0.35], [x, 0.55, -0.38], 0.035);
    }
    box(g, 2.04, 0.04, 0.22, 0, 0.55, -0.42, MAT.frame, 0.25);
    box(g, 2.04, 0.04, 0.22, 0, 0.88, -0.66, MAT.frame, 0.25);
    for (let i = 0; i < 8; i += 1) {
      const x = -0.88 + i * 0.25;
      const r = 0.055 + i * 0.006;
      for (const [y, z] of [[0.6, -0.42], [0.93, -0.66]]) {
        tube(g, [x, y + r, z - 0.12], [x, y + r, z + 0.12], 0.016, MAT.steel);
        disc(g, r, 0.07, x, y + r, z - 0.12, 'z', MAT.plate);
        disc(g, r, 0.07, x, y + r, z + 0.12, 'z', MAT.plate);
      }
    }
    box(g, 0.3, 0.08, 0.45, 0, 0.45, 0.45, MAT.pad);
    box(g, 0.3, 0.08, 0.75, 0, 0.7, 0.0 + 0.05, MAT.pad, -0.6);
    tube(g, [0, 0.05, 0.45], [0, 0.4, 0.45], 0.03);
    box(g, 0.45, 0.06, 0.08, 0, 0.03, 0.6);
  },
  bench_press(g) {
    box(g, 0.3, 0.09, 1.2, 0, 0.45, 0.35, MAT.pad);
    for (const z of [-0.05, 0.85]) tube(g, [0, 0.05, z], [0, 0.4, z], 0.03);
    for (const x of [-0.55, 0.55]) {
      tube(g, [x, 0.05, -0.35], [x, 1.3, -0.25], 0.035);
      box(g, 0.06, 0.06, 0.1, x, 1.15, -0.2, MAT.steel);
      box(g, 0.08, 0.06, 0.8, x, 0.03, -0.3);
      tube(g, [x, 0.4, -0.55], [x * 1.25, 0.4, -0.55], 0.02, MAT.steel);
      plate(g, x * 1.18, 0.4, -0.55);
    }
    barbell(g, 0, 1.2, -0.2, 2.1, 2);
  },
  squat_rack(g) {
    box(g, 2.2, 0.03, 1.6, 0, 0.015, 0, MAT.rubber);
    for (const x of [-0.6, 0.6]) for (const z of [-0.6, 0.6]) post(g, x, z, 2.3, 0.075);
    for (const z of [-0.6, 0.6]) box(g, 1.27, 0.075, 0.075, 0, 2.3, z);
    for (const x of [-0.6, 0.6]) {
      box(g, 0.075, 0.075, 1.27, x, 2.3, 0);
      tube(g, [x, 0.65, -0.65], [x, 0.65, 0.75], 0.025, MAT.steel);
      box(g, 0.1, 0.06, 0.12, x, 1.32, 0.66, MAT.steel);
    }
    barbell(g, 0, 1.38, 0.66, 2.2, 2);
  },
  barbell_area(g) {
    box(g, 2.4, 0.04, 2.4, 0, 0.02, 0, MAT.rubber);
    box(g, 1.0, 0.045, 2.38, 0, 0.022, 0, new THREE.MeshStandardMaterial({ color: 0x8a6a45, roughness: 0.8 }));
    barbell(g, 0, 0.27, 0, 2.2, 2);
  },
  generic(g) {
    base(g, 1.1, 1.3);
    seat(g, 0, 0.5, 0.2);
    back(g, 0, 0.92, -0.05, 0.6);
    for (const side of [-1, 1]) {
      tube(g, [side * 0.45, 1.3, -0.3], [side * 0.35, 1.0, 0.3], 0.03);
      grip(g, side * 0.35, 1.0, 0.32);
    }
    stack(g, 0, -0.45, 1.5, 0.32);
  },
};

export function buildModel(modelId) {
  const g = new THREE.Group();
  (BUILDERS[modelId] || BUILDERS.generic)(g);
  return g;
}
