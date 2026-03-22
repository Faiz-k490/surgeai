import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';

/* ═══════════════════════════════════════════════════════════════════════════
   SurgeonAI — Landing Page v4 (SUPER COLORFUL + PIXEL FONT)
   Pixel art + Outfit/Space Grotesk + Press Start 2P
   ═══════════════════════════════════════════════════════════════════════════ */

const FONT_HEADING = "'Outfit', sans-serif";
const FONT_BODY = "'Space Grotesk', sans-serif";
const FONT_PIXEL = "'Press Start 2P', cursive";

// ── Tech stack with links ──────────────────────────────────────────────────
const TECH_STACK = [
  { name: 'YOLOv8', url: 'https://docs.ultralytics.com/', color: '#2dd4bf' },
  { name: 'OpenCV', url: 'https://opencv.org/', color: '#3b82f6' },
  { name: 'Flask', url: 'https://flask.palletsprojects.com/', color: '#f59e0b' },
  { name: 'Socket.IO', url: 'https://socket.io/', color: '#a78bfa' },
  { name: 'React', url: 'https://react.dev/', color: '#61dafb' },
  { name: 'Vite', url: 'https://vitejs.dev/', color: '#ffbd00' },
  { name: 'ElevenLabs', url: 'https://elevenlabs.io/', color: '#ec4899' },
  { name: 'Google Cloud', url: 'https://cloud.google.com/', color: '#4285f4' },
  { name: 'Snowflake', url: 'https://www.snowflake.com/', color: '#29b6f6' },
  { name: 'MongoDB', url: 'https://www.mongodb.com/', color: '#4daf50' },
];

// ── Background Gradient Mesh ───────────────────────────────────────────────
function GradientMesh() {
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 0 }}>
      {/* Cyan orb */}
      <motion.div
        animate={{
          x: [0, 100, -50, 0],
          y: [0, -150, 50, 0],
          scale: [1, 1.2, 0.9, 1],
        }}
        transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        style={{
          position: 'absolute', top: '10%', left: '15%',
          width: 600, height: 600, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(45,212,191,0.15) 0%, transparent 70%)',
          filter: 'blur(80px)',
        }}
      />
      {/* Purple orb */}
      <motion.div
        animate={{
          x: [0, -120, 80, 0],
          y: [0, 100, -100, 0],
          scale: [1, 1.3, 0.8, 1],
        }}
        transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}
        style={{
          position: 'absolute', bottom: '15%', right: '10%',
          width: 700, height: 700, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(167,139,250,0.15) 0%, transparent 70%)',
          filter: 'blur(100px)',
        }}
      />
      {/* Pink orb */}
      <motion.div
        animate={{
          x: [0, 50, -80, 0],
          y: [0, 80, 120, 0],
        }}
        transition={{ duration: 18, repeat: Infinity, ease: 'linear' }}
        style={{
          position: 'absolute', top: '40%', left: '40%',
          width: 500, height: 500, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(244,114,182,0.1) 0%, transparent 70%)',
          filter: 'blur(120px)',
        }}
      />
    </div>
  );
}

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
  const pixels = Array.from({ length: 24 }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    delay: Math.random() * 6,
    duration: 6 + Math.random() * 10,
    size: 2 + Math.floor(Math.random() * 4),
    color: ['#2dd4bf', '#a78bfa', '#f472b6', '#67e8f9'][Math.floor(Math.random() * 4)],
  }));

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 1 }}>
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
function GlitchText({ children, color1 = '#a78bfa', color2 = '#2dd4bf' }) {
  return (
    <span style={{ position: 'relative', display: 'inline-block' }}>
      <span style={{ position: 'relative', zIndex: 1 }}>{children}</span>
      <motion.span
        style={{ position: 'absolute', top: 0, left: 0, color: color1, clipPath: 'inset(0 0 65% 0)', zIndex: 0, opacity: 0.6 }}
        animate={{ x: [0, -2, 2, 0], y: [0, 1, -1, 0] }}
        transition={{ duration: 0.3, repeat: Infinity, repeatDelay: 4 }}
        aria-hidden
      >{children}</motion.span>
      <motion.span
        style={{ position: 'absolute', top: 0, left: 0, color: color2, clipPath: 'inset(65% 0 0 0)', zIndex: 0, opacity: 0.6 }}
        animate={{ x: [0, 2, -2, 0], y: [0, -1, 1, 0] }}
        transition={{ duration: 0.3, repeat: Infinity, repeatDelay: 4, delay: 0.05 }}
        aria-hidden
      >{children}</motion.span>
    </span>
  );
}

// ── Animated counter ───────────────────────────────────────────────────────
function CountUp({ to, suffix = '', duration = 1.5 }) {
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
        position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 100, opacity: 0.03,
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.5) 2px, rgba(0,0,0,0.5) 4px)',
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
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, filter: 'blur(20px)', scale: 1.05 }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: '#04040a',
            overflowY: 'auto', overflowX: 'hidden',
            fontFamily: FONT_BODY,
            color: '#fff',
          }}
        >
          <GradientMesh />
          <Scanlines />
          <FloatingPixels />

          {/* ── NAVBAR ──────────────────────────────────── */}
          <nav style={{
            position: 'sticky', top: 0, zIndex: 60,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '16px 32px',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
            background: 'rgba(4,4,10,0.8)',
            backdropFilter: 'blur(24px)',
          }}>
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              style={{ display: 'flex', alignItems: 'center', gap: 12 }}
            >
              <motion.img
                src="/assets/pixel_robot.png" alt="SurgeonAI"
                style={{ width: 36, height: 36, borderRadius: 10, boxShadow: '0 0 20px rgba(45,212,191,0.4)' }}
                animate={{ rotate: [0, 5, -5, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
              />
              <span style={{ fontFamily: FONT_PIXEL, fontSize: 14, fontWeight: 'normal', letterSpacing: '0.05em' }}>
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
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 18px', borderRadius: 12,
                  border: '1px solid rgba(255,255,255,0.12)',
                  background: 'rgba(255,255,255,0.02)',
                  color: 'rgba(255,255,255,0.7)',
                  fontSize: 10, fontWeight: 600, fontFamily: FONT_PIXEL,
                  textDecoration: 'none',
                  transition: 'all 0.3s ease',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#a78bfa'; e.currentTarget.style.color = '#fff'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = 'rgba(255,255,255,0.7)'; }}
              >
                GITHUB
              </a>
            </motion.div>
          </nav>

          {/* ── HERO ────────────────────────────────────── */}
          <section style={{
            position: 'relative',
            display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center',
            minHeight: '90vh',
            padding: '64px 32px',
            gap: 60,
          }}>
            {/* Left text */}
            <div style={{ flex: '1 1 480px', maxWidth: 680, zIndex: 10 }}>
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 10,
                  padding: '8px 16px', borderRadius: 100, marginBottom: 32,
                  border: '1px solid rgba(167,139,250,0.3)',
                  background: 'linear-gradient(90deg, rgba(167,139,250,0.1), rgba(45,212,191,0.1))',
                  boxShadow: '0 0 20px rgba(167,139,250,0.1)',
                }}
              >
                <span style={{ fontSize: 14 }}>🏆</span>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#c4b5fd', textTransform: 'uppercase', fontFamily: FONT_PIXEL }}>
                  HACKATHON WINNER
                </span>
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.7 }}
                style={{
                  fontFamily: FONT_HEADING, fontSize: 'clamp(40px, 6vw, 84px)',
                  fontWeight: 900, lineHeight: 1.05,
                  letterSpacing: '-0.03em',
                  marginBottom: 28,
                }}
              >
                Surgeons need{' '}
                <GlitchText color1="#a78bfa" color2="#2dd4bf"><span style={{ color: '#2dd4bf' }}>practice.</span></GlitchText>
                <br />
                <span style={{ background: 'linear-gradient(90deg, #fff 0%, rgba(255,255,255,0.4) 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  Not enough trainers.
                </span>
              </motion.h1>

              {/* Terminal-typewriter subtitle */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                style={{
                  borderRadius: 16, border: '1px solid rgba(45,212,191,0.2)',
                  background: 'rgba(8,8,13,0.4)',
                  backdropFilter: 'blur(8px)',
                  padding: '18px 24px', marginBottom: 40,
                  fontFamily: FONT_BODY,
                  fontSize: 16, borderLeft: '4px solid #2dd4bf',
                }}
              >
                <span style={{ color: 'rgba(255,255,255,0.3)', marginRight: 10 }}>&gt;</span>
                <span style={{ color: '#2dd4bf', fontWeight: 500 }}>
                  <TypeWriter text="Augmented intelligence bridging the gap between theory and the operating room..." delay={1000} speed={30} />
                </span>
              </motion.div>

              {/* Main CTA */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.8 }}
                style={{ display: 'flex', flexWrap: 'wrap', gap: 20 }}
              >
                <motion.button
                  whileHover={{ scale: 1.05, boxShadow: '0 0 60px rgba(45,212,191,0.5)' }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleEnter}
                  style={{
                    padding: '20px 48px', borderRadius: 16, border: 'none',
                    fontFamily: FONT_PIXEL, fontWeight: 'normal',
                    fontSize: 13, letterSpacing: '0.05em',
                    color: '#04040a', cursor: 'pointer',
                    background: 'linear-gradient(135deg, #2dd4bf 0%, #a78bfa 100%)',
                    boxShadow: '0 8px 32px rgba(45,212,191,0.3)',
                    transition: 'box-shadow 0.3s ease',
                  }}
                >
                  LAUNCH DEMO
                </motion.button>
              </motion.div>
            </div>

            {/* Right: Mega Icon Section */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8, rotate: -3 }}
              animate={{ opacity: 1, scale: 1, rotate: 0 }}
              transition={{ delay: 0.5, type: 'spring', stiffness: 100 }}
              style={{ flexShrink: 0, position: 'relative' }}
            >
              <div style={{
                position: 'absolute', inset: -40,
                background: 'radial-gradient(circle, rgba(45,212,191,0.2) 0%, transparent 70%)',
                filter: 'blur(40px)', zIndex: 0,
              }} />
              <motion.img
                src="/assets/pixel_robot.png"
                alt="SurgeonAI Robot"
                style={{
                  width: 340, height: 340, borderRadius: 32,
                  border: '4px solid rgba(255,255,255,0.1)',
                  boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
                  position: 'relative', zIndex: 1,
                }}
                animate={{ y: [0, -15, 0] }}
                transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
              />
              <motion.div
                style={{
                  position: 'absolute', bottom: -15, right: -15, borderRadius: 16,
                  border: '1px solid rgba(167,139,250,0.4)',
                  background: 'rgba(4,4,10,0.95)',
                  backdropFilter: 'blur(12px)',
                  padding: '12px 20px', zIndex: 2,
                  boxShadow: '0 8px 20px rgba(0,0,0,0.4)',
                }}
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                <span style={{ fontSize: 10, fontWeight: 700, color: '#a78bfa', letterSpacing: '0.1em', fontFamily: FONT_PIXEL }}>
                  VER 0.8.0
                </span>
              </motion.div>
            </motion.div>
          </section>

          {/* ── STATS BAR (Integrated) ─────────────────── */}
          <section style={{
            margin: '0 32px', borderRadius: 32,
            background: 'linear-gradient(90deg, rgba(45,212,191,0.05), rgba(167,139,250,0.05))',
            border: '1px solid rgba(255,255,255,0.06)',
            padding: '48px 32px',
          }}>
            <div style={{ maxWidth: 1080, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 40, textAlign: 'center' }}>
              {[
                { n: 10, s: ' Residents', label: 'Per Supervising Surgeon', color: '#f87171' },
                { n: 85, s: '%', label: 'Trainees Request More Lab Access', color: '#60a5fa' },
                { n: 6, s: ' Stages', label: 'Procedural Protocol AI', color: '#2dd4bf' },
                { n: 33, s: 'ms', label: 'CV Loop Latency (Ultra-Low)', color: '#c084fc' },
              ].map(({ n, s, label, color }, i) => (
                <motion.div
                  key={label}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                >
                  <div style={{ fontFamily: FONT_HEADING, fontSize: 48, fontWeight: 900, color: color, marginBottom: 8, textShadow: `0 0 30px ${color}44` }}>
                    <CountUp to={n} suffix={s} />
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'rgba(255,255,255,0.4)', fontFamily: FONT_PIXEL }}>
                    {label}
                  </div>
                </motion.div>
              ))}
            </div>
          </section>

          {/* ── THE PROBLEM (Integrated visuals) ───────── */}
          <section style={{ padding: '120px 32px', position: 'relative' }}>
            <div style={{ maxWidth: 1120, margin: '0 auto' }}>
              <motion.div
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                style={{ marginBottom: 64, textAlign: 'center' }}
              >
                <div style={{
                  display: 'inline-block', padding: '6px 16px', borderRadius: 100,
                  background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)',
                  color: '#f87171', fontSize: 10, fontFamily: FONT_PIXEL, marginBottom: 20,
                }}>
                  CRITICAL FAILURE
                </div>
                <h2 style={{ fontFamily: FONT_HEADING, fontSize: 'clamp(32px, 5vw, 60px)', fontWeight: 900, lineHeight: 1.1 }}>
                  Surgical training is <span style={{ color: '#f87171' }}>obsolete.</span>
                </h2>
              </motion.div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 32 }}>
                {[
                  { img: '/assets/pixel_hospital.png', title: 'TRAINER SHORTAGE', body: 'One attending consultant supervises 5–10 residents. Real hands-on guidance becomes rushed or skipped entirely.', color: '#f87171' },
                  { img: '/assets/pixel_hourglass.png', title: 'LIMITED OR TIME', body: 'Trainees average a fraction of the autonomous hours needed. OR slots are competitive and scarce.', color: '#fb923c' },
                  { img: '/assets/pixel_nodata.png', title: 'ZERO FEEDBACK', body: 'No precision metrics. Trainees cannot measure whether their technique deviates from optimal geometry.', color: '#facc15' },
                ].map(({ img, title, body, color }, i) => (
                  <motion.div
                    key={title}
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.15 }}
                    style={{
                      borderRadius: 24, overflow: 'hidden',
                      border: '1px solid rgba(255,255,255,0.08)',
                      background: 'rgba(255,255,255,0.02)',
                      transition: 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
                    }}
                    whileHover={{ scale: 1.02, borderColor: `${color}66`, background: 'rgba(255,255,255,0.04)' }}
                  >
                    <div style={{ position: 'relative' }}>
                      <img src={img} alt={title} style={{ width: '100%', height: 240, objectFit: 'cover' }} />
                      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 80, background: 'linear-gradient(to top, rgba(4,4,10,1), transparent)' }} />
                    </div>
                    <div style={{ padding: '24px 28px 32px' }}>
                      <h3 style={{ fontFamily: FONT_PIXEL, fontSize: 13, color: color, marginBottom: 16 }}>{title}</h3>
                      <p style={{ fontSize: 15, lineHeight: 1.7, color: 'rgba(255,255,255,0.4)', fontWeight: 400 }}>{body}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* ── THE SOLUTION (Full Color Integration) ───── */}
          <section style={{ padding: '120px 32px', position: 'relative', background: 'rgba(45,212,191,0.02)' }}>
            <div style={{ maxWidth: 1120, margin: '0 auto' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 64, alignItems: 'center' }}>
                <div style={{ flex: '1 1 480px' }}>
                  <div style={{
                    display: 'inline-block', padding: '6px 16px', borderRadius: 100,
                    background: 'rgba(45,212,191,0.1)', border: '1px solid rgba(45,212,191,0.3)',
                    color: '#2dd4bf', fontSize: 10, fontFamily: FONT_PIXEL, marginBottom: 24,
                  }}>
                    SYSTEM UPGRADE
                  </div>
                  <h2 style={{ fontFamily: FONT_HEADING, fontSize: 'clamp(32px, 5vw, 56px)', fontWeight: 900, lineHeight: 1.1, marginBottom: 24 }}>
                    An AI mentor that<br />
                    <span style={{ color: '#2dd4bf' }}>never closes</span> its eyes.
                  </h2>
                  <p style={{ fontSize: 18, lineHeight: 1.7, color: 'rgba(255,255,255,0.5)', marginBottom: 48 }}>
                    SurgeonAI bridges the gap with a hyper-accurate computer-vision pipeline that monitors, measures, and coaches in real time.
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
                    {[
                      { icon: '🎯', label: 'PRECISE METRICS', desc: 'Real-time angle tracking against 30–60° ideal vector.', color: '#2dd4bf' },
                      { icon: '🔊', label: 'VOICE GUIDANCE', desc: 'ElevenLabs AI feedback directly into your headset.', color: '#a78bfa' },
                      { icon: '🧬', label: 'PHASE PROTOCOL', desc: '6-stage state machine ensures total procedure safety.', color: '#f472b6' },
                      { icon: '🛰️', label: 'EDGE PROCESSING', desc: 'Ultralytics YOLOv8 loops at 30fps with 0ms delay.', color: '#3b82f6' },
                    ].map((feat, i) => (
                      <motion.div
                        key={feat.label}
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: i * 0.1 }}
                        style={{ display: 'flex', gap: 20, alignItems: 'start' }}
                      >
                        <div style={{
                          width: 48, height: 48, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: `${feat.color}15`, border: `1px solid ${feat.color}33`, fontSize: 24, boxShadow: `0 0 20px ${feat.color}11`
                        }}>
                          {feat.icon}
                        </div>
                        <div>
                          <h4 style={{ fontFamily: FONT_PIXEL, fontSize: 11, color: feat.color, marginBottom: 6 }}>{feat.label}</h4>
                          <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.3)', lineHeight: 1.6 }}>{feat.desc}</p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>

                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  style={{ flex: '1 1 400px', maxWidth: 500, position: 'relative' }}
                >
                  <div style={{ position: 'absolute', inset: -30, background: 'radial-gradient(circle, rgba(167,139,250,0.15), transparent 70%)', filter: 'blur(30px)', zIndex: 0 }} />
                  <img
                    src="/assets/pixel_medical.png"
                    alt="System Icons"
                    style={{
                      width: '100%', borderRadius: 32, border: '1px solid rgba(255,255,255,0.1)',
                      boxShadow: '0 30px 60px rgba(0,0,0,0.6)', position: 'relative', zIndex: 1,
                    }}
                  />
                  <div style={{
                    position: 'absolute', top: 20, right: 20, zIndex: 2,
                    padding: '8px 14px', borderRadius: 8, background: '#04040a', border: '1px solid rgba(255,255,255,0.1)',
                    fontFamily: FONT_PIXEL, fontSize: 8, color: '#2dd4bf',
                  }}>
                    SPRITE_PK_v4
                  </div>
                </motion.div>
              </div>
            </div>
          </section>

          {/* ── BUILT WITH (Colorful Badges) ────────────── */}
          <section style={{ padding: '80px 32px', textAlign: 'center' }}>
            <div style={{ maxWidth: 1000, margin: '0 auto' }}>
              <h2 style={{ fontFamily: FONT_PIXEL, fontSize: 12, color: 'rgba(255,255,255,0.2)', letterSpacing: '0.4em', marginBottom: 48 }}>
                BUILT WITH
              </h2>
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 14 }}>
                {TECH_STACK.map((tech, i) => (
                  <motion.a
                    key={tech.name}
                    href={tech.url}
                    target="_blank"
                    rel="noreferrer"
                    initial={{ opacity: 0, scale: 0.9 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    style={{
                      padding: '12px 24px', borderRadius: 14,
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      fontFamily: FONT_HEADING, fontWeight: 700, fontSize: 13,
                      color: 'rgba(255,255,255,0.4)', textDecoration: 'none',
                      transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = `${tech.color}15`;
                      e.currentTarget.style.borderColor = `${tech.color}55`;
                      e.currentTarget.style.color = '#fff';
                      e.currentTarget.style.transform = 'translateY(-4px)';
                      e.currentTarget.style.boxShadow = `0 10px 40px ${tech.color}22`;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                      e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                      e.currentTarget.style.color = 'rgba(255,255,255,0.4)';
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    {tech.name}
                  </motion.a>
                ))}
              </div>
            </div>
          </section>

          {/* ── FOOTER CTA (Colorful) ───────────────────── */}
          <section style={{ padding: '120px 32px 160px', textAlign: 'center', position: 'relative' }}>
            {/* Mega glow */}
            <div style={{
              position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)',
              width: '100%', height: '100%', background: 'radial-gradient(circle, rgba(167,139,250,0.08) 0%, transparent 60%)',
              pointerEvents: 'none',
            }} />

            <div style={{ maxWidth: 800, margin: '0 auto', position: 'relative', zIndex: 1 }}>
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <motion.img
                  src="/assets/pixel_robot.png" alt=""
                  style={{ width: 100, height: 100, margin: '0 auto 32px', borderRadius: 24, boxShadow: '0 0 40px rgba(167,139,250,0.4)' }}
                  animate={{ y: [0, -10, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
                />
                <h2 style={{ fontFamily: FONT_HEADING, fontSize: 'clamp(36px, 6vw, 72px)', fontWeight: 900, marginBottom: 20 }}>
                  Ready to <GlitchText color1="#2dd4bf" color2="#f472b6"><span style={{ color: '#2dd4bf' }}>operate?</span></GlitchText>
                </h2>
                <p style={{ fontSize: 20, color: 'rgba(255,255,255,0.4)', marginBottom: 48, maxWidth: 500, marginInline: 'auto' }}>
                  The surgical theater of the future is open. Access the HUD now.
                </p>

                <motion.button
                  whileHover={{ scale: 1.05, boxShadow: '0 0 80px rgba(45,212,191,0.6)' }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleEnter}
                  style={{
                    padding: '24px 64px', borderRadius: 20, border: 'none',
                    fontFamily: FONT_PIXEL, fontWeight: 'normal',
                    fontSize: 16, letterSpacing: '0.05em',
                    color: '#04040a', cursor: 'pointer',
                    background: 'linear-gradient(135deg, #2dd4bf 0%, #a78bfa 100%)',
                    boxShadow: '0 10px 40px rgba(45,212,191,0.4)',
                  }}
                >
                  ENTER HUD
                </motion.button>
              </motion.div>
            </div>
          </section>

          {/* ── FOOTER CREDITS (Premium) ────────────────── */}
          <footer style={{
            padding: '48px 32px',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            textAlign: 'center', background: 'rgba(0,0,0,0.2)',
          }}>
            <div style={{ maxWidth: 1000, margin: '0 auto' }}>
              <p style={{ fontFamily: FONT_PIXEL, fontSize: 8, color: 'rgba(255,255,255,0.15)', letterSpacing: '0.2em', marginBottom: 24 }}>
                DESIGNED & ENGINEERED FOR THE FUTURE OF MEDICINE
              </p>
              <p style={{ fontFamily: FONT_BODY, fontSize: 15, color: 'rgba(255,255,255,0.3)', marginBottom: 8 }}>
                Built by <span style={{ color: '#2dd4bf', fontWeight: 600 }}>Faizan Khan</span> · <span style={{ color: '#a78bfa', fontWeight: 600 }}>Rabuor Tindi</span> · <span style={{ color: '#f472b6', fontWeight: 600 }}>Suess Luna</span>
              </p>
              <div style={{ height: 1, width: 60, background: 'rgba(255,255,255,0.1)', margin: '24px auto' }} />
              <p style={{ fontFamily: FONT_PIXEL, fontSize: 8, color: 'rgba(255,255,255,0.1)', letterSpacing: '0.5em' }}>
                SURGEONAI © 2026. ALL RIGHTS RESERVED.
              </p>
            </div>
          </footer>
        </motion.div>
      ) : (
        /* ── Transition screen ── */
        <motion.div
          key="transition"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 300,
            background: '#04040a',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <Scanlines />
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 32 }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
              style={{ padding: 4, borderRadius: '50%', background: 'linear-gradient(45deg, #2dd4bf, #a78bfa)' }}
            >
              <img src="/assets/pixel_robot.png" alt="" style={{ width: 80, height: 80, borderRadius: '50%' }} />
            </motion.div>
            <div style={{ width: 200, height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 99, overflow: 'hidden' }}>
              <motion.div
                initial={{ width: '0%' }}
                animate={{ width: '100%' }}
                transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                style={{ height: '100%', borderRadius: 99, background: 'linear-gradient(90deg, #2dd4bf, #a78bfa)' }}
              />
            </div>
            <motion.p
              fontFamily={FONT_PIXEL}
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 1, repeat: Infinity }}
              style={{ fontSize: 10, letterSpacing: '0.4em', color: '#2dd4bf' }}
            >
              INITIATING...
            </motion.p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
