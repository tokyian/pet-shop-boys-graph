/*
 * bake_layout.js — один раз «запекает» раскладку графа для телефона.
 *
 * Запускает ту же физику vis-network с теми же настройками, что в index.html
 * (forceAtlas2Based, 3000 итераций, gravitationalConstant -270, изогнутые
 * dynamic-связи), но без браузера, и сохраняет в layout.json:
 *   nodes — координаты слов,
 *   via   — положение «изгиба» каждой связи.
 * build_mobile.py вшивает их в mobile.html: телефон открывает граф уже
 * таким же, как на ПК, и физику при запуске не считает.
 *
 * Запуск (один раз, пока данные в index.html не меняются; ~1.5 минуты):
 *     npm install jsdom@24 vis-network@9.1.2
 *     node bake_layout.js
 */
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const nodes = JSON.parse(html.match(/nodes = new vis\.DataSet\((\[[\s\S]*?\n\])\);/)[1]);
const edges = JSON.parse(html.match(/edges = new vis\.DataSet\((\[[\s\S]*?\])\);\s*\n/)[1]);
edges.forEach((e, i) => { e.id = "e" + i; });          // стабильные id связей
const visSrc = fs.readFileSync(
  require.resolve("vis-network/standalone/umd/vis-network.min.js"), "utf8");

// стартовые позиции (воспроизводимо). В браузере их даёт vis (improvedLayout),
// без браузера задаём сами.
let seed = 12345;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
nodes.forEach((n) => { n.x = Math.round((rnd() - 0.5) * 6000); n.y = Math.round((rnd() - 0.5) * 6000); });

// canvas без браузера: нужна только ширина текста. Средняя ширина буквы
// шрифта Awke Bold ≈ 0.63 кегля (измерено по самому шрифту).
function makeCtx() {
  const st = { font: "10px sans-serif", canvas: { width: 1440, height: 900 } };
  st.measureText = function (s) {
    const px = parseFloat((/(\d+(?:\.\d+)?)px/.exec(st.font) || [0, 10])[1]);
    return { width: String(s).length * px * 0.63, actualBoundingBoxAscent: px * 0.8,
             actualBoundingBoxDescent: px * 0.2, fontBoundingBoxAscent: px * 0.9,
             fontBoundingBoxDescent: px * 0.2 };
  };
  return new Proxy(st, {
    get: (t, k) => (k in t ? t[k] : () => {}),
    set: (t, k, v) => { t[k] = v; return true; },
  });
}

const dom = new JSDOM('<div id="mynetwork"></div>', {
  runScripts: "outside-only", pretendToBeVisual: true, virtualConsole: new VirtualConsole(),
  beforeParse(w) {
    w.HTMLCanvasElement.prototype.getContext = function () { return makeCtx(); };
    Object.defineProperty(w.HTMLElement.prototype, "clientWidth", { get() { return 1440; } });
    Object.defineProperty(w.HTMLElement.prototype, "clientHeight", { get() { return 900; } });
  },
});
const w = dom.window;
w.eval(visSrc);

const net = new w.vis.Network(
  w.document.getElementById("mynetwork"),
  { nodes: new w.vis.DataSet(nodes), edges: new w.vis.DataSet(edges) },
  {
    nodes: { scaling: { label: { enabled: false } } },
    layout: { improvedLayout: false },
    edges: { smooth: { enabled: true, type: "dynamic" } },
    physics: {
      enabled: true, solver: "forceAtlas2Based",
      // как в index.html: после старта стабилизации гравитация = -270
      forceAtlas2Based: { theta: 0.5, gravitationalConstant: -270, centralGravity: 0.003,
                          springLength: 350, springConstant: 0.04, damping: 0.5, avoidOverlap: 0.8 },
      stabilization: { enabled: false },
    },
  }
);

const ITER = 3000, t0 = Date.now();
for (let i = 0; i < ITER; i++) {
  net.physics.physicsTick();
  if (i % 500 === 0) console.log("итерация", i, ((Date.now() - t0) / 1000).toFixed(0) + " с");
  if (net.physics.stabilized) { console.log("стабилизировалось на", i); break; }
}

const out = { nodes: {}, via: {} };
for (const n of nodes) {
  const b = net.body.nodes[n.id];
  if (!isFinite(b.x) || !isFinite(b.y)) throw new Error("NaN в координатах узла " + n.id);
  out.nodes[n.id] = [Math.round(b.x), Math.round(b.y)];
}
for (const e of edges) {
  const via = net.body.edges[e.id] && net.body.edges[e.id].edgeType && net.body.edges[e.id].edgeType.via;
  if (via && isFinite(via.x) && isFinite(via.y)) out.via[e.id] = [Math.round(via.x), Math.round(via.y)];
}
fs.writeFileSync(path.join(__dirname, "layout.json"), JSON.stringify(out));
console.log(`layout.json: ${Object.keys(out.nodes).length} узлов, ${Object.keys(out.via).length} изгибов за ${((Date.now() - t0) / 1000).toFixed(0)} с`);
process.exit(0);
