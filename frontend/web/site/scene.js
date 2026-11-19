// The site's living backdrop: the night stadium, with thousands of particles that assemble into each
// page's data, morph as the page scrolls, and scatter when the pointer swipes through them, drifting
// back over a few seconds. Every page has its own spot in the stadium; scrolling past the end of a
// page flies the camera to the next page's spot and opens it there.
//
//   immersive({ formations: [A, B, C], keyframes: [{ at, morph, pos, look }], palette, alt, next, shiftRight })
//
// A formation is a Float32Array of xyz points, or { points, tags } where tag 1 takes the `alt` colour.
// Positions in formations and keyframes are relative to the page's spot (STATIONS).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { addStadium } from '../design/stadium.js';
import { go } from './router.js';

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const small = () => window.innerWidth <= 860;
const smooth = (t) => t * t * (3 - 2 * t);
const clamp01 = (t) => Math.min(1, Math.max(0, t));

// Where each page stands in the stadium (the pitch runs along z, centre circle near z = -12).
export const STATIONS = {
  'index.html': [0, 0, -12], 'rankings.html': [0, 0, -40], 'leagues.html': [22, 0, -18],
  'compare.html': [0, 0, 16], 'how.html': [-22, 0, -18], 'player.html': [10, 0, 2], 'club.html': [-10, 0, 2],
};
const pageOf = (href) => (new URL(href, location.href).pathname.split('/').pop() || 'index.html');
// The pose every page is approached from: in front of its spot, looking at it.
const arrivalPose = (station) => ({ pos: [station[0], station[1] + 4.5, station[2] + 24], look: [station[0], station[1] + 3, station[2]] });

const VERTEX = /* glsl */`
  attribute vec4 aRand; attribute vec3 aTag; attribute vec2 aDyn;
  uniform float uSeg; uniform float uTime; uniform float uPixelRatio;
  uniform vec3 uColorA; uniform vec3 uColorB; uniform vec3 uColorC; uniform vec3 uSpark; uniform vec3 uAlt;
  varying vec3 vColor; varying float vAlpha;
  void main() {
    vec4 view = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * view;
    float speed = clamp(aDyn.y, 0.0, 1.0);
    gl_PointSize = (1.4 + aRand.y * 2.4) * uPixelRatio * (26.0 / -view.z) * (1.0 + speed * 0.9);
    vec3 cA = mix(uColorA, uAlt, aTag.x), cB = mix(uColorB, uAlt, aTag.y), cC = mix(uColorC, uAlt, aTag.z);
    vec3 base = uSeg < 1.0 ? mix(cA, cB, aDyn.x) : mix(cB, cC, aDyn.x);
    vColor = mix(base, uSpark, max(step(0.94, aRand.w) * 0.8, speed * 0.55));
    vAlpha = 0.6 + 0.22 * sin(uTime * (0.8 + aRand.w) + aRand.z * 12.0) + 0.3 * speed;
  }`;
const FRAGMENT = /* glsl */`
  varying vec3 vColor; varying float vAlpha;
  void main() {
    float r = length(gl_PointCoord - 0.5);
    if (r > 0.5) discard;
    gl_FragColor = vec4(vColor, vAlpha * smoothstep(0.5, 0.05, r));
  }`;

// Spring back to the shape, slowly: a swipe scatters particles and they drift home over a few seconds.
const STIFFNESS = 2.4, DAMPING = 2.3, SWIPE = 0.14, PUSH = 3.2, RADIUS = 1.9, MAX_SPEED = 9;

let world = null;   // one scene for the whole visit: pages re-target it instead of rebuilding it

export function immersive(options) {
  if (!world) world = createWorld(options);
  if (world) world.apply(options, world.started);
  return world;
}

function createWorld({ count } = {}) {
  const canvas = document.getElementById('scene');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
  } catch {
    canvas?.remove();   // no WebGL: every page works without the scene
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, small() ? 1.5 : 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x060B14);
  scene.fog = new THREE.FogExp2(0x060B14, 0.014);
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 400);
  const updaters = [];
  addStadium({ scene, camera, renderer, onFrame: (fn) => updaters.push(fn) }, { centerZ: -12, length: 64, crowd: small() ? 5000 : 9000 });
  scene.traverse((o) => { if (o.isSprite) o.material.opacity *= 0.5; });   // softer floodlights: they bloom through the glass

  const n = count || (small() ? 4500 : 9000);
  const home = [new Float32Array(n * 3), new Float32Array(n * 3), new Float32Array(n * 3)];
  const tag = new Float32Array(n * 3);
  const rand = new Float32Array(n * 4).map(() => Math.random());
  const position = new Float32Array(n * 3);
  const offset = new Float32Array(n * 3), velocity = new Float32Array(n * 3), dyn = new Float32Array(n * 2);
  const geometry = new THREE.BufferGeometry();
  const positionAttr = new THREE.BufferAttribute(position, 3).setUsage(THREE.DynamicDrawUsage);
  const dynAttr = new THREE.BufferAttribute(dyn, 2).setUsage(THREE.DynamicDrawUsage);
  const tagAttr = new THREE.BufferAttribute(tag, 3);
  geometry.setAttribute('position', positionAttr);
  geometry.setAttribute('aRand', new THREE.BufferAttribute(rand, 4));
  geometry.setAttribute('aTag', tagAttr);
  geometry.setAttribute('aDyn', dynAttr);
  geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 400);
  const uniforms = {
    uSeg: { value: 0 }, uTime: { value: 0 }, uPixelRatio: { value: renderer.getPixelRatio() },
    uColorA: { value: new THREE.Color() }, uColorB: { value: new THREE.Color() }, uColorC: { value: new THREE.Color() },
    uSpark: { value: new THREE.Color() }, uAlt: { value: new THREE.Color() },
  };
  scene.add(new THREE.Points(geometry, new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: FRAGMENT, uniforms,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));

  let composer = null;
  if (!small()) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), 0.6, 0.45, 0.32));
    composer.addPass(new OutputPass());
  }

  // what the current page sets
  let station = [0, 0, 0], shiftRight = 0.2, keys = [], next = null;
  let target = 0, progress = 0, lastShift = null;
  let arrival = null, boostStart = -1e9;
  const currentLook = new THREE.Vector3();

  const resample = (formation, into, tagIndex) => {
    const { points, tags } = formation instanceof Float32Array ? { points: formation, tags: null } : formation;
    const len = points.length / 3;
    for (let i = 0; i < n; i++) {
      const j = Math.floor(Math.random() * len);
      into[i * 3] = points[j * 3] + station[0]; into[i * 3 + 1] = points[j * 3 + 1] + station[1]; into[i * 3 + 2] = points[j * 3 + 2] + station[2];
      tag[i * 3 + tagIndex] = tags ? tags[j] : 0;
    }
    tagAttr.needsUpdate = true;
  };
  const shift = (v) => new THREE.Vector3(v[0] + station[0], v[1] + station[1], v[2] + station[2]);
  // `at` is a scroll fraction, or a selector: the moment that element's middle reaches the screen's middle
  const resolveKeys = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    for (const k of keys) {
      if (!k.anchor) continue;
      const el = document.querySelector(k.anchor);
      if (!el || max <= 0) continue;
      const box = el.getBoundingClientRect();
      k.at = clamp01((box.top + window.scrollY + box.height / 2 - window.innerHeight / 2) / max);
    }
    keys.sort((a, b) => a.at - b.at);
  };
  const readScroll = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    target = max > 0 ? window.scrollY / max : 0;
    if (reducedMotion) { progress = target; frame(0, 0); }
  };
  const pose = (t) => {
    let i = 0;
    while (i < keys.length - 2 && t > keys[i + 1].at) i++;
    const a = keys[i], b = keys[i + 1] || a;
    const u = b === a ? 0 : smooth(clamp01((t - a.at) / (b.at - a.at)));
    return { pos: a.pos.clone().lerp(b.pos, u), look: a.look.clone().lerp(b.look, u), morph: a.morph + (b.morph - a.morph) * u, shift: a.shift + (b.shift - a.shift) * u };
  };

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false);
    composer?.setSize(w, h);
    camera.aspect = w / h;
    lastShift = null;   // the frame sets the view offset
    if (reducedMotion) frame(0, 0);
  }

  // pointer: a ray from the camera; swipe velocity measured on the plane through what the camera looks at
  const ndc = new THREE.Vector2(9, 9), raycaster = new THREE.Raycaster(), plane = new THREE.Plane();
  const hit = new THREE.Vector3(), lastHit = new THREE.Vector3(), swipe = new THREE.Vector3();
  let hasHit = false, mouse = { x: 0, y: 0 };
  const mouseEased = { x: 0, y: 0 };
  window.addEventListener('pointermove', (e) => {
    ndc.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
    mouse = { x: e.clientX / window.innerWidth - 0.5, y: e.clientY / window.innerHeight - 0.5 };
  }, { passive: true });
  document.addEventListener('pointerleave', () => { ndc.set(9, 9); hasHit = false; });

  // the tour: keep scrolling at the bottom of a page to fly to the next page's spot
  const tour = createTour((href) => go(href));

  const tmp = new THREE.Vector3(), rel = new THREE.Vector3();
  const clock = new THREE.Clock();
  function frame(time, dt) {
    if (!keys.length) return;
    if (!reducedMotion) progress += (target - progress) * Math.min(1, dt * 4.2);
    const p = pose(progress);
    let pos = p.pos, look = p.look;
    if (arrival) {   // flying in from the last page's viewpoint, in an arc
      const t = Math.min(1, (performance.now() - arrival.start) / arrival.duration);   // wall-clock: the same on slow devices
      const u = smooth(t);
      pos = arrival.pos.clone().lerp(pos, u).add(tmp.set(0, Math.sin(u * Math.PI) * arrival.arc, 0));
      look = arrival.look.clone().lerp(look, u);
      camera.fov = 50 + Math.sin(u * Math.PI) * arrival.swell;
      lastShift = null;
      if (t >= 1) { arrival = null; camera.fov = 50; }
    }
    const pull = next && !reducedMotion ? tour.pull() : 0;   // a preview of the flight while the reader keeps scrolling
    if (pull) {
      const a = arrivalPose(STATIONS[pageOf(next.href)] || station);
      pos = pos.clone().lerp(new THREE.Vector3(...a.pos), pull * 0.18);
      look = look.clone().lerp(new THREE.Vector3(...a.look), pull * 0.25);
    }
    const sh = small() ? 0 : p.shift;   // the scene sits right of hero text, centred on stages
    if (lastShift === null || Math.abs(sh - lastShift) > 0.0005) {
      const w = window.innerWidth, h = window.innerHeight;
      if (sh) camera.setViewOffset(w, h, -w * sh, 0, w, h); else camera.clearViewOffset();
      camera.updateProjectionMatrix();
      lastShift = sh;
    }
    mouseEased.x += (mouse.x - mouseEased.x) * 0.05;
    mouseEased.y += (mouse.y - mouseEased.y) * 0.05;
    camera.position.copy(pos).add(tmp.set(mouseEased.x * 1.6, -mouseEased.y * 0.9, 0));
    camera.lookAt(look);
    currentLook.copy(look);

    let swiping = false;
    if (!reducedMotion && Math.abs(ndc.x) <= 1 && dt > 0) {
      raycaster.setFromCamera(ndc, camera);
      plane.setFromNormalAndCoplanarPoint(camera.getWorldDirection(tmp).negate(), look);
      if (raycaster.ray.intersectPlane(plane, hit)) {
        if (hasHit) swipe.copy(hit).sub(lastHit).divideScalar(dt).clampLength(0, 30);
        lastHit.copy(hit); hasHit = true; swiping = true;
      }
    }
    if (!swiping) swipe.multiplyScalar(0.8);
    const speed = swipe.length();
    const origin = raycaster.ray.origin, dir = raycaster.ray.direction;
    // after a page change the springs are stiffer and faster, so the particles stream to the new spot
    const boost = Math.max(0, 1 - (performance.now() - boostStart) / 2600);
    const stiff = STIFFNESS + boost * 6, damp = DAMPING + boost * 2.2, maxSpeed = MAX_SPEED + boost * 80;

    const morph = p.morph, seg = Math.min(Math.floor(morph), 1), local = morph - seg;
    const from = seg < 1 ? home[0] : home[1], to = seg < 1 ? home[1] : home[2];
    const t6 = time * 0.6;
    for (let i = 0, i3 = 0; i < n; i++, i3 += 3) {
      const r0 = rand[i * 4], r1 = rand[i * 4 + 1], r2 = rand[i * 4 + 2], r3 = rand[i * 4 + 3];
      const k = smooth(clamp01(local * 1.35 - r0 * 0.35));
      let hx = from[i3] + (to[i3] - from[i3]) * k, hy = from[i3 + 1] + (to[i3 + 1] - from[i3 + 1]) * k, hz = from[i3 + 2] + (to[i3 + 2] - from[i3 + 2]) * k;
      const travel = Math.sin(k * Math.PI);
      if (travel > 0.001) {   // travelling particles swirl instead of moving in straight lines
        const s = travel * (1.2 + r1 * 2), qx = hx * 0.35 + r2 * 6, qy = hy * 0.35 + r2 * 6, qz = hz * 0.35 + r2 * 6;
        hx += (Math.sin(qy * 0.9 + t6) + Math.sin(qz * 0.7 - t6 * 0.8)) * s;
        hy += (Math.sin(qz * 0.8 + t6 * 1.1) + Math.sin(qx * 0.6 + t6)) * s;
        hz += (Math.sin(qx * 0.7 - t6) + Math.sin(qy * 0.5 + t6 * 0.9)) * s;
      }
      hx += Math.sin(time * 0.7 + r2 * 6.28) * 0.05; hy += Math.cos(time * 0.6 + r3 * 6.28) * 0.05; hz += Math.sin(time * 0.5 + r1 * 6.28) * 0.05;
      let ox = offset[i3], oy = offset[i3 + 1], oz = offset[i3 + 2];
      let vx = velocity[i3], vy = velocity[i3 + 1], vz = velocity[i3 + 2];
      if (speed > 0.5 && dt > 0) {
        rel.set(hx + ox - origin.x, hy + oy - origin.y, hz + oz - origin.z);   // distance to the pointer's ray
        const along = rel.dot(dir);
        const px = rel.x - dir.x * along, py = rel.y - dir.y * along, pz = rel.z - dir.z * along;
        const d2 = px * px + py * py + pz * pz;
        if (d2 < RADIUS * RADIUS * 4) {
          const fall = Math.exp(-d2 / (RADIUS * RADIUS)) * Math.min(1, speed / 12);
          const inv = 1 / (Math.sqrt(d2) + 0.001);
          const kick = (0.6 + r1 * 0.8) * fall;
          vx += (swipe.x * SWIPE + px * inv * PUSH) * kick;
          vy += (swipe.y * SWIPE + py * inv * PUSH) * kick;
          vz += (swipe.z * SWIPE + pz * inv * PUSH) * kick;
        }
      }
      const v2 = vx * vx + vy * vy + vz * vz;
      if (v2 > maxSpeed * maxSpeed) { const c = maxSpeed / Math.sqrt(v2); vx *= c; vy *= c; vz *= c; }
      vx += (-stiff * ox - damp * vx) * dt; vy += (-stiff * oy - damp * vy) * dt; vz += (-stiff * oz - damp * vz) * dt;
      ox += vx * dt; oy += vy * dt; oz += vz * dt;
      offset[i3] = ox; offset[i3 + 1] = oy; offset[i3 + 2] = oz;
      velocity[i3] = vx; velocity[i3 + 1] = vy; velocity[i3 + 2] = vz;
      position[i3] = hx + ox; position[i3 + 1] = hy + oy; position[i3 + 2] = hz + oz;
      dyn[i * 2] = k;
      dyn[i * 2 + 1] = Math.min(1, Math.sqrt(vx * vx + vy * vy + vz * vz) / 6);
    }
    positionAttr.needsUpdate = true;
    dynAttr.needsUpdate = true;
    uniforms.uSeg.value = seg;
    uniforms.uTime.value = time;
    updaters.forEach((fn) => fn(time));
    if (composer) composer.render(); else renderer.render(scene, camera);
  }

  window.addEventListener('resize', resize);
  window.addEventListener('scroll', readScroll, { passive: true });
  new ResizeObserver(() => { resolveKeys(); readScroll(); }).observe(document.body);
  resize();

  const api = {
    started: false,
    // point the running scene at a page: its spot, shapes, colours, camera path and next stop
    apply({ formations, keyframes, palette = ['#FFD66B', '#FFD66B', '#7FA7D8'], alt = '#A9BBD0', spark = '#FFFFFF', shiftRight: sr = 0.2, next: nx = null }, transition) {
      station = STATIONS[pageOf(location.href)] || [0, 0, 0];
      shiftRight = sr;
      next = nx;
      [0, 1, 2].forEach((i) => resample(formations[Math.min(i, formations.length - 1)], home[i], i));
      uniforms.uColorA.value.set(palette[0]); uniforms.uColorB.value.set(palette[1]); uniforms.uColorC.value.set(palette[2]);
      uniforms.uSpark.value.set(spark); uniforms.uAlt.value.set(alt);
      keys = keyframes.map((k) => ({ ...k, shift: k.shift ?? shiftRight, anchor: typeof k.at === 'string' ? k.at : null, pos: shift(k.pos), look: shift(k.look) }));
      resolveKeys();
      readScroll();
      progress = target;
      tour.card(next);
      if (transition && !reducedMotion) {
        // fly from where the camera is; particles keep their places and stream to the new shape
        arrival = { pos: camera.position.clone(), look: currentLook.clone(), start: performance.now(), duration: 1700, arc: 5, swell: 12 };
        for (let i = 0; i < n * 3; i++) { offset[i] = position[i] - home[0][i]; velocity[i] = 0; }
        boostStart = performance.now();
      } else if (!transition) {
        position.set(home[0]);
      }
      if (!api.started) {
        api.started = true;
        if (reducedMotion) frame(0, 0);
        else {
          let last = 0;
          renderer.setAnimationLoop(() => {
            const time = clock.getElapsedTime();
            frame(time, Math.min(1 / 30, time - last));
            last = time;
          });
        }
      } else if (reducedMotion) frame(0, 0);
    },
    // swap one shape later (for example after the reader picks another player)
    setFormation(index, formation) {
      resample(formation, home[index], index);
      if (reducedMotion) frame(0, 0);
    },
  };
  return api;
}

/* The next stop: a card at the very bottom of the page. Keep scrolling (wheel or touch) at the bottom
   and its ring fills; full, the camera flies to the next page. Clicking it does the same. */
function createTour(onDepart) {
  const NEED = 900;
  let charge = 0, lastInput = 0, touchY = null, lastPull = performance.now(), current = null, ring = null, el = null;
  const atBottom = () => window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4;
  const feed = (amount) => {
    if (!current || reducedMotion) return;
    charge = Math.min(NEED, charge + amount);
    lastInput = performance.now();
    if (charge >= NEED && !el.classList.contains('is-going')) { el.classList.add('is-going'); onDepart(current.href); }
  };
  window.addEventListener('wheel', (e) => { if (atBottom() && e.deltaY > 0) feed(e.deltaY * (e.deltaMode === 1 ? 33 : 1)); }, { passive: true });
  window.addEventListener('touchstart', (e) => { touchY = e.touches[0].clientY; }, { passive: true });
  window.addEventListener('touchmove', (e) => {
    if (touchY === null || !atBottom()) return;
    const d = touchY - e.touches[0].clientY;
    if (d > 0) { feed(d * 2.2); touchY = e.touches[0].clientY; }
  }, { passive: true });
  return {
    card(next) {
      document.querySelector('.next-stop')?.remove();
      current = next; charge = 0; el = null; ring = null;
      if (!next) return;
      const page = document.querySelector('.page') || document.body;
      el = document.createElement('a');
      el.className = 'next-stop liquid';
      el.href = next.href;
      el.innerHTML = `<svg class="next-ring" viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="19"/><circle class="fill" cx="22" cy="22" r="19" pathLength="1"/></svg>
        <span><small>${reducedMotion ? 'Next stop' : 'Keep scrolling to fly to'}</small><strong>${next.label}</strong></span>`;
      page.append(el);
      ring = el.querySelector('.fill');
    },
    pull() {
      if (!el) return 0;
      const now = performance.now();
      if (now - lastInput > 450 && !el.classList.contains('is-going')) charge *= Math.pow(0.9, (now - lastPull) / 16.7);   // eases back in about a second
      lastPull = now;
      const pull = charge / NEED;
      ring.style.strokeDashoffset = String(1 - pull);
      el.style.setProperty('--pull', pull.toFixed(3));
      return pull;
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

// A football: points on a sphere, denser along the seams.
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

// Dust over the pitch and up into the stands, around this page's spot.
export function fieldFormation() {
  const pts = new Float32Array(30000);
  for (let i = 0; i < pts.length; i += 3) {
    const onPitch = Math.random() < 0.7;
    pts[i] = (Math.random() - 0.5) * (onPitch ? 30 : 56);
    pts[i + 1] = onPitch ? -0.9 + Math.random() * 0.3 : Math.random() * 12;
    pts[i + 2] = (Math.random() - 0.5) * (onPitch ? 40 : 60) - 8;
  }
  return pts;
}

// A slow spiral galaxy above the pitch.
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
