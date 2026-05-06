# SiriRevive

SiriRevive is a custom server implementation designed to intercept and process the legacy Apple Configuration Engine (ACE) protocol used by Siri on older iOS devices (specifically iOS 6 on the iPhone 4S). It acts as a man-in-the-middle proxy, bridging legacy hardware with modern LLMs.

By spoofing the original `guzzoni.apple.com` DNS request, the server captures the encrypted traffic, decodes the proprietary Speex audio stream, transcribes it using Whisper, and generates a response using Llama 3 via the Groq API. The response is then injected back into the ACE protocol as a native UI element. No jailbreak is required.

## Architecture

1. **DNS Server (Port 53):** Intercepts requests to `guzzoni.apple.com` and resolves them to the host machine's IP. Standard queries are forwarded to `8.8.8.8`.
2. **SSL Server (Port 443):** Terminates the TLS connection using a provided certificate.
3. **ACE Protocol Handler:** Decompresses zlib payloads, parses binary plists (`biplist`), and handles `SpeechPacket` and `FinishSpeech` ACE classes.
4. **Audio Processing:** Uses `ctypes` bindings for `libspeex` to decode 16kHz audio payloads into standard PCM WAV.
5. **Inference:** Routes audio to Groq's Whisper-large-v3 for transcription, then to Llama-3.1-8b-instant for text generation.

## Prerequisites

- Python 3.10 or higher.
- A valid Groq API key.
- `libspeex` shared library (`.dll`, `.dylib`, or `.so`) located in the project root or system path.
- `guzzoni.crt` and `guzzoni.key` located in the project root.

## Setup and Execution

Install the required Python dependencies:
```bash
pip install dnslib biplist groq pyinstaller
```

The server requires administrative privileges (root/sudo) to bind to privileged ports 53 and 443.

### GUI Mode
Run the script directly. It will launch a Tkinter interface.
```bash
sudo python3 SiriRevive.py
```

### CLI Mode (Headless)
Intended for deployment on a Linux VPS or a headless home server (e.g., Raspberry Pi).
```bash
sudo python3 SiriRevive.py --cli --ip 0.0.0.0 --key YOUR_GROQ_API_KEY
```

## Client Configuration (iOS)

1. Connect the iPhone to the same local network as the host machine.
2. Navigate to Settings > Wi-Fi.
3. Tap the network details and manually set the DNS field to the IP address of the machine running SiriRevive.
4. Trigger Siri via the Home button.

## Building Executables

You can compile the script into a standalone binary using PyInstaller.

**Windows:**
```cmd
pyinstaller --noconsole --onefile --add-data "guzzoni.crt;." --add-data "guzzoni.key;." --add-data "libspeex.dll;." SiriRevive.py
```

**macOS:**
```bash
pyinstaller --windowed --onefile --add-data "guzzoni.crt:." --add-data "guzzoni.key:." --add-data "libspeex.dylib:." SiriRevive.py
```

## Disclaimer

This software is provided for educational and research purposes only. It serves as a proof-of-concept for legacy protocol analysis and interoperability. This project is not affiliated with, endorsed by, or sponsored by Apple Inc. All product and company names are trademarks or registered trademarks of their respective holders.
```
