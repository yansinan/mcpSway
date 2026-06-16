# Debian 13 Trixie — Btrfs @rootfs 布局迁移实录

## 原始布局

```
顶层 (subvolid=5, FS_TREE)
  └── @rootfs (ID 256, top level 5, 挂在 /)
        ├── @      (ID 257, top level 256)  ← 空，未使用
        ├── @home  (ID 258, top level 256)  ← 空，未使用
        ├── @var   (ID 259, top level 256)  ← 空，未使用
        ├── @log   (ID 260, top level 256)  ← 空，未使用
        └── @cache (ID 261, top level 256)  ← 空，未使用
```

所有真实数据（/home、/var 等）存储在 @rootfs 自身。嵌套子卷是空的占位。

## 设备信息

- NVMe: nvme0n1
- 分区: nvme0n1p1 (vfat, /boot/efi), nvme0n1p2 (ext4), nvme0n1p3 (LVM2)
- LVM VG: x1tablet--vg
- LVM LV: root (btrfs), swap_1 (swap)
- Btrfs 设备: /dev/mapper/x1tablet--vg-root
- UUID: 142fb829-1fd4-4b70-82eb-e63e7864b561
- 标签: 'root'

## 迁移后布局

```
顶层 (subvolid=5, FS_TREE) ← 默认子卷（必须保持 FS_TREE）
  ├── @      (ID 262, top level 5, 挂在 /)           ← 从 @rootfs 快照
  ├── @home  (ID 263, top level 5, 挂在 /home)       ← 新创建，含 /home 数据
  └── timeshift-btrfs/snapshots/                     ← Timeshift 快照
        └── 2026-06-10_00-52-03/
              ├── @
              └── @home
```

## 关键发现

### 1. @ 不能是默认子卷

最初按常规做法设 @ 为默认子卷，导致 Timeshift 失败：

```
Timeshift 挂载备份 → 使用默认子卷(@) → 挂到 /run/timeshift/backup/
  → 试图 snapshot /run/timeshift/backup/@ → 不存在（@ 本身就是挂载的内容）
  → "Not a Btrfs subvolume"
```

**修复**：`sudo btrfs subvolume set-default 5 /mnt/btrfs/`

Timeshift 源码（SnapshotRepo.vala:189-202）：
```vala
mount_path = unlock_and_mount_device(device, App.mount_point_app + "/backup");
mount_paths["@"] = mount_path;  // mount_path = /run/timeshift/backup/
// 然后 snapshot: path_combine(mount_path, "@") = /run/timeshift/backup/@
```

当默认是 FS_TREE（ID 5）时，挂载的是 btrfs 顶层，/run/timeshift/backup/@ 正确解析为顶级 @ 子卷。

### 2. @home 必须是顶级子卷

Timeshift 的 `check_btrfs_layout_system()`（Main.vala:492-498）：
```vala
bool supported = sys_subvolumes.has_key("@");
if (include_home) {
    supported = supported && sys_subvolumes.has_key("@home");
}
```

`sys_subvolumes` 来自 `Subvolume.detect_subvolumes_for_system_by_path("/")`，该函数读取 `/etc/fstab` 的 `subvol=` 值。所以 fstab 必须有 `subvol=@` 和 `subvol=@home` 条目，且对应的子卷必须在 btrfs 顶级。

### 3. 快照后 fstab 修复的必要性

@ 是 @rootfs 的快照，其 /etc/fstab 保留旧值。重启后：
- @ 挂在 /（靠 GRUB 内核参数 rootflags=subvol=@）
- 但 /etc/fstab 还是 `subvol=@rootfs`（快照当时的内容）
- Timeshift 读 fstab 得到 @rootfs，`sys_subvolumes.has_key("@")` 返回 false

### 4. GRUB 自动清理

删除 @rootfs 后执行 `sudo update-grub`，GRUB 自动将内核路径从 `/@rootfs/boot/...` 更新为 `/@/boot/...`。

### 5. fstab 排版对 Timeshift 检测的影响

Timeshift 的 `FsTabEntry.is_for_system_directory()` 要求设备路径以 `/dev/` 或 `uuid=` 开头：

```vala
public bool is_for_system_directory(){
    if (mount_point.has_prefix("/mnt") || ...
        ... (!device_string.has_prefix("/dev/") && !device_string.down().has_prefix("uuid="))){
        return false;
    }
    return true;
}
```

若 fstab 使用 LABEL/PARTLABEL/PARTUUID 格式（如 `LABEL=root`），`is_for_system_directory()` 返回 false，该条目被跳过，`sys_subvolumes` 中缺失 @ 和 @home。用 `cat -A /etc/fstab` 检查空白字符。

### 6. Timeshift 调度 cron 行为

安装后自动创建 `/etc/cron.d/timeshift-hourly`：
```
0 * * * * root timeshift --check --scripted
```

`--check` 逻辑：
- 检查当前时间是否"轮次已到"
- 今天还没有每日快照？创建一个
- 本周还没有周快照？创建一个
- 本月还没有月快照？创建一个
- 超过保留数（count_daily=5 等）？删最旧的

**重要**：count_daily=5 不是"一天做 5 个"，是"保留最近 5 天的每日快照"（即每天 1 个，最多 5 个）。

### 7. Timeshift 恢复快照后进 GRUB rescue

执行 `sudo timeshift --restore --snapshot "before-sway" --target-device /dev/mapper/x1tablet--vg-root --yes` 后重启，系统停在 GRUB rescue。

**根因**：快照中的 GRUB 配置可能使用了旧的内核参数格式（日期不同导致的 /dev/mapper/ 路径解析问题）。

**手动引导命令**（在 GRUB> 提示符输入）：

```grub
set root=(lvm/x1tablet--vg-root)
linux /@/boot/vmlinuz-6.12.90+deb13.1-amd64 root=UUID=142fb829-1fd4-4b70-82eb-e63e7864b561 ro rootflags=subvol=@ quiet
initrd /@/boot/initrd.img-6.12.90+deb13.1-amd64
boot
```

**关键**：用 `root=UUID=...` 替代 `root=/dev/mapper/xxx-root`，之前报 `unable to mount root fs on /dev/mapper/x1tablet--bg-rt`（设备路径拼写也乱了，但用 UUID 解决了）。

## 完整迁移命令汇总

```bash
# === 阶段 A：前置探测 ===
sudo lsblk -f
sudo btrfs subvolume list /
sudo mount -o subvolid=5 /dev/mapper/x1tablet--vg-root /mnt/btrfs

# === 阶段 B：子卷迁移（rootfs 上操作） ===
sudo btrfs subvolume snapshot -r /mnt/btrfs/@rootfs /mnt/btrfs/@
sudo btrfs property set /mnt/btrfs/@ ro false

sudo btrfs subvolume create /mnt/btrfs/@home
sudo cp -a --reflink=always /mnt/btrfs/@/home/. /mnt/btrfs/@home/
sudo rm -rf /mnt/btrfs/@/home/*

sudo btrfs subvolume set-default 5 /mnt/btrfs/   # 关键：保持 FS_TREE

sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab
echo "/dev/mapper/x1tablet--vg-root /home btrfs defaults,subvol=@home 0 0" | sudo tee -a /etc/fstab

sudo sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="rootflags=subvol=@"/' /etc/default/grub
sudo update-grub

sudo mount /home
sudo reboot

# === 阶段 C：重启后收尾（@ 上操作） ===
sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab
grep subvol /etc/fstab

sudo mount -o subvolid=5 /dev/mapper/x1tablet--vg-root /mnt/btrfs
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@home
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@var
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@log
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@cache
sudo btrfs subvolume delete /mnt/btrfs/@rootfs
sudo umount /mnt/btrfs
sudo update-grub

# === 阶段 D：Timeshift 配置 ===
sudo timeshift --create --comments "初始快照"
sudo timeshift --list
```
