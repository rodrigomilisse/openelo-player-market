// The trading view's 3D scene: the week's price and rating with trend lines, meeting the order book as a depth wall.
import { THREE, COLOR, createStage, addStadium, addRibbon, addPillar, addDashedLine, textSprite, pointerTracker, reducedMotion } from './stadium.js';
import { week, book, MINT_PRICE } from './sample-data.js';
import { fitTrend } from './analysis.js';

const STEP = 2;
const last = week.price.length - 1;
const nowZ = -last * STEP;
const priceY = (price) => (price - 3.0) * 12;
const eloY = (rating) => (rating - 1812) / 32 * 6.5;

export const STEPS_PER_DAY = last / 7;

// Solid over the data, dashed a few steps beyond now.
function addTrend(scene, values, toY, x, color) {
  const n = values.length;
  const { mean, middle, slope } = fitTrend(values);
  const at = (i) => new THREE.Vector3(x, toY(mean + slope * (i - middle)), -i * STEP);
  scene.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.LineCurve3(at(0), at(n - 1)), 1, 0.035, 8, false),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.75, blending: THREE.AdditiveBlending, depthWrite: false })));
  addDashedLine(scene, at(n - 1), at(n + 5), color, { dash: 0.5, gap: 0.35 });
}

// shiftRight and distance let each layout frame the week in its own free space.
export async function buildTradeScene(canvas, { shiftRight = 0, distance = 34 } = {}) {
  const stage = createStage(canvas, { fog: 0.011, shiftRight });
  const { scene } = stage;
  addStadium(stage, { centerZ: nowZ / 2 - 6, length: -nowZ + 24, crowd: 7000 });
  addRibbon(scene, week.price, { toY: priceY, step: STEP, wiggle: 0.6, radius: 0.1 });
  const elo = addRibbon(scene, week.elo, { toY: eloY, step: STEP, x: -4, wiggle: 0.6, color: COLOR.elo, core: COLOR.eloCore, curtain: false, radius: 0.08 });
  addPillar(scene, elo.points[week.matchIndex], '255,214,107', { color: COLOR.elo });
  addTrend(scene, week.price, priceY, 0, COLOR.price);
  addTrend(scene, week.elo, eloY, -4, COLOR.elo);

  const nowPlane = new THREE.Mesh(new THREE.PlaneGeometry(10, 9),
    new THREE.MeshBasicMaterial({ color: 0xE4ECF5, transparent: true, opacity: 0.04, side: THREE.DoubleSide, depthWrite: false }));
  nowPlane.position.set(-1, 3.5, nowZ - 1);
  scene.add(nowPlane);

  const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(24, -nowZ + 20),
    new THREE.MeshBasicMaterial({ color: COLOR.ask, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false }));
  ceiling.rotation.x = -Math.PI / 2;
  ceiling.position.set(0, priceY(MINT_PRICE), nowZ / 2 - 4);
  scene.add(ceiling);
  addDashedLine(scene, new THREE.Vector3(1.5, priceY(MINT_PRICE), 4), new THREE.Vector3(1.5, priceY(MINT_PRICE), nowZ - 18), COLOR.ask);

  const bars = new Map();
  const addBar = ([price, shares], color) => {
    const length = shares / 24;
    const bar = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.26, length),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
    bar.position.set(0.5, priceY(Number(price)), nowZ - 2 - length / 2);
    scene.add(bar);
    bars.set(price, bar);
  };
  book.asks.forEach((level) => addBar(level, COLOR.ask));
  book.bids.forEach((level) => addBar(level, COLOR.price));

  await document.fonts.ready;
  ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'].forEach((day, d) => {
    const label = textSprite(day, { color: '#93A6BC', height: 0.7 });
    label.position.set(2.5, -0.5, -Math.round(d * last / 6) * STEP);
    scene.add(label);
  });
  const nowLabel = textSprite('NOW', { height: 0.8 });
  nowLabel.position.set(-1, 8.6, nowZ - 1);
  scene.add(nowLabel);

  let highlighted = null;
  const pointer = pointerTracker();
  // Side-on: the week runs left to right, the order book waiting at the right.
  const lookAt = new THREE.Vector3(-1, 3.8, nowZ * 0.55 - 3);
  stage.start((time) => {
    const mouse = pointer.step();
    bars.forEach((bar, price) => {
      const want = highlighted === null ? 0.5 : highlighted === price ? 1 : 0.18;
      bar.material.opacity += (want - bar.material.opacity) * (reducedMotion ? 1 : 0.15);
    });
    const orbit = reducedMotion ? 0 : Math.sin(time * 0.1) * 0.06;
    const angle = Math.PI / 2 - 0.22 + orbit + mouse.x * 0.2;
    stage.camera.position.set(lookAt.x + Math.sin(angle) * distance, lookAt.y + 5 - mouse.y * 3, lookAt.z + Math.cos(angle) * distance);
    stage.camera.lookAt(lookAt);
  });

  return {
    // Light up one book level (a price string such as '3.46'), or pass null to show all.
    highlight(price) {
      highlighted = price;
      stage.refresh();
    }
  };
}
