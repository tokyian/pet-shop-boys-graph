"""
build_mobile.py — собирает mobile.html из index.html.

mobile.html выглядит так же, как index.html на ПК: тот же шрифт Awke, цвета,
кегли, видео-фон, легенда, поиск, зум, About и ТА ЖЕ раскладка графа с теми же
изогнутыми связями. Отличия только технические:

  * физика при открытии не считается: раскладку один раз «запекает»
    bake_layout.js (та же физика, что на ПК: forceAtlas2Based, 3000 итераций,
    гравитация -270) и кладёт в layout.json; этот скрипт вшивает её в страницу;
  * панели физики на телефоне нет;
  * canvas ограничен 2x пикселей, узлы не перетаскиваются, связи прячутся
    на время жеста — чтобы не лагало;
  * видео-фон — ровно как в index.html (тот же тег и тот же CSS-фильтр).

Порядок работы:
    node bake_layout.js        # один раз (или когда поменялись данные) -> layout.json
    python3 build_mobile.py    # -> mobile.html
(без layout.json скрипт использует запасную раскладку, но она отличается от ПК)

Нужны: pip install networkx numpy pillow ; npm install jsdom@24 vis-network@9.1.2
"""

import json
import re

import networkx as nx
import numpy as np

SRC = "index.html"
OUT = "mobile.html"

html = open(SRC, encoding="utf-8").read()

# ------------------------------------------------------------------
# 1. Достаём узлы и связи прямо из index.html — данные всегда актуальны
# ------------------------------------------------------------------
m_nodes = re.search(r"nodes = new vis\.DataSet\((\[.*?\n\])\);", html, re.S)
m_edges = re.search(r"edges = new vis\.DataSet\((\[.*?\])\);\s*\n", html, re.S)
nodes = json.loads(m_nodes.group(1))
edges = json.loads(m_edges.group(1))
for _i, _e in enumerate(edges):
    _e["id"] = "e" + str(_i)          # стабильные id связей (как в bake_layout.js)
ids = [n["id"] for n in nodes]
idx = {i: k for k, i in enumerate(ids)}
n = len(nodes)

# ------------------------------------------------------------------
# 2. Раскладка (один раз, вместо физики в браузере)
#    Узлы — это подписи разного кегля, поэтому считаем их как
#    прямоугольники и растаскиваем так, чтобы ничего не налезало.
# ------------------------------------------------------------------
MARGIN = 40            # зазор между подписями, px

# настоящая ширина подписей: шрифт Awke берём из самого index.html
import base64, io
from PIL import ImageFont
_font_b64 = re.search(r"data:font/otf;base64,([A-Za-z0-9+/=]+)", html).group(1)
_font_bytes = base64.b64decode(_font_b64)
_measure = lambda text, px: ImageFont.truetype(io.BytesIO(_font_bytes), 100).getlength(text) * px / 100

size = np.array([nd["font"]["size"] for nd in nodes], float)
W = np.array([_measure(nd["label"], s) + 6 for nd, s in zip(nodes, size)])
H = size * 1.15

G = nx.Graph()
G.add_nodes_from(range(n))
G.add_edges_from((idx[e["from"]], idx[e["to"]]) for e in edges)

import json as _json, os as _os
E = np.array([(idx[e["from"]], idx[e["to"]]) for e in edges])
BAKED = _os.path.exists("layout.json")
VIA = {}
if BAKED:
    _lay = _json.load(open("layout.json", encoding="utf-8"))
    P = np.array([_lay["nodes"][nd["id"]] for nd in nodes], float)
    VIA = _lay.get("via", {})
    left = 0
    print("раскладка: layout.json (как на ПК)")
else:
    print("ВНИМАНИЕ: layout.json не найден — запасная раскладка, она отличается от ПК. Запустите: node bake_layout.js")
if not BAKED:
    rng = np.random.default_rng(7)
    start = nx.spring_layout(G, k=0.3, iterations=300, seed=7)
    P = np.array([start[i] for i in range(n)])

    # стартовый размер — из реальной площади подписей (заполнение ~15%),
    # иначе длинные подписи не удаётся растащить без налезаний
    _area = float((W * H).sum())
    _side = (_area / 0.15) ** 0.5
    P = (P - P.mean(0)) / np.abs(P).max() * (_side / 2)
    print(f"суммарная площадь подписей: {_area/1e6:.0f} М px², стартовая сторона: {int(_side)} px")

    E = np.array([(idx[e["from"]], idx[e["to"]]) for e in edges])
    _order = np.random.default_rng(3)


    def separate(P):
        """Растаскивает налезающие подписи ПО ОДНОЙ ПАРЕ за раз:
        при одновременном расталкивании зажатые между соседями подписи
        стоят на месте, а так расталкивание сходится до нуля налезаний.
        Возвращает число пар, которые налезали друг на друга."""
        dx = P[:, 0][:, None] - P[:, 0][None, :]
        dy = P[:, 1][:, None] - P[:, 1][None, :]
        ox = (W[:, None] + W[None, :]) / 2 + MARGIN - np.abs(dx)
        oy = (H[:, None] + H[None, :]) / 2 + MARGIN - np.abs(dy)
        hit = (ox > 0) & (oy > 0)
        np.fill_diagonal(hit, False)
        ii, jj = np.where(np.triu(hit))
        for k in _order.permutation(len(ii)):
            i, j = ii[k], jj[k]
            ddx, ddy = P[i, 0] - P[j, 0], P[i, 1] - P[j, 1]
            ox_ = (W[i] + W[j]) / 2 + MARGIN - abs(ddx)
            oy_ = (H[i] + H[j]) / 2 + MARGIN - abs(ddy)
            if ox_ <= 0 or oy_ <= 0:
                continue
            if ox_ < oy_:
                s = 1.0 if ddx >= 0 else -1.0
                P[i, 0] += s * (ox_ / 2 + 1)
                P[j, 0] -= s * (ox_ / 2 + 1)
            else:
                s = 1.0 if ddy >= 0 else -1.0
                P[i, 1] += s * (oy_ / 2 + 1)
                P[j, 1] -= s * (oy_ / 2 + 1)
        return len(ii)


    for it in range(250):
        # слабое притяжение вдоль связей, чтобы кластеры держались вместе
        d = P[E[:, 1]] - P[E[:, 0]]
        P[E[:, 0]] += d * 0.004
        P[E[:, 1]] -= d * 0.004
        separate(P)

    left = -1
    for _ in range(2500):        # финальная чистка без притяжения
        left = separate(P)
        if left == 0:
            break

for nd, (x, y) in zip(nodes, P):
    nd["x"] = int(round(x))
    nd["y"] = int(round(y))

_el = np.hypot(*(P[E[:, 0]] - P[E[:, 1]]).T)
SPRING = 350 if BAKED else int(np.median(_el))
print(f"узлов: {n}, связей: {len(edges)}, налезаний осталось: {left}, springLength для ползунка: {SPRING}")
print(f"размер раскладки: {int(np.ptp(P[:,0]))} x {int(np.ptp(P[:,1]))} px")

# ------------------------------------------------------------------
# 3. Собираем mobile.html из index.html
# ------------------------------------------------------------------

# 3a0. Если в index.html есть скрипт-перенаправление телефонов на mobile.html,
#      в мобильную версию его копировать нельзя (она бы перенаправляла сама на себя)
html = re.sub(r"<script>\s*/\* Телефоны сразу получают.*?</script>\s*", "", html, count=1, flags=re.S)

# 3a. В исходнике внутри <script src=...> лежит лишний inline-код — убираем
html = re.sub(
    r'(<script src="https://cdnjs[^>]*vis-network\.min\.js"[^>]*>)(.*?)(</script>)',
    r"\1\3", html, count=1, flags=re.S)

# 3a2. В index.html нет <meta viewport> — без него телефон рисует страницу
#      как уменьшенный десктоп (980px). Для мобильной версии он обязателен.
html = html.replace(
    '<meta charset="utf-8">',
    '<meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1, '
    'maximum-scale=1, user-scalable=no, viewport-fit=cover">\n  <title>Pet Shop Boys: Literary References</title>', 1)

# 3b. Мобильный CSS — добавляется в конец существующего <style>
MOBILE_CSS = """
    /* ===== MOBILE (build_mobile.py): только функциональное, внешний вид — как на ПК ===== */
    html, body { overflow: hidden; overscroll-behavior: none; }
    #wrap { height: 100vh; height: 100dvh; }
    #mynetwork, #mynetwork canvas { touch-action: none !important; }  /* все жесты — графу */
    #mynetwork { position: relative; background-color: transparent; }  /* видео просвечивает сквозь граф */
    #config-panel { display: none; }                                   /* панели физики на телефоне нет */
    #search-box { width: min(220px, calc(100vw - 215px)); }            /* чтобы не наезжать на легенду на узком экране */
"""

html = html.replace("</style>", MOBILE_CSS + "  </style>", 1)

# 3c/3d. Видео-фон остаётся ровно таким же, как в index.html (тег и CSS не трогаем)

# 3e. Вся логика графа — заменяется лёгкой версией
head, _ = html.split("<script>\nnodes = new vis.DataSet(", 1)

SCRIPT = r"""<script>
// --- ограничиваем разрешение canvas до 2x (на 3x-экранах в 2.25 раза меньше работы) ---
(function () {
  var real = window.devicePixelRatio || 1;
  if (real > 2) {
    Object.defineProperty(window, 'devicePixelRatio', { get: function () { return 2; } });
  }
})();

var nodes = new vis.DataSet(__NODES__);
var edges = new vis.DataSet(__EDGES__);

var container = document.getElementById('mynetwork');
var network = new vis.Network(container, { nodes: nodes, edges: edges }, {
  nodes: { scaling: { label: { enabled: false } } },
  // гравитация -270 как на ПК; физика при открытии не считается (координаты уже посчитаны)
  physics: {
    enabled: false,
    solver: "forceAtlas2Based",
    forceAtlas2Based: {
      theta: 0.5, gravitationalConstant: -270, centralGravity: 0.003,
      springLength: __SPRING__, springConstant: 0.04, damping: 0.5, avoidOverlap: 0.8
    },
    stabilization: { enabled: false }
  },
  layout: { improvedLayout: false },
  interaction: {
    dragNodes: false,                               // палец двигает граф, а не узел
    hideEdgesOnDrag: true,                          // связи прячутся на время жеста — плавнее
    hideEdgesOnZoom: true
  },
  edges: {
    smooth: { enabled: true, type: "dynamic" },     // как на ПК: изогнутые связи
    color: { color: "rgba(255,255,255,0.2)", highlight: "rgba(255,255,255,0.6)" }
  }
});

// изгибы связей из bake_layout.js (на ПК их задаёт физика, здесь они уже готовы)
var VIA = __VIA__;
Object.keys(VIA).forEach(function (id) {
  var e = network.body.edges[id];
  if (e && e.edgeType && e.edgeType.via) { e.edgeType.via.x = VIA[id][0]; e.edgeType.via.y = VIA[id][1]; }
});

// загрузочная плашка: показывается до первой отрисовки
network.once('afterDrawing', function () {
  network.fit({ animation: false });
  document.getElementById('loadingText').textContent = '100%';
  document.getElementById('loadingFill').style.width = '100%';
  var bar = document.getElementById('loadingBar');
  bar.style.opacity = 0;
  setTimeout(function () { bar.style.display = 'none'; }, 400);
});

// --- видео-фон: запуск по первому касанию и при возврате на вкладку ---
var bg = document.getElementById('bg-video');
bg.muted = true;
function playBg() { var p = bg.play(); if (p && p.catch) p.catch(function () {}); }
playBg();
bg.addEventListener('loadeddata', playBg);
['touchstart', 'pointerdown', 'click'].forEach(function (ev) {
  document.addEventListener(ev, function () { if (bg.paused) playBg(); }, { passive: true });
});
document.addEventListener('visibilitychange', function () { if (!document.hidden) playBg(); });

// --- Zoom ---
document.getElementById('btn-zoom-in').addEventListener('click', function () {
  network.moveTo({ scale: network.getScale() * 1.3 });
});
document.getElementById('btn-zoom-out').addEventListener('click', function () {
  network.moveTo({ scale: network.getScale() / 1.3 });
});
document.getElementById('btn-fit').addEventListener('click', function () {
  network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
});

// --- Search ---
var searchBox = document.getElementById('search-box');
var searchResults = document.getElementById('search-results');
searchBox.addEventListener('input', function () {
  var q = this.value.trim().toLowerCase();
  searchResults.innerHTML = '';
  if (!q) { searchResults.style.display = 'none'; return; }
  var matches = nodes.get().filter(function (n) {
    return n.label && n.label.toLowerCase().includes(q);
  }).slice(0, 10);
  if (!matches.length) { searchResults.style.display = 'none'; return; }
  matches.forEach(function (n) {
    var item = document.createElement('div');
    item.className = 'search-result-item';
    item.textContent = n.label;
    item.addEventListener('click', function () {
      network.focus(n.id, { scale: 1.5, animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
      network.selectNodes([n.id]);
      searchResults.style.display = 'none';
      searchBox.value = n.label;
    });
    searchResults.appendChild(item);
  });
  searchResults.style.display = 'block';
});
document.addEventListener('click', function (e) {
  if (!document.getElementById('overlay-controls').contains(e.target)) {
    searchResults.style.display = 'none';
  }
});

// --- About popup ---
document.getElementById('about-btn').addEventListener('click', function () {
  var p = document.getElementById('about-popup');
  p.style.display = p.style.display === 'block' ? 'none' : 'block';
});
document.getElementById('about-close').addEventListener('click', function () {
  document.getElementById('about-popup').style.display = 'none';
});
</script>
</body>
</html>
"""

SCRIPT = (SCRIPT
          .replace("__SPRING__", str(SPRING))
          .replace("__VIA__", json.dumps(VIA, separators=(",", ":")))
          .replace("__NODES__", json.dumps(nodes, ensure_ascii=False, separators=(",", ":")))
          .replace("__EDGES__", json.dumps(edges, ensure_ascii=False, separators=(",", ":"))))

open(OUT, "w", encoding="utf-8").write(head + SCRIPT)
print(f"{OUT}: {len((head + SCRIPT).encode('utf-8')) // 1024} КБ")

# для проверки раскладки глазами
np.save("/tmp/layout.npy", np.c_[P, W, H, size])
