# AI Prompting and Constraint Strategy

## Purpose

If I use AI to help write code, it must follow `protocol_blueprint.md` and `fsm_specification.md` instead of creating its own protocol or game rules.

## Protocol Prompt

> Help me implement the networking code for my Tic-Tac-Toe project.
>
> Follow `protocol_blueprint.md` exactly.
>
> Use TCP, UTF-8 JSON, and newline-delimited messages.
> Do not rename fields or create new message types.
> Handle partial messages and multiple messages arriving in one `recv()` call.
> Reject malformed messages instead of guessing missing information.

## FSM Prompt

> Implement the server logic using `fsm_specification.md`.
>
> Use only the states already defined.
> Invalid or out-of-turn moves should send an ERROR message.
> Player disconnects should not crash the server.
> If a player disconnects during a game, the other player wins by forfeit.

## Rules for AI-Generated Code

- Follow my protocol field names exactly.
- Follow my FSM transitions.
- Do not invent new message types.
- Validate messages before changing game state.
- Handle normal and unexpected disconnects.
