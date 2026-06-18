import { useMemo } from "react";
import DOMPurify from "dompurify";
import type {
  AiBoardItem,
  AiBoardPlot,
  AiBoardShape,
  AiBoardText,
} from "../../lib/whiteboard";
import { renderMathTextToHtml } from "../../lib/mathText";

export default function BoardItem({ item }: { item: AiBoardItem }) {
  if (item.kind === "text") return <TextItem item={item} />;
  if (item.kind === "plot") return <PlotItem item={item} />;
  if (item.kind === "shape") return <ShapeItem item={item} />;
  return null;
}

function TextItem({ item }: { item: AiBoardText }) {
  const html = useMemo(
    () => renderMathTextToHtml(item.markdown),
    [item.markdown],
  );
  return (
    <div className="ai-card board-item-text">
      <div
        dangerouslySetInnerHTML={{
          __html: DOMPurify.sanitize(html, {
            USE_PROFILES: { html: true, mathMl: true, svg: true },
          }),
        }}
      />
    </div>
  );
}

function PlotItem({ item }: { item: AiBoardPlot }) {
  const path = useMemo(() => buildPlotPath(item), [item]);
  const width = 320;
  const height = 200;
  return (
    <div className="ai-card board-item-plot">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
      >
        <rect
          x={0}
          y={0}
          width={width}
          height={height}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.15}
        />
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="currentColor"
          strokeOpacity={0.25}
        />
        <line
          x1={width / 2}
          y1={0}
          x2={width / 2}
          y2={height}
          stroke="currentColor"
          strokeOpacity={0.25}
        />
        <path
          d={path}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
        />
        {item.label ? (
          <text x={8} y={16} fill="currentColor" fontSize={12}>
            {item.label}
          </text>
        ) : null}
      </svg>
    </div>
  );
}

function buildPlotPath(item: AiBoardPlot): string {
  const width = 320;
  const height = 200;
  const samples = 200;
  const f = compileExpression(item.expression);

  const xs: number[] = [];
  const ys: number[] = [];
  let yMin = Infinity;
  let yMax = -Infinity;

  for (let i = 0; i <= samples; i++) {
    const x =
      item.x_min + ((item.x_max - item.x_min) * i) / samples;
    let y: number;
    try {
      y = f(x);
    } catch {
      y = NaN;
    }
    xs.push(x);
    ys.push(y);
    if (Number.isFinite(y)) {
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    }
  }
  if (!Number.isFinite(yMin) || !Number.isFinite(yMax) || yMin === yMax) {
    yMin = -1;
    yMax = 1;
  }

  const pad = (yMax - yMin) * 0.1;
  yMin -= pad;
  yMax += pad;

  const px = (x: number) =>
    ((x - item.x_min) / (item.x_max - item.x_min)) * width;
  const py = (y: number) =>
    height - ((y - yMin) / (yMax - yMin)) * height;

  let d = "";
  let pen = "M";
  for (let i = 0; i < xs.length; i++) {
    if (!Number.isFinite(ys[i])) {
      pen = "M";
      continue;
    }
    d += `${pen}${px(xs[i]).toFixed(2)},${py(ys[i]).toFixed(2)} `;
    pen = "L";
  }
  return d.trim();
}

function compileExpression(expr: string): (x: number) => number {
  // Allow only digits, x, basic operators, parentheses, and identifier chars
  // (so callers can write `sin(x)`, `pow(x,2)`, etc. — `with(Math)` resolves
  // them). Anything else is rejected outright.
  if (!/^[\sxX0-9+\-*/().,\^a-zA-Z_]+$/.test(expr)) {
    return () => NaN;
  }
  // Disallow obvious escape hatches.
  if (/(=>|=|`|\bnew\b|\bwindow\b|\bdocument\b|\bglobal\b)/.test(expr)) {
    return () => NaN;
  }
  // Convert "^" to "**" so users can write x^2.
  const safe = expr.replace(/\^/g, "**");
  try {
    const f = new Function(
      "x",
      `with (Math) { return (${safe}); }`,
    ) as (x: number) => number;
    // Smoke-test once; if it throws on a benign value, we treat as invalid.
    f(0);
    return f;
  } catch {
    return () => NaN;
  }
}

function ShapeItem({ item }: { item: AiBoardShape }) {
  const safe = useMemo(
    () =>
      DOMPurify.sanitize(`<svg viewBox="0 0 200 200">${item.svg}</svg>`, {
        USE_PROFILES: { svg: true, svgFilters: true },
      }),
    [item.svg],
  );
  return (
    <div
      className="ai-card board-item-shape"
      dangerouslySetInnerHTML={{ __html: safe }}
    />
  );
}
