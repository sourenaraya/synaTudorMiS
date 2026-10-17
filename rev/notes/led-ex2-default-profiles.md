# `VCSFW_CMD_LED_EX2` default profiles

Target: `synaWudfBioUsb123.dll` (x64, SHA-256
`61497cb129b85b75a1df34c41e44d863506978575fdbe7cc7f098b4d378e4792`).

## Where the payload data comes from

The LED profiles are not supplied by Windows and are not obtained from
`synaFpAdapter123.dll`. They are a hard-coded 0x2e8-byte table in the Wudf
DLL at VA `0x1800cc8a0`.

During session initialization:

```c
FUN_18004eae0(session)
    -> FUN_180055990(session);       // vfmUtilLedInitialize

FUN_180055990(session) {
    *(uint32_t *)(session + 0x420) = 0;
    memcpy((void *)(session + 0xf8), (void *)0x1800cc8a0, 0x2e8);
}
```

The copied table is six records of 0x7c bytes. `FUN_180056740(session, i)`
selects record `i` at `session + 0xf8 + 0x7c*i`, then passes it through
`vfmDeviceLedConfigure` to `sendLedEx2Cmd` (`FUN_180082960`). A later
`vfmUtilSetLedEventsConfig` call can replace the session copy, but the values
below are the built-in defaults.

## Record layout used by `sendLedEx2Cmd`

Input record size is 0x7c:

```text
offset  size       meaning in host code
0x00    4          event duration/timeout, copied verbatim
0x04    6*0x14     six LED action records

action +0x00       2 bytes copied
action +0x02       2 bytes ignored
action +0x04       4 bytes copied
action +0x08       2 bytes copied, +0x0a..0x0b ignored
action +0x0c       2 bytes copied, +0x0e..0x0f ignored
action +0x10       2 bytes copied, +0x12..0x13 ignored
```

(Corrected 2026-10-16 from the disassembly at `0x180082ad6`..`0x180082c78`:
the inner loop copies two bytes per 32-bit slot. The earlier text said
+0x04..0x0f were copied whole and +0x10 ignored. For the built-in table it
makes no difference: every ignored byte is zero, and so is every +0x10 value.
A byte-for-byte simulation of all six records matches what synatlsmoc sends.)

The serialized command is 0x7d bytes:

```c
out[0] = 0x39;                         // VCSFW_CMD_LED_EX2
u32le(out + 1) = u32le(in + 0);
for (int i = 0; i != 6; ++i) {
    const uint8_t *a = in + 4 + 0x14*i;    // source action
    uint8_t *b = out + 5 + 0x14*i;         // serialized action
    memcpy(b + 0x00, a + 0x00, 2);
    memcpy(b + 0x04, a + 0x04, 4);
    memcpy(b + 0x08, a + 0x08, 2);
    memcpy(b + 0x0c, a + 0x0c, 2);
    memcpy(b + 0x10, a + 0x10, 2);
    // all other bytes remain zero
}
```

Thus the firmware sees a normalized 20-byte action record: the host's two
ignored fields are replaced with zero. The exact physical interpretation of
the action fields is not named in this DLL; their likely meanings must be
confirmed against firmware behavior or additional protocol documentation.

## Built-in records and when they are selected

The following values are decoded as little-endian. `field0` is the first
two-byte action field; `params` are the three copied 32-bit values at action
offsets `+0x04`, `+0x08`, and `+0x0c`. `x` means the complete action is zero.

| event index | table VA | outer duration | nonzero actions (`field0`; params) | observed use |
|---:|---:|---:|---|---|
| 0 | `0x1800cc8a0` | 0 ms | all six: `0x0000; 0x20000000,0,0` | idle/default/reset/settled state |
| 1 | `0x1800cc91c` | 160000 ms | actions 0–2: `0xffff; 0x20000505,0,0x00000505` | capture/enrollment waiting-for-finger state |
| 2 | `0x1800cc998` | 500 ms | action 0: `0x01f4; 0x20000507,0,0x00000505`; action 2: `0x01f4; 0x20000500,0,0` | enrollment sample accepted, and enrollment complete |
| 3 | `0x1800cca14` | 1000 ms | action 0: `0x01f4; 0x20000107,0x00000101,0`; action 2: `0x01f4; 0x20000100,0,0` | enrollment sample rejected, or add-image error |
| 4 | `0x1800cca90` | 500 ms | identical to event 2 | match success |
| 5 | `0x1800ccb0c` | 1000 ms | actions 0–3: `0x004b` with params respectively `0x20000107,0x00000101,0`; `0x20000001,0,0`; `0x20000101,0,0`; `0x20000001,0,0` | match failure |

The event-to-state labels are inferred from the callers of
`FUN_180056740`: event 0 is the normal baseline path; event 1 is used while
waiting for capture/finger input; event 2 is an accepted enrollment
sample (also sent when enrollment completes) and event 3 a rejected one
(corrected 2026-10-16; see `rev/FINDINGS.md`); events 4 and 5 are match success/failure.

`0xd1` is `VCS_RESULT_SENSOR_BAD_CMD`. `sendLedEx2Cmd` retries the same
`LED_EX2` command once after this result; it is a firmware rejection of the
command, not an LED profile selector.

## The profiles are per-sensor (vid:pid), not per driver build

"Series" = Synaptics' UMDF driver build number = the 4th `DriverVer` component
(6.0.X.NNNN) with the leading "1" dropped (6.0.2.1154 -> 154). It is **not** a
monotonic generation (series 154, 2022, predates 136, 2023). The table a sensor
needs is a property of the **sensor**, not of the build that ships it: a build
ships one table per supported sensor, and a sensor keeps the same table across
the builds that ship it.

- **Profile A** — series 123 (`synaWudfBioUsb123.dll`, 6.0.20.1123) @
  `0x1800cc8a0`. Used by **047d:8054 (Kensington)** and **06cb:00d6
  (Synaptics)**. The 8054 table is byte-identical in the closed upstream PR #7
  (Kensington VeriMark IT), whose LED code is gated by `(vid, pid)` — i.e.
  per-sensor — independently confirming this keying.
- **Profile B** — series 154 (`synaWudfBioUsb154.dll`, 6.0.2.1154, T14 Gen 3
  AMD, SHA-256 `cfae86fd…9c7b9`) @ `0x1800e90c0`; byte-identical in series 136
  (`synaWudfBioUsb136.dll`, 6.0.42.1136, T14 Gen 3 Intel) @ file `0xf6050`.
  Used by **06cb:00f9** (fw 10.1; T14 Gen 3 / P14s, AMD+Intel).

Both profiles share the 0x7d-byte command and byte layout — loaded by the same
`vfmUtilLedInitialize` (`memcpy(session + 0xf8, <table>, 0x2e8)`) and serialized
by the same `sendLedEx2Cmd` permutation. **Only the action values differ**, and
that is the whole difference for LED behavior. pydrv's default (Profile A) is
accepted (`VCS_RESULT_OK`) on a Profile-B sensor but leaves the LED dark; sending
Profile B makes it light.

### Profile B values (06cb:00f9, series 154)

Decoded little-endian, `params` at source-action offsets `+0x04`, `+0x08`, `+0x0c`
(same convention as the Profile A table above). Live-verified on 06cb:00f9
(fw 10.1, keyflag set): event 1 = solid green, event 5 = orange blink.

| event index | duration | nonzero actions (`field0`; params) | observed use |
|---:|---:|---|---|
| 0 | 0 ms | all six: `0x0000; 0x20000000,0,0` | idle/off |
| 1 | 0 ms | action 0: `0xffff; 0x20009607,0x00009696,0` | waiting-for-finger (green on; duration 0 = stay on until changed) |
| 2 | 500 ms | action 0: `0x01f4; 0x20000007,0,0` | enrollment accepted / match success |
| 3 | 1000 ms | action 0: `0x00a6; 0x20003c01,0,0x00003c3c`; action 1: `0x00a6; 0x20000001,0,0` | enrollment rejected / match failure (orange blink) |
| 4 | 500 ms | identical to event 2 | match success |
| 5 | 1000 ms | identical to event 3 | match failure |

### Profile A vs B (the fields that differ)

| event | field | A (series 123) | B (series 154) |
|---|---|---|---|
| 1 | duration | 160000 | 0 |
| 1 | act0 param0 | 0x20000505 | 0x20009607 |
| 1 | act0 param2 | 0x00000505 | 0x00009696 |
| 5 | act0 field0 | 0x004b | 0x00a6 |
| 5 | act0 param0 | 0x20000107 | 0x20003c01 |

### Series 136 carries a table bank

The series-136 driver no longer ships a single hard-coded table; it carries a
**bank** of 6×0x7c tables (one per supported sensor), selected at runtime. The
entry at file offset `0xf6050` is **byte-identical to Profile B above**,
confirming the profile is stable across the builds that ship that sensor. Other
bank entries carry Profile-A-style values (e.g. file `0xf7560`, duration 160000,
match-fail field0 `0x004b`) for other sensors.

