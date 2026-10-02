# Application Protocol Blueprint

## 1. Transport and Serialization

This Tic-Tac-Toe application will use TCP for communication between the client and server.

Messages will be sent as JSON because it is structured, readable, and easy to work with in Python. Before sending a message, the JSON data will be encoded using UTF-8.

To separate messages, the protocol will use newline-delimited JSON. This means every complete JSON message will end with a newline character (`\n`).

This is important because TCP works as a continuous stream of bytes. One call to `recv()` does not always equal one full message. Sometimes one message arrives in pieces, and other times multiple messages arrive together. The newline at the end of each message gives the program a clear way to tell where one message ends and the next one begins.

## 2. TCP Framing Rule

Every JSON message will use UTF-8 and end with one newline character (`\n`). Each message will stay on one line, and the newline tells the program where that message ends.

For example:

```text
{"msg_type": "CONNECT", "player_id": "Alice", "timestamp":1727000000}\n
```

## 3. Message Format

Every message contains `msg_type`, `player_id`, and `timestamp`. Messages that need additional information also contain a `payload` object.

- `msg_type` - string that tells what kind of message it is
- `player_id` - string identifying the player or server
- `payload` - JSON object containing information for the message
- `timestamp` - integer containing the Unix timestamp in seconds

## 4. Message Types

### CONNECT

**Direction:** Client -> Server

**Purpose:** A player uses this message to join the game.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `timestamp` - integer

Example:

```json
{
  "msg_type": "CONNECT",
  "player_id": "Alice",
  "timestamp": 1727000000
}
```

### LOBBY_WAIT

**Direction:** Server -> Client

**Purpose:** Tells the first player that the server is waiting for another player.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `payload.status` - string containing the lobby status
- `timestamp` - integer

Example:

```json
{
  "msg_type": "LOBBY_WAIT",
  "player_id": "SERVER",
  "payload": {
    "status": "WAITING_FOR_PLAYER_2"
  },
  "timestamp": 1727000001
}
```


### GAME_START

**Direction:** Server -> Clients

**Purpose:** Tells both players that the game has started and assigns their roles.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `payload.player_1` - string
- `payload.player_2` - string
- `payload.x_player` - string
- `payload.o_player` - string
- `payload.active_player` - string
- `timestamp` - integer

Example:

```json
{
  "msg_type": "GAME_START",
  "player_id": "SERVER",
  "payload": {
    "player_1": "Alice",
    "player_2": "Bob",
    "x_player": "Alice",
    "o_player": "Bob",
    "active_player": "Alice"
  },
  "timestamp": 1727000002
}
```

### MOVE

**Direction:** Client -> Server

**Purpose:** The active player sends the row and column where they want to place their move.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `payload.row` - integer from 0 to 2
- `payload.col` - integer from 0 to 2
- `timestamp` - integer

Example:

```json
{
  "msg_type": "MOVE",
  "player_id": "Alice",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000005
}
```


### STATE_UPDATE

**Direction:** Server -> Clients

**Purpose:** Sends the updated board and tells both players whose turn is next.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `payload.board` - array of 9 strings; each string is `"X"`, `"O"`, or `""` for an empty square
- `payload.active_player` - string
- `payload.scores` - object mapping each player name to an integer score
- `timestamp` - integer

Example:

```json
{
  "msg_type": "STATE_UPDATE",
  "player_id": "SERVER",
  "payload": {
    "board": ["X", "", "", "", "O", "", "", "", ""],
    "active_player": "Bob",
    "scores": {
      "Alice": 0,
      "Bob": 0
    }
  },
  "timestamp": 1727000006
}
```

### ERROR

**Direction:** Server -> Client

**Purpose:** Tells a player that something was wrong with their move or message.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `payload.code` - string
- `payload.message` - string
- `timestamp` - integer

Example:

```json
{
  "msg_type": "ERROR",
  "player_id": "SERVER",
  "payload": {
    "code": "INVALID_MOVE",
    "message": "That square is already occupied."
  },
  "timestamp": 1727000007
}
```

### DISCONNECT

**Direction:** Client -> Server

**Purpose:** Tells the server that a player is intentionally leaving the game.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `payload.reason` - string
- `timestamp` - integer

Example:

```json
{
  "msg_type": "DISCONNECT",
  "player_id": "Alice",
  "payload": {
    "reason": "quit"
  },
  "timestamp": 1727000010
}
```


### GAME_OVER

**Direction:** Server -> Clients

**Purpose:** Tells both players that the game is finished and gives the final result.

**Fields:**
- `msg_type` - string
- `player_id` - string
- `payload.result` - string such as `WIN`, `DRAW`, or `FORFEIT`
- `payload.winner` - string or null
- `payload.board` - array of 9 strings; each string is `"X"`, `"O"`, or `""` for an empty square
- `payload.scores` - object mapping each player name to their final integer score
- `timestamp` - integer


Example:

```json
{
  "msg_type": "GAME_OVER",
  "player_id": "SERVER",
  "payload": {
    "result": "WIN",
    "winner": "Alice",
    "board": ["X", "O", "", "X", "O", "", "X", "", ""],
    "scores": {
      "Alice": 1,
      "Bob": 0
    }
  },
  "timestamp": 1727000020
}
```


## 5. Raw TCP Stream Example

TCP does not keep message boundaries, so multiple messages can arrive together or one message can arrive in pieces.

For example, two messages could appear on the wire like this:

```text
{"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":0,"col":2},"timestamp":1727000005}\n
```

The receiver keeps incoming data in a buffer.

When a newline character (`\n`) is found, the receiver knows that one complete message has arrived and can process it.

If multiple messages arrive together, they are separated using the newline characters.

If only part of a message arrives, the receiver keeps that data in the buffer and waits for the rest.

## 6. Connection Termination

A player can disconnect normally or unexpectedly.

### Normal Disconnect

A client can send a `DISCONNECT` message before closing the connection.

If the game is active, the other player wins by forfeit.

A normal TCP connection can also close using TCP FIN.

If `recv()` returns `b""`, it means the other side closed the connection. The server should stop the receive loop, close the socket, and treat the player as disconnected.

### Unexpected Disconnect

A connection can also end because of a network problem, client crash, or TCP reset.

The server should handle errors such as:

- `ConnectionResetError`
- `BrokenPipeError`
- `ConnectionAbortedError`
- `TimeoutError`

These errors should not crash the server.

If a player disconnects during an active game, the other player wins by forfeit. The server then moves to `GAME_OVER` and later to `CLEANUP`.
