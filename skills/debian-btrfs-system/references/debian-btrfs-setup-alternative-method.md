---
name: debian-btrfs-setup
category: devops
description: 诊断 Debian 13 (trixie+) 的 btrfs 嵌套子卷布局，迁移到标准 @ 布局，配置 Timeshift btrfs 模式快照。
tags: [debian, btrfs, timeshift, subvolume, snapshot, system-setup]
triggers:
  - user asks to set up Timeshift on a Debian system
  - user needs to check or restructure btrfs subvolume layout
  - Timeshift error: "Selected snapshot device is not a system disk"
  - Debian 13 btrfs root filesystem needs snapshot tool configuration
---

# Debian Btrfs Setup — Timeshift & Subvolume Layout

验证、诊断和重构 Debian 13 (trixie+) 的 btrfs 子卷布局，配置 Timeshift btrfs 快照模式。

## 1. 验证当前布局

```bash
# 文件系统概览
sudo lsblk -f

# btrfs 子卷列表
sudo btrfs subvolume list /

# 默认子卷
sudo btrfs subvolume get-default /

# 挂载点分布
df -h /

# fstab
cat /etc/fstab
```

## 2. 诊断 Debian 13 的嵌套布局

Debian 13 installer 使用**容器+嵌套**模式：

```
@rootfs (ID 256, top level 5, 挂在 /)
  +-- @        (ID 257, top level 256)
  +-- @home    (ID 258, top level 256)
  +-- @var     (ID 259, top level 256)
  +-- @log     (ID 260, top level 256)
  +-- @cache   (ID 261, top level 256)
```

**问题**：Timeshift btrfs 模式要求 @ 在 **top level 5**（顶级），而非嵌套在 @rootfs 下。
错误表现：`Selected snapshot device is not a system disk`，提示 "Select BTRFS system disk with root subvolume (@)"。

## 3. 迁移嵌套子卷到顶级

用 btrfs send/receive 将嵌套子卷提升到顶级（不重启即可完成）。

### 3.1 挂载 btrfs 顶级

```bash
sudo mkdir -p /mnt/btrfs
sudo mount -o subvolid=5 /dev/mapper/x1tablet--vg-root /mnt/btrfs
# 确认看到 @rootfs 目录
ls /mnt/btrfs/
```

### 3.2 创建只读快照 + send/receive（每个嵌套子卷）

```bash
# @ -> 顶级
sudo btrfs subvolume snapshot -r /mnt/btrfs/@rootfs/@ /mnt/btrfs/@_send
sudo btrfs send /mnt/btrfs/@_send | sudo btrfs receive /mnt/btrfs/
sudo btrfs subvolume delete /mnt/btrfs/@_send
sudo btrfs property set /mnt/btrfs/@ ro false

# @home -> 顶级
sudo btrfs subvolume snapshot -r /mnt/btrfs/@rootfs/@home /mnt/btrfs/@home_send
sudo btrfs send /mnt/btrfs/@home_send | sudo btrfs receive /mnt/btrfs/
sudo btrfs subvolume delete /mnt/btrfs/@home_send
sudo btrfs property set /mnt/btrfs/@home ro false

# 对其他嵌套子卷重复：@var, @log, @cache
```

### 3.3 更新 fstab

```bash
sudo cp /etc/fstab /etc/fstab.bak
```

添加独立的子卷挂载项：
```
/dev/mapper/x1tablet--vg-root /               btrfs   defaults,subvol=@      0       0
/dev/mapper/x1tablet--vg-root /home           btrfs   defaults,subvol=@home  0       0
# 可选：
# /dev/mapper/x1tablet--vg-root /var          btrfs   defaults,subvol=@var   0       0
```

### 3.4 设置默认子卷 + 重启

```bash
# 找新 @ 的 subvolid
sudo btrfs subvolume list /mnt/btrfs/ | grep ' @$'

# 设为默认
sudo btrfs subvolume set-default <NEW_ID> /mnt/btrfs/

# 卸载临时挂载
sudo umount /mnt/btrfs

# 重启
sudo reboot
```

### 3.5 清理旧 @rootfs

重启后验证一切正常，删除旧嵌套子卷：

```bash
sudo mount -o subvolid=5 /dev/mapper/x1tablet--vg-root /mnt/btrfs
# 确认内容已迁移
sudo btrfs subvolume delete /mnt/btrfs/@rootfs
sudo umount /mnt/btrfs
```

## 4. 配置 Timeshift btrfs 模式

```bash
# 验证 Timeshift 已装
sudo timeshift --version

# 写配置文件 /etc/timeshift/timeshift.json
sudo mkdir -p /etc/timeshift
```

推荐配置（btrfs 模式，每日/周/月 + 排除缓存日志）：

```json
{
  "backup_device_uuid": "<BTRFS_UUID>",
  "parent_device_uuid": "<BTRFS_UUID>",
  "do_first_run": "false",
  "btrfs_mode": "true",
  "include_btrfs_home": "true",
  "stop_cron_emails": "true",
  "schedule_monthly": "true",
  "schedule_weekly": "true",
  "schedule_daily": "true",
  "schedule_hourly": "false",
  "schedule_boot": "false",
  "count_monthly": "2",
  "count_weekly": "3",
  "count_daily": "5",
  "count_hourly": "6",
  "count_boot": "5",
  "exclude": [
    "/var/cache/**",
    "/var/log/**",
    "/var/tmp/**",
    "/tmp/**",
    "/.cache/**",
    "/home/**/.cache/**",
    "/home/**/Downloads/**"
  ],
  "exclude-apps": []
}
```

获取 BTRFS_UUID：`sudo blkid -o value -s UUID /dev/mapper/x1tablet--vg-root`

## 5. 验证

```bash
# 查看状态
sudo timeshift --list

# 创建初始快照
sudo timeshift --create --comments "初始快照"

# 验证快照存在
sudo timeshift --list
```

## 常见陷阱

- **Timeshift 自动选了 ext4 分区**：首次运行时如果 /etc/timeshift/timeshift.json 不存在，Timeshift 可能扫描 ext4 分区并默认 RSYNC 模式而非 btrfs。必须手动写配置文件强制 btrfs 模式。
- **send/receive 时 @ 不能是当前挂载的 root**：必须从 top level (subvolid=5) 临时挂载操作，或在恢复模式下操作。
- **子卷设为只读后才能 send**：如果子卷是 rw，需先用 `snapshot -r` 创建只读副本。
- **btrfs property set ro false** 在接收后必须执行，否则新子卷只读不可写。
- **重启前务必备份 fstab**：配错 fstab 会导致无法启动。

## 参考

参考文件：`debian13-subvolume-layout.md` 在 references/ 目录
