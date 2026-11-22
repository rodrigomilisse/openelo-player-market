// The living backdrop: one fixed WebGL canvas behind the page. Scroll flies the camera along a
// path, eased every frame; the pointer adds a small parallax. Glow comes from additive points and
// bloom (larger screens only). Reduced motion gets still frames, redrawn only when something changes.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const small = () => innerWidth <= 860;
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, small() ? 1.5 : 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color();
scene.fog = new THREE.FogExp2(0x000000, 0.02);          // fades the distance into the ground colour: depth for free
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 400);

// Thousands of lights in one draw call. Each point twinkles on its own phase in the shader.
const count = small() ? 4500 : 9000;
const positions = new Float32Array(count * 3), phases = new Float32Array(count);
for (let i = 0; i < count; i++) {
  const r = 6 + Math.random() * 30, a = Math.random() * Math.PI * 2;
  positions.set([Math.cos(a) * r, (Math.random() - 0.3) * 14, -20 + Math.sin(a) * r], i * 3);
  phases[i] = Math.random() * Math.PI * 2;
}
const geometry = new THREE.BufferGeometry();
geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
const uniforms = { uTime: { value: 0 }, uColor: { value: new THREE.Color() }, uPixelRatio: { value: renderer.getPixelRatio() } };
const points = new THREE.Points(geometry, new THREE.ShaderMaterial({
  uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  vertexShader: /* glsl */`
    attribute float aPhase; uniform float uTime; uniform float uPixelRatio; varying float vAlpha;
    void main() {
      vec4 view = modelViewMatrix * vec4(position, 1.0);
      gl_Position = projectionMatrix * view;
      gl_PointSize = 2.2 * uPixelRatio * (30.0 / -view.z);          // nearer points are bigger
      vAlpha = 0.45 + 0.55 * sin(uTime * 1.6 + aPhase);
    }`,
  fragmentShader: /* glsl */`
    uniform vec3 uColor; varying float vAlpha;
    void main() {
      float d = length(gl_PointCoord - 0.5);
      gl_FragColor = vec4(uColor, smoothstep(0.5, 0.0, d) * vAlpha);
    }`,
}));
scene.add(points);

let composer = null, bloom = null;
if (!small()) {
  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.6, 0.45, 0.32));
  composer.addPass(new OutputPass());
}

// Night or day. Day: pale sky, points blended normally (adding light to white shows nothing), no bloom.
function applyTheme() {
  const light = document.documentElement.dataset.theme === 'light';
  scene.background.set(token('--ground'));
  scene.fog.color.set(token('--ground'));
  uniforms.uColor.value.set(token(light ? '--ink' : '--accent'));
  points.material.blending = light ? THREE.NormalBlending : THREE.AdditiveBlending;
  points.material.needsUpdate = true;
  if (bloom) bloom.enabled = !light;
  if (reduced) frame(0);
}
addEventListener('themechange', applyTheme);

// Scroll becomes a 0 to 1 progress; the camera follows a path through the scene, eased each frame.
const path = new THREE.CatmullRomCurve3([
  new THREE.Vector3(0, 6, 34), new THREE.Vector3(10, 3, 12), new THREE.Vector3(-6, 2, -4), new THREE.Vector3(0, 9, -30),
]);
let target = 0, progress = 0, mx = 0, my = 0, px = 0, py = 0;
function readScroll() {
  target = scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight);
  if (reduced) frame(0);
}
addEventListener('scroll', readScroll, { passive: true });
addEventListener('pointermove', (e) => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; }, { passive: true });

function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  composer?.setSize(w, h);
  camera.aspect = w / h;
  // Shift the projection so the scene's centre sits right of the hero text, not under it.
  if (!small()) camera.setViewOffset(w, h, -w * 0.18, 0, w, h); else camera.clearViewOffset();
  camera.updateProjectionMatrix();
  if (reduced) frame(0);
}
addEventListener('resize', resize);

function frame(time) {
  if (reduced) { progress = target; px = py = 0; }
  else {
    progress += (target - progress) * 0.07;
    px += (mx - px) * 0.05; py += (my - py) * 0.05;
    uniforms.uTime.value = time / 1000;
  }
  const p = path.getPointAt(Math.min(1, Math.max(0, progress)));
  camera.position.set(p.x + px * 2.4, p.y - py * 1.4, p.z);
  camera.lookAt(0, 2, -20);
  if (composer) composer.render(); else renderer.render(scene, camera);
}

readScroll();
resize();
applyTheme();
if (!reduced) renderer.setAnimationLoop(frame);
