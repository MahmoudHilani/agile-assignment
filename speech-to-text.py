# speech_to_text.py

import speech_recognition as sr
import datetime
import os
from config import CONFIG

# ─────────────────────────────────────────
# STEP 1: Initialize Recognizer
# ─────────────────────────────────────────
def initialize_recognizer():
    """Setup the recognizer with config settings"""
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = CONFIG["energy_threshold"]
    recognizer.pause_threshold  = CONFIG["pause_threshold"]
    print("✅ Recognizer initialized successfully")
    return recognizer


# ─────────────────────────────────────────
# STEP 2: List Available Microphones
# ─────────────────────────────────────────
def list_microphones():
    """Show all available microphones"""
    print("\n🎤 Available Microphones:")
    print("─" * 40)
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"  [{index}] {name}")
    print("─" * 40)


# ─────────────────────────────────────────
# STEP 3: Capture Audio from Microphone
# ─────────────────────────────────────────
def capture_audio(recognizer, mic_index=None):
    """
    Capture audio from microphone
    mic_index = None  → uses default microphone
    mic_index = 0,1,2 → uses specific microphone
    """
    try:
        # Use specific mic or default
        mic = sr.Microphone(device_index=mic_index)

        with mic as source:
            print("\n🔧 Adjusting for ambient noise... Please wait")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("✅ Adjustment done!")
            print("\n🎙️  Speak Now... (Listening...)")

            # Listen with timeout settings from config
            audio = recognizer.listen(
                source,
                timeout=CONFIG["timeout"],
                phrase_time_limit=CONFIG["phrase_time_limit"]
            )
            print("✅ Audio captured successfully!")
            return audio

    except sr.WaitTimeoutError:
        print("⚠️  No speech detected within timeout period")
        return None

    except OSError as e:
        print(f"❌ Microphone Error: {e}")
        print("💡 Tip: Check if microphone is connected properly")
        return None


# ─────────────────────────────────────────
# STEP 4: Convert Audio to Text
# ─────────────────────────────────────────
def audio_to_text(recognizer, audio):
    """
    Convert captured audio to text
    Uses Google's free speech recognition API
    """
    if audio is None:
        return None

    try:
        print("\n⏳ Converting speech to text...")

        # Google Speech Recognition (Free - No API key needed)
        text = recognizer.recognize_google(
            audio,
            language=CONFIG["language"]
        )
        print(f"✅ Conversion successful!")
        return text

    except sr.UnknownValueError:
        print("⚠️  Could not understand the audio")
        print("💡 Tip: Speak clearly and closer to the microphone")
        return None

    except sr.RequestError as e:
        print(f"❌ API Error: {e}")
        print("💡 Tip: Check your internet connection")
        return None


# ─────────────────────────────────────────
# STEP 5: Save Output to File
# ─────────────────────────────────────────
def save_to_file(text):
    """Save recognized text to output file with timestamp"""
    if not text:
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_file = CONFIG["output_file"]

    # Append to file (keeps previous recordings)
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {text}\n")

    print(f"💾 Text saved to '{output_file}'")


# ─────────────────────────────────────────
# STEP 6: Display Result
# ─────────────────────────────────────────
def display_result(text):
    """Display the recognized text nicely"""
    print("\n" + "═" * 50)
    print("📝 RECOGNIZED TEXT:")
    print("─" * 50)
    if text:
        print(f"  {text}")
    else:
        print("  ❌ No text recognized")
    print("═" * 50)


# ─────────────────────────────────────────
# STEP 7: Continuous Listening Mode
# ─────────────────────────────────────────
def continuous_mode(recognizer):
    """
    Keep listening until user says 'stop' or 'exit'
    or presses Ctrl+C
    """
    print("\n🔁 CONTINUOUS MODE STARTED")
    print("💡 Say 'stop' or 'exit' to quit")
    print("💡 Or press Ctrl+C to force quit\n")

    session_texts = []  # Store all recognized texts

    while True:
        try:
            # Capture audio
            audio = capture_audio(recognizer)

            # Convert to text
            text = audio_to_text(recognizer, audio)

            # Display result
            display_result(text)

            if text:
                session_texts.append(text)

                # Save each result if enabled
                if CONFIG["save_to_file"]:
                    save_to_file(text)

                # Check for stop command
                if text.lower() in ["stop", "exit", "quit", "stop listening"]:
                    print("\n🛑 Stop command detected. Exiting...")
                    break

        except KeyboardInterrupt:
            print("\n\n🛑 Stopped by user (Ctrl+C)")
            break

    # Show session summary
    print("\n" + "═" * 50)
    print("📊 SESSION SUMMARY")
    print("─" * 50)
    print(f"  Total phrases recognized: {len(session_texts)}")
    if session_texts:
        print("  All recognized texts:")
        for i, t in enumerate(session_texts, 1):
            print(f"    {i}. {t}")
    print("═" * 50)


# ─────────────────────────────────────────
# STEP 8: Single Recording Mode
# ─────────────────────────────────────────
def single_mode(recognizer):
    """Record and convert just one time"""
    print("\n🎯 SINGLE RECORDING MODE")

    audio = capture_audio(recognizer)
    text  = audio_to_text(recognizer, audio)

    display_result(text)

    if text and CONFIG["save_to_file"]:
        save_to_file(text)


# ─────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────
def main():
    print("╔══════════════════════════════════════╗")
    print("║     🎤 SPEECH TO TEXT APP 🎤          ║")
    print("╚══════════════════════════════════════╝")

    # Initialize
    recognizer = initialize_recognizer()

    # Show available microphones
    list_microphones()

    # Choose mode
    print("\n📌 SELECT MODE:")
    print("  [1] Single Recording")
    print("  [2] Continuous Listening")
    print("  [3] Exit")

    choice = input("\nEnter choice (1/2/3): ").strip()

    if choice == "1":
        single_mode(recognizer)

    elif choice == "2":
        continuous_mode(recognizer)

    elif choice == "3":
        print("👋 Goodbye!")

    else:
        print("❌ Invalid choice. Running Single mode by default...")
        single_mode(recognizer)


# ─────────────────────────────────────────
# RUN THE APP
# ─────────────────────────────────────────
if __name__ == "__main__":
    main()