import json
import socket
import threading

HOST = "127.0.0.1"
PORT = 6000


def receive_messages(client_socket):
    while True:
        try:
            data, _ = client_socket.recvfrom(4096)
            response = json.loads(data.decode("utf-8"))

            if response.get("type") == "message":
                print(
                    f"\nСообщение от {response['sender']} "
                    f"[{response['priority']}]: {response['text']}"
                )
            else:
                print(f"\n{response.get('message', response)}")

            print("Введите команду: ", end="", flush=True)

        except OSError:
            break
        except json.JSONDecodeError:
            print("\nПолучен некорректный ответ.")


def main():
    client_id = input("Введите ID клиента (Client3 или Client4): ").strip()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.settimeout(5)

        registration = {
            "type": "register",
            "client_id": client_id
        }

        client_socket.sendto(
            json.dumps(registration, ensure_ascii=False).encode("utf-8"),
            (HOST, PORT)
        )

        try:
            data, _ = client_socket.recvfrom(4096)
            response = json.loads(data.decode("utf-8"))
        except socket.timeout:
            print("Нет ответа от маршрутизатора. Проверь, запущен ли он.")
            return

        print(response.get("message", response))

        if response.get("type") != "registered":
            return

        client_socket.settimeout(None)

        threading.Thread(
            target=receive_messages,
            args=(client_socket,),
            daemon=True
        ).start()

        print("Команда: получатель | приоритет | текст")
        print("Пример: Client1 | HIGH | Привет")
        print("Для выхода введи exit")

        while True:
            try:
                command = input("Введите команду: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if command.lower() == "exit":
                break

            parts = command.split("|", 2)

            if len(parts) != 3:
                print("Формат: получатель | NORMAL/HIGH | текст")
                continue

            recipient, priority, text = [part.strip() for part in parts]

            if priority.upper() not in ("NORMAL", "HIGH"):
                print("Приоритет должен быть NORMAL или HIGH.")
                continue

            request = {
                "type": "message",
                "client_id": client_id,
                "recipient": recipient,
                "priority": priority.upper(),
                "text": text
            }

            client_socket.sendto(
                json.dumps(request, ensure_ascii=False).encode("utf-8"),
                (HOST, PORT)
            )

    print("UDP-клиент завершил работу.")


if __name__ == "__main__":
    main()