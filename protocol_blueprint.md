# Application Protocol Blueprint

## 1. Transport and Serialization

This Tic-Tac-Toe application will use TCP for communication between the client and server.

Messages will be sent as JSON because it is structured, readable, and easy to work with in Python. Before sending a message, the JSON data will be encoded using UTF-8.

To separate messages, the protocol will use newline-delimited JSON. This means every complete JSON message will end with a newline character (`\n`).

This is important because TCP works as a continuous stream of bytes. One call to `recv()` does not always equal one full message. Sometimes one message arrives in pieces, and other times multiple messages arrive together. The newline at the end of each message gives the program a clear way to tell where one message ends and the next one begins.

## 2. TCP Framing Rule

Every JSON message will be encoded using UTF-8 and followed by one newline character (\n).

For example:

```text
{"msg_type": "CONNECT", "player_id": "Alice", "timestamp":1727000000}\n
