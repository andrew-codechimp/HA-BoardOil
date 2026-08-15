# BoardOil Home Assistant Integration

## Preview Release

This integration connects Home Assistant to [BoardOil](https://github.com/dozigden/boardoil).

### Sensors
- One device for each board
- One sensor for each column, showing the current card count

Sensor attributes include additional card details.

### Actions
- Get all cards for a board, optionally a specific column
- Get a specific card
- Add a new card

### Events
- Card events fire when a card is added, updated, moved, or removed.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrew-codechimp&repository=HA-BoardOil&category=Integration)

This is a HACS custom integration; if the link does not work, you will have to add this repository URL via HACS custom repositories.

## Setup

In BoardOil, create a Client Account in System Settings, then copy its token to use when adding this integration.

For each board you want Home Assistant to access, open Board Configuration and add that client account as a contributor under Members.
