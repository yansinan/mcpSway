# Session: 2026-06-10 — Debian 13 Timeshift btrfs setup

## Summary
New Debian 13 (trixie) ThinkPad X1 Tablet at 192.168.1.249. Default btrfs layout has `@rootfs` containing everything with empty nested subvolumes. Timeshift btrfs mode requires `@` and `@home` at top level.

## Commands run (condensed)

### Phase 1: Subvolume migration
```bash
# Discovered layout
sudo btrfs subvolume list /
# ID 256: @rootfs (mounted at /)
# ID 257-261: @, @home, @var, @log, @cache (nested, empty)

# Mount top-level, create @ as snapshot of @rootfs
sudo mount -o subvolid=5 /dev/mapper/x1tablet--vg-root /mnt/btrfs
sudo btrfs subvolume snapshot -r /mnt/btrfs/@rootfs /mnt/btrfs/@
sudo btrfs property set /mnt/btrfs/@ ro false

# Set @ as default (later reverted to ID 5)
sudo btrfs subvolume set-default /mnt/btrfs/@

# Update fstab on @rootfs (before reboot)
sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab

# Create @home top-level
sudo btrfs subvolume create /mnt/btrfs/@home
sudo cp -a --reflink=always /mnt/btrfs/@/home/. /mnt/btrfs/@home/
echo "/dev/mapper/x1tablet--vg-root /home btrfs defaults,subvol=@home 0 0" | sudo tee -a /etc/fstab

# Fix GRUB
sudo sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="rootflags=subvol=@"/' /etc/default/grub
sudo update-grub

# Reboot
```

### Phase 2: Post-reboot fixes
```bash
# Discovered @'s fstab still had subvol=@rootfs (snapshot trap!)
sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab

# Set default back to ID 5 (needed for Timeshift backup mount)
sudo mount -o subvolid=5 /dev/mapper/x1tablet--vg-root /mnt/btrfs
sudo btrfs subvolume set-default 5 /mnt/btrfs

# Clean up old layout
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@home
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@var
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@log
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@cache
sudo btrfs subvolume delete /mnt/btrfs/@rootfs
sudo update-grub  # clean kernel paths

# Mount @home
sudo mount /home
sudo rm -rf /mnt/btrfs/@/home/*
```

### Phase 3: Timeshift
```bash
# Config written to /etc/timeshift/timeshift.json
sudo timeshift --create --comments "initial snapshot"  # Success!
```

### Phase 4: Docker + Tailscale
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker dr
curl -fsSL https://tailscale.com/install.sh | sudo sh
sudo tailscale up  # requires browser auth
```

### Phase 5: Sway (installed directly, container attempt failed)
```bash
sudo apt install -y sway swaybg foot wayvnc seatd
sudo systemctl enable --now seatd
sudo usermod -aG seat dr
# Sway needs seatd, WLR_BACKENDS=headless for headless, and wayvnc for VNC access
```

## Final layout
```
FS_TREE (subvolid=5, default)
  ├── @ (ID 262, mounted at /)
  └── @home (ID 263, mounted at /home)
```

## Timeshift schedule
- cron: `0 * * * * root timeshift --check --scripted`
- Daily: keep 5, Weekly: keep 3, Monthly: keep 2
- Hourly & Boot: off
