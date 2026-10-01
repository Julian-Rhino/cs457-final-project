# Game State Machine Specification

## 1. Overview

The server uses a state machine to control the Tic-Tac-Toe game. Each state represents a different part of the game, such as waiting for players, taking turns, checking moves, and ending the game.

The main states are:

- `INIT`
- `WAITING_FOR_PLAYERS`
- `GAME_START`
- `PLAYER_TURN`
- `EVALUATE_MOVE`
- `GAME_OVER`
- `CLEANUP`

The state machine also handles invalid moves, out-of-turn moves, malformed messages, and player disconnects.

## 2. Server State Diagram

```mermaid
stateDiagram-v2
    [*] --> INIT

    INIT --> WAITING_FOR_PLAYERS: Server started and listening

    WAITING_FOR_PLAYERS --> GAME_START: 2 clients connected
    WAITING_FOR_PLAYERS --> CLEANUP: Waiting player disconnects

    GAME_START --> PLAYER_TURN: Initialize board, Player 1 = X and Player 2 = O

    PLAYER_TURN --> EVALUATE_MOVE: Active player sends MOVE
    PLAYER_TURN --> PLAYER_TURN: Out-of-turn or malformed MOVE / send ERROR
    PLAYER_TURN --> GAME_OVER: Player disconnects / opponent wins by forfeit

    EVALUATE_MOVE --> PLAYER_TURN: Valid move / next player's turn
    EVALUATE_MOVE --> PLAYER_TURN: Invalid move / send ERROR
    EVALUATE_MOVE --> GAME_OVER: Victory or draw detected
    EVALUATE_MOVE --> GAME_OVER: Player disconnects

    GAME_OVER --> CLEANUP: Broadcast final results
    CLEANUP --> WAITING_FOR_PLAYERS: Reset state
