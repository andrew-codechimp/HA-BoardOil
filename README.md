# BoardOil Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Downloads][download-latest-shield]]()
[![License][license-shield]](LICENSE)

This integration connects Home Assistant to [BoardOil](https://github.com/dozigden/boardoil) allowing you to automate card tasks.

Card viewing is not available from the UI because cards support complex features like card type, tags, slicks, and column transitions that Home Assistant to-do lists do not support.

### Sensors
- One device for each board
- One sensor for each column, showing the current card count

Sensor attributes include additional card details.

### Diagnostic sensors
- Card types count
- Tags count
- Slicks count
- Members count

Sensor attributes include lists of their relevant data.

### Actions
- Get all cards for a board, optionally a specific column
- Get a specific card
- Add a new card
- Update a card
- Delete a card
- Archive a card
- Add a comment to a card

### Events
- Card events fire when a card is added, updated, moved, or removed.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrew-codechimp&repository=HA-BoardOil&category=Integration)

This is a HACS custom integration; if the link does not work, you will have to add this repository URL via HACS custom repositories.

## Setup

In BoardOil, create a Client Account in System Settings, then copy its token to use when adding this integration.

For each board you want Home Assistant to access, open Board Configuration and add that client account as a contributor under Members.


[commits-shield]: https://img.shields.io/github/commit-activity/y/andrew-codechimp/HA-BoardOil.svg?style=for-the-badge
[commits]: https://github.com/andrew-codechimp/HA-BoardOil/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/andrew-codechimp/HA-BoardOil.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/andrew-codechimp/HA-BoardOil.svg?style=for-the-badge
[releases]: https://github.com/andrew-codechimp/HA-BoardOil/releases
[download-latest-shield]: https://img.shields.io/github/downloads/andrew-codechimp/HA-BoardOil/latest/total?style=for-the-badge
[hacs-installs-shield]: https://img.shields.io/endpoint.svg?url=https%3A%2F%2Flauwbier.nl%2Fhacs%2Fboardoil&style=for-the-badge
