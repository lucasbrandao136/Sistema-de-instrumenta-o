import socket

PORT = 8888

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', PORT))

print(f"Servidor escutando na porta {PORT}...\n")

while True:
    data, addr = sock.recvfrom(1024)
    print(f"[{addr[0]}] {data.decode()}")
