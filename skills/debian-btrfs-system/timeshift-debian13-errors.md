# Timeshift on Debian 13 — Errors & Fixes

## Layout check: "unsupported subvolume layout"

**Error:**
```
E: The system partition has an unsupported subvolume layout.
Only ubuntu-type layouts with @ and @home subvolumes are currently supported.
```

**Causes:**
1. Debian 13's @rootfs container layout — no top-level @/@home
2. After migration: @ is at top level but GRUB/fstab still has @rootfs

**Root cause detection:** Timeshift reads `/etc/fstab` and builds `sys_subvolumes` map from fstab entries. If fstab says `subvol=@rootfs`, the map key is `@rootfs` not `@`. Fix: `sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab`.

**Source code reference:** https://github.com/linuxmint/timeshift
- `src/Core/Main.vala` line 496: `sys_subvolumes.has_key("@")`
- `src/Core/Subvolume.vala` line 87+: `detect_subvolumes_for_system_by_path()` reads fstab
- `src/Utility/FsTabEntry.vala` line 162: `subvolume_name()` extracts from fstab options

## Snapshot creation: "Not a Btrfs subvolume"

**Error:**
```
E: ERROR: Not a Btrfs subvolume: Invalid argument
E: btrfs returned an error: 256
E: Failed to create subvolume snapshot: @
```

**Cause:** Default subvolume is @ (ID 262). Timeshift mounts the backup device using the default subvolume, then tries to find `@` as a nested subvolume inside the mount. But @ IS the mounted subvolume — no nested @ exists.

**Fix:** Set default back to FS_TREE (ID 5):
```bash
mount -o subvolid=5 /dev/mapper/xxx-root /mnt/btrfs
btrfs subvolume set-default 5 /mnt/btrfs
```

## Timeshift restore: dropped to GRUB shell

**Symptom:** After `timeshift --restore`, reboot drops to GRUB rescue shell. Manual commands work:
```
set root=(lvm/x1tablet--vg-root)
linux /@/boot/vmlinuz-... root=/dev/mapper/xxx-root ro rootflags=subvol=@ quiet
initrd /@/boot/initrd.img-...
boot
```

**Cause:** Restored snapshot has old GRUB config that uses `root=/dev/mapper/...` but LVM is not active at boot time.

**Fix:** Change GRUB to use UUID:
```bash
GRUB_CMDLINE_LINUX="root=UUID=<btrfs-volume-uuid>"
update-grub
```

## BusyBox after reboot

**Scenario:** System boots to BusyBox initramfs shell after GRUB changes.

**Fix:**
```sh
lvm vgchange -ay
exit
```

## GRUB kernel path uses /@rootfs/

**Symptom:** `linux /@rootfs/boot/vmlinuz-... rootflags=subvol=@rootfs` in grub.cfg

**Fix:** Update GRUB config:
```bash
# Override rootflags
sed -i 's|GRUB_CMDLINE_LINUX=""|GRUB_CMDLINE_LINUX="root=UUID=xxx rootflags=subvol=@"|' /etc/default/grub
update-grub
```

The duplicate `rootflags=subvol=@rootfs rootflags=subvol=@` is handled by the kernel taking the last value.
