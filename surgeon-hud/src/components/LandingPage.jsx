import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import cadModelImg from './Hardware CAD Model.png';

/* ═══════════════════════════════════════════════════════════════════════════
   SurgeonAI — Landing Page v3
   Pixel art + Outfit/Space Grotesk fonts + clean hackathon design
   ═══════════════════════════════════════════════════════════════════════════ */

const FONT_HEADING = "'Outfit', sans-serif";
const FONT_BODY = "'Space Grotesk', sans-serif";

// ── Tech stack with links ──────────────────────────────────────────────────
const TECH_STACK = [
  { name: 'YOLOv8', url: 'https://docs.ultralytics.com/' },
  { name: 'OpenCV', url: 'https://opencv.org/' },
  { name: 'Flask', url: 'https://flask.palletsprojects.com/' },
  { name: 'Socket.IO', url: 'https://socket.io/' },
  { name: 'React', url: 'https://react.dev/' },
  { name: 'Vite', url: 'https://vitejs.dev/' },
  { name: 'ElevenLabs', url: 'https://elevenlabs.io/' },
  { name: 'Google Cloud', url: 'https://cloud.google.com/' },
  { name: 'Snowflake', url: 'https://www.snowflake.com/' },
  { name: 'MongoDB', url: 'https://www.mongodb.com/' },
];

// ── Pixel-style animated typing ────────────────────────────────────────────
function TypeWriter({ text, delay = 0, speed = 35 }) {
  const [displayed, setDisplayed] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      let i = 0;
      const iv = setInterval(() => {
        setDisplayed(text.slice(0, ++i));
        if (i >= text.length) clearInterval(iv);
      }, speed);
      return () => clearInterval(iv);
    }, delay);
    return () => clearTimeout(timer);
  }, [text, delay, speed]);
  return (
    <span>
      {displayed}
      <motion.span
        animate={{ opacity: [1, 0] }}
        transition={{ duration: 0.5, repeat: Infinity, repeatType: 'reverse' }}
        style={{ display: 'inline-block', width: 2, height: '1em', background: '#2dd4bf', marginLeft: 2, verticalAlign: 'middle' }}
      />
    </span>
  );
}

// ── Floating pixel particles ───────────────────────────────────────────────
function FloatingPixels() {
  const pixels = Array.from({ length: 18 }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    delay: Math.random() * 6,
    duration: 6 + Math.random() * 10,
    size: 2 + Math.floor(Math.random() * 3),
    color: ['#2dd4bf', '#a78bfa', '#f472b6', '#67e8f9'][Math.floor(Math.random() * 4)],
  }));

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
      {pixels.map((p) => (
        <motion.div
          key={p.id}
          style={{
            position: 'absolute',
            left: p.left,
            width: p.size,
            height: p.size,
            backgroundColor: p.color,
            boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
          }}
          initial={{ bottom: -10, opacity: 0 }}
          animate={{ bottom: '110%', opacity: [0, 0.7, 0.7, 0] }}
          transition={{ duration: p.duration, delay: p.delay, repeat: Infinity, ease: 'linear' }}
        />
      ))}
    </div>
  );
}

// ── Glitch text ────────────────────────────────────────────────────────────
function GlitchText({ children }) {
  return (
    <span style={{ position: 'relative', display: 'inline-block' }}>
      <span style={{ position: 'relative', zIndex: 1 }}>{children}</span>
      <motion.span
        style={{ position: 'absolute', top: 0, left: 0, color: '#a78bfa', clipPath: 'inset(0 0 65% 0)', zIndex: 0, opacity: 0.6 }}
        animate={{ x: [0, -2, 2, 0], y: [0, 1, -1, 0] }}
        transition={{ duration: 0.3, repeat: Infinity, repeatDelay: 4 }}
        aria-hidden
      >{children}</motion.span>
      <motion.span
        style={{ position: 'absolute', top: 0, left: 0, color: '#2dd4bf', clipPath: 'inset(65% 0 0 0)', zIndex: 0, opacity: 0.6 }}
        animate={{ x: [0, 2, -2, 0], y: [0, -1, 1, 0] }}
        transition={{ duration: 0.3, repeat: Infinity, repeatDelay: 4, delay: 0.05 }}
        aria-hidden
      >{children}</motion.span>
    </span>
  );
}

// ── Animated counter ───────────────────────────────────────────────────────
function CountUp({ to, suffix = '', duration = 2 }) {
  const [val, setVal] = useState(0);
  const ref = useRef(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setStarted(true); }, { threshold: 0.3 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!started) return;
    let start = null;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / (duration * 1000), 1);
      setVal(Math.round(to * p));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [started, to, duration]);

  return <span ref={ref}>{val}{suffix}</span>;
}

// ── Scanlines ──────────────────────────────────────────────────────────────
function Scanlines() {
  return (
    <div
      style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 100, opacity: 0.025,
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.4) 2px, rgba(0,0,0,0.4) 4px)',
      }}
    />
  );
}


// ══════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════════════════════════════════════
export default function LandingPage({ onEnter }) {
  const [entering, setEntering] = useState(false);

  const handleEnter = () => {
    setEntering(true);
    setTimeout(() => onEnter(), 900);
  };

  return (
    <AnimatePresence>
      {!entering ? (
        <motion.div
          key="landing"
          exit={{ opacity: 0, filter: 'blur(14px)', scale: 1.04 }}
          transition={{ duration: 0.8, ease: 'easeInOut' }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: '#08080d',
            overflowY: 'auto', overflowX: 'hidden',
            fontFamily: FONT_BODY,
            color: '#fff',
          }}
        >
          <Scanlines />
          <FloatingPixels />

          {/* ── NAVBAR ──────────────────────────────────── */}
          <nav style={{
            position: 'sticky', top: 0, zIndex: 60,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 32px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            background: 'rgba(8,8,13,0.92)',
            backdropFilter: 'blur(20px)',
          }}>
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              style={{ display: 'flex', alignItems: 'center', gap: 10 }}
            >
              <img src="/assets/pixel_robot.png" alt="SurgeonAI" style={{ width: 32, height: 32, borderRadius: 8 }} />
              <span style={{ fontFamily: FONT_HEADING, fontSize: 16, fontWeight: 800, letterSpacing: '0.12em' }}>
                SURGEON<span style={{ color: '#2dd4bf' }}>AI</span>
              </span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
            >
              <a
                href="https://github.com/Faiz-k490/surgeai"
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 14px', borderRadius: 10,
                  border: '1px solid rgba(255,255,255,0.08)',
                  background: 'rgba(255,255,255,0.02)',
                  color: 'rgba(255,255,255,0.5)',
                  fontSize: 11, fontWeight: 500, letterSpacing: '0.1em',
                  textDecoration: 'none', textTransform: 'uppercase',
                  transition: 'all 0.3s ease',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" /></svg>
                GitHub
              </a>
            </motion.div>
          </nav>

          {/* ── HERO ────────────────────────────────────── */}
          <section style={{
            position: 'relative',
            display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center',
            minHeight: '90vh',
            padding: '48px 32px',
            gap: 48,
          }}>
            {/* Left text */}
            <div style={{ flex: '1 1 480px', maxWidth: 640, zIndex: 10 }}>
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 8,
                  padding: '6px 14px', borderRadius: 10, marginBottom: 28,
                  border: '1px solid rgba(167,139,250,0.2)',
                  background: 'rgba(167,139,250,0.05)',
                }}
              >
                <span style={{ fontSize: 12 }}>🏆</span>
                <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.15em', color: '#c4b5fd', textTransform: 'uppercase' }}>
                  Hackathon Project
                </span>
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.7 }}
                style={{
                  fontFamily: FONT_HEADING, fontSize: 'clamp(36px, 5.5vw, 72px)',
                  fontWeight: 900, lineHeight: 1.08,
                  letterSpacing: '-0.02em',
                  marginBottom: 24,
                }}
              >
                Surgeons need{' '}
                <GlitchText><span style={{ color: '#2dd4bf' }}>practice.</span></GlitchText>
                <br />
                <span style={{ color: 'rgba(255,255,255,0.7)' }}>There aren't enough trainers.</span>
              </motion.h1>

              {/* Terminal style subtitle */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                style={{
                  borderRadius: 12, border: '1px solid rgba(255,255,255,0.06)',
                  background: 'rgba(255,255,255,0.02)',
                  padding: '14px 18px', marginBottom: 32,
                  fontFamily: "'Space Grotesk', monospace",
                  fontSize: 13, color: '#2dd4bf',
                }}
              >
                <span style={{ color: 'rgba(255,255,255,0.25)' }}>$ </span>
                <TypeWriter text="Real-time computer vision guides trainees through precise surgical incisions..." delay={800} speed={28} />
              </motion.div>

              {/* CTA */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.8 }}
                style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}
              >
                <motion.button
                  whileHover={{ scale: 1.04, boxShadow: '0 0 50px rgba(45,212,191,0.4)' }}
                  whileTap={{ scale: 0.96 }}
                  onClick={handleEnter}
                  style={{
                    padding: '14px 32px', borderRadius: 14, border: 'none',
                    fontFamily: FONT_HEADING, fontWeight: 700,
                    fontSize: 13, letterSpacing: '0.18em', textTransform: 'uppercase',
                    color: '#08080d', cursor: 'pointer',
                    background: 'linear-gradient(135deg, #2dd4bf 0%, #a78bfa 100%)',
                    boxShadow: '0 4px 30px rgba(45,212,191,0.3)',
                  }}
                >
                  ▶ Launch SurgeonAI
                </motion.button>
              </motion.div>

              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.25 }}
                transition={{ delay: 1.1 }}
                style={{ marginTop: 12, fontSize: 10, fontWeight: 500, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.3)' }}
              >
                Requires camera access · Scalpel needed for Phase 3+
              </motion.p>
            </div>

            {/* Right: Pixel robot */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8, rotate: -5 }}
              animate={{ opacity: 1, scale: 1, rotate: 0 }}
              transition={{ delay: 0.5, type: 'spring', stiffness: 120 }}
              style={{ flexShrink: 0, position: 'relative' }}
            >
              <motion.img
                src="/assets/pixel_robot.png"
                alt="SurgeonAI Robot"
                style={{
                  width: 280, height: 280, borderRadius: 24,
                  filter: 'drop-shadow(0 0 40px rgba(45,212,191,0.3)) drop-shadow(0 0 80px rgba(167,139,250,0.15))',
                }}
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
              />
              <motion.div
                style={{
                  position: 'absolute', bottom: -8, right: -8, borderRadius: 12,
                  border: '1px solid rgba(45,212,191,0.25)',
                  background: 'rgba(8,8,13,0.9)',
                  backdropFilter: 'blur(8px)',
                  padding: '6px 12px',
                }}
                animate={{ y: [0, -4, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
              >
                <span style={{ fontSize: 10, fontWeight: 600, color: '#2dd4bf', letterSpacing: '0.12em' }}>
                  <a href="https://docs.ultralytics.com/" target="_blank" rel="noreferrer" style={{ color: '#2dd4bf', textDecoration: 'none' }}>YOLOv8</a>
                  {' + '}
                  <a href="https://opencv.org/" target="_blank" rel="noreferrer" style={{ color: '#2dd4bf', textDecoration: 'none' }}>OpenCV</a>
                </span>
              </motion.div>
            </motion.div>

            {/* Background glow */}
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              width: 600, height: 600, borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(167,139,250,0.2) 0%, rgba(45,212,191,0.1) 40%, transparent 70%)',
              filter: 'blur(100px)',
              pointerEvents: 'none', opacity: 0.25,
            }} />
          </section>

          {/* ── STATS BAR ──────────────────────────────── */}
          <section style={{
            padding: '28px 32px',
            borderTop: '1px solid rgba(255,255,255,0.04)',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
            background: 'rgba(255,255,255,0.01)',
          }}>
            <div style={{ maxWidth: 960, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 24, textAlign: 'center' }}>
              {[
                { n: 5, s: 'x', label: 'More trainees than trainers' },
                { n: 40, s: '%', label: 'Report insufficient practice' },
                { n: 6, s: '', label: 'Phase AI protocol' },
                { n: 30, s: ' fps', label: 'Real-time CV pipeline' },
              ].map(({ n, s, label }, i) => (
                <motion.div
                  key={label}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                >
                  <div style={{ fontFamily: FONT_HEADING, fontSize: 36, fontWeight: 900, color: '#fff', marginBottom: 4 }}>
                    <CountUp to={n} suffix={s} />
                  </div>
                  <div style={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.25)' }}>
                    {label}
                  </div>
                </motion.div>
              ))}
            </div>
          </section>

          {/* ── THE PROBLEM (with pixel art) ────────────── */}
          <section style={{ padding: '80px 32px', position: 'relative' }}>
            <div style={{ maxWidth: 1080, margin: '0 auto' }}>
              <motion.div
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                style={{ marginBottom: 48 }}
              >
                <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.4em', textTransform: 'uppercase', color: 'rgba(248,113,113,0.6)' }}>⚠ The Problem</span>
                <h2 style={{ fontFamily: FONT_HEADING, fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: 900, marginTop: 12, lineHeight: 1.15 }}>
                  Surgical training is <span style={{ color: '#f87171' }}>broken.</span>
                </h2>
              </motion.div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24 }}>
                {[
                  { img: '/assets/pixel_hospital.png', title: 'Trainer Shortage', body: 'One attending consultant supervises 5–10 residents simultaneously. Real hands-on guidance becomes rushed or skipped entirely during high-pressure rotations.', accent: '#f87171' },
                  { img: '/assets/pixel_hourglass.png', title: 'Limited OR Time', body: 'Trainees average a fraction of the autonomous surgical hours needed to build genuine competence. OR slots are competitive and scarce.', accent: '#fb923c' },
                  { img: '/assets/pixel_nodata.png', title: 'Zero Feedback', body: 'No real-time precision metrics exist. Trainees cannot measure whether their technique deviates from the optimal incision geometry.', accent: '#fbbf24' },
                ].map(({ img, title, body, accent }, i) => (
                  <motion.div
                    key={title}
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.12 }}
                    style={{
                      borderRadius: 20, overflow: 'hidden',
                      border: '1px solid rgba(255,255,255,0.06)',
                      background: 'rgba(255,255,255,0.015)',
                      transition: 'border-color 0.4s ease',
                    }}
                  >
                    <img
                      src={img} alt={title}
                      style={{
                        width: '100%', height: 200, objectFit: 'cover',
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                      }}
                    />
                    <div style={{ padding: '20px 22px 24px' }}>
                      <h3 style={{ fontFamily: FONT_HEADING, fontSize: 17, fontWeight: 700, color: 'rgba(255,255,255,0.85)', marginBottom: 8 }}>{title}</h3>
                      <p style={{ fontSize: 12, lineHeight: 1.7, color: 'rgba(255,255,255,0.7)' }}>{body}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* ── THE SOLUTION ────────────────────────────── */}
          <section style={{ padding: '80px 32px', position: 'relative' }}>
            <div style={{ maxWidth: 1080, margin: '0 auto' }}>
              <motion.div
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                style={{ marginBottom: 48 }}
              >
                <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.4em', textTransform: 'uppercase', color: 'rgba(45,212,191,0.6)' }}>💡 The Solution</span>
                <h2 style={{ fontFamily: FONT_HEADING, fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: 900, marginTop: 12, lineHeight: 1.15, maxWidth: 640 }}>
                  An AI trainer that <span style={{ color: '#2dd4bf' }}>never leaves</span> the OR.
                </h2>
                <p style={{ marginTop: 16, fontSize: 14, color: 'rgba(255,255,255,0.7)', maxWidth: 560, lineHeight: 1.7 }}>
                  SurgeonAI uses a live camera, a real scalpel, and a computer-vision pipeline to
                  guide trainees through precise surgical procedures — measuring every angle, flagging every deviation, in real time.
                </p>
              </motion.div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
                {/* Pixel sprite sheet */}
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  style={{
                    borderRadius: 10, overflow: 'hidden',
                    border: '1px solid rgba(45,212,191,0.22)',
                    background: 'linear-gradient(180deg, rgba(9,14,26,0.92) 0%, rgba(6,10,20,0.95) 100%)',
                    padding: 0,
                    boxShadow: '0 0 0 1px rgba(45,212,191,0.08) inset, 0 18px 38px rgba(0,0,0,0.45)',
                  }}
                >
                  <img src="/assets/pixel_medical.png" alt="Medical pixel sprites" style={{ width: '100%', display: 'block' }} />
                </motion.div>

                {/* Pixel mission panel */}
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 14,
                  justifyContent: 'center',
                  borderRadius: 10,
                  border: '1px solid rgba(45,212,191,0.2)',
                  background: 'linear-gradient(180deg, rgba(9,14,26,0.9) 0%, rgba(7,11,21,0.96) 100%)',
                  boxShadow: '0 0 0 1px rgba(45,212,191,0.08) inset',
                  padding: '14px',
                  position: 'relative',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'repeating-linear-gradient(180deg, rgba(45,212,191,0.04) 0, rgba(45,212,191,0.04) 1px, transparent 1px, transparent 8px)',
                    pointerEvents: 'none',
                  }} />
                  <div style={{
                    position: 'relative',
                    zIndex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderBottom: '1px solid rgba(45,212,191,0.18)',
                    paddingBottom: 10,
                    marginBottom: 4,
                  }}>
                    <p style={{
                      margin: 0,
                      fontFamily: FONT_HEADING,
                      fontSize: 14,
                      letterSpacing: '0.14em',
                      textTransform: 'uppercase',
                      color: 'rgba(167,243,208,0.95)',
                    }}>
                      Mission Modules
                    </p>
                    <span style={{
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: '0.2em',
                      color: 'rgba(45,212,191,0.8)',
                    }}>
                      v1.0
                    </span>
                  </div>
                  {[
                    { glyph: '[AIM]', label: 'Real-Time Angle Tracking', desc: 'CV measures scalpel approach angle frame-by-frame against ideal 30–60° incision vector.', tone: '#f87171' },
                    { glyph: '[VOX]', label: 'AI Voice Coaching', desc: 'ElevenLabs TTS issues live verbal guidance — like a senior surgeon in your ear.', tone: '#2dd4bf' },
                    { glyph: '[SEQ]', label: '6-Phase State Machine', desc: 'Rigid protocol enforces correct procedural sequence, not just technique.', tone: '#a78bfa' },
                    { glyph: '[CAM]', label: 'Zero Extra Hardware', desc: 'No AR headset. No haptic gloves. Just a camera, a scalpel, and SurgeonAI.', tone: '#67e8f9' },
                  ].map(({ glyph, label, desc, tone }, i) => (
                    <motion.div
                      key={label}
                      initial={{ opacity: 0, x: -15 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.08 }}
                      style={{
                        position: 'relative',
                        zIndex: 1,
                        display: 'grid',
                        gridTemplateColumns: '82px 1fr',
                        gap: 10,
                        alignItems: 'start',
                        border: '1px solid rgba(255,255,255,0.08)',
                        background: 'rgba(4,8,16,0.78)',
                        borderRadius: 8,
                        padding: '10px 11px',
                      }}
                    >
                      <span style={{
                        fontFamily: FONT_BODY,
                        fontSize: 11,
                        fontWeight: 700,
                        letterSpacing: '0.1em',
                        color: tone,
                        border: `1px solid ${tone}55`,
                        background: `${tone}1A`,
                        borderRadius: 6,
                        padding: '5px 6px',
                        textAlign: 'center',
                        marginTop: 2,
                      }}>{glyph}</span>
                      <div>
                        <p style={{
                          fontFamily: FONT_HEADING,
                          fontSize: 14,
                          fontWeight: 700,
                          color: 'rgba(238,255,252,0.9)',
                          marginBottom: 4,
                          textTransform: 'uppercase',
                          letterSpacing: '0.03em',
                        }}>{label}</p>
                        <p style={{ fontSize: 12, color: 'rgba(195,214,225,0.65)', lineHeight: 1.6 }}>{desc}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* ── OPEN SOURCE HARDWARE ────────────────────── */}
          <section style={{ padding: '80px 32px', position: 'relative', background: 'rgba(255,255,255,0.015)', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
            <div style={{ maxWidth: 1080, margin: '0 auto', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 48 }}>
              {/* Text Side */}
              <div style={{ flex: '1 1 400px' }}>
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                >
                  <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.4em', textTransform: 'uppercase', color: 'rgba(167,139,250,0.8)' }}>🌍 Open Source Hardware</span>
                  <h2 style={{ fontFamily: FONT_HEADING, fontSize: 'clamp(28px, 4vw, 42px)', fontWeight: 900, marginTop: 12, lineHeight: 1.15 }}>
                    Democratizing Surgical <span style={{ color: '#a78bfa' }}>Training.</span>
                  </h2>
                  <p style={{ marginTop: 16, fontSize: 14, color: 'rgba(255,255,255,0.7)', lineHeight: 1.7 }}>
                    The physical SurgeonAI mount is entirely open-source. Anyone with a 3D printer and less than $25 can build our hardware at home or in a clinical setting.
                  </p>
                  <p style={{ marginTop: 12, fontSize: 14, color: 'rgba(255,255,255,0.7)', lineHeight: 1.7 }}>
                    By removing expensive hardware barriers, we enable doctors and medical students in the third world to access our surgical platform without massive overhead costs.
                  </p>

                  <motion.div
                    initial={{ opacity: 0, y: 15 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.2 }}
                    style={{ marginTop: 28 }}
                  >
                    <a
                      href="#"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 8,
                        padding: '12px 24px', borderRadius: 12,
                        border: '1px solid rgba(167,139,250,0.3)',
                        background: 'rgba(167,139,250,0.1)',
                        color: 'rgba(167,139,250,0.95)',
                        fontFamily: FONT_HEADING, fontSize: 12, fontWeight: 700, letterSpacing: '0.1em',
                        textDecoration: 'none', textTransform: 'uppercase',
                        transition: 'all 0.3s ease',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(167,139,250,0.2)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(167,139,250,0.1)'; }}
                    >
                      <span>💾 Get the CAD Files</span>
                    </a>
                  </motion.div>
                </motion.div>
              </div>

              {/* CAD Model Image Side */}
              <div style={{ flex: '1 1 400px', display: 'flex', justifyContent: 'center' }}>
                <motion.div
                  initial={{ opacity: 0, scale: 0.9, y: 20 }}
                  whileInView={{ opacity: 1, scale: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.2 }}
                  style={{
                    position: 'relative',
                    width: '100%',
                    maxWidth: 500,
                    borderRadius: 20,
                    border: '1px solid rgba(167,139,250,0.2)',
                    background: 'linear-gradient(135deg, rgba(167,139,250,0.05), rgba(45,212,191,0.02))',
                    padding: 4,
                    boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
                  }}
                >
                  <img src={cadModelImg} alt="Hardware CAD Model" style={{ width: '100%', borderRadius: 16, display: 'block', objectFit: 'contain', backgroundColor: 'rgba(0,0,0,0.2)' }} />
                  <div style={{
                    position: 'absolute', top: 16, right: 16,
                    padding: '4px 8px', borderRadius: 6,
                    background: 'rgba(8,8,13,0.8)', backdropFilter: 'blur(4px)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.8)',
                    letterSpacing: '0.1em', textTransform: 'uppercase'
                  }}>
                    Model v1.0
                  </div>
                </motion.div>
              </div>
            </div>
          </section>

          {/* ── BUILT WITH ──────────────────────────────── */}
          <section style={{
            padding: '56px 32px',
            borderTop: '1px solid rgba(255,255,255,0.04)',
            textAlign: 'center',
          }}>
            <div style={{ maxWidth: 900, margin: '0 auto' }}>
              <motion.p
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.35em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.2)', marginBottom: 24 }}
              >
                Built With
              </motion.p>
              <motion.div
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 10 }}
              >
                {TECH_STACK.map(({ name, url }) => (
                  <a
                    key={name}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      padding: '10px 18px', borderRadius: 12,
                      border: '1px solid rgba(255,255,255,0.06)',
                      background: 'rgba(255,255,255,0.02)',
                      fontSize: 11, fontWeight: 600, letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      color: 'rgba(255,255,255,0.35)',
                      textDecoration: 'none',
                      transition: 'all 0.3s ease',
                    }}
                    onMouseEnter={(e) => { e.target.style.color = '#2dd4bf'; e.target.style.borderColor = 'rgba(45,212,191,0.3)'; }}
                    onMouseLeave={(e) => { e.target.style.color = 'rgba(255,255,255,0.35)'; e.target.style.borderColor = 'rgba(255,255,255,0.06)'; }}
                  >
                    {name}
                  </a>
                ))}
              </motion.div>
            </div>
          </section>

          {/* ── FOOTER CTA ──────────────────────────────── */}
          <section style={{ padding: '80px 32px', textAlign: 'center' }}>
            <div style={{ maxWidth: 560, margin: '0 auto' }}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <img
                  src="/assets/pixel_robot.png" alt=""
                  style={{ width: 72, height: 72, margin: '0 auto 24px', borderRadius: 14, filter: 'drop-shadow(0 0 25px rgba(45,212,191,0.3))' }}
                />
                <h2 style={{ fontFamily: FONT_HEADING, fontSize: 'clamp(26px, 3.5vw, 40px)', fontWeight: 900, marginBottom: 12 }}>
                  Ready to <GlitchText><span style={{ color: '#2dd4bf' }}>operate?</span></GlitchText>
                </h2>
                <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', marginBottom: 32 }}>
                  Pick up your scalpel. The AI is watching.
                </p>
                <motion.button
                  whileHover={{ scale: 1.04, boxShadow: '0 0 60px rgba(45,212,191,0.4)' }}
                  whileTap={{ scale: 0.96 }}
                  onClick={handleEnter}
                  style={{
                    padding: '16px 40px', borderRadius: 16, border: 'none',
                    fontFamily: FONT_HEADING, fontWeight: 700,
                    fontSize: 14, letterSpacing: '0.2em', textTransform: 'uppercase',
                    color: '#08080d', cursor: 'pointer',
                    background: 'linear-gradient(135deg, #2dd4bf 0%, #a78bfa 100%)',
                    boxShadow: '0 4px 40px rgba(45,212,191,0.3)',
                  }}
                >
                  ▶ Launch SurgeonAI
                </motion.button>
              </motion.div>
            </div>
          </section>

          {/* ── FOOTER CREDITS ──────────────────────────── */}
          <div style={{
            padding: '24px 32px',
            borderTop: '1px solid rgba(255,255,255,0.04)',
            textAlign: 'center',
          }}>
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', fontWeight: 500, marginBottom: 6 }}>
              This application was built by <strong style={{ color: 'rgba(255,255,255,0.5)' }}>Faizan Khan</strong>,{' '}
              <strong style={{ color: 'rgba(255,255,255,0.5)' }}>Rabuor Tindi</strong>, and{' '}
              <strong style={{ color: 'rgba(255,255,255,0.5)' }}>Suess Luna</strong>
            </p>
            <p style={{ fontSize: 9, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.1)', marginTop: 8 }}>
              SurgeonAI · v0.1.0
            </p>
          </div>
        </motion.div>
      ) : (
        /* ── Transition screen ── */
        <motion.div
          key="transition"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: '#08080d',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <Scanlines />
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}
          >
            <motion.img
              src="/assets/pixel_robot.png" alt=""
              style={{ width: 56, height: 56, borderRadius: 12 }}
              animate={{ y: [0, -6, 0] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            />
            <div style={{ width: 180, height: 3, background: 'rgba(255,255,255,0.05)', borderRadius: 99, overflow: 'hidden' }}>
              <motion.div
                initial={{ width: '0%' }}
                animate={{ width: '100%' }}
                transition={{ duration: 0.8, ease: 'easeInOut' }}
                style={{ height: '100%', borderRadius: 99, background: 'linear-gradient(90deg, #2dd4bf, #a78bfa)' }}
              />
            </div>
            <motion.p
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1.2, repeat: Infinity }}
              style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.3em', textTransform: 'uppercase', color: '#2dd4bf' }}
            >
              Booting SurgeonAI...
            </motion.p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
