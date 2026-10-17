# Tudor MiS: template "worlds" — Linux vs pre-boot (UEFI) interop (OPEN)

## Observed behavior (live, T14 Gen 3 AMD 06cb:00f9)
- A template enrolled on **Windows** unlocks the NVMe in **UEFI** (pre-boot).
- The same Linux host (paired via `synatlsmoc`/pydrv) **cannot see** the Windows
  templates: `fprint-verify` says "no fingers added".
- A Linux host **can see** the Windows templates for *duplicate detection* only:
  enrolling a Windows-enrolled finger says "duplicate" (but `fprint-list` shows none).
  → the sensor has a **global** "finger already enrolled" check, but template
  list/verify is **world-scoped**.
- After a sensor storage reset, Linux enrolled + verified fine (OS auth + LEDs work),
  but the UEFI **match failed** on the Linux-enrolled template.

So the two OSes live in **different template worlds**, and the world is NOT the
host pairing cert's `cert_type`.

## Ruled out: host-cert `cert_type` (tested, wrong)
The pairing host cert (400 bytes, magic `0x5f3f`) carries a `cert_type` byte at
offset 0x8d. `sample_recv_host_cert` (the Windows capture) has it **2**; the sensor
cert has it **0**. Hypothesis: "send 2 from the host". **Refuted live:**

- The pairing flow (per `rev/proto.txt` and `rev/rev.txt`) is: host → sensor
  "host certificate" (the host's own, type **0**); sensor → host "**host certificate
  echo**" (type **2**, stamped by the **sensor**) + device cert. The type-2 cert in
  the capture is the sensor's *echo*, not what the host sends.
- Windows generates the host keypair **fresh** each pairing
  (`_tudorSecurityGenHostKeyPair`) and signs the host cert with the **shared vendor HS
  key** (the same PRF in `genhskey.py` / `pairing.c` / the Windows DLL). So the CA is
  shared and the identity key is fresh — the world cannot be either of those in the
  naive sense.
- Forcing the *sent* host cert to `cert_type 2` made the sensor reject the pair with
  `VCS_RESULT_GEN_OBJECT_DOESNT_EXIST_1` (0x403) during open. **Reverted** (libfprint
  `pairing.c`, commit c610046); the host must send type 0.

## Working model (unproven, the next target)
Templates are world-scoped by the **host identity** (the EC keypair generated at
pairing, its public key in the host cert; per-host, persisted in the host's storage
— fprintd: `/var/lib/fprint/0-persistent/synatlsmoc/<device_id>`). Each host's
enrolled templates are only visible/verifiable to that host (or to things the sensor
has bound to it). The **UEFI NVMe unlock is bound to the host that was active when it
was set up** (Windows → `K_win`), so it reads `K_win`'s world. Linux pairs as a
different host (`K_linux`) → its world is invisible to the UEFI.

## Open questions (need UEFI-driver RE or a live matrix)
1. How does the UEFI (its fixed static PD key) gain read access to a host world?
   (Is the NVMe binding per-host, set once at setup? Re-bindable from the UEFI?)
2. When the UEFI sets up the NVMe unlock, does it enroll the template *into a
   host world*, or into a global store? (The failed UEFI bind of a Linux-enrolled
   finger suggests the global duplicate check blocks it.)
3. Is there any command that re-points the pre-boot binding at a new host?

## Status
OPEN. The wrong-hypothesis fix (cert_type 2) is reverted; OS-side LED + auth work.
