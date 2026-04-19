# config.py - All settings in one place

CONFIG = {
    "language": "en-US",          # Language for recognition
    "timeout": 5,                  # Seconds to wait for speech to start
    "phrase_time_limit": 10,       # Max seconds for a single phrase
    "energy_threshold": 300,       # Mic sensitivity (lower = more sensitive)
    "pause_threshold": 0.8,        # Seconds of silence to end phrase
    "save_to_file": True,          # Save output to text file
    "output_file": "output.txt",   # Output file name
}