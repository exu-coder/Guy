#!/usr/bin/env python3
import os
import sys
import time
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ============================================================================
# 𝐂𝐨𝐧𝐟𝐢𝐠𝐮𝐫𝐚𝐭𝐢𝐨𝐧
# ============================================================================
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")
APP_FILE = "app.py"
CHECK_INTERVAL = 30  # 𝐂𝐡𝐞𝐜𝐤 𝐞𝐯𝐞𝐫𝐲 30 𝐬𝐞𝐜𝐨𝐧𝐝𝐬

# ============================================================================
# 𝐇𝐓𝐓𝐏 𝐇𝐚𝐧𝐝𝐥𝐞𝐫 𝐟𝐨𝐫 𝐡𝐞𝐚𝐥𝐭𝐡 𝐜𝐡𝐞𝐜𝐤𝐬
# ============================================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    """𝐇𝐚𝐧𝐝𝐥𝐞𝐬 𝐡𝐞𝐚𝐥𝐭𝐡 𝐜𝐡𝐞𝐜𝐤 𝐫𝐞𝐪𝐮𝐞𝐬𝐭𝐬 𝐭𝐨 𝐤𝐞𝐞𝐩 𝐭𝐡𝐞 𝐬𝐞𝐫𝐯𝐞𝐫 𝐚𝐥𝐢𝐯𝐞"""
    
    def log_message(self, format, *args):
        """𝐎𝐯𝐞𝐫𝐫𝐢𝐝𝐞 𝐭𝐨 𝐬𝐮𝐩𝐩𝐫𝐞𝐬𝐬 𝐧𝐨𝐢𝐬𝐲 𝐥𝐨𝐠𝐬"""
        pass
    
    def do_GET(self):
        """𝐇𝐚𝐧𝐝𝐥𝐞 𝐆𝐄𝐓 𝐫𝐞𝐪𝐮𝐞𝐬𝐭𝐬"""
        if self.path == "/" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            status = f"""
            <html>
            <head><title>𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐁𝐨𝐭</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px; background: #0d1117; color: #c9d1d9;">
                <h1 style="color: #58a6ff;">🤖 𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐁𝐨𝐭</h1>
                <p style="font-size: 18px;">✅ <strong>𝐁𝐨𝐭 𝐢𝐬 𝐫𝐮𝐧𝐧𝐢𝐧𝐠!</strong></p>
                <p style="font-size: 14px; color: #8b949e;">𝐒𝐭𝐚𝐭𝐮𝐬: <span style="color: #3fb950;">𝐀𝐜𝐭𝐢𝐯𝐞</span></p>
                <p style="font-size: 14px; color: #8b949e;">𝐓𝐢𝐦𝐞: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p style="font-size: 14px; color: #8b949e;">𝐏𝐨𝐫𝐭: {PORT}</p>
                <hr style="border: 1px solid #30363d; margin: 30px;">
                <p style="font-size: 12px; color: #8b949e;">𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦 𝐁𝐨𝐭 𝐀𝐏𝐈</p>
            </body>
            </html>
            """
            self.wfile.write(status.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_HEAD(self):
        """𝐇𝐚𝐧𝐝𝐥𝐞 𝐇𝐄𝐀𝐃 𝐫𝐞𝐪𝐮𝐞𝐬𝐭𝐬"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()


# ============================================================================
# 𝐁𝐨𝐭 𝐌𝐚𝐧𝐚𝐠𝐞𝐫
# ============================================================================
class BotManager:
    """𝐌𝐚𝐧𝐚𝐠𝐞𝐬 𝐭𝐡𝐞 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦 𝐛𝐨𝐭 𝐩𝐫𝐨𝐜𝐞𝐬𝐬"""
    
    def __init__(self):
        self.process = None
        self.running = False
    
    def start_bot(self):
        """𝐒𝐭𝐚𝐫𝐭 𝐭𝐡𝐞 𝐛𝐨𝐭 𝐚𝐬 𝐚 𝐬𝐮𝐛𝐩𝐫𝐨𝐜𝐞𝐬𝐬"""
        if self.process and self.process.poll() is None:
            print("[!] 𝐁𝐨𝐭 𝐢𝐬 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐫𝐮𝐧𝐧𝐢𝐧𝐠.")
            return
        
        print("[+] 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐁𝐨𝐭...")
        try:
            self.process = subprocess.Popen(
                [sys.executable, APP_FILE],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            self.running = True
            print(f"[+] 𝐁𝐨𝐭 𝐬𝐭𝐚𝐫𝐭𝐞𝐝 𝐰𝐢𝐭𝐡 𝐏𝐈𝐃: {self.process.pid}")
            
            # 𝐒𝐭𝐚𝐫𝐭 𝐚 𝐭𝐡𝐫𝐞𝐚𝐝 𝐭𝐨 𝐫𝐞𝐚𝐝 𝐨𝐮𝐭𝐩𝐮𝐭
            threading.Thread(target=self._read_output, daemon=True).start()
            
        except Exception as e:
            print(f"[!] 𝐅𝐚𝐢𝐥𝐞𝐝 𝐭𝐨 𝐬𝐭𝐚𝐫𝐭 𝐛𝐨𝐭: {e}")
            self.running = False
    
    def _read_output(self):
        """𝐑𝐞𝐚𝐝 𝐚𝐧𝐝 𝐩𝐫𝐢𝐧𝐭 𝐛𝐨𝐭 𝐨𝐮𝐭𝐩𝐮𝐭"""
        if not self.process:
            return
        
        # 𝐑𝐞𝐚𝐝 𝐬𝐭𝐝𝐨𝐮𝐭
        for line in self.process.stdout:
            if line.strip():
                print(f"[𝐁𝐎𝐓] {line.strip()}")
        
        # 𝐂𝐡𝐞𝐜𝐤 𝐢𝐟 𝐩𝐫𝐨𝐜𝐞𝐬𝐬 𝐡𝐚𝐬 𝐞𝐧𝐝𝐞𝐝
        if self.process.poll() is not None:
            self.running = False
            print("[!] 𝐁𝐨𝐭 𝐩𝐫𝐨𝐜𝐞𝐬𝐬 𝐡𝐚𝐬 𝐬𝐭𝐨𝐩𝐩𝐞𝐝.")
    
    def stop_bot(self):
        """𝐒𝐭𝐨𝐩 𝐭𝐡𝐞 𝐛𝐨𝐭 𝐩𝐫𝐨𝐜𝐞𝐬𝐬"""
        if self.process and self.process.poll() is None:
            print("[+] 𝐒𝐭𝐨𝐩𝐩𝐢𝐧𝐠 𝐛𝐨𝐭...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.running = False
            print("[+] 𝐁𝐨𝐭 𝐬𝐭𝐨𝐩𝐩𝐞𝐝.")
    
    def is_running(self):
        """𝐂𝐡𝐞𝐜𝐤 𝐢𝐟 𝐭𝐡𝐞 𝐛𝐨𝐭 𝐢𝐬 𝐫𝐮𝐧𝐧𝐢𝐧𝐠"""
        if self.process:
            return self.process.poll() is None
        return False
    
    def restart_bot(self):
        """𝐑𝐞𝐬𝐭𝐚𝐫𝐭 𝐭𝐡𝐞 𝐛𝐨𝐭"""
        print("[+] 𝐑𝐞𝐬𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐛𝐨𝐭...")
        self.stop_bot()
        time.sleep(2)
        self.start_bot()


# ============================================================================
# 𝐇𝐞𝐚𝐥𝐭𝐡 𝐂𝐡𝐞𝐜𝐤 𝐌𝐨𝐧𝐢𝐭𝐨𝐫
# ============================================================================
def monitor_bot(bot_manager):
    """𝐌𝐨𝐧𝐢𝐭𝐨𝐫 𝐭𝐡𝐞 𝐛𝐨𝐭 𝐚𝐧𝐝 𝐫𝐞𝐬𝐭𝐚𝐫𝐭 𝐢𝐟 𝐧𝐞𝐞𝐝𝐞𝐝"""
    while True:
        time.sleep(CHECK_INTERVAL)
        
        if not bot_manager.is_running() and bot_manager.running:
            print("[!] 𝐁𝐨𝐭 𝐢𝐬 𝐧𝐨𝐭 𝐫𝐮𝐧𝐧𝐢𝐧𝐠! 𝐀𝐭𝐭𝐞𝐦𝐩𝐭𝐢𝐧𝐠 𝐫𝐞𝐬𝐭𝐚𝐫𝐭...")
            bot_manager.restart_bot()
        elif bot_manager.is_running():
            print(f"[✓] 𝐁𝐨𝐭 𝐢𝐬 𝐡𝐞𝐚𝐥𝐭𝐡𝐲 (𝐏𝐈𝐃: {bot_manager.process.pid})")
        else:
            print("[!] 𝐁𝐨𝐭 𝐢𝐬 𝐬𝐭𝐨𝐩𝐩𝐞𝐝. 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠...")
            bot_manager.start_bot()


# ============================================================================
# 𝐌𝐚𝐢𝐧
# ============================================================================
def main():
    """𝐌𝐚𝐢𝐧 𝐟𝐮𝐧𝐜𝐭𝐢𝐨𝐧 𝐭𝐨 𝐫𝐮𝐧 𝐭𝐡𝐞 𝐬𝐞𝐫𝐯𝐞𝐫 𝐚𝐧𝐝 𝐛𝐨𝐭"""
    
    # 𝐏𝐫𝐢𝐧𝐭 𝐛𝐚𝐧𝐧𝐞𝐫
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ██████╗ ██╗████████╗██╗  ██╗██╗   ██╗██████╗             ║
    ║   ██╔══██╗██║╚══██╔══╝██║  ██║██║   ██║██╔══██╗            ║
    ║   ██████╔╝██║   ██║   ███████║██║   ██║██████╔╝            ║
    ║   ██╔══██╗██║   ██║   ██╔══██║██║   ██║██╔══██╗            ║
    ║   ██████╔╝██║   ██║   ██║  ██║╚██████╔╝██████╔╝            ║
    ║   ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝             ║
    ║                                                              ║
    ║   ███████╗ ██████╗██████╗  █████╗ ██████╗ ███████╗██████╗   ║
    ║   ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗  ║
    ║   ███████╗██║     ██████╔╝███████║██████╔╝█████╗  ██████╔╝  ║
    ║   ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗  ║
    ║   ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗██║  ██║  ║
    ║   ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝  ║
    ║                                                              ║
    ║            𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐁𝐨𝐭 𝐌𝐚𝐧𝐚𝐠𝐞𝐫                    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"[+] 𝐒𝐞𝐫𝐯𝐞𝐫: {HOST}:{PORT}")
    print(f"[+] 𝐁𝐨𝐭 𝐅𝐢𝐥𝐞: {APP_FILE}")
    print(f"[+] 𝐂𝐡𝐞𝐜𝐤 𝐈𝐧𝐭𝐞𝐫𝐯𝐚𝐥: {CHECK_INTERVAL}𝐬")
    print("-" * 60)
    
    # 𝐂𝐡𝐞𝐜𝐤 𝐢𝐟 𝐚𝐩𝐩.𝐩𝐲 𝐞𝐱𝐢𝐬𝐭𝐬
    if not os.path.exists(APP_FILE):
        print(f"[!] 𝐄𝐫𝐫𝐨𝐫: {APP_FILE} 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝!")
        print(f"[!] 𝐏𝐥𝐞𝐚𝐬𝐞 𝐞𝐧𝐬𝐮𝐫𝐞 {APP_FILE} 𝐢𝐬 𝐢𝐧 𝐭𝐡𝐞 𝐬𝐚𝐦𝐞 𝐝𝐢𝐫𝐞𝐜𝐭𝐨𝐫𝐲.")
        sys.exit(1)
    
    # 𝐂𝐫𝐞𝐚𝐭𝐞 𝐛𝐨𝐭 𝐦𝐚𝐧𝐚𝐠𝐞𝐫
    bot_manager = BotManager()
    
    # 𝐒𝐭𝐚𝐫𝐭 𝐭𝐡𝐞 𝐛𝐨𝐭
    bot_manager.start_bot()
    
    # 𝐒𝐭𝐚𝐫𝐭 𝐭𝐡𝐞 𝐦𝐨𝐧𝐢𝐭𝐨𝐫 𝐢𝐧 𝐚 𝐬𝐞𝐩𝐚𝐫𝐚𝐭𝐞 𝐭𝐡𝐫𝐞𝐚𝐝
    monitor_thread = threading.Thread(
        target=monitor_bot,
        args=(bot_manager,),
        daemon=True
    )
    monitor_thread.start()
    print("[+] 𝐁𝐨𝐭 𝐦𝐨𝐧𝐢𝐭𝐨𝐫 𝐬𝐭𝐚𝐫𝐭𝐞𝐝.")
    
    # 𝐂𝐫𝐞𝐚𝐭𝐞 𝐚𝐧𝐝 𝐫𝐮𝐧 𝐭𝐡𝐞 𝐇𝐓𝐓𝐏 𝐬𝐞𝐫𝐯𝐞𝐫
    try:
        server = HTTPServer((HOST, PORT), HealthCheckHandler)
        print(f"[+] 𝐇𝐓𝐓𝐏 𝐬𝐞𝐫𝐯𝐞𝐫 𝐫𝐮𝐧𝐧𝐢𝐧𝐠 𝐨𝐧 http://{HOST}:{PORT}")
        print("[+] 𝐏𝐫𝐞𝐬𝐬 𝐂𝐭𝐫𝐥+𝐂 𝐭𝐨 𝐬𝐭𝐨𝐩.")
        print("-" * 60)
        
        # 𝐊𝐞𝐞𝐩 𝐭𝐡𝐞 𝐬𝐞𝐫𝐯𝐞𝐫 𝐫𝐮𝐧𝐧𝐢𝐧𝐠
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n[!] 𝐑𝐞𝐜𝐞𝐢𝐯𝐞𝐝 𝐢𝐧𝐭𝐞𝐫𝐫𝐮𝐩𝐭 𝐬𝐢𝐠𝐧𝐚𝐥. 𝐒𝐡𝐮𝐭𝐭𝐢𝐧𝐠 𝐝𝐨𝐰𝐧...")
    except Exception as e:
        print(f"[!] 𝐒𝐞𝐫𝐯𝐞𝐫 𝐞𝐫𝐫𝐨𝐫: {e}")
    finally:
        bot_manager.stop_bot()
        print("[+] 𝐒𝐡𝐮𝐭𝐝𝐨𝐰𝐧 𝐜𝐨𝐦𝐩𝐥𝐞𝐭𝐞.")


# ============================================================================
# 𝐄𝐧𝐭𝐫𝐲 𝐏𝐨𝐢𝐧𝐭
# ============================================================================
if __name__ == "__main__":
    main()
