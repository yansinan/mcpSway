# Modern Standby (S0ix) on Linux — what swayidle can and cannot do

Reference data for laptops built since ~2018 (Intel Kaby Lake-R / 8th gen onward, AMD Renoir+). Most of these ship as **Modern Standby (S0ix) only** — no traditional S3 deep sleep. This is the OEM trend, not a Linux deficiency. The trade-off: wake is sub-second (like Windows Modern Standby), but power draw is higher than S3 and most "wake the laptop over the network" tricks do not work.

## 4 sleep states compared

| State | Power | Wake latency | Survives power loss | Linux path | Windows equivalent |
|-------|-------|--------------|---------------------|------------|---------------------|
| **s2idle (S0ix)** | 0.5-2 W | < 1 s | No | `systemctl suspend` (when `mem_sleep=[s2idle]`) | Modern Standby / Connected Standby (Win8+) |
| **S3 deep** | 0.1-0.5 W | 1-3 s | No | `mem_sleep=deep` + `systemctl suspend` | "Sleep" on Win10-era laptops |
| **Hybrid sleep** | 0.5-2 W | < 1 s normally, 10-30 s on power loss | Yes (writes RAM to swap first) | `systemctl hybrid-sleep` | "Hybrid sleep" (default on Win10 desktops) |
| **Hibernate (S4)** | 0 W | 10-30 s | Yes (RAM already on swap) | `systemctl hibernate` (requires `swap ≥ RAM`) | "Hibernate" |

The "Modern Standby / Connected Standby" row is the new one. The OEM choice between s2idle and S3 is essentially a firmware decision; the kernel respects what the ACPI table offers.

## Quick detection recipe

```bash
# 1. What sleep modes does the kernel offer?
cat /sys/power/mem_sleep
# [s2idle]        → s2idle only (Modern Standby device, no S3)
# [s2idle] deep   → both available, currently s2idle
# s2idle [deep]   → both available, currently deep
# (only [deep])   → legacy S3, no Modern Standby

# 2. If s2idle-only, confirm S3 is truly unavailable:
echo deep | sudo tee /sys/power/mem_sleep
# "tee: ... Invalid argument" → confirmed s2idle-only

# 3. What states can the kernel write to /sys/power/state?
cat /sys/power/state
# freeze mem disk
#   freeze = software suspend (cpuidle-style, lightest)
#   mem    = RAM self-refresh (s2idle or deep, depends on mem_sleep)
#   disk   = hibernate (write to swap)

# 4. CPU generation hint (most S0ix-only devices are 8th gen+ Intel or Renoir+ AMD):
lscpu | grep "Model name"

# 5. Hibernate image size budget (default = 2/5 of RAM):
cat /sys/power/image_size
# On a 15 GiB RAM machine → ~6.1 GiB; needs at least that much swap free
```

**Important:** `cat /sys/power/mem_sleep` shows the **supported** sleep mode(s) the kernel can offer, NOT the current state. To tell whether the system is *currently* in s2idle, you need one of:

```bash
# Counter of how many times s2idle/S3 has been entered successfully:
cat /sys/power/suspend_stats/success
# 0 = machine has NEVER entered any suspend state (was just CPU-idle)

# Recent kernel PM log:
journalctl -k --since "1 minute ago" | grep -iE "PM:|suspend|resume|freeze"
# A "PM: suspend entry (s2idle)" + "PM: suspend exit" pair means the system
# actually walked the suspend path. If you don't see this, the system was
# just CPU-idle (cpufreq at 800 MHz) but never entered s2idle.

# Force a 5-second s2idle + auto-wake to verify the path works on this hardware:
sudo rtcwake -m mem -s 5
# On an s2idle-only machine, "mem" walks the s2idle path. Screen goes black,
# machine wakes 5 s later. Check journalctl -k for the PM: lines.
```

## Wire formats — what `systemctl suspend` does on each kind of machine

```
S0ix-only machine (e.g. ThinkPad X1 Tablet Gen 3, 2018+):
  systemctl suspend  →  kernel calls ACPI _S0 (S0ix entry)  →  CPU deep C-state
                       →  iwlwifi / e1000e runtime PM suspend (only if power/control=auto)
                       →  wake sources: lid, power button, USB (per ACPI)
  systemctl hibernate  →  RAM pages to swap, machine off, 10-30s wake

S3-capable machine (e.g. older ThinkPad X230, Sandy Bridge):
  systemctl suspend  →  kernel calls ACPI _S3 (deep suspend entry)
                       →  RAM self-refresh, devices fully off
                       →  wake sources: lid, power button, USB, sometimes LAN
  systemctl hibernate  →  same as S0ix
```

The user cannot tell which path `systemctl suspend` will walk without checking `mem_sleep`. On an S0ix-only machine, `systemctl suspend` is **not** a "real" S3 — it's a low-power S0 with the CPU mostly asleep. This is the most common misconception.

## SSH into a sleeping laptop: the actual answer

**The common misconception: "s2idle is sleep, so SSH can't work."** This is partially wrong.

s2idle is **NOT** a sleep state in the S3 sense. The system is still in S0 — the CPU is in deep C-state (C10 on Kaby Lake-R, ~100-200 μs exit latency), but the OS framework is still alive, the network stack is still in memory, and sshd is still listening. The real question is whether inbound packets can wake the CPU enough to be processed.

**The actual determining factor: the NIC's `power/control` setting.**

```bash
cat /sys/class/net/<iface>/device/power/control
# "on"   → NIC stays in D0, no runtime PM, s2idle does NOT affect it
# "auto" → kernel can put NIC in D3 during s2idle, wake on configured events
```

**Case 1: `power/control = on`** (common on desktops that haven't run `powertop --auto-tune`, and many laptop default configs):

- **SSH into the laptop in s2idle: YES, essentially immediate.** Latency = network RTT + 1-5 ms. The NIC was never asleep. The CPU is in C10 but the interrupt exits it in microseconds.
- Empirically verified: a 5-min monitor on a Kaby Lake-R ThinkPad X1 Tablet Gen 3 showed CPU frequency at 800 MHz (deep idle) while SSH connections were accepted and responded to in < 1 s, no wakeup chain required.

**Case 2: `power/control = auto`** (laptop has been through `powertop --auto-tune` or aggressive laptop-mode tools):

- **SSH into the laptop in s2idle: depends on NIC wake configuration.** NIC is in D3, kernel will wake it on configured events. Default wake events are usually "any packet", "magic packet" (WoL), or "specific pattern". Most consumer iwlwifi firmwares support "any packet" wake — but you have to check with `iw phy0 wowlan show`.
- Latency: similar (RTT + 1-5 ms) IF the wake event fires. If not, packets are silently dropped.

**Important: the 5-30 s wakeup chain is a different scenario.** It applies only when the system went through a *true* sleep transition (lid close → suspend → wake) that tore down the network stack and AP association. It does NOT apply to "system is just CPU-idle at 800 MHz":

| Stage | Latency | When it applies |
|-------|---------|-----------------|
| Physical wake event (lid, button, USB) | < 1 s | Only if the system had entered s2idle/S3 *first* |
| NIC runtime PM resume | 0.5-2 s | Only if NIC was in D3 |
| Wi-Fi re-associate with AP | 2-10 s | Only if AP association was torn down |
| Tailscale / WireGuard re-handshake | 5-30 s | Only if tunnel was timed out |
| sshd reachable from external client | **5-30 s total** | Only in the above tear-down chain |

**If you want to make SSH-into-s2idle reliable (regardless of NIC power state):**

1. **Force the NIC to stay on** with a udev rule:
   ```
   # /etc/udev/rules.d/90-keep-nic-on.rules
   ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x8086", \
     ATTR{driver}=="iwlwifi", TEST=="power/control", ATTR{power/control}="on"
   ```
   Cost: idle power 0.5-2 W → 5-10 W. Probably not worth it just for SSH — see above, the NIC wake events usually work.
2. **Or configure WoWLAN for "any packet" wake**:
   ```
   sudo iw phy0 wowlan enable any
   ```
   This survives NIC D3 and lets the kernel wake on any incoming packet. Cheaper than option 1.
3. **Or accept the reality**: with default settings on this user's machine (`power/control = on` on the iwlwifi NIC), SSH into s2idle is immediate. No config needed.

**Wireless WoL via magic packet: still essentially nonexistent.** No consumer Wi-Fi card supports it. The 802.11 spec includes a power-save mode, but it's client-initiated (the AP doesn't ping clients to wake them). If a guide tells you to enable WoL on a wireless interface, it is wrong.

**The wired WoL angle is the only one that has a chance, and only on certain machines:** on S0ix-only machines, the ACPI wakeup table typically lists the LAN device under `S4`, not `S3` or `S0`. The kernel cannot bridge that to s2idle. So even with `wol g` set, the magic packet will not wake the laptop from s2idle. Test before assuming.

## Diagnostic recipes for live s2idle testing

```bash
# 1. Is the machine currently s2idle-capable?
cat /sys/power/mem_sleep
cat /sys/power/state

# 2. Has the machine EVER entered suspend?
cat /sys/power/suspend_stats/success
# 0 = never suspended, just CPU-idle

# 3. Force a 5-second s2idle + auto-wake (the only way to verify the path
#    actually works on this specific hardware+kernel combo):
sudo rtcwake -m mem -s 5
# Screen will go black, machine wakes 5 s later.
# On s2idle-only machines, "mem" walks the s2idle path.
# journalctl -k will show "PM: suspend entry (s2idle)" and "PM: suspend exit".

# 4. Watch the kernel PM log live:
journalctl -k -f | grep -iE "PM:|suspend|resume|freeze"

# 5. Check Wi-Fi wake capability (most useful for laptop-mode configs):
iw phy0 wowlan show
# "WoWLAN is disabled" → no wake events configured
# "WoWLAN is enabled:" + " * Wake on any" → wake on any packet (good for SSH)

# 6. Check NIC runtime PM state:
cat /sys/class/net/<iface>/device/power/control       # "on" or "auto"
cat /sys/class/net/<iface>/device/power/runtime_status # "active" or "suspended"
# If control=on, runtime_status=active regardless of s2idle state
# If control=auto, runtime_status flips with s2idle

# 7. ACPI wakeup table (which devices can wake the system):
cat /proc/acpi/wakeup
# "S3 *enabled" → can wake from S3 (and from s2idle on s2idle-only machines)
# "S4 *enabled" → can wake from S4 only, not s2idle (common for LAN on s2idle-only machines)
```

## Hibernate vs s2idle decision matrix

| Scenario | Better choice |
|----------|---------------|
| Lid close for a meeting (1-2 h) | s2idle. Wake is instant, 1-2 Wh drain. |
| Lid close overnight (8 h) | s2idle. ~16 Wh drain, but instant morning wake. |
| Lid close for a week | hibernate (S4). 0 Wh drain, but 10-30s wake. |
| Battery below 20% on lid close | hibernate. s2idle on a low battery will eventually drain it. |
| Lid close while Tailscale is needed | s2idle. After wake, Tailscale re-handshakes. Hibernate also works, but adds 10-30s wake latency. |

**The hard requirement for hibernate: `swap ≥ RAM`.** On this user's machine (15 GiB RAM, was 12 GiB swap → 20 GiB swap after expansion), hibernate is now feasible. Always test with `sudo rtcwake -m disk -s 10` before relying on it for an actual trip — the kernel can refuse to hibernate if the modified-page image exceeds the swap size, and you only find out at hibernate time, not at swap-time.

## logind configuration on Debian 13

The `logind.conf` defaults on Debian 13 are conservative:

| Key | Default | What it does |
|-----|---------|--------------|
| `HandlePowerKey` | `poweroff` | Short-press power button |
| `HandlePowerKeyLongPress` | `ignore` | Long-press power button |
| `HandleLidSwitch` | `suspend` | Lid close |
| `HandleLidSwitchExternalPower` | `suspend` | Lid close while on AC |
| `HandleLidSwitchDocked` | `ignore` | Lid close while docked to external display |
| `HandleSuspendKey` | `suspend` | Sleep key (Fn+...) |
| `HandleHibernateKey` | `hibernate` | Hibernate key (Fn+...) |

The "long-press is ignore" default is good — it means holding the button doesn't accidentally trigger anything. The "short-press is poweroff" default is bad for a S0ix device because there is no graceful warning. **Recommended change:** `HandlePowerKey=suspend` (walks `mem_sleep`, so it's s2idle on a Modern Standby device).

To apply:
```bash
sudo sed -i 's/^#HandlePowerKey=poweroff$/HandlePowerKey=suspend/' /etc/systemd/logind.conf
# pick one:
sudo reboot                                  # no session disruption
sudo systemctl restart systemd-logind        # ends your sway session
```

`systemctl restart systemd-logind` ends the current user session because logind owns the session bus. This is unavoidable — there is no SIGHUP-style reload for logind. Plan for it: do the restart when you're ready to log back in, or just reboot.

**Detecting when logind is mid-suspend** (for your own scripts):
```bash
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
  org.freedesktop.login1.Manager PreparingForSleep
# "b false" = not preparing to sleep
# "b true"  = in the middle of a sleep transition
```

`logind`'s `PrepareForSleep` signal is what swayidle's `before-sleep` and `after-resume` events are tied to.

## Bluetooth USB wake from s2idle

Bluetooth HID (mouse click, keyboard keypress) is the most reliable wake source for an s2idle machine — it does not need the network stack to be alive, so it bypasses the freeze_processes / Tailscale / Wi-Fi-AP-association problems that block SSH-wake.

**How it works on this kind of machine:**

```
Bluetooth mouse click / keyboard keypress
   ↓ HID report
Bluetooth USB controller (Intel 8087:0a2b is on bus 001, port 9 = sysfs "1-9")
   ↓ USB interrupt
XHC (USB 3.0 controller, ACPI S-state: S3 *enabled — also responds to s2idle on S0ix-only machines)
   ↓ ACPI GPE
kernel thaw_processes()
   ↓
sway 恢复 + bluetoothd 重连蓝牙设备 (1-3 秒)
```

Note the ACPI tag says "S3" but the machine is s2idle-only. **This is normal and works** — on S0ix-only hardware, anything in `/proc/acpi/wakeup` listed as "S3 enabled" can wake from s2idle too. The S3 label is the ACPI table value, not the actual s2idle path restriction.

**Step 1 — verify your Bluetooth device path and current wakeup state:**

```bash
# Find the BT USB device (filter on Intel 8087 vendor id, common for built-in BT)
lsusb | grep -i bluetooth
# Example: Bus 001 Device 004: ID 8087:0a2b Intel Corp. Bluetooth wireless interface

# Confirm the ACPI wakeup path
cat /proc/acpi/wakeup | grep XHC
# XHC   S3 *enabled   pci:0000:00:14.0

# Check wakeup attribute on the BT USB device specifically
cat /sys/bus/usb/devices/1-9/power/wakeup
# "disabled" ← this is the default; needs to be "enabled"
```

**Step 2 — enable temporarily (gone on reboot):**

```bash
echo enabled | sudo tee /sys/bus/usb/devices/1-9/power/wakeup
```

**Step 3 — persist via udev (file under `/etc/udev/rules.d/`):**

```bash
# Match by USB vendor/product id, not by sysfs path — paths renumber on dock/undock
cat > /etc/udev/rules.d/90-bluetooth-wakeup.rules <<'EOF'
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="8087", ATTR{idProduct}=="0a2b", \
  ATTR{power/wakeup}="enabled"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor=8087
```

`ATTR{idVendor}=="8087"` is Intel; pair it with your actual product id from `lsusb`. The `ACTION=="add"` matches the moment the device enumerates on the USB bus, so this fires every boot and after every dock/undock. Using `ATTR{idVendor}/idProduct` rather than the bus path (`1-9`) is the durable choice — the bus path is **not** stable across reboots or when you plug the device into a different USB port on a dock.

**Step 4 — test the path:**

1. Trigger s2idle: `sudo systemctl suspend` (or via your swayidle `mod+Shift+p` bindsym if you set one)
2. Screen goes black, sway 进程 frozen
3. Click your Bluetooth mouse (or tap a key on the Bluetooth keyboard)
4. Screen comes back, sway 恢复, bluetoothd re-attaches the device in 1-3s

If it doesn't wake: check `journalctl -k --since "1 minute ago" | grep -i resume` to see what triggered the wake. If nothing triggered, your Bluetooth USB device path may have changed (you undocked/redocked); re-`udevadm trigger`.

**What this wake CAN do:**
- Bluetooth mouse (HID clicks / movement)
- Bluetooth keyboard (HID keypress)
- Bluetooth trackball / presenter / remote (anything that emits HID)
- Bluetooth audio (volume buttons, play/pause) on most modern receivers

**What it CANNOT do (because user tasks are still frozen during s2idle):**
- Anything that requires the BT protocol stack to be processing data (BLE scans, audio streaming) — those wake the device but the receiving user-space daemon is frozen, so the event is dropped
- Wake from "any" state — only wakes from s2idle; for S3 deep this still works because USB controllers are typically ACPI-wake-enabled
- Wake over BT tethering / PAN — same user-task-frozen problem as SSH

**Pitfall: don't try to "wake on BT connection" via `bluetoothctl` settings.** The `bluetoothctl` wake-on-connection knobs control the firmware state, but the OS-side listener (bluetoothd) is frozen during s2idle anyway. The only wake path that works is the HID report → USB interrupt → ACPI GPE chain, which is what the udev rule enables. Skip the bluetoothctl layer; the udev rule is sufficient.
