import io
import wave
import array
import pyaudio
from elevenlabs import ElevenLabs
from elevenlabs.play import play as elevenlabs_play

APOLOGY_KEYWORDS = [
    "sorry",
    "my bad",
    "apologies",
]

class VoiceAudio:
    client: ElevenLabs
    audio_cache: map

    def __init__(self, key):
        self.client = ElevenLabs(api_key=key)

    def play(self, voice_id, text):
        audio = self.client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
        )

        elevenlabs_play(audio=audio, use_ffmpeg=False)

    def listen_for_apology(self, duration=5, silence_threshold=500):
        """
        Records audio and transcribes it, but only if the volume exceeds the silence threshold.

        Args:
            duration (int): Seconds to record.
            silence_threshold (int): Amplitude threshold (0-32768).
                                    Below ~500 is usually just background noise.
        """
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000

        p = pyaudio.PyAudio()

        print(f"🎤 Recording for {duration} seconds... (Speak now)")

        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        frames = []

        # Record audio
        for _ in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        # --- SILENCE DETECTION START ---
        # Combine all chunks into one byte stream
        raw_data = b''.join(frames)

        # Convert raw bytes to integers (16-bit signed) using array
        # 'h' represents a signed short integer (2 bytes)
        audio_data = array.array('h', raw_data)

        # Find the loudest point in the recording
        # We take the absolute value because sound waves oscillate positive/negative
        max_amplitude = max(abs(sample) for sample in audio_data)

        print(f"📊 Max Volume Detected: {max_amplitude}/{32767}")

        if max_amplitude < silence_threshold:
            print("❌ No speech detected (Volume too low). Skipping API call.")
            return False
        # --- SILENCE DETECTION END ---

        print("✅ Speech detected. Transcribing...")

        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(raw_data)

        audio_buffer.seek(0)

        try:
            transcription: str = self.client.speech_to_text.convert(
                file=audio_buffer,
                model_id="scribe_v2",
                tag_audio_events=False,
                language_code="eng"
            )

            transcription = transcription.text

            if type(transcription) is not str:
                return False

            for keyword in APOLOGY_KEYWORDS:
                if transcription.lower().find(keyword) != -1:
                    return True

            return False
        except Exception as e:
            return f"Error during transcription: {e}"