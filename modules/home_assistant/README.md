# Home Assistant module

Koppel Server Up met Home Assistant via de REST API.

## Vereisten

- Home Assistant bereikbaar op het netwerk
- Long-Lived Access Token (geen extra dependencies — gebruikt Python stdlib)

## Configuratie

Ga naar **Instellingen** en vul in:

| Instelling | Voorbeeld |
|---|---|
| `HA_URL` | `http://homeassistant.local:8123` |
| `HA_TOKEN` | `eyJhbGciOiJI...` (Long-Lived Access Token) |
| `HA_WEBHOOK_ID` | `server_up_events` (optioneel) |

### Token aanmaken in HA

1. Ga naar **Profiel** → **Beveiliging**
2. Scroll naar **Long-Lived Access Tokens**
3. Klik **Token aanmaken** → geef naam → kopieer

## Functies

- **Verbindingsstatus** — toont HA versie en verbindingsstatus
- **Service aanroepen** — roep elke HA service aan (licht, schakelaar, script, ...)
- **Notificatie sturen** — via elke HA notify service
- **Webhook triggeren** — trigger HA automations via webhook

## Combineren met MQTT

Installeer ook de **MQTT module** om rechtstreeks naar MQTT te publiceren.  
De MQTT module heeft een `test-ha` endpoint die via MQTT een testbericht naar HA stuurt.
