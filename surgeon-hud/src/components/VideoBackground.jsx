import { useState } from 'react';
import { getApiBase } from '../config';
import { log } from '../lib/logger';

export default function VideoBackground() {
  const [imgError, setImgError] = useState(false);
  const base = getApiBase();
  const src = `${base}/video`;

  return (
    <>
      <img
        src={src}
        alt="Live surgical feed (MJPEG from backend)"
        className="absolute top-0 left-0 z-0 h-screen w-screen object-cover"
        onError={() => {
          log.bad(`MJPEG /video failed to load — ${src}`);
          setImgError(true);
        }}
      />
      {imgError && (
        <div className="absolute inset-0 z-[5] flex flex-col items-center justify-center bg-black/90 px-6 text-center">
          <p className="font-mono text-sm text-red-400/90">Could not load live feed</p>
          <p className="mt-2 max-w-md font-mono text-xs leading-relaxed text-gray-500">
            Requested <code className="text-gray-300">{src}</code>. Start the backend, set{' '}
            <code className="text-gray-300">VITE_API_BASE</code> to the same host/port as{' '}
            <code className="text-gray-300">PORT</code>, and ensure the camera opens (see{' '}
            <code className="text-gray-300">CAMERA_INDEX</code> on Windows).
          </p>
        </div>
      )}
    </>
  );
}
