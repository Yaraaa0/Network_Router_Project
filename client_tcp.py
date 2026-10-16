import json
import socket
import threading

HOST = "127.0.0.1"
PORT = 5000


def receive_messages(client_socket):
    buffer = ""

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
                    response = json.loads(line)
                except json.JSONDecodeError:
                    print("Получен неизвестный ответ:", line)
                    continue

                if response.get("type") == "message":
                    print(
                        f"\nСообщение от {response['sender']} "
                        f"[{response['priority']}]: {response['text']}"
                    )
                    print("Введите команду: ", end="", flush=True)
                else:
                    print(f"\n{response.get('message', response)}")
                    print("Введите команду: ", end="", flush=True)

    except OSError:
        pass


def main():
    client_id = input("Введите ID клиента (Client1 или Client2): ").strip()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, PORT))

        registration = {
            "type": "register",
            "client_id": client_id
        }
        client_socket.sendall(
            (json.dumps(registration, ensure_ascii=False) + "\n").encode("utf-8")
        )

        response_buffer = ""
        while "\n" not in response_buffer:
            data = client_socket.recv(4096)
            if not data:
                print("Маршрутизатор закрыл соединение.")
                return
            response_buffer += data.decode("utf-8")

        line, response_buffer = response_buffer.split("\n", 1)
        response = json.loads(line)
        print(response.get("message", response))

        if response.get("type") != "registered":
            return

        threading.Thread(
            target=receive_messages,
            args=(client_socket,),
            daemon=True
        ).start()

        print("Команда: получатель | приоритет | текст")
        print("Пример: Client3 | HIGH | Привет")
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
                "recipient": recipient,
                "priority": priority.upper(),
                "text": text
            }

            try:
                client_socket.sendall(
                    (json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8")
                )
            except OSError:
                print("Соединение потеряно.")
                break

    print("TCP-клиент завершил работу.")


if __name__ == "__main__":
    main()