
# SiriRevive

SiriRevive is a custom server implementation designed to intercept and process the legacy Apple Configuration Engine (ACE) protocol used by Siri on older iOS devices (specifically iOS 6 on the iPhone 4S). It acts as a man-in-the-middle proxy, bridging legacy hardware with modern LLMs.

By spoofing the original `guzzoni.apple.com` DNS request, the server captures the encrypted traffic, decodes the proprietary Speex audio stream, transcribes it using Whisper, and generates a response using Llama 3 via the Groq API. The response is then injected back into the ACE protocol as a native UI element. No jailbreak is required.

## Architecture

1.  **DNS Server (Port 53):** Intercepts requests to `guzzoni.apple.com` and resolves them to the host machine's IP. Standard queries are forwarded to `8.8.8.8`.
2.  **HTTP Certificate Server (Port 80/1337):** Provides an automated Over-The-Air (OTA) installation path for the required root certificate. Includes automatic port fallback if port 80 is occupied.
3.  **SSL Server (Port 443):** Terminates the TLS connection using a provided certificate and manages the bidirectional binary plist stream.
4.  **ACE Protocol Handler:** Decompresses zlib payloads, parses binary plists (`biplist`), and handles `SpeechPacket` and `FinishSpeech` ACE classes.
5.  **Audio Processing:** Uses `ctypes` bindings for `libspeex` to decode 16kHz audio payloads into standard PCM WAV.
6.  **Inference:** Routes audio to Groq's Whisper-large-v3 for transcription, then to Llama-3.1-8b-instant for text generation.

## Prerequisites

* Python 3.10 or higher.
* A valid Groq API key.
* `libspeex` shared library (`.dll`, `.dylib`, or `.so`) located in the project root.
* `guzzoni.crt` and `guzzoni.key` located in the project root.

## Setup and Execution

Install the required Python dependencies:
```bash
pip install dnslib biplist groq pyinstaller
```

The server requires administrative privileges (root/sudo) to bind to privileged ports 53 and 443.

### GUI Mode
Run the script directly to launch the Tkinter interface:
```bash
sudo python3 SiriRevive.py
```

### CLI Mode (Headless)
Intended for deployment on a Linux VPS or a headless server:
```bash
sudo python3 SiriRevive.py --cli --ip 0.0.0.0 --key YOUR_GROQ_API_KEY
```

---

## Client Configuration (iOS)

To bridge the device to the server, follow these steps precisely:

1.  **Network Alignment:** Connect the iPhone to the same local network as the host machine.
2.  **DNS Configuration:** Navigate to **Settings > Wi-Fi**, tap the "i" icon next to your network, and manually set the **DNS** field to the Local IP address shown in the SiriRevive app.
3.  **Certificate Installation:** Open **Safari** on the iPhone and navigate to the certificate URL shown in the app (e.g., `http://192.168.1.235:1337`). Download and **Install** the configuration profile when prompted.
4.  **Enable Trust (Critical):** On the iPhone, go to **Settings > General > About > Certificate Trust Settings**. Enable the toggle for the `guzzoni.apple.com` certificate to allow full SSL interception.
5.  **Trigger:** Hold the Home button and speak to Siri.

---

## Building Executables

To compile the script into a standalone binary using PyInstaller:

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
