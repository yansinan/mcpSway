# Timeshift Subvolume Detection Internals

## How Timeshift detects @ and @home

Source: https://github.com/linuxmint/timeshift (v24.06.x)

### Detection chain

1. **`Main.vala:3803`** — `Subvolume.detect_subvolumes_for_system_by_path("/")`
2. **`Subvolume.vala:87`** — reads `/etc/fstab` via `FsTabEntry.read_file()`
3. For each fstab entry, checks `is_for_system_directory()`:
   - Returns false if mount point starts with `/mnt`, `/mount`, `/sdcard`, `/cdrom`, `/media`
   - Returns false if device doesn't start with `/dev/` AND doesn't start with `UUID=`
   - Returns true otherwise
4. Extracts subvolume name via `subvolume_name()`:
   - Finds `subvol=` in options
   - Takes the value after `subvol=`, strips leading `/` if present
   - **If the value is `@rootfs`, that becomes the subvolume name — not `@`**
5. Builds a HashMap of `{name: Subvolume}`
6. **`Main.vala:496`** — `check_btrfs_layout_system()`:
   ```vala
   bool supported = sys_subvolumes.has_key("@");
   if (include_home) supported = supported && sys_subvolumes.has_key("@home");
   ```
   - If fstab says `subvol=@rootfs`, the HashMap has key `@rootfs`, NOT `@`
   - `has_key("@")` returns false → "unsupported subvolume layout" error

### Critical fix

After subvolume migration, verify fstab subvolume name matches Timeshift's expectation:
```bash
grep "subvol=" /etc/fstab | grep -v "^#"
# Must show subvol=@ for /, subvol=@home for /home
# NOT subvol=@rootfs
```

### Backup mount and snapshot creation

1. **`SnapshotRepo.vala:189`** — `unlock_and_mount_device()` mounts the backup device
2. Mount uses the **default subvolume** (no explicit subvol= parameter)
3. If default subvolume is `@` (ID 262), the backup mount IS `@`
4. **`Main.vala:1762`** — snapshot source path is `path_combine(mount_path, "@")`
5. If mount_path is already `@`, this looks for `@` inside `@` → "Not a Btrfs subvolume" error

**Fix**: Set default subvolume to ID 5 (FS_TREE):
```bash
sudo btrfs subvolume set-default 5 /mnt/btrfs/
```
