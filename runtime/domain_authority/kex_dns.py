import socket
import struct
import threading
import time

class KexDNSServer:
    """
    Sovereign KEDDEH Network DNS Server.
    Intercepts *.keddeh queries and routes them directly into the KEX mesh.
    Operates without reliance on ICANN or standard registrars.
    """
    def __init__(self, host='127.0.0.1', port=9053):
        self.host = host
        self.port = port
        self.running = False
        self.sock = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.running = True
        print(f"[KEX_DNS] Sovereign Resolver online at {self.host}:{self.port}")
        
        thread = threading.Thread(target=self._listen, daemon=True)
        thread.start()

    def _listen(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(512)
                response = self._build_response(data)
                if response:
                    self.sock.sendto(response, addr)
            except Exception as e:
                print(f"[KEX_DNS] Error: {e}")

    def _build_response(self, data):
        try:
            header = struct.unpack('!HHHHHH', data[:12])
            tx_id = header[0]
            qdcount = header[2]
            idx = 12
            domain_parts = []
            while True:
                length = data[idx]
                if length == 0:
                    idx += 1
                    break
                domain_parts.append(data[idx+1:idx+1+length].decode('utf-8'))
                idx += length + 1

            domain = ".".join(domain_parts)
            qtype, qclass = struct.unpack('!HH', data[idx:idx+4])
            resolved_ip = None
            if qtype == 1:
                from kex_registrar_service import resolve_domain
                resolved_ip = resolve_domain(domain)

            if resolved_ip:
                print(f"[KEX_DNS] Found Route in Substrate: {domain} -> {resolved_ip}")
                response_flags = 0x8180
                ans_count = 1
                res_header = struct.pack('!HHHHHH', tx_id, response_flags, qdcount, ans_count, 0, 0)
                res_question = data[12:idx+4]
                ip_bytes = socket.inet_aton(resolved_ip)
                res_answer = struct.pack('!HHHLH', 0xC00C, 1, 1, 60, 4) + ip_bytes
                return data[:12] + res_header[12:] + res_question + res_answer
            else:
                response_flags = 0x8183
                res_header = struct.pack('!HHHHHH', tx_id, response_flags, qdcount, 0, 0, 0)
                return data[:12] + res_header[12:] + data[12:idx+4]

        except Exception as e:
            print(f"[KEX_DNS] Parsing Error: {e}")
            return None

def start_dns_mesh():
    server = KexDNSServer()
    server.start()
    return server

if __name__ == "__main__":
    s = start_dns_mesh()
    while True:
        time.sleep(1)
