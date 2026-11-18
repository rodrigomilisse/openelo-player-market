import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';

export { THREE };

export const COLOR = {
  night: 0x060B14,
  price: 0x5AA9FF,
  priceCore: 0xBFE0FF,
  elo: 0xFFD66B,
  eloCore: 0xFFF3CC,
  ask: 0xFF9A4D,
  grid: 0x1D3A5C,
  gridFaint: 0x10233A,
  pitch: 0x3C5E86
};

export const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function smoothstep(edge0, edge1, x) {
  const t = Math.min(Math.max((x - edge0) / (edge1 - edge0), 0), 1);
  return t * t * (3 - 2 * t);
}

// shiftRight moves the scene's centre right by that fraction of the width, to clear a left-hand panel.
export function createStage(canvas, { shiftRight = 0, fog = 0.022 } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COLOR.night);
  scene.fog = new THREE.FogExp2(COLOR.night, fog);
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 400);
  const updaters = [];
  let draw = () => {};

  function resize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    if (width > 860 && shiftRight) camera.setViewOffset(width, height, -width * shiftRight, 0, width, height);
    else camera.clearViewOffset();
    camera.updateProjectionMatrix();
    if (reducedMotion) renderOnce();
  }

  function renderOnce() {
    draw(0);
    renderer.render(scene, camera);
  }

  function start(placeCamera) {
    draw = placeCamera;
    if (reducedMotion) {
      renderOnce();
      return;
    }
    const clock = new THREE.Clock();
    const loop = () => {
      const time = clock.getElapsedTime();
      updaters.forEach((update) => update(time));
      draw(time);
      renderer.render(scene, camera);
      requestAnimationFrame(loop);
    };
    loop();
  }

  window.addEventListener('resize', resize);
  resize();
  // With reduced motion there is no loop, so state changes must ask for a frame.
  const refresh = () => { if (reducedMotion) renderOnce(); };
  return { renderer, scene, camera, onFrame: (update) => updaters.push(update), start, refresh };
}

const glowCache = new Map();
export function glowTexture(rgb) {
  if (glowCache.has(rgb)) return glowCache.get(rgb);
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.25, `rgba(${rgb},0.5)`);
  gradient.addColorStop(1, 'rgba(0,0,0,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  glowCache.set(rgb, texture);
  return texture;
}

export function glowSprite(rgb, size) {
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(rgb), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  sprite.scale.set(size, size, 1);
  return sprite;
}

// Call after document.fonts.ready, or the canvas draws in a fallback face.
export function textSprite(text, { color = '#E4ECF5', font = '700 56px "Barlow Condensed"', height = 0.9 } = {}) {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  context.font = font;
  const width = Math.ceil(context.measureText(text).width) + 16;
  canvas.width = width;
  canvas.height = 80;
  context.font = font;
  context.fillStyle = color;
  context.textBaseline = 'middle';
  context.fillText(text, 8, 42);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true, depthWrite: false }));
  sprite.scale.set(height * width / 80, height, 1);
  return sprite;
}

function fadeable(material, opacity) {
  material.transparent = true;
  material.opacity = opacity;
  material.userData.baseOpacity = opacity;
  return material;
}

// A series drawn as a glowing tube with a faint curtain down to the ground.
export function addRibbon(scene, values, { toY, step = 2, x = 0, wiggle = 1.4, color = COLOR.price, core = COLOR.priceCore, radius = 0.06, curtain = true, ground = -1 }) {
  const group = new THREE.Group();
  const points = values.map((value, i) => new THREE.Vector3(x + Math.sin(i * 0.35) * wiggle, toY(value), -i * step));
  const curve = new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0.4);
  group.add(new THREE.Mesh(new THREE.TubeGeometry(curve, values.length * 14, radius, 10, false), fadeable(new THREE.MeshBasicMaterial({ color: core }), 1)));
  group.add(new THREE.Mesh(new THREE.TubeGeometry(curve, values.length * 14, radius * 4.6, 12, false),
    fadeable(new THREE.MeshBasicMaterial({ color, blending: THREE.AdditiveBlending, depthWrite: false }), 0.16)));
  if (curtain) {
    const along = curve.getPoints(values.length * 10);
    const positions = [];
    for (let i = 0; i < along.length - 1; i++) {
      const a = along[i];
      const b = along[i + 1];
      positions.push(a.x, a.y, a.z, b.x, b.y, b.z, a.x, ground, a.z, b.x, b.y, b.z, b.x, ground, b.z, a.x, ground, a.z);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    group.add(new THREE.Mesh(geometry, fadeable(new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }), 0.06)));
  }
  scene.add(group);
  return {
    curve,
    points,
    group,
    setOpacity(alpha) {
      group.traverse((child) => {
        if (child.material) child.material.opacity = child.material.userData.baseOpacity * alpha;
        if (child.isSprite) child.visible = alpha > 0.02;
      });
    }
  };
}

export function addPillar(scene, top, rgb, { ground = -1, color } = {}) {
  const height = top.y - ground;
  const group = new THREE.Group();
  const pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, height, 8),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending }));
  pillar.position.set(top.x, ground + height / 2, top.z);
  const halo = glowSprite(rgb, 2.2);
  halo.position.copy(top);
  group.add(pillar, halo);
  scene.add(group);
  return group;
}

export function addDashedLine(scene, from, to, color, { dash = 0.6, gap = 0.4 } = {}) {
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([from, to]), new THREE.LineDashedMaterial({ color, dashSize: dash, gapSize: gap }));
  line.computeLineDistances();
  scene.add(line);
  return line;
}

// Floodlit stands of twinkling lights around a pitch grid.
export function addStadium(stage, { centerZ = -30, length = 64, crowd = 9000 } = {}) {
  const { scene } = stage;
  const grid = new THREE.GridHelper(140, 70, COLOR.grid, COLOR.gridFaint);
  grid.position.set(0, -1, centerZ);
  scene.add(grid);

  const halfLength = length / 2;
  scene.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-18, -0.98, centerZ + halfLength), new THREE.Vector3(18, -0.98, centerZ + halfLength),
    new THREE.Vector3(18, -0.98, centerZ - halfLength), new THREE.Vector3(-18, -0.98, centerZ - halfLength)
  ]), new THREE.LineBasicMaterial({ color: COLOR.pitch, transparent: true, opacity: 0.5 })));

  [[-28, 16, centerZ + halfLength + 4], [28, 16, centerZ + halfLength + 4], [-28, 16, centerZ - halfLength - 4], [28, 16, centerZ - halfLength - 4]].forEach(([x, y, z]) => {
    const flood = glowSprite('255,240,210', 14);
    flood.position.set(x, y, z);
    scene.add(flood);
  });

  const positions = new Float32Array(crowd * 3);
  const colors = new Float32Array(crowd * 3);
  const phases = new Float32Array(crowd);
  const palette = [0xFFF1D6, 0xBFD6F2, COLOR.price, COLOR.ask, 0x8A2A45].map((hex) => new THREE.Color(hex));
  const depthStretch = Math.max(1.2, length / 40);
  for (let i = 0; i < crowd; i++) {
    const angle = Math.random() * Math.PI * 2;
    const tier = Math.random();
    const radius = 26 + tier * 14;
    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = -1 + tier * 13 + Math.random() * 0.4;
    positions[i * 3 + 2] = centerZ + Math.sin(angle) * radius * depthStretch;
    const roll = Math.random();
    const pick = palette[roll < 0.55 ? 0 : roll < 0.8 ? 1 : roll < 0.9 ? 2 : roll < 0.96 ? 3 : 4];
    colors.set([pick.r, pick.g, pick.b], i * 3);
    phases[i] = Math.random() * Math.PI * 2;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('phase', new THREE.BufferAttribute(phases, 1));
  const material = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, pixelRatio: { value: stage.renderer.getPixelRatio() } },
    vertexShader: `
      attribute float phase; attribute vec3 color; uniform float time; uniform float pixelRatio;
      varying vec3 vColor; varying float vAlpha;
      void main() {
        vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
        vColor = color;
        vAlpha = 0.35 + 0.65 * (0.5 + 0.5 * sin(time * (0.6 + fract(phase) * 1.6) + phase * 7.0));
        gl_PointSize = (2.2 + fract(phase * 3.0) * 2.0) * pixelRatio * (40.0 / -viewPosition.z);
        gl_Position = projectionMatrix * viewPosition;
      }`,
    fragmentShader: `
      varying vec3 vColor; varying float vAlpha;
      void main() {
        float distanceFromCentre = length(gl_PointCoord - 0.5);
        if (distanceFromCentre > 0.5) discard;
        gl_FragColor = vec4(vColor, vAlpha * smoothstep(0.5, 0.0, distanceFromCentre));
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending
  });
  scene.add(new THREE.Points(geometry, material));

  const dustCount = 1500;
  const dustPositions = new Float32Array(dustCount * 3);
  for (let i = 0; i < dustCount; i++) {
    dustPositions[i * 3] = (Math.random() - 0.5) * 44;
    dustPositions[i * 3 + 1] = Math.random() * 14 - 1;
    dustPositions[i * 3 + 2] = centerZ + (Math.random() - 0.5) * (length + 16);
  }
  const dustGeometry = new THREE.BufferGeometry();
  dustGeometry.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));
  const dust = new THREE.Points(dustGeometry, new THREE.PointsMaterial({ color: 0xCFE3FF, size: 0.05, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(dust);

  stage.onFrame((time) => {
    material.uniforms.time.value = time;
    dust.rotation.y = time * 0.01;
  });
}

export function scrollTracker(ease = 0.07) {
  let target = 0;
  let value = 0;
  const read = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    target = max > 0 ? window.scrollY / max : 0;
  };
  window.addEventListener('scroll', read, { passive: true });
  read();
  return { step: () => (value += (target - value) * ease) };
}

export function pointerTracker(ease = 0.05) {
  const target = { x: 0, y: 0 };
  const value = { x: 0, y: 0 };
  window.addEventListener('pointermove', (event) => {
    target.x = event.clientX / window.innerWidth - 0.5;
    target.y = event.clientY / window.innerHeight - 0.5;
  });
  return {
    step() {
      value.x += (target.x - value.x) * ease;
      value.y += (target.y - value.y) * ease;
      return value;
    }
  };
}
