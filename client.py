import argparse
import json
import socket
import sys
import time


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
        description="Tic-Tac-Toe game client"
    )

    parser.add_argument(
        "-i",
        "--hostname",
        required=True,
        help="Server DNS hostname or IP address",
    )

    parser.add_argument(
        "-p",
        "--port",
        type=valid_port,
        required=True,
        help="Server port number (1024-65535)",
    )

    return parser.parse_args()


def encode_message(message):
    return (json.dumps(message) + "\n").encode("utf-8")


def send_message(sock, msg_type, player_id, payload=None):
    message = {
        "msg_type": msg_type,
        "player_id": player_id,
        "timestamp": int(time.time()),
    }

    if payload is not None:
        message["payload"] = payload

    sock.sendall(encode_message(message))


def receive_message(sock, buffer):
    while "\n" not in buffer:
        data = sock.recv(1024)

        if not data:
            return None, buffer

        buffer += data.decode("utf-8")

    line, buffer = buffer.split("\n", 1)

    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return {}, buffer

    return message, buffer


def display_board(board):
    cells = []

    for index, value in enumerate(board):
        if value:
            cells.append(value)
        else:
            cells.append(str(index + 1))

    print()
    print(f" {cells[0]} | {cells[1]} | {cells[2]} ")
    print("---+---+---")
    print(f" {cells[3]} | {cells[4]} | {cells[5]} ")
    print("---+---+---")
    print(f" {cells[6]} | {cells[7]} | {cells[8]} ")
    print()


def get_move():
    while True:
        choice = input("Choose a square (1-9): ").strip()

        try:
            position = int(choice)
        except ValueError:
            print("Please enter a number from 1 to 9.")
            continue

        if position < 1 or position > 9:
            print("Please enter a number from 1 to 9.")
            continue

        index = position - 1
        row = index // 3
        col = index % 3

        return row, col


def main():
    args = parse_arguments()

    try:
        server_ip = socket.gethostbyname(args.hostname)
    except socket.gaierror:
        print(
            f"[ERROR] Unable to resolve DNS hostname "
            f"'{args.hostname}'."
        )
        print(
            "Please check your Cisco router DNS configuration "
            "('ip dns server' / 'ip host') or verify domain spelling."
        )
        sys.exit(1)

    print(f"Server resolved to {server_ip}")

    player_name = input("Enter your player name: ").strip()

    while not player_name:
        print("Player name cannot be empty.")
        player_name = input("Enter your player name: ").strip()

    client_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    try:
        client_socket.connect((server_ip, args.port))
    except ConnectionRefusedError:
        print(
            f"[ERROR] Connection to {args.hostname}:{args.port} "
            "was refused."
        )
        client_socket.close()
        sys.exit(1)
    except OSError as error:
        print(f"[ERROR] Unable to connect to the server: {error}")
        client_socket.close()
        sys.exit(1)

    print(f"Connected to {args.hostname}:{args.port}")

    send_message(
        client_socket,
        "CONNECT",
        player_name,
    )

    buffer = ""
    my_mark = None
    game_finished = False

    try:
        while not game_finished:
            message, buffer = receive_message(
                client_socket,
                buffer,
            )

            if message is None:
                print("Server disconnected.")
                break

            if not message:
                continue

            msg_type = message.get("msg_type")
            payload = message.get("payload", {})

            if msg_type == "LOBBY_WAIT":
                print("Waiting for Player 2...")

            elif msg_type == "GAME_START":
                x_player = payload.get("x_player")
                o_player = payload.get("o_player")
                active_player = payload.get("active_player")

                if player_name == x_player:
                    my_mark = "X"
                elif player_name == o_player:
                    my_mark = "O"

                print()
                print("Game started!")
                print(f"You are Player {my_mark}.")
                print(f"Player X: {x_player}")
                print(f"Player O: {o_player}")

                if active_player == player_name:
                    print("Your Turn")
                    display_board([""] * 9)

                    row, col = get_move()

                    send_message(
                        client_socket,
                        "MOVE",
                        player_name,
                        {
                            "row": row,
                            "col": col,
                        },
                    )
                else:
                    print("Waiting for the other player...")

            elif msg_type == "STATE_UPDATE":
                board = payload.get("board", [""] * 9)
                active_player = payload.get("active_player")
                scores = payload.get("scores", {})

                display_board(board)

                print("Scores:")

                for name, score in scores.items():
                    print(f"  {name}: {score}")

                if active_player == player_name:
                    print("\nYour Turn")

                    row, col = get_move()

                    send_message(
                        client_socket,
                        "MOVE",
                        player_name,
                        {
                            "row": row,
                            "col": col,
                        },
                    )
                else:
                    print("\nWaiting for the other player...")

            elif msg_type == "ERROR":
                code = payload.get("code", "ERROR")
                text = payload.get(
                    "message",
                    "An error occurred.",
                )

                print(f"\n[ERROR] {code}: {text}")

                if code in {
                    "INVALID_MOVE",
                    "OUT_OF_TURN",
                }:
                    if code == "INVALID_MOVE":
                        print("Try another move.")

                        row, col = get_move()

                        send_message(
                            client_socket,
                            "MOVE",
                            player_name,
                            {
                                "row": row,
                                "col": col,
                            },
                        )

            elif msg_type == "GAME_OVER":
                board = payload.get("board", [""] * 9)
                result = payload.get("result")
                winner = payload.get("winner")
                scores = payload.get("scores", {})

                display_board(board)

                if result == "WIN":
                    if winner == player_name:
                        print("You won!")
                    else:
                        print(f"{winner} won the game.")

                elif result == "DRAW":
                    print("The game ended in a draw.")

                elif result == "FORFEIT":
                    if winner == player_name:
                        print("You won by forfeit.")
                    else:
                        print("The game ended by forfeit.")

                print("\nFinal scores:")

                for name, score in scores.items():
                    print(f"  {name}: {score}")

                game_finished = True

    except KeyboardInterrupt:
        print("\nDisconnecting from the server.")

        try:
            send_message(
                client_socket,
                "DISCONNECT",
                player_name,
                {
                    "reason": "quit",
                },
            )
        except OSError:
            pass

    except (
        ConnectionResetError,
        ConnectionAbortedError,
        BrokenPipeError,
    ):
        print("\nConnection to the server was lost.")

    finally:
        client_socket.close()


if __name__ == "__main__":
    main()