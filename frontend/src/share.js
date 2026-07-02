// Canvas-drawn share cards (1200x630) + native share / download fallback.
// No dependencies: plain 2D canvas, using the fonts the app already loads.

const W = 1200;
const H = 630;
const BG = "#070b09";
const TEXT = "#e9f2eb";
const DIM = "#93a399";
const FAINT = "#5d6c63";
const GRASS = "#3ee07a";
const GOLD = "#f3c350";
const CORAL = "#ff6b42";

const SITE = "world-cup-detector.vercel.app";

const pct = (x) => Math.round(x * 100);

function newCanvas() {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, W, H);
  // Faint stadium glow, echoing the app background.
  const g1 = ctx.createRadialGradient(140, -60, 0, 140, -60, 640);
  g1.addColorStop(0, "rgba(62,224,122,0.16)");
  g1.addColorStop(1, "rgba(62,224,122,0)");
  ctx.fillStyle = g1;
  ctx.fillRect(0, 0, W, H);
  const g2 = ctx.createRadialGradient(W, 0, 0, W, 0, 560);
  g2.addColorStop(0, "rgba(255,107,66,0.10)");
  g2.addColorStop(1, "rgba(255,107,66,0)");
  ctx.fillStyle = g2;
  ctx.fillRect(0, 0, W, H);
  return [c, ctx];
}

function display(size) {
  return `${size}px Anton, "Arial Black", Arial, sans-serif`;
}
function body(size, weight = 600) {
  return `${weight} ${size}px "Hanken Grotesk", Arial, sans-serif`;
}
function mono(size) {
  return `600 ${size}px "IBM Plex Mono", Consolas, monospace`;
}

function header(ctx) {
  // Crest
  ctx.fillStyle = GRASS;
  ctx.beginPath();
  ctx.roundRect(80, 56, 54, 54, 13);
  ctx.fill();
  ctx.fillStyle = "#04130a";
  ctx.font = display(30);
  ctx.textAlign = "center";
  ctx.fillText("W", 107, 96);
  // Wordmark
  ctx.textAlign = "left";
  ctx.fillStyle = TEXT;
  ctx.font = display(34);
  ctx.fillText("WORLD ", 154, 94);
  const w1 = ctx.measureText("WORLD ").width;
  ctx.fillStyle = GRASS;
  ctx.fillText("CUP ", 154 + w1, 94);
  const w2 = ctx.measureText("CUP ").width;
  ctx.fillStyle = TEXT;
  ctx.fillText("DETECTOR", 154 + w1 + w2, 94);
}

function footer(ctx, note) {
  ctx.font = mono(20);
  ctx.fillStyle = FAINT;
  ctx.textAlign = "left";
  ctx.fillText(note, 80, H - 48);
  ctx.textAlign = "right";
  ctx.fillStyle = DIM;
  ctx.fillText(SITE, W - 80, H - 48);
  ctx.textAlign = "left";
}

function fitText(ctx, text, font, maxWidth, startSize) {
  let size = startSize;
  do {
    ctx.font = font(size);
    if (ctx.measureText(text).width <= maxWidth) break;
    size -= 4;
  } while (size > 24);
  return size;
}

export async function drawMatchCard(prediction) {
  await document.fonts.ready.catch(() => {});
  const [c, ctx] = newCanvas();
  const { home, away, probabilities: p, most_likely } = prediction;

  header(ctx);

  // Matchup title (auto-shrinks for long names)
  const title = `${home}  vs  ${away}`.toUpperCase();
  fitText(ctx, title, display, W - 160, 72);
  ctx.fillStyle = TEXT;
  ctx.fillText(title, 80, 232);

  // Verdict line
  const verdict =
    most_likely === "home_win" ? `${home} win` : most_likely === "away_win" ? `${away} win` : "Draw";
  const top = Math.max(p.home_win, p.draw, p.away_win);
  ctx.font = body(28);
  ctx.fillStyle = DIM;
  ctx.fillText("MOST LIKELY", 80, 292);
  const labelW = ctx.measureText("MOST LIKELY").width;
  ctx.font = body(28, 800);
  ctx.fillStyle = GRASS;
  ctx.fillText(`${verdict} · ${pct(top)}%`, 80 + labelW + 18, 292);

  // Probability bar
  const bx = 80, by = 340, bw = W - 160, bh = 96, r = 18;
  const segs = [
    [p.home_win, GRASS, "#21b257", "#05130b", home],
    [p.draw, GOLD, "#d8a531", "#1c1606", "DRAW"],
    [p.away_win, CORAL, "#e2502a", "#190702", away],
  ];
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(bx, by, bw, bh, r);
  ctx.clip();
  let x = bx;
  for (const [val, c1, c2, tc, label] of segs) {
    const w = bw * val;
    const grad = ctx.createLinearGradient(0, by, 0, by + bh);
    grad.addColorStop(0, c1);
    grad.addColorStop(1, c2);
    ctx.fillStyle = grad;
    ctx.fillRect(x, by, w, bh);
    if (val > 0.09) {
      ctx.fillStyle = tc;
      ctx.textAlign = "center";
      ctx.font = display(34);
      ctx.fillText(`${pct(val)}%`, x + w / 2, by + 48);
      ctx.font = body(16, 800);
      const short = label.length > 14 ? label.slice(0, 13) + "…" : label;
      ctx.fillText(short.toUpperCase(), x + w / 2, by + 76);
    }
    x += w;
  }
  ctx.restore();
  ctx.textAlign = "left";

  footer(ctx, "Elo + logistic model · 49,000+ matches");
  return c;
}

export async function drawSimCard(teams, runs) {
  await document.fonts.ready.catch(() => {});
  const [c, ctx] = newCanvas();
  header(ctx);

  ctx.fillStyle = TEXT;
  ctx.font = display(56);
  ctx.fillText("WHO WINS THE 2026 WORLD CUP?", 80, 196);

  const top = teams.slice(0, 8);
  const max = top[0]?.win_title || 1;
  const rows = top.length;
  const y0 = 240, rowH = 38, barMax = 560;
  top.forEach((t, i) => {
    const y = y0 + i * rowH;
    ctx.font = body(24, i === 0 ? 800 : 600);
    ctx.fillStyle = i === 0 ? GRASS : TEXT;
    ctx.textAlign = "left";
    ctx.fillText(`${i + 1}. ${t.team}`, 80, y + 24);
    const w = Math.max(6, (t.win_title / max) * barMax);
    const grad = ctx.createLinearGradient(360, 0, 360 + w, 0);
    grad.addColorStop(0, GRASS);
    grad.addColorStop(1, "#15a84d");
    ctx.fillStyle = grad;
    ctx.globalAlpha = i === 0 ? 0.95 : 0.55;
    ctx.beginPath();
    ctx.roundRect(360, y + 6, w, 20, 8);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.font = mono(24);
    ctx.fillStyle = i === 0 ? GRASS : DIM;
    ctx.fillText(`${(t.win_title * 100).toFixed(1)}%`, 360 + w + 16, y + 24);
  });

  footer(ctx, `${runs.toLocaleString()} Monte-Carlo simulations`);
  return c;
}

export async function shareCanvas(canvas, filename, text) {
  const blob = await new Promise((res) => canvas.toBlob(res, "image/png"));
  if (!blob) return;
  const file = new File([blob], filename, { type: "image/png" });
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: "World Cup Detector", text });
      return;
    } catch (e) {
      if (e.name === "AbortError") return; // user cancelled
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
