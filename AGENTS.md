# Project Context

This is a fork VPforce TelemFFB that sends FFB telemetry to zFSB, a force sensing joystick base that has USB PID Force Feedback support.

Use dev_guidelines.md for coding style and additional architecture notes.

## Target Device

- Device name: zFSB Mk .II
- VID: `2E8A`
- PID: `FFB2`
- Firmware uses OpenFFB-style HID PID reports from

## TelemFFB Backend

- Use `telemffb/hw/ffb_zfsb.py`, not `ffb_rhino.py`.
- Default device should be `2E8A:FFB2`.
- VPForce `.vpconf` upload/configurator features are not required.
- VPForce Rhino report IDs should not be used unless explicitly implementing compatibility.

## FFB Override Behavior

- TelemFFB sends Effect Operation report `0x0A`.
- `OP_START_OVERRIDE = 4`.
- zFSB firmware should treat operation `4` as TelemFFB override mode, stopping or deprioritizing game-created effects as needed.

## Joystick Base Firmware Context

- Joystick firmware code may live in a separate repo.
- The code can be found above this repo (../zFSB2)


## Styles for UI elements (styles.py)
Whenever possible, centralize all the UI style defintions to styles.py
Use the variables and functions found in styles.py