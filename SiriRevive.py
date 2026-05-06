import tkinter as tk
from tkinter import messagebox, font
import threading
import sys, os, socket, platform, ssl, zlib, struct, biplist, wave, ctypes, uuid, argparse
from ctypes.util import find_library
from dnslib import DNSRecord, RR, A, QTYPE
from groq import Groq

is_running = False
server_sockets = []

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

os_name = platform.system()
lib_name = 'libspeex.dll' if os_name == "Windows" else ('libspeex.dylib' if os_name == "Darwin" else 'libspeex.so')
lib_path = resource_path(lib_name)
if not os.path.exists(lib_path):
    lib_path = find_library('speex') or '/usr/local/lib/libspeex.dylib'

try:
    libspeex = ctypes.cdll.LoadLibrary(lib_path)
    libspeex.speex_lib_get_mode.argtypes = [ctypes.c_int]
    libspeex.speex_lib_get_mode.restype = ctypes.c_void_p
    libspeex.speex_decoder_init.argtypes = [ctypes.c_void_p]
    libspeex.speex_decoder_init.restype = ctypes.c_void_p
    libspeex.speex_bits_init.argtypes = [ctypes.c_void_p]
    libspeex.speex_bits_init.restype = None
    libspeex.speex_bits_read_from.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    libspeex.speex_bits_read_from.restype = None
    libspeex.speex_decode_int.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_short)]
    libspeex.speex_decode_int.restype = ctypes.c_int
    libspeex.speex_bits_destroy.argtypes = [ctypes.c_void_p]
    libspeex.speex_bits_destroy.restype = None
    speex_mode = libspeex.speex_lib_get_mode(1)
    speex_state = libspeex.speex_decoder_init(speex_mode)
except Exception as e:
    print(f"Error loading Speex: {e}")
    sys.exit(1)

def decode_speex_frames(frames):
    pcm_data = b""
    bits_buf = ctypes.create_string_buffer(512)
    bits_ptr = ctypes.cast(bits_buf, ctypes.c_void_p)
    for pkt in frames:
        libspeex.speex_bits_init(bits_ptr)
        libspeex.speex_bits_read_from(bits_ptr, pkt, len(pkt))
        pcm_frame = (ctypes.c_short * 320)()
        while libspeex.speex_decode_int(speex_state, bits_ptr, pcm_frame) == 0:
            pcm_data += bytes(pcm_frame)
        libspeex.speex_bits_destroy(bits_ptr)
    return pcm_data

def create_ace_packet(obj, ref_id=None):
    obj['aceId'] = str(uuid.uuid4()).upper()
    if ref_id: obj['refId'] = ref_id
    plist_data = biplist.writePlistToString(obj)
    return b'\x02' + struct.pack('>I', len(plist_data)) + plist_data

def run_full_server(ip_address, api_key):
    global is_running, server_sockets
    server_sockets = []
    try:
        groq_client = Groq(api_key=api_key)

        def dns_logic():
            try:
                dns_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                dns_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                dns_sock.bind(('0.0.0.0', 53))
                server_sockets.append(dns_sock)
                while is_running:
                    try:
                        dns_sock.settimeout(1.0)
                        data, addr = dns_sock.recvfrom(512)
                        request = DNSRecord.parse(data)
                        qname = str(request.q.qname)
                        if "guzzoni.apple.com" in qname:
                            reply = request.reply()
                            reply.add_answer(RR(qname, QTYPE.A, rdata=A(ip_address), ttl=60))
                            dns_sock.sendto(reply.pack(), addr)
                        else:
                            up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            up.sendto(data, ('8.8.8.8', 53))
                            dns_sock.sendto(up.recvfrom(512)[0], addr)
                    except: continue
                dns_sock.close()
            except Exception as e:
                print(f"DNS Server Error: {e}")

        def http_logic():
            port = 80
            http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            http_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                http_sock.bind(('0.0.0.0', port))
            except:
                port = 1337
                http_sock.bind(('0.0.0.0', port))
            
            http_sock.listen(5)
            server_sockets.append(http_sock)
            print(f"CERTIFICATE SERVER active at http://{ip_address}:{port}")

            while is_running:
                try:
                    http_sock.settimeout(1.0)
                    conn, addr = http_sock.accept()
                    req = conn.recv(1024)
                    if b"GET" in req:
                        with open(resource_path('guzzoni.crt'), 'rb') as f:
                            cert_data = f.read()
                        resp = (b"HTTP/1.1 200 OK\r\nContent-Type: application/x-x509-ca-cert\r\n"
                                b"Content-Length: " + str(len(cert_data)).encode() + b"\r\n\r\n" + cert_data)
                        conn.sendall(resp)
                    conn.close()
                except: continue
            http_sock.close()

        threading.Thread(target=dns_logic, daemon=True).start()
        threading.Thread(target=http_logic, daemon=True).start()

        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=resource_path('guzzoni.crt'), keyfile=resource_path('guzzoni.key'))
        main_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        main_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        main_sock.bind((ip_address, 443))
        main_sock.listen(5)
        server_sockets.append(main_sock)
        main_sock.settimeout(1.0)
        
        print(f"SIRI SERVER active on {ip_address}:443")
       

        while is_running:
            try:
                newsocket, fromaddr = main_sock.accept()
                conn = context.wrap_socket(newsocket, server_side=True)
                data = conn.recv(1024)
                if not data or b"ACE /ace" not in data: continue

                conn.sendall(b"HTTP/1.1 200 OK\r\nConnection: keep-alive\r\nContent-Type: application/x-apple-ace\r\n\r\n")
                conn.sendall(b'\xaa\xcc\xee\x02')
                
                decompressor, compressor = zlib.decompressobj(), zlib.compressobj()
                speex_frames = []
                request_id = None 

                while is_running:
                    chunk = conn.recv(8192)
                    if not chunk: break
                    raw = decompressor.decompress(chunk)
                    offset = 0
                    while offset < len(raw):
                        if raw[offset] == 0x02:
                            p_len = struct.unpack('>I', raw[offset+1:offset+5])[0]
                            obj = biplist.readPlistFromString(raw[offset+5:offset+5+p_len])
                            cls = obj.get('class')
                            ace_id = obj.get('aceId')
                            
                            if cls in ["LoadAssistant", "CreateSessionInfoRequest"]:
                                reply = {"class": "AssistantLoaded", "group": "com.apple.ace.system", "properties": {"version": "1.0", "requestSync": False}}
                                conn.sendall(compressor.compress(create_ace_packet(reply, ace_id)) + compressor.flush(zlib.Z_SYNC_FLUSH))
                            
                            if cls == "StartSpeechRequest":
                                request_id = ace_id

                            if cls == "SpeechPacket":
                                speex_frames.extend(obj.get('properties', {}).get('packets', []))
                            
                            if cls == "FinishSpeech":
                                if not speex_frames: continue
                                pcm_bytes = decode_speex_frames(speex_frames)
                                speex_frames = [] 
                                if pcm_bytes:
                                    with wave.open("temp.wav", "wb") as w:
                                        w.setnchannels(1)
                                        w.setsampwidth(2)
                                        w.setframerate(16000)
                                        w.writeframes(pcm_bytes)
                                    try:
                                        with open("temp.wav", "rb") as f:
                                            text = groq_client.audio.transcriptions.create(file=("temp.wav", f.read()), model="whisper-large-v3").text
                                        print(f"USER: {text}")
                                        chat = groq_client.chat.completions.create(messages=[{"role": "user", "content": text}], model="llama-3.1-8b-instant")
                                        reply = chat.choices[0].message.content
                                        print(f"LLAMA: {reply}")
                                        speech_recog = {
                                            "class": "SpeechRecognized", "group": "com.apple.ace.speech",
                                            "properties": {"sessionId": request_id, "recognition": {"class": "Recognition", "group": "com.apple.ace.speech",
                                            "properties": {"phrases": [{"class": "Phrase", "group": "com.apple.ace.speech",
                                            "properties": {"interpretations": [{"class": "Interpretation", "group": "com.apple.ace.speech",
                                            "properties": {"tokens": [{"class": "Token", "group": "com.apple.ace.speech",
                                            "properties": {"text": text, "spaceAfter": True}}]}}]}}]}}}}
                                        conn.sendall(compressor.compress(create_ace_packet(speech_recog, request_id)) + compressor.flush(zlib.Z_SYNC_FLUSH))
                                        ace_reply = {
                                            "class": "AddViews", "group": "com.apple.ace.assistant",
                                            "properties": {"views": [{"class": "AssistantUtteranceView", "group": "com.apple.ace.assistant",
                                            "properties": {"text": reply, "speakableText": reply, "dialogIdentifier": "Llama"}}]}}
                                        conn.sendall(compressor.compress(create_ace_packet(ace_reply, request_id)) + compressor.flush(zlib.Z_SYNC_FLUSH))
                                        req_completed = {"class": "RequestCompleted", "group": "com.apple.ace.system", "properties": {"callbacks": []}}
                                        conn.sendall(compressor.compress(create_ace_packet(req_completed, request_id)) + compressor.flush(zlib.Z_SYNC_FLUSH))
                                    except Exception as e:
                                        print(f"AI Error: {e}")
                            offset += 5 + p_len
                        elif raw[offset] == 0x03: 
                            ping_seq = raw[offset+1:offset+5]
                            pong_packet = b'\x04' + ping_seq
                            conn.sendall(compressor.compress(pong_packet) + compressor.flush(zlib.Z_SYNC_FLUSH))
                            offset += 5
                        elif raw[offset] == 0x04:
                            offset += 5
                        else:
                            break 
            except socket.timeout: continue
            except: continue
        main_sock.close()
    except Exception as e:
        print(f"Critical error: {e}")
        stop_server_logic()

def stop_server_logic():
    global is_running
    is_running = False
    for s in server_sockets:
        try: s.close()
        except: pass
    btn_start.config(text="START SERVER", bg="#28a745")
    status_label.config(text="Status: Stopped")

def toggle_server(event=None):
    global is_running
    if not is_running:
        api_key = entry_key.get().strip()
        ip_addr = entry_ip.get().strip()
        if not api_key:
            messagebox.showwarning("Warning", "Please enter Groq API Key!")
            return
        is_running = True
        btn_start.config(text="STOP SERVER", bg="#dc3545")
        status_label.config(text="Status: Running")
        threading.Thread(target=run_full_server, args=(ip_addr, api_key), daemon=True).start()
    else:
        stop_server_logic()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SiriRevive Server")
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--ip", type=str, default="0.0.0.0")
    parser.add_argument("--key", type=str)
    args = parser.parse_args()

    if args.cli:
        if not args.key:
            print("Error: Key is required in CLI mode! Example: --key YOUR_KEY")
            sys.exit(1)
        print(f"Starting in Headless mode on IP: {args.ip}")
        is_running = True
        run_full_server(args.ip, args.key)
    else:
        root = tk.Tk()
        root.title("Siri Revive")
        root.geometry("500x350")
        root.minsize(400, 300)

        BG_COLOR = "#1E1E1E"
        TEXT_COLOR = "#E0E0E0"
        ACCENT_COLOR = "#4AF626"
        ENTRY_BG = "#2D2D2D"

        root.configure(bg=BG_COLOR)
        root.columnconfigure(0, weight=1)
        
        main_frame = tk.Frame(root, bg=BG_COLOR)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        title_font = font.Font(family="Helvetica", size=24, weight="bold")
        tk.Label(main_frame, text="Siri Revive", font=title_font, bg=BG_COLOR, fg=ACCENT_COLOR).pack(pady=10)

        tk.Label(main_frame, text="Local IP Address:", bg=BG_COLOR, fg=TEXT_COLOR).pack()
        entry_ip = tk.Entry(main_frame, font=("Consolas", 12), justify="center", bg=ENTRY_BG, fg="white", insertbackground="white", relief="flat")
        entry_ip.insert(0, get_local_ip())
        entry_ip.pack(pady=5, fill="x", ipady=5)

        tk.Label(main_frame, text="Groq API Key:", bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=(10, 0))
        entry_key = tk.Entry(main_frame, font=("Consolas", 12), show="*", justify="center", bg=ENTRY_BG, fg="white", insertbackground="white", relief="flat")
        entry_key.pack(pady=5, fill="x", ipady=5)

        btn_start = tk.Label(main_frame, text="START SERVER", font=("Arial", 12, "bold"), bg="#28a745", fg="white", cursor="hand2")
        btn_start.pack(pady=20, fill="x", ipady=15)
        btn_start.bind("<Button-1>", toggle_server)

        status_label = tk.Label(root, text="Status: Ready", bg="#2D2D2D", fg="#AAAAAA", anchor="w")
        status_label.pack(side="bottom", fill="x")

        root.mainloop()
