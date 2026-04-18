/** SVG radar chart for 3 dimensions: Skills, Experience, Leverage. Light theme (dashboard-aligned). */

const GRID_STROKE = "#cbd5e1";
const LABEL_FILL = "#5c6b82";
const LABEL_SUB = "#64748b";
const FILL = "rgba(91, 159, 212, 0.22)";
const STROKE = "#5b9fd4";

interface Props {
  hardSkills: number;   // 0–100
  experience: number;
  synergy: number;      // displayed as "Leverage"
}

const SIZE = 200;
const CX = SIZE / 2;
const CY = SIZE / 2;
const R = 75;  // outer radius

// Axes: top = Skills, bottom-right = Experience, bottom-left = Leverage
const AXES = [
  { label: "Skills",     angle: -Math.PI / 2 },
  { label: "Experience", angle: -Math.PI / 2 + (2 * Math.PI) / 3 },
  { label: "Leverage",   angle: -Math.PI / 2 + (4 * Math.PI) / 3 },
];

function pt(value: number, angle: number, scale = 1) {
  const r = (value / 100) * R * scale;
  return { x: CX + r * Math.cos(angle), y: CY + r * Math.sin(angle) };
}

function polyPoints(values: number[]) {
  return values
    .map((v, i) => {
      const { x, y } = pt(v, AXES[i].angle);
      return `${x},${y}`;
    })
    .join(" ");
}

export default function RadarChart({ hardSkills, experience, synergy }: Props) {
  const values = [hardSkills, experience, synergy];

  // Grid rings at 33 / 66 / 100
  const rings = [33, 66, 100];

  return (
    <div className="flex flex-col items-center">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        {/* Grid rings */}
        {rings.map((pct) => (
          <polygon
            key={pct}
            points={polyPoints([pct, pct, pct])}
            fill="none"
            stroke={GRID_STROKE}
            strokeWidth="1"
          />
        ))}

        {/* Axis lines */}
        {AXES.map((ax) => {
          const outer = pt(100, ax.angle);
          return (
            <line
              key={ax.label}
              x1={CX} y1={CY}
              x2={outer.x} y2={outer.y}
              stroke={GRID_STROKE} strokeWidth="1"
            />
          );
        })}

        {/* Data polygon */}
        <polygon
          points={polyPoints(values)}
          fill={FILL}
          stroke={STROKE}
          strokeWidth="2"
        />

        {/* Data dots */}
        {values.map((v, i) => {
          const { x, y } = pt(v, AXES[i].angle);
          return <circle key={i} cx={x} cy={y} r={4} fill={STROKE} />;
        })}

        {/* Axis labels */}
        {AXES.map((ax, i) => {
          const { x, y } = pt(115, ax.angle);
          const textAnchor =
            Math.cos(ax.angle) > 0.1 ? "start" : Math.cos(ax.angle) < -0.1 ? "end" : "middle";
          return (
            <text
              key={ax.label}
              x={x} y={y}
              textAnchor={textAnchor}
              dominantBaseline="middle"
              fontSize="11"
              fill={LABEL_FILL}
            >
              {ax.label}
              <tspan x={x} dy="13" fontSize="10" fill={LABEL_SUB}>
                {values[i]}
              </tspan>
            </text>
          );
        })}
      </svg>
    </div>
  );
}
