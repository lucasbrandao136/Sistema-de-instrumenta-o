import socket
import threading
import time

ESP_PORT = 8889
PC_PORT = 8888

esps = {} 
ips_para_id = {}
id_counter = 1
lock = threading.Lock()
running = True
sock = None

num_sensores = 0
distancia_sensores_cm = 0.0 

velocidades = {} 

def setup_socket():
    """Configura e retorna o socket UDP."""
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", PC_PORT))
    sock.settimeout(0.5)

def enviar_cmd(id_esp, comando):
    """Envia um comando para um ou todos os ESPs."""
    with lock:
        if id_esp == 'all':
            ips_a_enviar = [info['ip'] for info in esps.values()]
        else:
            ips_a_enviar = [esps[id_esp]['ip']] if id_esp in esps else []

        if not ips_a_enviar:
            print(f"[ERRO] ESP {id_esp} não encontrado ou lista vazia.")
            return

        for ip in ips_a_enviar:
            try:
                sock.sendto(f"{comando}".encode(), (ip, ESP_PORT))
                print(f"[ENVIADO] Comando '{comando}' para ESP com IP {ip}")
            except Exception as e:
                print(f"Erro ao enviar comando para {ip}: {e}")

def ping_loop():
    """Envia pings de broadcast para manter a detecção de ESPs ativos."""
    while running:
        sock.sendto(b"handshake_request", ("255.255.255.255", ESP_PORT))
        time.sleep(5)

def escuta_esp():
    """Ouve por mensagens de todos os ESPs e realiza a análise de movimento."""
    global id_counter
    global velocidades
    while running:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode(errors="ignore").strip()
            ip_origem = addr[0]
            current_time = time.time()

            with lock:
                if msg == "handshake_request":
                    if ip_origem not in ips_para_id:
                        novo_id = str(id_counter)
                        id_counter += 1
                        esps[novo_id] = {"ip": ip_origem, "last": current_time, "online": True, "last_detection_time": 0}
                        ips_para_id[ip_origem] = novo_id
                        sock.sendto(f"id:{novo_id}".encode(), (ip_origem, ESP_PORT))
                        print(f"[HANDSHAKE] Novo ESP em {ip_origem} -> ID {novo_id}")
                    else:
                        id_existente = ips_para_id[ip_origem]
                        esps[id_existente]['last'] = current_time
                        esps[id_existente]['online'] = True
                
                elif msg.startswith("object_detected:"):
                    esp_id = msg.split(":")[1]
                    detection_time_display = time.strftime('%H:%M:%S', time.localtime(current_time))
                    print(f"\n[DETECÇÃO] Obstáculo no ESP de ID {esp_id} em {detection_time_display}")
                    
                    if esp_id in esps:
                        esps[esp_id]['last_detection_time'] = current_time
                        
                        if num_sensores >= 2 and distancia_sensores_cm > 0:
                            sorted_ids = sorted(esps.keys(), key=int)
                            try:
                                current_index = sorted_ids.index(esp_id)
                                if current_index > 0:
                                    prev_id = sorted_ids[current_index - 1]
                                    prev_detection_time = esps[prev_id]['last_detection_time']

                                    if prev_detection_time > 0 and (current_time - prev_detection_time) > 0.05:
                                        delta_t = current_time - prev_detection_time
                                        velocidade_cm_s = distancia_sensores_cm / delta_t
                                        velocidade_m_s = velocidade_cm_s / 100
                                        velocidades[esp_id] = velocidade_m_s
                                        print(f"  --> Velocidade entre ID {prev_id} e ID {esp_id}: {velocidade_cm_s:.2f} cm/s | {velocidade_m_s:.2f} m/s")

                                        if num_sensores >= 3 and current_index >= 2:
                                            prev_prev_id = sorted_ids[current_index - 2]
                                            if prev_id in velocidades:
                                                v1 = velocidades[prev_id]
                                                v2 = velocidades[esp_id]
                                                
                                                if abs(v2 - v1) < 0.1: 
                                                    movimento = "Movimento Uniforme"
                                                elif v2 > v1:
                                                    movimento = "Movimento Uniformemente Acelerado"
                                                else:
                                                    movimento = "Movimento Uniformemente Retardado"
                                                
                                                print(f"  --> Tipo de movimento: {movimento}")

                            except ValueError:
                                continue

        except socket.timeout:
            pass
        except Exception as e:
            if running:
                print(f"[ERRO] no listener: {e}")

def watchdog():
    """Monitora o status dos ESPs e marca como offline se não houver resposta."""
    while running:
        with lock:
            now = time.time()
            for id_esp, info in list(esps.items()):
                if now - info["last"] > 15:
                    if info["online"]:
                        info["online"] = False
                        print(f"[OFFLINE] ESP {id_esp} ({info['ip']})")
                else:
                    if not info["online"]:
                        info["online"] = True
                        print(f"[ONLINE] ESP {id_esp} ({info['ip']})")
        time.sleep(5)

def listar_esps():
    """Função para listar os ESPs conectados."""
    with lock:
        if not esps:
            print("Nenhum ESP encontrado.")
        else:
            print("\n--- ESPs conectados ---")
            for id_esp, info in sorted(esps.items(), key=lambda item: int(item[0])):
                status = "ONLINE" if info["online"] else "OFFLINE"
                last_seen = time.strftime('%H:%M:%S', time.localtime(info['last']))
                print(f"  - ID {id_esp} | IP: {info['ip']} | Status: {status} (Última vez visto: {last_seen})")

def menu():
    global running, num_sensores, distancia_sensores_cm

    print("--- Configuração Inicial ---")
    try:
        num_sensores = int(input("Digite a quantidade de sensores: "))
        distancia_sensores_cm = float(input("Digite a distância entre os sensores (em centímetros): "))
    except ValueError:
        print("Entrada inválida. Usando valores padrão: 2 sensores e 50 cm.")
        num_sensores = 2
        distancia_sensores_cm = 50.0

    print("\nIniciando o sistema de controle. Aguardando ESPs...")

    threading.Thread(target=ping_loop, daemon=True).start()
    threading.Thread(target=escuta_esp, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()

    while running:
        print("\n--- MENU ---")
        print("1 - Listar ESPs")
        print("2 - Piscar LED branco (Blink) em um ESP")
        print("3 - Resetar um ESP")
        print("4 - Esquecer obstáculo (resetar flag de detecção)")
        print("5 - Sair")
        
        escolha = input("Escolha uma opção: ").strip()

        if escolha == '1':
            listar_esps()
        elif escolha == '2':
            id_alvo = input("Digite o ID do ESP ou 'all' para todos: ").strip()
            enviar_cmd(id_alvo, "blink_white_led")
        elif escolha == '3':
            id_alvo = input("Digite o ID do ESP ou 'all' para todos: ").strip()
            enviar_cmd(id_alvo, "cancel_handshake")
        elif escolha == '4':
            id_alvo = input("Digite o ID do ESP ou 'all' para todos: ").strip()
            enviar_cmd(id_alvo, "forget_obstacle")
        elif escolha == '5':
            running = False
            print("Encerrando o programa...")
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    setup_socket()
    menu()