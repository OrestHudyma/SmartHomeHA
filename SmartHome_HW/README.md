# Hardware interface firmware

Open `SmartHome_HW.cywrk` with PSoC Creator 4.4 and regenerate application
sources before building. Generated code and personal IDE settings are not tracked.

## Host regression tests

Run `python SmartHome_HW/test.py -v` from the repository root with GCC on PATH
(or set `CC` to its executable). No extra Python packages are required.
On Linux, set `HW_TEST_SANITIZERS=1` to enable AddressSanitizer and UBSan, as in CI.

Tests include the real `HW_interface.cydsn/main.c`, replacing only PSoC APIs
and the entry-point name. UART stubs exercise receive callbacks, checksum/header
validation, field boundaries, exact command matching and interrupted transmission.
Each case runs in a separate process with a timeout. The main-loop tests stop at
the first serial ACK; they do not replicate the application loop in test code.

These tests do not validate physical UART timing, RF delivery, MCU interrupt
priorities, PSoC code generation or the target compiler. They are not a firmware
build or hardware acceptance test.

Known limitations remain: busy radio packets are discarded, overflow does not
discard until a fresh start delimiter, local-command buffers are not protected
against concurrent replacement, and invalid local packets still share the radio
forwarding path. The current tests do not certify those behaviors as safe.
