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
    # Keep partial TCP data until a complete JSON line is available.
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
    # Store outgoing data until the socket is ready to send it.
    outgoing_buffers[client_socket] += encode_message(message)

    selector.modify(
        client_socket,
        selectors.EVENT_READ | selectors.EVENT_WRITE,
        data="client",
    )


def send_error(selector, client_socket, outgoing_buffers, code, text):
    message = make_server_message(
        "ERROR",
        {
            "code": code,
            "message": text,
        },
    )

    queue_message(
        selector,
        client_socket,
        outgoing_buffers,
        message,
    )


def check_winner(board, mark):
    # Check every possible winning row, column, and diagonal.
    winning_lines = [
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),
        (0, 4, 8),
        (2, 4, 6),
    ]

    for a, b, c in winning_lines:
        if board[a] == mark and board[b] == mark and board[c] == mark:
            return True

    return False


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

    board = [""] * 9
    active_player = None
    x_player = None
    o_player = None
    scores = {}
    game_over = False

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

    # One selector loop handles the server socket and both players.
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

                            msg_type = message.get("msg_type")

                            if msg_type == "CONNECT":
                                player_name = message.get("player_id")

                                if not player_name:
                                    send_error(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        "INVALID_CONNECT",
                                        "Player name is required.",
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

                                    board = [""] * 9
                                    x_player = player_1
                                    o_player = player_2
                                    active_player = player_1
                                    game_over = False

                                    scores[player_1] = 0
                                    scores[player_2] = 0

                                    start_message = make_server_message(
                                        "GAME_START",
                                        {
                                            "player_1": player_1,
                                            "player_2": player_2,
                                            "x_player": x_player,
                                            "o_player": o_player,
                                            "active_player": active_player,
                                        },
                                    )

                                    for player_socket in players:
                                        queue_message(
                                            selector,
                                            player_socket,
                                            outgoing_buffers,
                                            start_message,
                                        )

                            elif msg_type == "MOVE":
                                # Check the move before changing the board.
                                player_name = player_names.get(client_socket)

                                if len(players) < 2:
                                    send_error(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        "GAME_NOT_READY",
                                        "The game has not started yet.",
                                    )
                                    continue

                                if game_over:
                                    send_error(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        "GAME_OVER",
                                        "The game is already over.",
                                    )
                                    continue

                                if player_name != active_player:
                                    send_error(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        "OUT_OF_TURN",
                                        "It is not your turn.",
                                    )
                                    continue

                                payload = message.get("payload", {})
                                row = payload.get("row")
                                col = payload.get("col")

                                if not isinstance(row, int) or not isinstance(col, int):
                                    send_error(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        "INVALID_MOVE",
                                        "Row and column must be numbers from 0 to 2.",
                                    )
                                    continue

                                if row < 0 or row > 2 or col < 0 or col > 2:
                                    send_error(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        "INVALID_MOVE",
                                        "Row and column must be between 0 and 2.",
                                    )
                                    continue

                                index = row * 3 + col

                                if board[index] != "":
                                    send_error(
                                        selector,
                                        client_socket,
                                        outgoing_buffers,
                                        "INVALID_MOVE",
                                        "That square is already occupied.",
                                    )
                                    continue

                                if player_name == x_player:
                                    mark = "X"
                                else:
                                    mark = "O"

                                board[index] = mark

                                if check_winner(board, mark):
                                    scores[player_name] += 1
                                    game_over = True

                                    state_message = make_server_message(
                                        "STATE_UPDATE",
                                        {
                                            "board": board,
                                            "active_player": player_name,
                                            "scores": scores,
                                        },
                                    )

                                    game_over_message = make_server_message(
                                        "GAME_OVER",
                                        {
                                            "result": "WIN",
                                            "winner": player_name,
                                            "board": board,
                                            "scores": scores,
                                        },
                                    )

                                    for player_socket in players:
                                        queue_message(
                                            selector,
                                            player_socket,
                                            outgoing_buffers,
                                            state_message,
                                        )

                                        queue_message(
                                            selector,
                                            player_socket,
                                            outgoing_buffers,
                                            game_over_message,
                                        )

                                    print(f"Winner: {player_name}")
                                    print(f"Final board: {board}")

                                    continue

                                if "" not in board:
                                    game_over = True

                                    state_message = make_server_message(
                                        "STATE_UPDATE",
                                        {
                                            "board": board,
                                            "active_player": player_name,
                                            "scores": scores,
                                        },
                                    )

                                    game_over_message = make_server_message(
                                        "GAME_OVER",
                                        {
                                            "result": "DRAW",
                                            "winner": None,
                                            "board": board,
                                            "scores": scores,
                                        },
                                    )

                                    for player_socket in players:
                                        queue_message(
                                            selector,
                                            player_socket,
                                            outgoing_buffers,
                                            state_message,
                                        )

                                        queue_message(
                                            selector,
                                            player_socket,
                                            outgoing_buffers,
                                            game_over_message,
                                        )

                                    print("Game ended in a draw.")
                                    print(f"Final board: {board}")

                                    continue

                                if active_player == x_player:
                                    active_player = o_player
                                else:
                                    active_player = x_player

                                state_message = make_server_message(
                                    "STATE_UPDATE",
                                    {
                                        "board": board,
                                        "active_player": active_player,
                                        "scores": scores,
                                    },
                                )

                                for player_socket in players:
                                    queue_message(
                                        selector,
                                        player_socket,
                                        outgoing_buffers,
                                        state_message,
                                    )

                                print(f"Board: {board}")
                                print(f"Next turn: {active_player}")

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