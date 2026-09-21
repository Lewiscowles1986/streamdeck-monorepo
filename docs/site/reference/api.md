# REST API reference

The config API is a FastAPI app (`streamdeck.app:app`, served by
`streamdeck serve`). This page summarizes
[docs/openapi.yaml](../../openapi.yaml) — the machine-readable contract —
and adds the dialect notes you need when writing clients by hand. All
bodies are JSON.

Base URL (default): `http://127.0.0.1:8000`.

## Dialect rules

These are pinned by parity tests; don't "fix" them silently.

1. **Devices, Configs, AgentActions serialize camelCase aliases**:
   `deviceType`, `currentConfigId`, `activeAgentId`, `agentId`,
   `buttonIndex`, `deviceId`, `createdAt`.
2. **The `Agent` model is the exception — snake_case** (`last_seen`): it has
   no aliases at all. The frontend reads both spellings elsewhere.
3. **Device `type` values are human names** from the vendored core
   ("Stream Deck XL", "Stream Deck Original", "Stream Deck +", …). Configs
   store kebab ids (`stream-deck-xl`); the runner matches
   case-insensitively with space→dash tolerance.
4. **`buttons` and `triggers` (and `AgentAction.action`) are schema-less
   JSON columns** — the API stores whatever JSON you send and hands it back
   verbatim; validation is the runner's/agent's job (they defend against
   garbage instead of rejecting).
5. **`PUT /config/{id}` replaces the whole row** — a body missing
   `name`/`deviceType`/`buttons` is rejected (422), and a body *without* a
   `triggers` key **clears** the triggers block (replace semantics, same as
   every other field).
6. **`DELETE /config/{id}` returns 200 with the deleted row** — not 204.
   Deleting a config also clears any `current_config_id` pointing at it.

## Endpoints

### Devices

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/devices` | List all devices ever seen | Enumerates real/emulated decks as a side effect and upserts newly seen ones; returns rows with live `connected` status. |
| PUT | `/device/{device_id}/config/{config_id}` | Assign a config to a device | 404 if either id is unknown. Returns the updated device. |
| GET | `/device/{device_id}/config` | The config currently assigned to a device | Runner-facing. Returns `{config, device}` — `config` is `null` when nothing is assigned. Device serialized camelCase. |

```sh
# assign
curl -X PUT http://127.0.0.1:8000/device/DUMMY0fd90060/config/$CONFIG_ID

# what the runner consumes
curl -s http://127.0.0.1:8000/device/DUMMY0fd90060/config
```

```json
{
  "config": {
    "buttons": [{"index": 0, "idle": {"text": "HI"}}],
    "deviceType": "stream-deck-xl",
    "name": "Docs Spot-Check",
    "triggers": null,
    "id": "b8ba7ddc-d720-45f5-a61a-eb8ba88823af"
  },
  "device": {
    "connected": false,
    "id": "DUMMY0fd90060",
    "activeAgentId": null,
    "name": "Stream Deck Original - DUMMY0fd90060",
    "currentConfigId": "b8ba7ddc-d720-45f5-a61a-eb8ba88823af",
    "type": "Stream Deck Original"
  }
}
```

### Configs

| Method | Path | Purpose | Status |
| --- | --- | --- | --- |
| GET | `/configs` | List all configurations | 200 |
| POST | `/config` | Create a configuration | **201** (id server-generated) |
| GET | `/config/{config_id}` | Fetch one configuration | 200 / 404 |
| PUT | `/config/{config_id}` | **Replace** a configuration (full body required) | 200 / 404 / **422** for partial bodies |
| DELETE | `/config/{config_id}` | Delete a configuration (also clears device assignments) | **200 with the deleted row** / 404 |

```sh
# create (201)
curl -s -X POST http://127.0.0.1:8000/config \
  -H 'Content-Type: application/json' \
  -d '{"name":"Docs Spot-Check","deviceType":"stream-deck-xl",
       "buttons":[{"index":0,"idle":{"text":"HI"}}]}'
```

CORS: the API allows the UI origins (`http://localhost:8080`,
`http://localhost:8081`) plus `*` with credentials — the UI on other ports
still works for local development (parity rule P5).

### Agents

The nominate-a-computer flow. **Snake_case wire dialect** on the `Agent`
model.

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/agents` | List registered agent computers | |
| POST | `/agents` | Register an agent (**idempotent upsert** by client-generated id) | 201 |
| DELETE | `/agents/{agent_id}` | Remove an agent | Clears any device nominations first. 200 with the deleted row / 404 |
| PUT | `/device/{device_id}/agent/{agent_id}` | Nominate an agent for a device | 404 if either id unknown |
| DELETE | `/device/{device_id}/agent` | Clear the device nomination | Actions fall back to local handling |
| GET | `/agents/{agent_id}/actions` | **Agent poll**: fetch pending actions | Marks each as `dispatched` (in the same request, serialized before the flip). 404 if agent unknown |
| POST | `/agents/{agent_id}/actions/{action_id}/result` | Report an action result | Body: `{"status": "done"|"failed"|"detached", …}` — stored on the row |
| POST | `/agent-actions` | Queue an action for an agent | **202**; `404` for unknown `agentId`; status forced to `pending`. Used by the device runner (and handy for curl testing) |

`AgentAction` lifecycle: `pending → dispatched → done | failed`.

```sh
# queue an action for an agent (202)
curl -s -X POST http://127.0.0.1:8000/agent-actions \
  -H 'Content-Type: application/json' \
  -d '{"agentId":"docs-agent-studio-1","deviceId":"DUMMY0fd90060",
       "buttonIndex":0,"action":{"type":"command","executable":"/bin/echo",
       "arguments":"hi"},"createdAt":"2026-09-20T12:00:00+0100"}'
```

The `action` field is schema-less JSON: whatever the runner/UI put on the
button (command, sequence, with templates) travels to the agent untouched.

## Object shapes

**Device** — `id` (serial), `type` (human name), `name`, `connected`,
`currentConfigId?`, `activeAgentId?`.

**Config** — `id` (server-generated), `name`, `deviceType` (kebab id),
`buttons` (JSON blob — see the [config schema](config-schema.md)),
`triggers` (JSON blob or null — see the [triggers reference](triggers.md)).

**Agent** — `id` (client-generated stable UUID), `hostname`, `user?`,
`platform?`, `active`, `last_seen?`.

**AgentAction** — `id`, `agentId`, `buttonIndex?`, `deviceId?`, `action`
(schema-less JSON), `status`, `createdAt?`, `result?` (schema-less).

## Error model

Standard FastAPI errors: `{"detail": "…"}` with 404 (unknown ids), 422
(validation — e.g. partial `PUT /config/{id}` bodies). See
[openapi.yaml](../../openapi.yaml) for the complete schemas.