import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';

// ── Animated ECG / heartbeat path ──────────────────────────────────────────
function ECGLine({ className }) {
  return (
    <svg className={`${className} overflow-visible`} viewBox="0 0 400 60" fill="none">
      <motion.polyline
        points="0,30 40,30 55,10 70,50 85,30 100,30 115,5 130,55 145,30 400,30"
        stroke="url(#ecgGrad)"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 2, ease: 'easeInOut', delay: 0.5 }}
      />
      <defs>
        <linearGradient id="ecgGrad" x1="0" y1="0" x2="400" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0d9488" stopOpacity="0" />
          <stop offset="40%" stopColor="#2dd4bf" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#14b8a6" stopOpacity="0.2" />
        </linearGradient>
      </defs>
    </svg>
  );
}

// ── Animated number counter ────────────────────────────────────────────────
function CountUp({ from, to, suffix = '', duration = 2 }) {
  const [val, setVal] = useState(from);
  useEffect(() => {
    let start = null;
    const step = (ts) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / (duration * 1000), 1);
      setVal(Math.round(from + (to - from) * progress));
      if (progress < 1) requestAnimationFrame(step);
    };
    const raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [from, to, duration]);
  return <>{val}{suffix}</>;
}

// ── Floating grid dot ──────────────────────────────────────────────────────
function GridBackground() {
  return (
    <div
      className="absolute inset-0 pointer-events-none"
      style={{
        backgroundImage: `
          linear-gradient(rgba(45,212,191,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(45,212,191,0.04) 1px, transparent 1px)`,
        backgroundSize: '48px 48px',
      }}
    />
  );
}

// ── Stat card ──────────────────────────────────────────────────────────────
function StatCard({ number, suffix, label, delay }) {
  const [inView, setInView] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold: 0.3 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay, duration: 0.6 }}
      className="flex flex-col items-center gap-2 px-8 py-6 rounded-2xl border border-teal-500/15 bg-teal-950/10 backdrop-blur-sm"
    >
      <span
        className="text-5xl font-bold font-mono tabular-nums"
        style={{ color: '#2dd4bf', textShadow: '0 0 30px rgba(45,212,191,0.4)' }}
      >
        {inView ? <CountUp from={0} to={number} suffix={suffix} duration={2} /> : `0${suffix}`}
      </span>
      <span className="text-xs font-mono tracking-[0.2em] text-white/40 uppercase text-center max-w-[140px] leading-relaxed">
        {label}
      </span>
    </motion.div>
  );
}

// ── Problem card ───────────────────────────────────────────────────────────
function ProblemCard({ icon, title, body, delay }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay, duration: 0.6 }}
      className="flex flex-col gap-4 p-6 rounded-2xl border border-white/5 bg-white/[0.02] backdrop-blur-sm hover:border-teal-500/20 transition-colors duration-500 group"
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
        style={{ background: 'rgba(45,212,191,0.08)', border: '1px solid rgba(45,212,191,0.15)' }}
      >
        {icon}
      </div>
      <h3 className="text-base font-semibold text-white/80 group-hover:text-white transition-colors">{title}</h3>
      <p className="text-sm text-white/35 leading-relaxed group-hover:text-white/50 transition-colors">{body}</p>
    </motion.div>
  );
}

// ── Main Landing Page ──────────────────────────────────────────────────────
export default function LandingPage({ onEnter }) {
  const [entering, setEntering] = useState(false);

  const handleEnter = () => {
    setEntering(true);
    setTimeout(() => onEnter(), 800);
  };

  return (
    <AnimatePresence>
      {!entering ? (
        <motion.div
          key="landing"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 1.03 }}
          transition={{ duration: 0.7, ease: 'easeInOut' }}
          className="fixed inset-0 z-[200] bg-[#020d0c] overflow-y-auto overflow-x-hidden"
          style={{ fontFamily: "'Inter', system-ui, sans-serif" }}
        >
          <GridBackground />

          {/* Ambient radial glow */}
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] pointer-events-none"
            style={{
              background: 'radial-gradient(ellipse at center top, rgba(20,184,166,0.12) 0%, transparent 70%)',
            }}
          />

          {/* ─── NAVBAR ─── */}
          <nav className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 border-b border-white/[0.04] bg-[#020d0c]/80 backdrop-blur-xl">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5 }}
              className="flex items-center gap-2"
            >
              {/* Cross icon */}
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <rect x="8.5" y="2" width="3" height="16" rx="1.5" fill="#2dd4bf" />
                <rect x="2" y="8.5" width="16" height="3" rx="1.5" fill="#2dd4bf" />
              </svg>
              <span className="text-base font-bold tracking-[0.15em] text-white font-mono">
                SURGEON<span style={{ color: '#2dd4bf' }}>AI</span>
              </span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="flex items-center gap-2"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
              <span className="text-[10px] font-mono tracking-[0.3em] text-teal-400/70 uppercase">Live Demo Active</span>
            </motion.div>
          </nav>

          {/* ─── HERO ─── */}
          <section className="relative flex flex-col items-center justify-center min-h-[90vh] px-6 text-center pt-12 pb-8">
            {/* ECG line header decoration */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="w-full max-w-md mb-8"
            >
              <ECGLine className="w-full h-12 opacity-60" />
            </motion.div>

            {/* Tag pill */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="inline-flex items-center gap-2 rounded-full border border-teal-500/25 bg-teal-500/5 px-4 py-1.5 mb-8"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
              <span className="text-xs font-mono tracking-[0.25em] text-teal-400 uppercase">
                Google Cloud × MLH Hackathon Build
              </span>
            </motion.div>

            {/* Hero headline */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.7 }}
              className="text-5xl sm:text-7xl font-bold leading-[1.1] tracking-tight text-white max-w-4xl mb-6"
            >
              The{' '}
              <span
                className="relative"
                style={{
                  color: '#2dd4bf',
                  textShadow: '0 0 60px rgba(45,212,191,0.4)',
                }}
              >
                surgical training
              </span>
              {' '}gap is a crisis.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.55, duration: 0.7 }}
              className="text-base sm:text-lg text-white/40 max-w-2xl mx-auto leading-relaxed mb-12"
            >
              There are far more surgical trainees than there are qualified trainers to guide them.
              Rotations are limited, repetitions are scarce, and patients pay the price.
              <br className="hidden sm:block" />
              <strong className="text-white/70"> SurgeonAI closes that gap — in real time.</strong>
            </motion.p>

            {/* CTA */}
            <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.7, type: 'spring', stiffness: 200 }}
              whileHover={{ scale: 1.04, boxShadow: '0 0 40px rgba(45,212,191,0.3)' }}
              whileTap={{ scale: 0.97 }}
              onClick={handleEnter}
              className="relative px-10 py-4 rounded-2xl font-mono font-semibold text-sm tracking-[0.2em] uppercase text-black cursor-pointer"
              style={{
                background: 'linear-gradient(135deg, #2dd4bf 0%, #14b8a6 100%)',
                boxShadow: '0 0 20px rgba(45,212,191,0.2)',
              }}
            >
              Launch Demo System
              <span className="ml-3 opacity-70">→</span>
            </motion.button>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.3 }}
              transition={{ delay: 1 }}
              className="mt-4 text-[10px] font-mono tracking-widest text-white/30 uppercase"
            >
              Requires camera access · Scalpel required for Phase 3+
            </motion.p>
          </section>

          {/* ─── STATS ─── */}
          <section className="relative px-6 pb-24 flex flex-col items-center">
            <div className="w-full max-w-5xl grid grid-cols-2 sm:grid-cols-4 gap-4">
              <StatCard number={1200} suffix="+" label="Surgical residents in the US training annually" delay={0} />
              <StatCard number={5} suffix="x" label="More trainees than senior consultant slots" delay={0.1} />
              <StatCard number={40} suffix="%" label="Reported insufficient hands-on training time" delay={0.2} />
              <StatCard number={0} suffix="ms" label="Reaction delay with SurgeonAI real-time feedback" delay={0.3} />
            </div>
          </section>

          {/* ─── PROBLEM ─── */}
          <section className="relative px-6 pb-24 flex flex-col items-center">
            <div className="w-full max-w-5xl">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-center mb-14"
              >
                <p className="text-xs font-mono tracking-[0.4em] text-teal-500/60 uppercase mb-3">The Problem</p>
                <h2 className="text-3xl sm:text-4xl font-bold text-white max-w-2xl mx-auto leading-snug">
                  Surgical skill is built through repetition.
                  <span className="text-white/35"> Repetition is not available.</span>
                </h2>
              </motion.div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <ProblemCard
                  icon="🏥"
                  title="Training Bottleneck"
                  body="One attending consultant supervises 5–10 residents simultaneously. Real hands-on guidance becomes impractical, rushed, or skipped entirely during high-pressure rotations."
                  delay={0}
                />
                <ProblemCard
                  icon="⏱️"
                  title="Limited Rotations"
                  body="OR slots are competitive. Trainees average just a fraction of the autonomous surgical time needed to build genuine procedural competence before practising on real patients."
                  delay={0.1}
                />
                <ProblemCard
                  icon="📉"
                  title="No Objective Feedback"
                  body="Existing simulation labs lack real-time haptic and angular precision feedback. Trainees cannot measure whether their technique is deviating from the optimal incision geometry."
                  delay={0.2}
                />
              </div>
            </div>
          </section>

          {/* ─── SOLUTION ─── */}
          <section className="relative px-6 pb-32 flex flex-col items-center">
            <div className="w-full max-w-5xl">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-center mb-14"
              >
                <p className="text-xs font-mono tracking-[0.4em] text-teal-500/60 uppercase mb-3">The Solution</p>
                <h2 className="text-3xl sm:text-4xl font-bold text-white max-w-2xl mx-auto leading-snug">
                  An AI trainer that never
                  <span style={{ color: '#2dd4bf' }}> leaves the OR.</span>
                </h2>
                <p className="mt-4 text-white/35 max-w-xl mx-auto text-sm leading-relaxed">
                  SurgeonAI uses a live camera, a real scalpel, and a computer-vision state machine to
                  guide trainees through precise surgical procedures — measuring every angle, flagging every deviation.
                </p>
              </motion.div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 items-start">
                {/* Feature list */}
                <div className="flex flex-col gap-5">
                  {[
                    { label: 'Real-Time Angle Tracking', desc: 'Computer vision measures your scalpel approach angle frame-by-frame against the ideal 30–60° incision vector.' },
                    { label: 'AI Voice Coaching', desc: 'ElevenLabs TTS issues live verbal guidance — just like a senior surgeon whispering in your ear.' },
                    { label: 'Phase-Locked State Machine', desc: 'A rigid 6-phase protocol ensures trainees follow correct procedural sequence, not just technique.' },
                    { label: 'Zero Hardware Required', desc: 'No AR headset. No haptic gloves. Just a camera, a scalpel, and SurgeonAI.' },
                  ].map(({ label, desc }, i) => (
                    <motion.div
                      key={label}
                      initial={{ opacity: 0, x: -20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.08 }}
                      className="flex gap-4 items-start"
                    >
                      <div
                        className="mt-1 w-5 h-5 rounded-full shrink-0 flex items-center justify-center"
                        style={{ background: 'rgba(45,212,191,0.12)', border: '1px solid rgba(45,212,191,0.25)' }}
                      >
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                          <path d="M2 5l2.5 2.5L8 2.5" stroke="#2dd4bf" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white/80 mb-1">{label}</p>
                        <p className="text-xs text-white/35 leading-relaxed">{desc}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>

                {/* Phase timeline */}
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6 }}
                  className="rounded-2xl border border-white/[0.06] bg-white/[0.015] backdrop-blur-sm p-6"
                >
                  <p className="text-[10px] font-mono tracking-[0.35em] text-teal-500/50 uppercase mb-5">6-Phase Protocol</p>
                  <div className="flex flex-col gap-3">
                    {[
                      ['Phase 0', 'Idle', 'Scanning environment'],
                      ['Phase 1', 'Target Acquired', 'Tissue site identified'],
                      ['Phase 2', 'Tool Tracking', 'Scalpel in hand detected'],
                      ['Phase 3', 'Incision', 'Live angle feedback active'],
                      ['Phase 4', 'Clamping', 'Hemostasis protocol'],
                      ['Phase 5', 'Complete', 'Procedure successful'],
                    ].map(([phase, name, desc], i) => (
                      <div key={phase} className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-[10px] font-mono font-bold"
                          style={{
                            background: i === 3 ? 'rgba(45,212,191,0.15)' : 'rgba(255,255,255,0.03)',
                            border: `1px solid ${i === 3 ? 'rgba(45,212,191,0.3)' : 'rgba(255,255,255,0.06)'}`,
                            color: i === 3 ? '#2dd4bf' : 'rgba(255,255,255,0.3)',
                          }}
                        >
                          {i}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs font-medium truncate ${i === 3 ? 'text-teal-300' : 'text-white/50'}`}>
                            {name}
                          </p>
                          <p className="text-[10px] text-white/20 truncate">{desc}</p>
                        </div>
                        {i < 5 && (
                          <div className="w-px h-3 bg-white/10 self-end -mb-3 ml-4 absolute" style={{ display: 'none' }} />
                        )}
                      </div>
                    ))}
                  </div>
                </motion.div>
              </div>
            </div>
          </section>

          {/* ─── FOOTER CTA ─── */}
          <section className="relative px-6 pb-24 flex flex-col items-center text-center border-t border-white/[0.04]">
            <div className="w-full max-w-2xl pt-20">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <ECGLine className="w-full h-10 opacity-40 mb-8" />
                <h2 className="text-3xl font-bold text-white mb-4">
                  Ready to train the next generation of surgeons?
                </h2>
                <p className="text-sm text-white/35 mb-8">
                  The demo is live. Pick up your scalpel.
                </p>
                <motion.button
                  whileHover={{ scale: 1.03, boxShadow: '0 0 50px rgba(45,212,191,0.3)' }}
                  whileTap={{ scale: 0.97 }}
                  onClick={handleEnter}
                  className="px-10 py-4 rounded-2xl font-mono font-semibold text-sm tracking-[0.2em] uppercase text-black cursor-pointer"
                  style={{ background: 'linear-gradient(135deg, #2dd4bf 0%, #14b8a6 100%)' }}
                >
                  Enter SurgeonAI →
                </motion.button>
              </motion.div>
            </div>
          </section>

          {/* Footer */}
          <div className="pb-8 text-center">
            <p className="text-[10px] font-mono tracking-widest text-white/15 uppercase">
              SurgeonAI · Built at Google Cloud × MLH Hackathon · v0.1.0
            </p>
          </div>
        </motion.div>
      ) : (
        <motion.div
          key="transition"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[200] bg-black flex items-center justify-center"
          transition={{ duration: 0.4 }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center gap-4"
          >
            <div className="w-64 h-[2px] bg-white/5 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: '0%' }}
                animate={{ width: '100%' }}
                transition={{ duration: 0.7, ease: 'easeInOut' }}
                className="h-full rounded-full"
                style={{ background: 'linear-gradient(90deg, #14b8a6, #2dd4bf)' }}
              />
            </div>
            <motion.p
              animate={{ opacity: [0.3, 0.9, 0.3] }}
              transition={{ duration: 1.2, repeat: Infinity }}
              className="text-xs font-mono tracking-[0.35em] uppercase"
              style={{ color: '#2dd4bf' }}
            >
              Initialising SurgeonAI
            </motion.p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
