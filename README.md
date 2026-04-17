# Board Oil Home Assistant Integration

## Preview Release

This integration connects Home Assistant to [Board Oil](https://github.com/dozigden/boardoil).

It creates:
- One device for each board
- One sensor for each column, showing the current card count

Sensor attributes include additional card details.

It also provides actions to:
- Get all cards
- Get a specific card
- Add a new card

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrew-codechimp&repository=HA-BoardOil&category=Integration)

## Setup

In Board Oil, create a Client Account in System Settings, then copy its token to use when adding this integration.

For each board you want Home Assistant to access, open Board Configuration and add that client account as a contributor under Members.
