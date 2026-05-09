# # if you dont use pipenv uncomment the following:
# # from dotenv import load_dotenv
# # load_dotenv()

# #Step1a: Setup Text to Speech–TTS–model with gTTS
# import os
# from gtts import gTTS

# def text_to_speech_with_gtts_old(input_text, output_filepath):
#     language="en"

#     audioobj= gTTS(
#         text=input_text,
#         lang=language,
#         slow=False
#     )
#     audioobj.save(output_filepath)


# input_text="Hi this is Ai with Meet!"
# # text_to_speech_with_gtts_old(input_text=input_text, output_filepath="gtts_testing.mp3")

# #Step1b: Setup Text to Speech–TTS–model with ElevenLabs
# from elevenlabs import ElevenLabs
# from elevenlabs import play

# ELEVENLABS_API_KEY = os.environ.get("ELEVEN_API_KEY")

# def text_to_speech_with_elevenlabs_old(input_text, output_filepath):
#     client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

#     # NEW METHOD
#     audio = client.text_to_speech.convert(
#         voice_id="EXAVITQu4vr4xnSDxMaL",   # Rachel (official voice ID)
#         model_id="eleven_multilingual_v2",
#         text=input_text,
#         output_format="mp3_22050_32"
#     )


#     # Save MP3
#     with open(output_filepath, "wb") as f:
#         for chunk in audio:
#             f.write(chunk)

# # text_to_speech_with_elevenlabs_old(input_text, output_filepath="elevenlabs_testing.mp3")
# # print("Saved:", output_filepath)

# #Step2: Use Model for Text output to Voice

# import subprocess
# import platform

# def text_to_speech_with_gtts(input_text, output_filepath):
#     language="en"

#     audioobj= gTTS(
#         text=input_text,
#         lang=language,
#         slow=False
#     )
#     audioobj.save(output_filepath)
#     os_name = platform.system()
#     try:
#         if os_name == "Darwin":  # macOS
#             subprocess.run(['afplay', output_filepath])
#         elif os_name == "Windows":  # Windows
#             subprocess.run(['powershell', '-c', f'(New-Object Media.SoundPlayer "{output_filepath}").PlaySync();'])
#         elif os_name == "Linux":  # Linux
#             subprocess.run(['aplay', output_filepath])  # Alternative: use 'mpg123' or 'ffplay'
#         else:
#             raise OSError("Unsupported operating system")
#     except Exception as e:
#         print(f"An error occurred while trying to play the audio: {e}")


# input_text="Hi this is Ai with Meet, autoplay testing!"
# # text_to_speech_with_gtts(input_text=input_text, output_filepath="gtts_testing_autoplay.mp3")


# def text_to_speech_with_elevenlabs(input_text, output_filepath):
#     client=ElevenLabs(api_key=ELEVENLABS_API_KEY)
#     audio=client.generate(
#         text= input_text,
#         voice= "Aria",
#         output_format= "mp3_22050_32",
#         model= "eleven_turbo_v2"
#     )
#     elevenlabs.save(audio, output_filepath)
#     os_name = platform.system()
#     try:
#         if os_name == "Darwin":  # macOS
#             subprocess.run(['afplay', output_filepath])
#         elif os_name == "Windows":  # Windows
#             subprocess.run(['powershell', '-c', f'(New-Object Media.SoundPlayer "{output_filepath}").PlaySync();'])
#         elif os_name == "Linux":  # Linux
#             subprocess.run(['aplay', output_filepath])  # Alternative: use 'mpg123' or 'ffplay'
#         else:
#             raise OSError("Unsupported operating system")
#     except Exception as e:
#         print(f"An error occurred while trying to play the audio: {e}")

# text_to_speech_with_elevenlabs(input_text, output_filepath="elevenlabs_testing_autoplay.mp3")



# if you dont use pipenv uncomment the following:
# from dotenv import load_dotenv
# load_dotenv()

# Step1a: Setup Text to Speech–TTS–model with gTTS
import os
from gtts import gTTS
from elevenlabs import ElevenLabs

ELEVENLABS_API_KEY = os.environ.get("ELEVEN_API_KEY")

# Optional: configure language-specific voices (put real IDs in your env)
ELEVEN_VOICE_DEFAULT = os.environ.get("ELEVEN_VOICE_DEFAULT", "EXAVITQu4vr4xnSDxMaL")  # Rachel fallback
ELEVEN_VOICE_HI = os.environ.get("ELEVEN_VOICE_HI")  # Hindi
ELEVEN_VOICE_GU = os.environ.get("ELEVEN_VOICE_GU")  # Gujarati
ELEVEN_VOICE_MR = os.environ.get("ELEVEN_VOICE_MR")  # Marathi

VOICE_BY_LANG = {
    "hi": ELEVEN_VOICE_HI,
    "gu": ELEVEN_VOICE_GU,
    "mr": ELEVEN_VOICE_MR,
}

def _pick_voice(lang_code: str | None) -> str:
    if lang_code and VOICE_BY_LANG.get(lang_code):
        return VOICE_BY_LANG[lang_code]
    return ELEVEN_VOICE_DEFAULT

# -------------------------------
# gTTS FUNCTION (OLD + WORKING)
# -------------------------------
def text_to_speech_with_gtts(input_text, output_filepath):
    audioobj = gTTS(text=input_text, lang="en", slow=False)
    audioobj.save(output_filepath)
    # The audio file is saved for the browser/client to play. Do not autoplay server-side.
    return output_filepath



# ---------------------------------------------
# NEW FIXED ELEVENLABS SDK – FINAL WORKING CODE
# ---------------------------------------------
def text_to_speech_with_elevenlabs(input_text, output_filepath, language="auto", voice_id=None):
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    v_id = voice_id or _pick_voice(language)

    audio_stream = client.text_to_speech.convert(
        voice_id=v_id,
        model_id="eleven_multilingual_v2",  # best for non‑English
        text=input_text,
        output_format="mp3_22050_32"
    )
    with open(output_filepath, "wb") as f:
        for chunk in audio_stream:
            f.write(chunk)
    # Do not play audio on the server; return path for client-side playback.
    return output_filepath


# -------------------------------
# TEST CALL
# -------------------------------
if __name__ == "__main__":
    input_text = "Hi this is Ai with Meet, autoplay test using ElevenLabs!"
    text_to_speech_with_elevenlabs(input_text, output_filepath="elevenlabs_testing_autoplay.mp3")
