import argparse
import selectors
import socket


HOST = "0.0.0.0"
MAX_CLIENTS = 2


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

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, args.port))
    server_socket.listen()
    server_socket.setblocking(False)

    selector.register(server_socket, selectors.EVENT_READ, data="server")

    print(f"Server listening on 0.0.0.0:{args.port}")

    try:
        while True:
            events = selector.select()

            for key, _ in events:
                if key.data == "server":
                    client_socket, address = server_socket.accept()

                    if len(clients) >= MAX_CLIENTS:
                        print(f"Connection rejected from {address}")
                        client_socket.close()
                        continue

                    client_socket.setblocking(False)
                    clients.add(client_socket)
                    selector.register(
                        client_socket,
                        selectors.EVENT_READ,
                        data="client",
                    )

                    print(f"Client connected: {address}")

                else:
                    client_socket = key.fileobj

                    try:
                        data = client_socket.recv(1024)
                    except ConnectionResetError:
                        data = b""

                    if not data:
                        print("Client disconnected")
                        selector.unregister(client_socket)
                        clients.remove(client_socket)
                        client_socket.close()

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