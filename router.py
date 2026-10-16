import json
import socket
import threading

HOST = "127.0.0.1"
TCP_PORT = 5000
UDP_PORT = 6000

with open("clients.json", "r", encoding="utf-8") as file:
    clients = json.load(file)

connected_clients = {}
clients_lock = threading.Lock()


def send_tcp(client_socket, data):
    message = json.dumps(data, ensure_ascii=False) + "\n"
    client_socket.sendall(message.encode("utf-8"))


def send_udp(udp_socket, address, data):
    message = json.dumps(data, ensure_ascii=False)
    udp_socket.sendto(message.encode("utf-8"), address)


def route_message(sender, recipient, priority, text, protocol, udp_socket):
    if recipient not in clients:
        return {
            "type": "error",
            "message": f"Получатель {recipient} не найден"
        }

    if recipient == sender:
        return {
            "type": "error",
            "message": "Нельзя отправить сообщение самому себе"
        }

    sender_info = clients[sender]
    target_info = clients[recipient]

    with clients_lock:
        target = connected_clients.get(recipient)

    print("\n[ROUTER] Получено сообщение")
    print("Отправитель:", sender)
    print("Получатель:", recipient)
    print("Подсеть отправителя:", sender_info["subnet"])
    print("Подсеть получателя:", target_info["subnet"])
    print("Протокол отправителя:", protocol)
    print("Протокол получателя:", target_info["protocol"])
    print("Приоритет:", priority)
    print("Сообщение:", text)

    if priority == "HIGH":
        print("[ROUTER] Приоритетное сообщение")

    if sender_info["subnet"] != target_info["subnet"]:
        print("[ROUTER] Выполняется маршрут между подсетями")
    else:
        print("[ROUTER] Сообщение внутри одной подсети")

    if protocol != target_info["protocol"]:
        print("[ROUTER] Пересылка между TCP и UDP")

    if target is None:
        return {
            "type": "error",
            "message": f"Получатель {recipient} не подключён"
        }

    forwarded = {
        "type": "message",
        "sender": sender,
        "recipient": recipient,
        "priority": priority,
        "text": text
    }

    try:
        if target_info["protocol"] == "TCP":
            send_tcp(target["socket"], forwarded)
        else:
            send_udp(udp_socket, target["address"], forwarded)
    except OSError as error:
        print("[ROUTER] Ошибка отправки:", error)
        return {
            "type": "error",
            "message": "Не удалось доставить сообщение"
        }

    print("[ROUTER] Сообщение отправлено")
    return {
        "type": "ack",
        "message": f"Сообщение отправлено клиенту {recipient}"
    }


def handle_tcp_client(client_socket, address, udp_socket):
    client_id = None
    buffer = ""

    print("[TCP] Подключение:", address)

    try:
        while True:
            data = client_socket.recv(4096)

            if not data:
                break

            buffer += data.decode("utf-8")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)

                if not line.strip():
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    send_tcp(client_socket, {
                        "type": "error",
                        "message": "Некорректный формат данных"
                    })
                    continue

                if request.get("type") == "register":
                    requested_id = request.get("client_id", "")

                    if requested_id not in clients:
                        send_tcp(client_socket, {
                            "type": "error",
                            "message": "Клиент не найден в clients.json"
                        })
                        continue

                    if clients[requested_id]["protocol"] != "TCP":
                        send_tcp(client_socket, {
                            "type": "error",
                            "message": "Для этого клиента нужен UDP"
                        })
                        continue

                    with clients_lock:
                        if requested_id in connected_clients:
                            send_tcp(client_socket, {
                                "type": "error",
                                "message": "Этот клиент уже подключён"
                            })
                            continue

                        client_id = requested_id
                        connected_clients[client_id] = {
                            "protocol": "TCP",
                            "socket": client_socket,
                            "address": address
                        }

                    print("[TCP] Зарегистрирован:", client_id)
                    send_tcp(client_socket, {
                        "type": "registered",
                        "message": f"{client_id} успешно подключён"
                    })

                elif request.get("type") == "message":
                    if client_id is None:
                        send_tcp(client_socket, {
                            "type": "error",
                            "message": "Сначала зарегистрируйтесь"
                        })
                        continue

                    result = route_message(
                        client_id,
                        request.get("recipient", ""),
                        request.get("priority", "NORMAL").upper(),
                        request.get("text", ""),
                        "TCP",
                        udp_socket
                    )
                    send_tcp(client_socket, result)

    except (ConnectionResetError, OSError) as error:
        print("[TCP] Соединение завершено:", error)

    finally:
        if client_id is not None:
            with clients_lock:
                current = connected_clients.get(client_id)
                if current and current.get("socket") is client_socket:
                    del connected_clients[client_id]

            print("[TCP] Отключён:", client_id)

        client_socket.close()


def tcp_server(udp_socket):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, TCP_PORT))
    server_socket.listen()

    print(f"[TCP] Сервер запущен: {HOST}:{TCP_PORT}")

    while True:
        client_socket, address = server_socket.accept()

        threading.Thread(
            target=handle_tcp_client,
            args=(client_socket, address, udp_socket),
            daemon=True
        ).start()


def udp_server(udp_socket):
    print(f"[UDP] Сервер запущен: {HOST}:{UDP_PORT}")

    while True:
        data, address = udp_socket.recvfrom(4096)

        try:
            request = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            send_udp(udp_socket, address, {
                "type": "error",
                "message": "Некорректный формат данных"
            })
            continue

        if request.get("type") == "register":
            client_id = request.get("client_id", "")

            if client_id not in clients:
                send_udp(udp_socket, address, {
                    "type": "error",
                    "message": "Клиент не найден в clients.json"
                })
                continue

            if clients[client_id]["protocol"] != "UDP":
                send_udp(udp_socket, address, {
                    "type": "error",
                    "message": "Для этого клиента нужен TCP"
                })
                continue

            with clients_lock:
                current = connected_clients.get(client_id)

                if current and current["address"] != address:
                    send_udp(udp_socket, address, {
                        "type": "error",
                        "message": "Этот клиент уже подключён"
                    })
                    continue

                connected_clients[client_id] = {
                    "protocol": "UDP",
                    "address": address
                }

            print("[UDP] Зарегистрирован:", client_id)
            send_udp(udp_socket, address, {
                "type": "registered",
                "message": f"{client_id} успешно подключён"
            })

        elif request.get("type") == "message":
            client_id = request.get("client_id", "")

            with clients_lock:
                current = connected_clients.get(client_id)

            if not current or current["address"] != address:
                send_udp(udp_socket, address, {
                    "type": "error",
                    "message": "Сначала зарегистрируйтесь"
                })
                continue

            result = route_message(
                client_id,
                request.get("recipient", ""),
                request.get("priority", "NORMAL").upper(),
                request.get("text", ""),
                "UDP",
                udp_socket
            )
            send_udp(udp_socket, address, result)


def main():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((HOST, UDP_PORT))

    print("Маршрутизатор запущен.")

    threading.Thread(
        target=tcp_server,
        args=(udp_socket,),
        daemon=True
    ).start()

    threading.Thread(
        target=udp_server,
        args=(udp_socket,),
        daemon=True
    ).start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nМаршрутизатор остановлен.")
    finally:
        udp_socket.close()


if __name__ == "__main__":
    main()