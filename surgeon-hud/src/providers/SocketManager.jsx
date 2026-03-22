/* eslint-disable react/prop-types */
import { useCallback, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import { getApiBase, getSocketUrl } from '../config';
import { log } from '../lib/logger';
import { useHudStore } from '../store/useHudStore';

function unwrap(data) {
  return data?.payload ?? data;
}

function getSpeechRecognitionCtor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function speakFallback(text) {
  if (!text || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.98;
  utterance.pitch = 0.95;
  window.speechSynthesis.speak(utterance);
}

export default function SocketManager({ children }) {
  const setIsConnected = useHudStore((s) => s.setIsConnected);
  const setMetrics = useHudStore((s) => s.setMetrics);
  const applyFrameState = useHudStore((s) => s.applyFrameState);
  const activationRequested = useHudStore((s) => s.activationRequested);
  const consumeActivationRequest = useHudStore((s) => s.consumeActivationRequest);
  const setMicPermission = useHudStore((s) => s.setMicPermission);
  const setListeningState = useHudStore((s) => s.setListeningState);
  const setTranscriptPreview = useHudStore((s) => s.setTranscriptPreview);
  const setClientVoiceState = useHudStore((s) => s.setClientVoiceState);
  const sessionTerminated = useHudStore((s) => s.sessionTerminated);

  const socketRef = useRef(null);
  const recognitionRef = useRef(null);
  const shouldRunRecognitionRef = useRef(false);
  const recognitionRestartTimerRef = useRef(null);
  const activeCommandRef = useRef(false);
  const lastWakeAtRef = useRef(0);
  const lastQueryAtRef = useRef(0);
  const playbackAudioRef = useRef(null);
  const lastPlayedVoiceIdRef = useRef(null);

  const stopRecognition = useCallback(() => {
    shouldRunRecognitionRef.current = false;
    window.clearTimeout(recognitionRestartTimerRef.current);
    try {
      recognitionRef.current?.stop?.();
    } catch {
      // Browser speech APIs throw if stop() races with onend; ignore it.
    }
  }, []);

  const startRecognition = useCallback(() => {
    const SpeechRecognitionCtor = getSpeechRecognitionCtor();
    if (!SpeechRecognitionCtor) {
      setMicPermission('unsupported');
      setClientVoiceState('unsupported');
      return;
    }

    shouldRunRecognitionRef.current = true;
    if (!recognitionRef.current) {
      const recognition = new SpeechRecognitionCtor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setMicPermission('granted');
        if (useHudStore.getState().sessionTerminated) {
          shouldRunRecognitionRef.current = false;
          try {
            recognition.stop();
          } catch {
            // no-op
          }
          return;
        }
        if (!activeCommandRef.current) {
          setClientVoiceState('passive');
        }
      };

      recognition.onresult = (event) => {
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          const transcript = result[0]?.transcript?.trim() || '';
          if (!transcript) continue;
          if (useHudStore.getState().sessionTerminated) {
            activeCommandRef.current = false;
            return;
          }

          const normalized = transcript.toLowerCase();
          const wakeMatch = normalized.includes('hey surgeon');
          const now = Date.now();

          if (!activeCommandRef.current && wakeMatch) {
            if ((now - lastWakeAtRef.current) < 2000) {
              continue;
            }

            lastWakeAtRef.current = now;
            activeCommandRef.current = true;
            setClientVoiceState('wake');
            setListeningState('wake');

            const inlineCommand = transcript.replace(/hey surgeon[\s,:-]*/i, '').trim();
            if (result.isFinal && inlineCommand) {
              if ((now - lastQueryAtRef.current) < 2000) {
                activeCommandRef.current = false;
                setClientVoiceState('passive');
                continue;
              }
              lastQueryAtRef.current = now;
              activeCommandRef.current = false;
              setTranscriptPreview(inlineCommand);
              setClientVoiceState('thinking');
              setListeningState('thinking');
              socketRef.current?.emit('voice_text_query', {
                text: inlineCommand,
                trigger_kind: 'wake_inline',
              });
            }
            continue;
          }

          if (!activeCommandRef.current) {
            continue;
          }

          setTranscriptPreview(transcript);
          setClientVoiceState(result.isFinal ? 'thinking' : 'listening');
          setListeningState(result.isFinal ? 'thinking' : 'listening');

          if (!result.isFinal) {
            continue;
          }

          const cleanCommand = transcript.replace(/hey surgeon[\s,:-]*/i, '').trim();
          if (!cleanCommand || (now - lastQueryAtRef.current) < 2000) {
            activeCommandRef.current = false;
            setClientVoiceState('passive');
            setListeningState('idle');
            continue;
          }

          lastQueryAtRef.current = now;
          activeCommandRef.current = false;
          socketRef.current?.emit('voice_text_query', {
            text: cleanCommand,
            trigger_kind: 'wake_followup',
          });
        }
      };

      recognition.onerror = (event) => {
        const code = event?.error || 'unknown';
        log.warn(`Speech recognition error: ${code}`);
        if (code === 'not-allowed' || code === 'service-not-allowed') {
          setMicPermission('denied');
          setClientVoiceState('error');
          shouldRunRecognitionRef.current = false;
          return;
        }
        setClientVoiceState('restarting');
      };

      recognition.onend = () => {
        if (!shouldRunRecognitionRef.current) return;
        recognitionRestartTimerRef.current = window.setTimeout(() => {
          try {
            recognition.start();
          } catch {
            // A pending restart can collide with browser speech internals. Keep retrying.
            recognitionRestartTimerRef.current = window.setTimeout(() => {
              try {
                recognition.start();
              } catch {
                // no-op
              }
            }, 1200);
          }
        }, 500);
      };

      recognitionRef.current = recognition;
    }

    try {
      recognitionRef.current.start();
    } catch {
      // ignore duplicate start() while already active
    }
  }, [setClientVoiceState, setListeningState, setMicPermission, setTranscriptPreview]);

  useEffect(() => {
    let cancelled = false;

    async function waitForBackendAndConnect() {
      while (!cancelled && !socketRef.current) {
        try {
          const response = await fetch(`${getApiBase()}/health`, { cache: 'no-store' });
          if (!response.ok) {
            throw new Error(`Health returned ${response.status}`);
          }

          const socket = io(getSocketUrl(), {
            path: '/socket.io',
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 500,
            timeout: 5000,
          });

          socketRef.current = socket;

          socket.on('connect', () => {
            setIsConnected(true);
            log.ok(`Socket.IO connected - ${getSocketUrl()}`);
            if (useHudStore.getState().activationRequested) {
              socket.emit('activate_surgeai');
              useHudStore.getState().consumeActivationRequest();
            }
            startRecognition();
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
            const voiceEventId = payload?.voice_event_id;
            const audioBase64 = payload?.audio_base64;
            const rawAudioUrl = payload?.audio_url;
            const voicePrompt = payload?.voice_prompt;
            if (!voiceEventId || voiceEventId === lastPlayedVoiceIdRef.current) return;

            stopRecognition();
            setClientVoiceState('speaking');
            lastPlayedVoiceIdRef.current = voiceEventId;

            try {
              if (playbackAudioRef.current) {
                playbackAudioRef.current.pause();
              }

              const audioSrc = audioBase64
                ? `data:audio/mpeg;base64,${audioBase64}`
                : rawAudioUrl
                  ? `${getApiBase()}${rawAudioUrl}`
                  : null;

              if (!audioSrc) {
                throw new Error('No TTS audio payload returned');
              }

              const audio = new Audio(audioSrc);
              playbackAudioRef.current = audio;
          audio.onended = () => {
                socket.emit('voice_playback_complete');
                if (useHudStore.getState().sessionTerminated) {
                  setClientVoiceState('complete');
                } else {
                  setClientVoiceState('passive');
                  startRecognition();
                }
              };
              await audio.play();
            } catch (error) {
              log.warn(`Audio playback failed, using browser TTS fallback: ${error?.message || error}`);
              speakFallback(voicePrompt);
              socket.emit('voice_playback_complete');
              if (useHudStore.getState().sessionTerminated) {
                setClientVoiceState('complete');
              } else {
                setClientVoiceState('passive');
                startRecognition();
              }
            }
          });

          return;
        } catch {
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
        }
      }
    }

    waitForBackendAndConnect();

    return () => {
      cancelled = true;
      stopRecognition();
      if (playbackAudioRef.current) {
        playbackAudioRef.current.pause();
      }
      window.speechSynthesis?.cancel?.();
      socketRef.current?.disconnect?.();
      socketRef.current = null;
    };
  }, [applyFrameState, setClientVoiceState, setIsConnected, setMetrics, startRecognition, stopRecognition]);

  useEffect(() => {
    if (!sessionTerminated) return;
    activeCommandRef.current = false;
    stopRecognition();
    setListeningState('complete');
    setClientVoiceState('complete');
  }, [sessionTerminated, setClientVoiceState, setListeningState, stopRecognition]);

  useEffect(() => {
    const socket = socketRef.current;
    if (!activationRequested || !socket || !socket.connected) return;

    socket.emit('activate_surgeai');
    consumeActivationRequest();
  }, [activationRequested, consumeActivationRequest]);

  return <>{children}</>;
}
