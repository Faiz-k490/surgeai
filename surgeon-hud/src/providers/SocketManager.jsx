/* eslint-disable react/prop-types */
import { useCallback, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import { getApiBase, getSocketUrl } from '../config';
import { log } from '../lib/logger';
import { useHudStore } from '../store/useHudStore';

function unwrap(data) {
  return data?.payload ?? data;
}

function chooseMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'];
  return candidates.find((candidate) => window.MediaRecorder?.isTypeSupported?.(candidate)) || '';
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = String(reader.result || '');
      const [, b64 = ''] = result.split(',');
      resolve(b64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function computeLevel(analyser, dataArray) {
  analyser.getByteTimeDomainData(dataArray);
  let sum = 0;
  for (let i = 0; i < dataArray.length; i += 1) {
    const normalized = (dataArray[i] - 128) / 128;
    sum += normalized * normalized;
  }
  return Math.sqrt(sum / dataArray.length);
}

export default function SocketManager({ children }) {
  const setIsConnected = useHudStore((s) => s.setIsConnected);
  const setMetrics = useHudStore((s) => s.setMetrics);
  const applyFrameState = useHudStore((s) => s.applyFrameState);
  const activationRequested = useHudStore((s) => s.activationRequested);
  const consumeActivationRequest = useHudStore((s) => s.consumeActivationRequest);
  const manualCaptureRequested = useHudStore((s) => s.manualCaptureRequested);
  const consumeManualCaptureRequest = useHudStore((s) => s.consumeManualCaptureRequest);
  const setMicPermission = useHudStore((s) => s.setMicPermission);

  const socketRef = useRef(null);
  const streamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const triggerKindRef = useRef('auto');
  const recordingSinceRef = useRef(0);
  const silenceSinceRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const levelArrayRef = useRef(null);
  const levelIntervalRef = useRef(null);
  const playbackAudioRef = useRef(null);
  const lastPlayedVoiceIdRef = useRef(null);
  const micPromiseRef = useRef(null);

  useEffect(() => {
    const socket = io(getSocketUrl(), {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      upgrade: true,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setIsConnected(true);
      log.ok(`Socket.IO connected - ${getSocketUrl()}`);
      if (useHudStore.getState().activationRequested) {
        socket.emit('activate_surgeai');
        useHudStore.getState().consumeActivationRequest();
      }
    });

    socket.on('disconnect', (reason) => {
      setIsConnected(false);
      log.warn(`Socket.IO disconnected - ${reason}`);
    });

    socket.on('connect_error', (err) => {
      log.bad(`Socket.IO connect_error: ${err?.message || err}`);
    });

    socket.on('frame_state', (raw) => {
      applyFrameState(unwrap(raw));
    });

    socket.on('system_health', (raw) => {
      setMetrics(unwrap(raw));
    });

    socket.on('voice_tts_ready', async (raw) => {
      const payload = unwrap(raw);
      const rawAudioUrl = payload?.audio_url;
      const voiceEventId = payload?.voice_event_id;
      if (!rawAudioUrl || !voiceEventId || voiceEventId === lastPlayedVoiceIdRef.current) return;
      const audioUrl = rawAudioUrl.startsWith('http') ? rawAudioUrl : `${getApiBase()}${rawAudioUrl}`;

      try {
        if (playbackAudioRef.current) {
          playbackAudioRef.current.pause();
        }
        const audio = new Audio(audioUrl);
        playbackAudioRef.current = audio;
        lastPlayedVoiceIdRef.current = voiceEventId;
        audio.onended = () => socket.emit('voice_playback_complete');
        await audio.play();
      } catch (error) {
        log.warn(`Audio playback failed: ${error?.message || error}`);
        socket.emit('voice_playback_complete');
      }
    });

    return () => {
      socketRef.current = null;
      socket.disconnect();
    };
  }, [setIsConnected, setMetrics, applyFrameState]);

  useEffect(() => {
    const socket = socketRef.current;
    if (!activationRequested || !socket || !socket.connected) return;

    socket.emit('activate_surgeai');
    consumeActivationRequest();
  }, [activationRequested, consumeActivationRequest]);

  const startRecording = useCallback((triggerKind) => {
    const socket = socketRef.current;
    const stream = streamRef.current;
    if (!socket?.connected || !stream) return;
    if (mediaRecorderRef.current?.state === 'recording') return;

    const mimeType = chooseMimeType();
    const mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    chunksRef.current = [];
    triggerKindRef.current = triggerKind;
    recordingSinceRef.current = Date.now();
    silenceSinceRef.current = null;

    mediaRecorder.ondataavailable = (event) => {
      if (event.data?.size) {
        chunksRef.current.push(event.data);
        blobToBase64(event.data)
          .then((audioBase64) => {
            socket.emit('voice_audio_chunk', { audio_base64: audioBase64 });
          })
          .catch((error) => {
            log.warn(`Voice chunk upload failed: ${error?.message || error}`);
          });
      }
    };

    mediaRecorder.onstop = async () => {
      const chunkBlob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType || 'audio/webm' });
      chunksRef.current = [];
      if (!chunkBlob.size) {
        socket.emit('voice_cancel');
        return;
      }

      try {
        const audioBase64 = await blobToBase64(chunkBlob);
        socket.emit('voice_turn_end', {
          trigger_kind: triggerKindRef.current,
          mime_type: chunkBlob.type || 'audio/webm',
          audio_base64: audioBase64,
        });
      } catch (error) {
        log.warn(`Voice upload failed: ${error?.message || error}`);
        socket.emit('voice_cancel');
      }
    };

    mediaRecorderRef.current = mediaRecorder;
    socket.emit('voice_turn_start', { trigger_kind: triggerKind });
    mediaRecorder.start(250);
  }, []);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;
    recorder.stop();
  }, []);

  const ensureMicrophone = useCallback(() => {
    if (streamRef.current) return Promise.resolve(streamRef.current);
    if (micPromiseRef.current) return micPromiseRef.current;
    if (!navigator.mediaDevices?.getUserMedia) return Promise.resolve(null);

    micPromiseRef.current = navigator.mediaDevices
      .getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      .then((stream) => {
        streamRef.current = stream;
        setMicPermission('granted');
        const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextCtor) return;

        const audioContext = new AudioContextCtor();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);

        audioContextRef.current = audioContext;
        analyserRef.current = analyser;
        levelArrayRef.current = new Uint8Array(analyser.fftSize);

        levelIntervalRef.current = window.setInterval(() => {
          const analyserNode = analyserRef.current;
          const levelArray = levelArrayRef.current;
          const socket = socketRef.current;
          const state = useHudStore.getState();
          if (!analyserNode || !levelArray || !socket?.connected || !state.sessionId) return;
          if (state.runtimeState === 'THINKING' || state.runtimeState === 'SPEAKING') return;
          if (mediaRecorderRef.current?.state === 'recording' && triggerKindRef.current === 'manual') return;

          const level = computeLevel(analyserNode, levelArray);
          const now = Date.now();
          const isRecording = mediaRecorderRef.current?.state === 'recording';

          if (!isRecording) {
            if (level > 0.065) {
              startRecording('auto');
              silenceSinceRef.current = null;
            }
            return;
          }

          if (level > 0.045) {
            silenceSinceRef.current = null;
            return;
          }

          silenceSinceRef.current = silenceSinceRef.current || now;
          const spokenLongEnough = now - recordingSinceRef.current > 600;
          const silentLongEnough = now - silenceSinceRef.current > 1200;
          const maxTurnReached = now - recordingSinceRef.current > 9000;
          if ((spokenLongEnough && silentLongEnough) || maxTurnReached) {
            stopRecording();
          }
        }, 100);
        micPromiseRef.current = null;
        return stream;
      })
      .catch((error) => {
        setMicPermission('denied');
        log.warn(`Microphone unavailable: ${error?.message || error}`);
        micPromiseRef.current = null;
        return null;
      });
    return micPromiseRef.current;
  }, [setMicPermission, startRecording, stopRecording]);

  useEffect(() => {
    if (!manualCaptureRequested) return;
    const socket = socketRef.current;
    if (!socket || !socket.connected) {
      consumeManualCaptureRequest();
      return;
    }

    ensureMicrophone().then(() => {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
        startRecording('manual');
      }
    });
    consumeManualCaptureRequest();
  }, [manualCaptureRequested, consumeManualCaptureRequest, ensureMicrophone, startRecording]);

  useEffect(() => {
    ensureMicrophone();
    return () => {
      window.clearInterval(levelIntervalRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (playbackAudioRef.current) {
        playbackAudioRef.current.pause();
      }
      streamRef.current?.getTracks?.().forEach((track) => track.stop());
      audioContextRef.current?.close?.();
    };
  }, [ensureMicrophone]);

  return <>{children}</>;
}
