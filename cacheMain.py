import win32com.client
import speech_recognition as sr
from openai import OpenAI
import os
from dotenv import load_dotenv
from pathlib import Path
import sounddevice as sd
import soundfile as sf
from collections import defaultdict
import edge_tts 
import asyncio
import vlc
from pytube import YouTube
import yt_dlp


load_dotenv()
speech_file = Path(__file__).parent / "speech.mp3"

# Initialize OpenAI client and speech synthesizer
speaker = win32com.client.Dispatch("SAPI.SpVoice")
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
intro = "Hello, I am Haku. How can I help you?"
print(intro)

# Initialize edge-tts synthesizer
async def synthesize_speech(text, output_file):
    """Generates speech using edge-tts and saves to the output file."""
    communicate = edge_tts.Communicate(text, voice="en-US-JennyNeural")  # You can change the voice
    await communicate.save(output_file)

# Synthesize the intro speech using edge-tts
asyncio.run(synthesize_speech(intro, str(speech_file)))
audio_data, samplerate = sf.read(speech_file)
sd.play(audio_data, samplerate)
sd.wait()


# Initialize cache for common responses and conversation history
response_cache = defaultdict(str)
conversation_history = []

def get_cached_response(prompt):
    """Fetches a response from the cache if available, otherwise queries OpenAI."""
    if prompt in response_cache:
        return response_cache[prompt]
    else:
        # Append conversation history for context
        conversation = [{"role": "system", "content": "You are a helpful assistant who provides concise, straightforward answers and ends responses polite prompt."}]
        for entry in conversation_history:
            conversation.append({"role": entry["role"], "content": entry["content"]})

        # Add the user's latest input
        conversation.append({"role": "user", "content": prompt})

        # Generate response from OpenAI
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation,
            max_tokens=150,
            n=1,
            temperature=0.5,
        )
        response = completion.choices[0].message.content
        
        # Cache the response for future use
        response_cache[prompt] = response
        
        # Save conversation history
        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": response})

        # Add the follow-up question
        response += " "
        
        return response

def listen_for_wake_word(recognizer, microphone):
    """Listens for the wake word 'hello' and returns True if detected."""
    with microphone as source:
        print("Listening for wake word...")
        audio = recognizer.listen(source)
        try:
            transcript = recognizer.recognize_google(audio, language="en-in")
            if "hello" or 'okay' or 'yeah' or 'yup' or 'yep' or 'lets see' in transcript.lower():
                return True
        except sr.UnknownValueError:
            pass  # Ignore unknown value errors
        except sr.RequestError:
            print("Could not request results; check your network connection.")
    return False

def process_command(recognizer, microphone):
    """Processes commands after detecting the wake word."""
    speech_file_path = Path(__file__).parent / "speech.mp3"  # Define speech_file_path before try block
    
    with microphone as source:
        print("Listening for command...")
        audio = recognizer.listen(source)
        try:
            prompt = recognizer.recognize_google(audio, language="en-in")
            print("Command detected:", prompt)

            
            # Get response from cache or OpenAI
            response = get_cached_response(prompt)
            print("Response:", response)
            
            if response:
                # Use edge-tts for audio response synthesis
                asyncio.run(synthesize_speech(response, str(speech_file_path)))
                audio_data, samplerate = sf.read(speech_file_path)
                sd.play(audio_data, samplerate)
                sd.wait()

        except sr.UnknownValueError:
            asyncio.run(synthesize_speech("Google Speech Recognition could not understand the audio", str(speech_file_path)))
            audio_data, samplerate = sf.read(speech_file_path)
            sd.play(audio_data, samplerate)
            sd.wait()
        except sr.RequestError as e:
            asyncio.run(synthesize_speech(f"Could not request results from Google Speech Recognition service; {e}", str(speech_file_path)))
            audio_data, samplerate = sf.read(speech_file_path)
            sd.play(audio_data, samplerate)
            sd.wait()


recognizer = sr.Recognizer()
microphone = sr.Microphone()

while True:
    if listen_for_wake_word(recognizer, microphone):
        process_command(recognizer, microphone)
