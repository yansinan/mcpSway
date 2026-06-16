# Expanding LVM swap on a btrfs root (when VG is full)

A common setup: `/` is btrfs-on-LVM (LUKS underneath), and swap is an LVM logical volume in the same VG. If you started with the default "swap = RAM/2 or so" sizing, you will eventually need to grow swap — especially if you want hibernate to work, which requires `swap ≥ RAM`. But if the root LV has eaten most of the VG, `lvextend` for swap fails with "insufficient free space".

The fix is to **shrink the root LV first, then grow the swap LV**. The order matters and it is NOT obvious from the LVM docs.

## Procedure (5 steps, each independently reversible)

```bash
export PATH=/usr/sbin:/sbin:$PATH

# 0. Defensive snapshot. btrfs resize is mounted-state, LVM resize is offline-ish;
#    if anything goes wrong, timeshift restore brings you back in < 1 min.
sudo timeshift --create --comments "before-swap-expand"

# 1. Shrink the btrfs filesystem by N GiB. Must come BEFORE the LV shrink.
#    btrfs in mounted state supports shrink if used < size-N. Verify first:
btrfs filesystem usage / | grep -E "Device size|Used:|Free \(estimated\)"
#    Need: Used < (Device size - N). Typical desktops have 90% free, so 8 GiB is fine.
sudo btrfs filesystem resize -N G /   # N = how much you want to shrink by, in GiB

# 2. Shrink the root LV to match. lvreduce detects that the FS already shrunk
#    and skips its own resize step. If you reverse the order (shrink LV first)
#    you can corrupt the FS — never do that.
sudo lvreduce -L -N G vgname/root

# 3. Grow the swap LV by the same N GiB.
sudo lvextend -L +N G vgname/swap_1

# 4. Rebuild the swap signature. mkswap is mandatory after extending the LV —
#    the old signature is for the old size and the kernel will refuse to swapon
#    a device with a mismatched signature. This destroys the UUID.
sudo swapoff /dev/vgname/swap_1
sudo mkswap /dev/vgname/swap_1
sudo swapon /dev/vgname/swap_1

# 5. Verify
free -h | grep -E "Mem|Swap"   # Swap should show new size
swapon --show                    # path + size

# 6. Confirm fstab still references the device (not the UUID), or update it
grep -i swap /etc/fstab
#    Expected: /dev/mapper/vgname--swap_1 none swap sw 0 0
#    If it says UUID=<old-uuid>, update it. /dev/mapper paths survive mkswap;
#    UUIDs do not.
```

## Why the order matters

| Order | What happens | Result |
|-------|--------------|--------|
| FS shrink → LV shrink → LV extend swap → mkswap | Resize the FS to expose free extents, then re-assign them to swap | ✓ Safe |
| LV shrink → FS shrink | LV is now smaller than the FS, the FS is sitting on a now-truncated LV, kernel may panic or silently truncate the superblock | ✗ **Filesystem corruption** |
| LV extend swap without mkswap | LV is bigger, but the swap signature still says old size; `swapon` returns "device or resource busy" or "invalid argument" | ✗ Stuck — old swap not active |
| mkswap without swapoff first | If the swap is currently active, mkswap refuses with a warning; if you force it, you can lose whatever is currently swapped out | ✗ Data loss |

## hibernate-specific sizing check

For `systemctl hibernate` to work, the kernel needs to write the modified-page image to swap. The default budget is `2/5 of RAM`:

```bash
cat /sys/power/image_size
# 6539100160  →  ~6.1 GiB on a 15 GiB RAM machine
```

The kernel only writes pages that have been modified since the last clean state, so the image is usually much smaller than RAM. But peak modified-page counts (e.g. after restoring a browser session, or compiling) can exceed the default budget. The kernel will then **refuse to hibernate** with a clear error in `journalctl -b` — and you only find out when you try to hibernate, not when you resize the swap.

**Rule of thumb:** swap ≥ RAM is the safe target for hibernate. Swap ≥ 0.5 × RAM is enough for general use but not hibernate. On a 15 GiB RAM laptop, 20 GiB swap (≈1.3 × RAM) is comfortable; 12 GiB (≈0.8 × RAM) is borderline.

**Test before you need it:**

```bash
# 5-second real hibernate test
sudo rtcwake -m disk -s 5
# Machine writes RAM to swap, powers off, then RTC alarm fires, machine boots,
# kernel reads image from swap, resumes. If this works end-to-end, hibernate is good.
# If it boots to a fresh login (or hangs), hibernate is broken — check journal.
```

`rtcwake -m disk` is the only way to actually exercise the hibernate path; reading `mem_sleep` and `image_size` only tells you what *should* be possible, not what *actually* works on this specific hardware+kernel combo.

## When the VG is NOT full (the easy case)

If the VG has free space, skip steps 1 and 2 entirely:

```bash
sudo lvextend -L +N G vgname/swap_1
sudo swapoff /dev/vgname/swap_1
sudo mkswap /dev/vgname/swap_1
sudo swapon /dev/vgname/swap_1
```

You will still need `mkswap` because the swap signature is size-specific.

## The btrfs-swapfile alternative (when LVM is not in play)

If you have a plain btrfs root (no LVM), you can use a swapfile instead of a swap partition. Btrfs swapfiles have constraints that make them more annoying than LVM swap:

- The file must be on a non-snapshotted subvolume (Timeshift btrfs mode will include it in `@` snapshots and bloat them).
- Must `chattr +C` the file to disable COW.
- Cannot use `dd` to allocate; use `btrfs filesystem mkswapfile` (kernel 6.1+).
- File layout must be aligned (btrfs internally requires hole-punching, which is why older kernels do not work).

For this user's setup (LVM already in place), the LVM-swap-extension recipe is simpler. Only reach for btrfs swapfiles if you do not have an LVM layer.

## Rollback

If anything in steps 1-3 goes wrong, **stop and rollback**:

```bash
# Reverse: extend root back, shrink swap back
sudo lvextend -L +N G vgname/root
sudo lvreduce -L -N G vgname/swap_1
sudo mkswap /dev/vgname/swap_1   # also rebuilds the signature
sudo swapon /dev/vgname/swap_1

# Then grow the btrfs filesystem back to fill the restored root LV:
sudo btrfs filesystem resize +N G /
```

If the btrfs resize itself fails partway, restore from the timeshift snapshot you took in step 0. That is why it is step 0.
