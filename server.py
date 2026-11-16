import argparse
import json
import selectors
import socket
import time


HOST = "0.0.0.0"
MAX_CLIENTS = 2


def encode_message(message):
    return (json.dumps(message) + "\n").encode("utf-8")


def decode_messages(buffer, data):
    buffer += data.decode("utf-8")
    messages = []

    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)

        if not line.strip():
            continue

        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            print("Received invalid JSON message")

    return messages, buffer


def make_server_message(msg_type, payload=None):
    message = {
        "msg_type": msg_type,
        "player_id": "SERVER",
        "timestamp": int(time.time()),
    }

    if payload is not None:
        message["payload"] = payload

    return message


def queue_message(selector, client_socket, outgoing_buffers, message):
    outgoing_buffers[client_socket] += encode_message(message)

    selector.modify(
        client_socket,
        selectors.EVENT_READ | selectors.EVENT_WRITE,
        data="client",
    )


def valid_port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Port must be a number.")

    if port < 1024 or port > 65535:
        raise argparse.ArgumentTypeError(
            "Port must be between 1024 and 65535."
        )

    return port


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Tic-Tac-Toe game server"
    )

    parser.add_argument(
        "-p",
        "--port",
        type=valid_port,
        required=True,
        help="Port number to listen on (1024-65535)",
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    selector = selectors.DefaultSelector()

    clients = set()
    receive_buffers = {}
    outgoing_buffers = {}
    player_names = {}
    players = []

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )

    server_socket.bind((HOST, args.port))
    server_socket.listen()
    server_socket.setblocking(False)

    selector.register(
        server_socket,
        selectors.EVENT_READ,
        data="server",
    )

    print(f"Server listening on 0.0.0.0:{args.port}")

    try:
        while True:
            events = selector.select()

            for key, mask in events:
                if key.data == "server":
                    client_socket, address = server_socket.accept()

                    if len(clients) >= MAX_CLIENTS:
                        print(f"Connection rejected from {address}")
                        client_socket.close()
                        continue

                    client_socket.setblocking(False)

                    clients.add(client_socket)
                    receive_buffers[client_socket] = ""
                    outgoing_buffers[client_socket] = b""

                    selector.register(
                        client_socket,
                        selectors.EVENT_READ,
                        data="client",
                    )

                    print(f"Client connected: {address}")

                else:
                    client_socket = key.fileobj

                    if mask & selectors.EVENT_READ:
                        try:
                            data = client_socket.recv(1024)
                        except ConnectionResetError:
                            data = b""

                        if not data:
                            print("Client disconnected")

                            selector.unregister(client_socket)
                            clients.remove(client_socket)
                            receive_buffers.pop(client_socket, None)
                            outgoing_buffers.pop(client_socket, None)
                            player_names.pop(client_socket, None)

                            if client_socket in players:
                                players.remove(client_socket)

                            client_socket.close()
                            continue

                        messages, receive_buffers[client_socket] = (
                            decode_messages(
                                receive_buffers[client_socket],
                                data,
                            )
                        )

                        for message in messages:
                            print(f"Received: {message}")

                            if message.get("msg_type") == "CONNECT":
                                player_name = message.get("player_id")

                                if not player_name:
                                    error_message = make_server_message(
                                        "ERROR",
                                        {
                                            "code": "INVALID_CONNECT",
                                            "message": "Player name is required.",
                                        },
                                    )

                                    queue_message(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        error_message,
                                    )

                                    continue

                                if client_socket in player_names:
                                    continue

                                player_names[client_socket] = player_name
                                players.append(client_socket)

                                print(f"Player joined: {player_name}")

                                if len(players) == 1:
                                    wait_message = make_server_message(
                                        "LOBBY_WAIT",
                                        {
                                            "status": "WAITING_FOR_PLAYER_2"
                                        },
                                    )

                                    queue_message(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        wait_message,
                                    )

                                elif len(players) == 2:
                                    player_1 = player_names[players[0]]
                                    player_2 = player_names[players[1]]

                                    start_message = make_server_message(
                                        "GAME_START",
                                        {
                                            "player_1": player_1,
                                            "player_2": player_2,
                                            "x_player": player_1,
                                            "o_player": player_2,
                                            "active_player": player_1,
                                        },
                                    )

                                    for player_socket in players:
                                        queue_message(
                                            selector,
                                            player_socket,
                                            outgoing_buffers,
                                            start_message,
                                        )

                    if mask & selectors.EVENT_WRITE:
                        data = outgoing_buffers.get(client_socket, b"")

                        if data:
                            try:
                                sent = client_socket.send(data)
                                outgoing_buffers[client_socket] = data[sent:]
                            except BlockingIOError:
                                pass

                        if not outgoing_buffers.get(client_socket):
                            selector.modify(
                                client_socket,
                                selectors.EVENT_READ,
                                data="client",
                            )

    except KeyboardInterrupt:
        print("\nServer stopped.")

    finally:
        for client_socket in list(clients):
            selector.unregister(client_socket)
            client_socket.close()

        selector.unregister(server_socket)
        server_socket.close()
        selector.close()


if __name__ == "__main__":
    main()