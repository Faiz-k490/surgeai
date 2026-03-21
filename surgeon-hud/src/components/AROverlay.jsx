import { motion, AnimatePresence } from 'framer-motion';
import { useHudStore } from '../store/useHudStore';

function TargetBracket({ box }) {
  const style = {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.width * 100}%`,
    height: `${box.height * 100}%`,
  };

  const cornerSize = '12px';
  const borderWidth = '2px';
  const color = box.color || 'rgb(34, 211, 238)';

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="absolute"
      style={style}
    >
      {/* Top-left corner */}
      <div
        className="absolute top-0 left-0"
        style={{
          width: cornerSize,
          height: cornerSize,
          borderTop: `${borderWidth} solid ${color}`,
          borderLeft: `${borderWidth} solid ${color}`,
        }}
      />
      {/* Top-right corner */}
      <div
        className="absolute top-0 right-0"
        style={{
          width: cornerSize,
          height: cornerSize,
          borderTop: `${borderWidth} solid ${color}`,
          borderRight: `${borderWidth} solid ${color}`,
        }}
      />
      {/* Bottom-left corner */}
      <div
        className="absolute bottom-0 left-0"
        style={{
          width: cornerSize,
          height: cornerSize,
          borderBottom: `${borderWidth} solid ${color}`,
          borderLeft: `${borderWidth} solid ${color}`,
        }}
      />
      {/* Bottom-right corner */}
      <div
        className="absolute bottom-0 right-0"
        style={{
          width: cornerSize,
          height: cornerSize,
          borderBottom: `${borderWidth} solid ${color}`,
          borderRight: `${borderWidth} solid ${color}`,
        }}
      />

      {/* Label */}
      {box.label && (
        <div
          className="absolute -top-5 left-0 px-1.5 py-0.5 text-[10px] font-mono tracking-wider uppercase"
          style={{
            color,
            backgroundColor: 'rgba(0,0,0,0.6)',
            borderLeft: `${borderWidth} solid ${color}`,
          }}
        >
          {box.label}
          {box.confidence != null && (
            <span className="ml-1.5 opacity-50">{Math.round(box.confidence * 100)}%</span>
          )}
        </div>
      )}
    </motion.div>
  );
}

export default function AROverlay() {
  const arBoxes = useHudStore((s) => s.arBoxes);

  return (
    <div className="absolute inset-0 pointer-events-none z-20">
      <AnimatePresence>
        {arBoxes.map((box, i) => (
          <TargetBracket key={box.id || i} box={box} />
        ))}
      </AnimatePresence>
    </div>
  );
}
