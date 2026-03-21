import { useHudStore } from '../store/useHudStore';

export default function StepTracker() {
  const currentStep = useHudStore((state) => state.currentStep);

  return (
    <div className="absolute top-6 left-6 z-10">
      <div className="px-6 py-3 rounded-xl bg-black/60 backdrop-blur-md border border-green-500/30 shadow-[0_0_15px_rgba(34,197,94,0.2)]">
        <h2 className="text-xl font-bold tracking-wide text-green-400 uppercase">
          {currentStep}
        </h2>
      </div>
    </div>
  );
}
