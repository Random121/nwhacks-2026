from elevenlabs import ElevenLabs
from elevenlabs.play import play as elevenlabs_play

class VoiceAudio:
    client: ElevenLabs

    def __init__(self, key):
        self.client = ElevenLabs(api_key=key)

    def play(self, voice_id, text):
        audio = self.client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,

        )

        elevenlabs_play(audio=audio, use_ffmpeg=False)
