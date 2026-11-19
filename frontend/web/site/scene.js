// The site's living backdrop: the night stadium, with thousands of particles that assemble into each
// page's data (a rating, a season, a squad), morph as the page scrolls, and part around the pointer.
// The camera flies a path through the stadium on scroll. Bloom adds the glow.
//
//   immersive({ formations: [A, B, C], keyframes: [{ at, morph, pos, look }], palette, shiftRight })
//
// A formation is a Float32Array of xyz points (any length: it is resampled to the particle count).
// Build them with textFormation, curveFormation, columnsFormation, sphereFormation, fieldFormation,
// galaxyFormation. `morph` 0 shows A, 1 shows B, 2 shows C, in between they travel.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { addStadium } from '../design/stadium.js';

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const small = () => window.innerWidth <= 860;
const smooth = (t) => t * t * (3 - 2 * t);

const VERTEX = /* glsl */`
  attribute vec3 aA; attribute vec3 aB; attribute vec3 aC; attribute vec4 aRand; attribute vec3 aTag;
  uniform float uMorph; uniform float uTime; uniform vec3 uMouse; uniform float uPush; uniform float uRadius; uniform float uPixelRatio;
  uniform vec3 uColorA; uniform vec3 uColorB; uniform vec3 uColorC; uniform vec3 uSpark; uniform vec3 uAlt;
  varying vec3 vColor; varying float vAlpha;
  vec3 flow(vec3 p, float t) {   // a cheap swirling field: particles travel on curves, not straight lines
    return vec3(sin(p.y * 0.9 + t) + sin(p.z * 0.7 - t * 0.8), sin(p.z * 0.8 + t * 1.1) + sin(p.x * 0.6 + t), sin(p.x * 0.7 - t) + sin(p.y * 0.5 + t * 0.9));
  }
  void main() {
    // each particle starts its move a little later than the last: the shape dissolves and re-forms
    float seg = min(floor(uMorph), 1.0);
    float k = smoothstep(0.0, 1.0, clamp((uMorph - seg) * 1.35 - aRand.x * 0.35, 0.0, 1.0));
    vec3 p = seg < 1.0 ? mix(aA, aB, k) : mix(aB, aC, k);
    float travel = sin(k * 3.14159);
    p += flow(p * 0.35 + aRand.z * 6.0, uTime * 0.6) * travel * (1.2 + aRand.y * 2.0);
    p += vec3(sin(uTime * 0.7 + aRand.z * 6.28), cos(uTime * 0.6 + aRand.w * 6.28), sin(uTime * 0.5 + aRand.y * 6.28)) * 0.05;
    vec3 away = p - uMouse;
    float d = length(away);
    float push = exp(-d * d / (uRadius * uRadius)) * uPush;
    p += normalize(away + vec3(0.0001)) * push + vec3(0.0, push * 0.35, 0.0);
    vec4 view = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * view;
    gl_PointSize = (1.4 + aRand.y * 2.4) * uPixelRatio * (26.0 / -view.z) * (1.0 + push * 0.6);
    vec3 cA = mix(uColorA, uAlt, aTag.x), cB = mix(uColorB, uAlt, aTag.y), cC = mix(uColorC, uAlt, aTag.z);
    vec3 base = seg < 1.0 ? mix(cA, cB, k) : mix(cB, cC, k);
    vColor = mix(base, uSpark, step(0.94, aRand.w) * 0.8);
    vAlpha = 0.6 + 0.22 * sin(uTime * (0.8 + aRand.w) + aRand.z * 12.0) + 0.2 * travel;
  }`;
const FRAGMENT = /* glsl */`
  varying vec3 vColor; varying float vAlpha;
  void main() {
    float r = length(gl_PointCoord - 0.5);
    if (r > 0.5) discard;
    gl_FragColor = vec4(vColor, vAlpha * smoothstep(0.5, 0.05, r));
  }`;

export function immersive({ formations, keyframes, palette = ['#FFD66B', '#FFD66B', '#7FA7D8'], alt = '#A9BBD0', spark = '#FFFFFF', shiftRight = 0.2, count, extras } = {}) {
  const canvas = document.getElementById('scene');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
  } catch {
    canvas.remove();   // no WebGL: every page works without the scene
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, small() ? 1.5 : 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x060B14);
  scene.fog = new THREE.FogExp2(0x060B14, 0.016);
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 400);
  const updaters = [];
  const stage = { scene, camera, renderer, onFrame: (fn) => updaters.push(fn) };
  addStadium(stage, { centerZ: -12, length: 64, crowd: small() ? 5000 : 9000 });

  // particles
  const n = count || (small() ? 4500 : 9000);
  const geometry = new THREE.BufferGeometry();
  // a formation is points, or { points, tags } where tag 1 takes the alternative colour
  const resample = (formation) => {
    const { points, tags } = formation instanceof Float32Array ? { points: formation, tags: null } : formation;
    const out = new Float32Array(n * 3), outTags = new Float32Array(n);
    const len = points.length / 3;
    for (let i = 0; i < n; i++) {
      const j = Math.floor(Math.random() * len);
      out.set([points[j * 3], points[j * 3 + 1], points[j * 3 + 2]], i * 3);
      outTags[i] = tags ? tags[j] : 0;
    }
    return { out, outTags };
  };
  const rand = new Float32Array(n * 4).map(() => Math.random());
  const sampled = [0, 1, 2].map((i) => resample(formations[Math.min(i, formations.length - 1)]));
  const [A, B, C] = sampled.map((x) => x.out);
  const tag = new Float32Array(n * 3);
  sampled.forEach((x, k) => x.outTags.forEach((t, i) => { tag[i * 3 + k] = t; }));
  geometry.setAttribute('position', new THREE.BufferAttribute(A.slice(), 3));
  geometry.setAttribute('aA', new THREE.BufferAttribute(A, 3));
  geometry.setAttribute('aB', new THREE.BufferAttribute(B, 3));
  geometry.setAttribute('aC', new THREE.BufferAttribute(C, 3));
  geometry.setAttribute('aRand', new THREE.BufferAttribute(rand, 4));
  geometry.setAttribute('aTag', new THREE.BufferAttribute(tag, 3));
  geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 200);
  const uniforms = {
    uMorph: { value: 0 }, uTime: { value: 0 }, uMouse: { value: new THREE.Vector3(999, 999, 999) }, uPush: { value: 0 }, uRadius: { value: 2.2 },
    uPixelRatio: { value: renderer.getPixelRatio() },
    uColorA: { value: new THREE.Color(palette[0]) }, uColorB: { value: new THREE.Color(palette[1]) }, uColorC: { value: new THREE.Color(palette[2]) },
    uSpark: { value: new THREE.Color(spark) }, uAlt: { value: new THREE.Color(alt) },
  };
  const material = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: FRAGMENT, uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  const points = new THREE.Points(geometry, material);
  scene.add(points);
  if (extras) extras({ scene, THREE });

  // bloom on larger screens
  let composer = null;
  if (!small()) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), 0.6, 0.45, 0.32));
    composer.addPass(new OutputPass());
  }

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false);
    composer?.setSize(w, h);
    camera.aspect = w / h;
    if (!small() && shiftRight) camera.setViewOffset(w, h, -w * shiftRight, 0, w, h); else camera.clearViewOffset();
    camera.updateProjectionMatrix();
    if (reducedMotion) frame(0);
  }

  // scroll: 0..1 over the page, eased; the keyframes turn it into a camera path and a morph
  let target = 0, progress = 0;
  const readScroll = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    target = max > 0 ? window.scrollY / max : 0;
    if (reducedMotion) { progress = target; frame(0); }
  };
  const keys = keyframes.map((k) => ({ ...k, pos: new THREE.Vector3(...k.pos), look: new THREE.Vector3(...k.look) }));
  const pose = (t) => {
    let i = 0;
    while (i < keys.length - 2 && t > keys[i + 1].at) i++;
    const a = keys[i], b = keys[i + 1] || a;
    const u = b === a ? 0 : smooth(Math.min(1, Math.max(0, (t - a.at) / (b.at - a.at))));
    return { pos: a.pos.clone().lerp(b.pos, u), look: a.look.clone().lerp(b.look, u), morph: a.morph + (b.morph - a.morph) * u };
  };

  // pointer: a point on the plane facing the camera through what it looks at; speed adds strength
  const ndc = new THREE.Vector2(9, 9), last = new THREE.Vector2(), raycaster = new THREE.Raycaster(), plane = new THREE.Plane(), hit = new THREE.Vector3();
  let speed = 0, mouse = { x: 0, y: 0 }, mouseEased = { x: 0, y: 0 };
  window.addEventListener('pointermove', (e) => {
    ndc.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
    speed = Math.min(1, speed + last.distanceTo(ndc) * 3);
    last.copy(ndc);
    mouse = { x: e.clientX / window.innerWidth - 0.5, y: e.clientY / window.innerHeight - 0.5 };
  }, { passive: true });
  window.addEventListener('pointerleave', () => ndc.set(9, 9));

  const clock = new THREE.Clock();
  function frame(time) {
    if (!reducedMotion) progress += (target - progress) * 0.07;
    const { pos, look, morph } = pose(progress);
    mouseEased.x += (mouse.x - mouseEased.x) * 0.05;
    mouseEased.y += (mouse.y - mouseEased.y) * 0.05;
    camera.position.copy(pos).add(new THREE.Vector3(mouseEased.x * 1.6, -mouseEased.y * 0.9, 0));
    camera.lookAt(look);
    uniforms.uMorph.value = morph;
    uniforms.uTime.value = time;
    if (!reducedMotion && Math.abs(ndc.x) <= 1) {
      raycaster.setFromCamera(ndc, camera);
      plane.setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()).negate(), look);
      if (raycaster.ray.intersectPlane(plane, hit)) uniforms.uMouse.value.lerp(hit, 0.25);
      uniforms.uPush.value += ((0.9 + speed * 2.6) - uniforms.uPush.value) * 0.12;
    } else uniforms.uPush.value *= 0.92;
    speed *= 0.94;
    updaters.forEach((fn) => fn(time));
    if (composer) composer.render(); else renderer.render(scene, camera);
  }

  window.addEventListener('resize', resize);
  window.addEventListener('scroll', readScroll, { passive: true });
  resize();
  readScroll();
  if (reducedMotion) frame(0);
  else renderer.setAnimationLoop(() => frame(clock.getElapsedTime()));
  return {
    // swap a formation later (for example after data loads or the reader picks another player)
    setFormation(index, formation) {
      const { out, outTags } = resample(formation);
      const attr = geometry.getAttribute(['aA', 'aB', 'aC'][index]);
      attr.array.set(out);
      attr.needsUpdate = true;
      const tags = geometry.getAttribute('aTag');
      outTags.forEach((t, i) => { tags.array[i * 3 + index] = t; });
      tags.needsUpdate = true;
      if (reducedMotion) frame(0);
    },
  };
}

/* ---------- formations ---------- */

// Text drawn to a hidden canvas, every lit pixel a candidate point. width = world units across.
export async function textFormation(text, { center = [0, 3, 0], width = 14, font = 'italic 900 220px "Barlow Condensed"', depth = 0.6 } = {}) {
  try { await document.fonts.load(font); } catch { /* fall back to whatever is loaded */ }
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  ctx.font = font;
  const w = Math.ceil(ctx.measureText(text).width) + 20;
  c.width = w; c.height = 260;
  ctx.font = font; ctx.fillStyle = '#fff'; ctx.textBaseline = 'middle';
  ctx.fillText(text, 10, 135);
  const data = ctx.getImageData(0, 0, c.width, c.height).data;
  const pts = [];
  const scale = width / w;
  for (let y = 0; y < c.height; y += 2) for (let x = 0; x < c.width; x += 2) {
    if (data[(y * c.width + x) * 4 + 3] > 128) pts.push(center[0] + (x - w / 2) * scale, center[1] + (c.height / 2 - y) * scale, center[2] + (Math.random() - 0.5) * depth);
  }
  return new Float32Array(pts.length ? pts : center);
}

// One or more series as glowing bands through space: values mapped to height, time to x and depth.
export function curveFormation(seriesList, { from = [-9, 0, 4], to = [9, 0, -6], height = 6.5, thickness = 0.18, curtain = 0.25 } = {}) {
  const all = seriesList.flatMap((s) => s.values);
  const lo = Math.min(...all), hi = Math.max(...all);
  const pts = [], tags = [];
  seriesList.forEach((s, k) => {
    const offset = (k - (seriesList.length - 1) / 2) * 2.4;
    const per = Math.ceil(60000 / seriesList.length / s.values.length);
    for (let i = 0; i < s.values.length - 1; i++) {
      for (let j = 0; j < per * (s.weight ?? 1); j++) {
        const t = (i + Math.random()) / (s.values.length - 1);
        const v = s.values[i] + (s.values[i + 1] - s.values[i]) * (t * (s.values.length - 1) - i);
        const y = from[1] + ((v - lo) / (hi - lo || 1)) * height;
        const x = from[0] + (to[0] - from[0]) * t, z = from[2] + (to[2] - from[2]) * t + offset;
        const drop = Math.random() < curtain ? Math.random() * (y - from[1] + 1) : 0;
        pts.push(x + (Math.random() - 0.5) * thickness, y - drop + (Math.random() - 0.5) * thickness, z + (Math.random() - 0.5) * thickness);
        tags.push(s.alt ? 1 : 0);
      }
    }
  });
  return { points: new Float32Array(pts), tags: new Float32Array(tags) };
}

// Columns rising or hanging from a zero plane: one per value (a squad's gaps to its club).
export function columnsFormation(values, { center = [0, 2, 0], width = 18, scale = 0.018, radius = 0.16 } = {}) {
  const pts = [], tags = [];
  values.forEach((v, i) => {
    const x = center[0] - width / 2 + (i + 0.5) * (width / values.length);
    const h = v * scale;
    const per = 300 + Math.abs(h) * 260;
    for (let j = 0; j < per; j++) {
      const a = Math.random() * Math.PI * 2, r = radius * Math.sqrt(Math.random());
      pts.push(x + Math.cos(a) * r, center[1] + Math.random() * h, center[2] + Math.sin(a) * r);
      tags.push(v < 0 ? 1 : 0);
    }
  });
  for (let j = 0; j < 2500; j++) {   // the club's line
    pts.push(center[0] + (Math.random() - 0.5) * width * 1.05, center[1], center[2] + (Math.random() - 0.5) * 0.15);
    tags.push(1);
  }
  return { points: new Float32Array(pts), tags: new Float32Array(tags) };
}

// A football: points on a sphere with the classic pentagon pattern denser.
export function sphereFormation({ center = [0, 3, 0], radius = 3.4 } = {}) {
  const pts = [];
  const total = 9000, golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < total; i++) {
    const y = 1 - (i / (total - 1)) * 2, r = Math.sqrt(1 - y * y), a = golden * i;
    const p = [Math.cos(a) * r, y, Math.sin(a) * r];
    const seam = Math.abs(Math.sin(p[0] * 5.2) * Math.sin(p[1] * 5.2) * Math.sin(p[2] * 5.2));
    if (seam < 0.18 || Math.random() < 0.45) pts.push(center[0] + p[0] * radius, center[1] + p[1] * radius, center[2] + p[2] * radius);
  }
  return new Float32Array(pts);
}

// Dust over the pitch and up into the stands: where everything settles at the end of a page.
export function fieldFormation({ centerZ = -12 } = {}) {
  const pts = new Float32Array(30000);
  for (let i = 0; i < pts.length; i += 3) {
    const onPitch = Math.random() < 0.7;
    pts[i] = (Math.random() - 0.5) * (onPitch ? 36 : 70);
    pts[i + 1] = onPitch ? -0.9 + Math.random() * 0.3 : Math.random() * 12;
    pts[i + 2] = centerZ + (Math.random() - 0.5) * (onPitch ? 60 : 90);
  }
  return pts;
}

// A slow spiral galaxy above the centre circle.
export function galaxyFormation({ center = [0, 3, -4], radius = 9, arms = 3 } = {}) {
  const pts = [];
  for (let i = 0; i < 12000; i++) {
    const r = Math.pow(Math.random(), 0.7) * radius;
    const arm = (i % arms) / arms * Math.PI * 2;
    const a = arm + r * 0.55 + (Math.random() - 0.5) * (0.9 - r / radius * 0.5);
    pts.push(center[0] + Math.cos(a) * r, center[1] + (Math.random() - 0.5) * (1.2 - r / radius), center[2] + Math.sin(a) * r);
  }
  return new Float32Array(pts);
}

// Several formations as one, each with its own tag (0 main colour, 1 alternative).
export function mergeFormations(parts) {
  const list = parts.map(({ formation, tag }) => ({ points: formation instanceof Float32Array ? formation : formation.points, tag }));
  const total = list.reduce((s, x) => s + x.points.length, 0);
  const points = new Float32Array(total), tags = new Float32Array(total / 3);
  let o = 0;
  for (const x of list) { points.set(x.points, o); tags.fill(x.tag, o / 3, o / 3 + x.points.length / 3); o += x.points.length; }
  return { points, tags };
}
