import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

/**
 * SVG-based AR overlay — pointer-events-none, z-10.
 * Reads ar_elements from backend and renders:
 *   - "box"     → targeting brackets with dynamic color
 *   - "polygon" → red incision zone outline
 *   - "line"    → scalpel-to-target trace line with deviation color
 */

export default function AROverlay() {
  const arElements = useHudStore((s) => s.arElements);
  const phase = useHudStore((s) => s.phase);

  // Don't render anything in Phase 0 (clean video only)
  if (phase === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-10">
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        className="absolute inset-0 w-full h-full"
        style={{ overflow: 'visible' }}
      >
        <defs>
          {/* Glow filter for lines */}
          <filter id="glow">
            <feGaussianBlur stdDeviation="0.003" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <AnimatePresence>
          {arElements.map((el, i) => {
            // Use stable key: type+label (or index fallback for unlabeled elements)
            // This prevents React from unmounting/remounting unchanged boxes (BUG-3 fix)
            const stableKey = el.label ? `${el.type}-${el.label}` : `${el.type}-${i}`;
            if (el.type === 'box') return <BoxBracket key={stableKey} el={el} />;
            if (el.type === 'polygon') return <PolygonOutline key={stableKey} el={el} />;
            if (el.type === 'line') return <TraceLine key={stableKey} el={el} />;
            if (el.type === 'zone_debug') return <ZoneDebug key="zone_debug" />;
            return null;
          })}
        </AnimatePresence>
      </svg>

      {/* HTML labels (outside SVG for better text rendering) */}
      <AnimatePresence>
        {arElements
          .filter((el) => el.type === 'box' && el.label)
          .map((el) => (
            <BoxLabel key={`label-${el.label}`} el={el} />
          ))}
      </AnimatePresence>
    </div>
  );
}


// ── Box Bracket (SVG corner brackets) ──────────────────────────────────────
function BoxBracket({ el }) {
  const { x, y, width, height, color } = el;
  const cs = 0.015; // corner size in normalized coords
  const sw = 0.002; // stroke width

  return (
    <g opacity="0.9">
      {/* Top-left */}
      <line x1={x} y1={y} x2={x + cs} y2={y} stroke={color} strokeWidth={sw} />
      <line x1={x} y1={y} x2={x} y2={y + cs} stroke={color} strokeWidth={sw} />
      {/* Top-right */}
      <line x1={x + width} y1={y} x2={x + width - cs} y2={y} stroke={color} strokeWidth={sw} />
      <line x1={x + width} y1={y} x2={x + width} y2={y + cs} stroke={color} strokeWidth={sw} />
      {/* Bottom-left */}
      <line x1={x} y1={y + height} x2={x + cs} y2={y + height} stroke={color} strokeWidth={sw} />
      <line x1={x} y1={y + height} x2={x} y2={y + height - cs} stroke={color} strokeWidth={sw} />
      {/* Bottom-right */}
      <line x1={x + width} y1={y + height} x2={x + width - cs} y2={y + height} stroke={color} strokeWidth={sw} />
      <line x1={x + width} y1={y + height} x2={x + width} y2={y + height - cs} stroke={color} strokeWidth={sw} />
    </g>
  );
}


// ── Polygon Outline (incision zone) ────────────────────────────────────────
function PolygonOutline({ el }) {
  if (!el.points || el.points.length < 3) return null;
  const pts = el.points.map((p) => `${p[0]},${p[1]}`).join(' ');
  return (
    <polygon
      points={pts}
      fill="none"
      stroke={el.color}
      strokeWidth="0.003"
      strokeDasharray="0.01 0.005"
      opacity="0.7"
      filter="url(#glow)"
    />
  );
}


// ── Trace Line (scalpel → target) ──────────────────────────────────────────
function TraceLine({ el }) {
  return (
    <line
      x1={el.x1} y1={el.y1}
      x2={el.x2} y2={el.y2}
      stroke={el.color}
      strokeWidth="0.004"
      strokeLinecap="round"
      filter="url(#glow)"
      opacity="0.85"
    />
  );
}


// ── Zone Debug (spatial classification regions) ─────────────────────────────
function ZoneDebug() {
  return (
    <g opacity="0.15">
      <line x1="0.5" y1="0" x2="0.5" y2="1"
            stroke="#ffffff" strokeWidth="0.001" strokeDasharray="0.01 0.008" />
      <text x="0.25" y="0.04" fill="#3b82f6" fontSize="0.018"
            textAnchor="middle" fontFamily="monospace">CLAMP</text>
      <text x="0.75" y="0.04" fill="#22c55e" fontSize="0.018"
            textAnchor="middle" fontFamily="monospace">SCALPEL</text>
    </g>
  );
}


// ── HTML Label (floating above box) ────────────────────────────────────────
function BoxLabel({ el }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="absolute text-[10px] font-mono tracking-widest uppercase px-1.5 py-0.5"
      style={{
        left: `${el.x * 100}%`,
        top: `calc(${el.y * 100}% - 20px)`,
        color: el.color,
        backgroundColor: 'rgba(0,0,0,0.7)',
        borderLeft: `2px solid ${el.color}`,
        textShadow: `0 0 6px ${el.color}`,
      }}
    >
      {el.label}
      {el.confidence != null && (
        <span className="ml-1 opacity-40">{Math.round(el.confidence * 100)}%</span>
      )}
    </motion.div>
  );
}
