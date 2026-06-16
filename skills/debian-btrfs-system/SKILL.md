---
name: debian-btrfs-system
source:
  - https://github.com/linuxmint/timeshift
  - https://wiki.archlinux.org/title/Btrfs
  - https://www.debian.org/releases/trixie/
description: "Debian 13+ btrfs subvolume layout migration (@rootfs → @/@home), Timeshift btrfs mode setup, GRUB/LVM boot repair, snapshot restore recovery."
tags: [debian, btrfs, timeshift, subvolume, lvm, grub]
---

# Debian Btrfs Subvolume Layout Migration

## 概述

Debian 13 (trixie) 默认的 btrfs 安装使用 `@rootfs` 作为**容器子卷**，所有标准子卷（@, @home, @var, @log, @cache）嵌套于其下。这种布局与 Timeshift btrfs 模式不兼容——Timeshift 要求 @ 在**顶级**。

迁移方法：使用 btrfs send/receive 将容器子卷内容复制到顶级 @ 子卷，切换默认子卷，更新 fstab 和 GRUB。

## 何时使用

- Timeshift btrfs 报错 "root subvolume (@) not found"
- `btrfs subvolume list /` 显示 @, @home 等子卷的 top level > 5（嵌套在容器子卷内）
- 新装 Debian 13+ btrfs 系统需要配置 Timeshift 快照

## 检测布局

```bash
# 查看子卷布局
sudo btrfs subvolume list /
# 注意 top level 列：值为 5 是顶级，>5 是嵌套

# 查看默认子卷
sudo btrfs subvolume get-default /

# 查看挂载选项
mount | grep btrfs

# 挂载 btrfs 顶级查看完整结构
sudo mkdir -p /mnt/btrfs
sudo mount -o subvolid=5 /dev/mapper/x1tablet--vg-root /mnt/btrfs
sudo ls /mnt/btrfs/
```

## 迁移步骤

### 1. 创建顶级 @ 子卷

```bash
# 挂载 btrfs 顶级
sudo mount -o subvolid=5 /dev/mapper/xxx-root /mnt/btrfs

# 快照容器子卷为新的顶级 @
sudo btrfs subvolume snapshot -r /mnt/btrfs/@rootfs /mnt/btrfs/@

# 设为读写
sudo btrfs property set /mnt/btrfs/@ ro false
```

### 2. 创建 @home 顶级子卷

Timeshift btrfs 模式要求 @home 也作为顶级子卷。当前嵌套的 @home 是空的占位，实际 /home 数据在 @rootfs 中。

```bash
# 创建 @home 顶级子卷
sudo btrfs subvolume create /mnt/btrfs/@home

# 从 @ 快照复制 /home 数据（--reflink=always 共享数据块不占额外空间）
sudo cp -a --reflink=always /mnt/btrfs/@/home/. /mnt/btrfs/@home/

# 清理 @ 中旧 /home 内容（保留空目录作挂载点）
sudo rm -rf /mnt/btrfs/@/home/*
```

### 3. 保持默认子卷为 FS_TREE（关键！）

**不要设 @ 为默认子卷！** Timeshift 挂载备份设备时使用默认子卷。若默认是 @，Timeshift 会挂在 @ 内部然后找 `@/@`，导致"Not a Btrfs subvolume"错误。

```bash
# 确认默认是 FS_TREE（ID 5）
sudo btrfs subvolume get-default /mnt/btrfs/
# 应输出: ID 5 (FS_TREE)

# 如果已设为 @，改回 FS_TREE
sudo btrfs subvolume set-default 5 /mnt/btrfs/
```

> **原理**：引导和挂载依赖于 GRUB 内核参数 `rootflags=subvol=@` 和 fstab 中的 `subvol=@`，而非默认子卷。默认子卷只影响不带 subvol= 的挂载，保持 FS_TREE 恰好让 Timeshift 挂载后能访问顶级 @ 和 @home。

### 4. 更新 fstab

先在当前系统修改（针对 @rootfs 的 fstab）：

```bash
sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab
```

添加 @home 挂载：

```bash
echo "/dev/mapper/xxx-root /home btrfs defaults,subvol=@home 0 0" | sudo tee -a /etc/fstab
```

### 5. 更新 GRUB

GRUB 脚本 `10_linux` 会自动添加 `rootflags=subvol=${rootsubvol}`。需要显式覆盖：

```bash
# 给 GRUB_CMDLINE_LINUX 添加 rootflags=subvol=@
# 最终内核会有两个 rootflags 参数，内核使用最后一个
sudo sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="rootflags=subvol=@"/' /etc/default/grub
sudo update-grub
```

### 6. 重启验证

```bash
sudo reboot
# 重启后检查：
btrfs subvolume get-default /
mount | grep " / "
```

### 7. 重启后修复 @ 的 fstab（关键！）（关键！）

@ 是快照产生的，其 /etc/fstab 仍是 @rootfs 时期的旧内容（`subvol=@rootfs`，且可能缺少 @home 条目）。

Timeshift 读取**当前系统**的 /etc/fstab 来识别子卷名称。若 fstab 仍为 `subvol=@rootfs`，`sys_subvolumes` 中会以 `@rootfs` 为键而非 `@`，导致校验失败。

```bash
# 重启后立即修复 fstab
sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab

# 验证
grep subvol /etc/fstab
# 应看到:
#   subvol=@  (根)
#   subvol=@home  (/home)
```

### 8. 清理旧 @rootfs（重启后）

```bash
sudo mount -o subvolid=5 /dev/mapper/xxx-root /mnt/btrfs

# 先删嵌套空子卷（可选）
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@home
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@var
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@log
sudo btrfs subvolume delete /mnt/btrfs/@rootfs/@cache

# 删 @rootfs
sudo btrfs subvolume delete /mnt/btrfs/@rootfs
sudo umount /mnt/btrfs

# 更新 GRUB 清理内核路径中的 @rootfs 引用
sudo update-grub
# 验证内核路径已变为 /@/boot/vmlinuz-...
sudo grep "rootflags=subvol=" /boot/grub/grub.cfg | head -2
```

## 配置 Timeshift

### 安装与配置

```bash
sudo apt install -y timeshift
```

创建或修改 `/etc/timeshift/timeshift.json`：

```json
{
  "backup_device_uuid" : "<btrfs-uuid>",
  "parent_device_uuid" : "<btrfs-uuid>",
  "do_first_run" : "false",
  "btrfs_mode" : "true",
  "include_btrfs_home" : "true",
  "stop_cron_emails" : "true",
  "schedule_monthly" : "true",
  "schedule_weekly" : "true",
  "schedule_daily" : "true",
  "schedule_hourly" : "false",
  "schedule_boot" : "false",
  "count_monthly" : "2",
  "count_weekly" : "3",
  "count_daily" : "5",
  "count_hourly" : "6",
  "count_boot" : "5",
  "exclude" : [
    "/var/cache/**",
    "/var/log/**",
    "/var/tmp/**",
    "/tmp/**",
    "/.cache/**",
    "/home/**/.cache/**",
    "/home/**/Downloads/**"
  ]
}
```

### 验证 Timeshift

```bash
# 确保 Timeshift 配置正确
sudo timeshift --list
# 应显示 Mode: BTRFS

# 创建测试快照
sudo timeshift --create --comments "test snapshot"
```

### Timeshift 定时调度说明

Timeshift 安装后自动创建 `/etc/cron.d/timeshift-hourly`：

```cron
0 * * * * root timeshift --check --scripted
```

`--check --scripted` 每小时整点运行一次，逻辑：

| 计划 | count 值 | 行为 |
|---|---|---|
| daily (5) | 今天还没有每日快照？→ 创建一个 | 超过 5 个时删最旧的 |
| weekly (3) | 本周还没有周快照？→ 创建一个 | 超过 3 个时删最旧的 |
| monthly (2) | 本月还没有月快照？→ 创建一个 | 超过 2 个时删最旧的 |

**不是"每天做 N 个快照"**，是"每天最多做 1 个快照，保留最近 N 天的量"。例如 `count_daily=5` 意味着保留最近 5 天各 1 个快照（共 5 个）。

- 每日快照创建时间：**00:00**（当天首次 check 命中时）
- 每周快照创建时间：**周一 00:00**
- 每月快照创建时间：**1 号 00:00**

手动创建快照：

```bash
sudo timeshift --create --comments "升级内核前备份"
```

查看/删除快照：

```bash
sudo timeshift --list
sudo timeshift --delete --snapshot '2026-06-10_00-52-03'
```

## 常见陷阱

- **@rootfs 嵌套子卷可能是空的**：Debian 安装程序创建了 @home 等嵌套子卷但从未使用，实际数据在 @rootfs 中。迁移后无需单独处理这些空子卷。
- **GRUB 内核路径仍引用 @rootfs**：不影响引导，因为 @rootfs 在迁移后仍然存在（作为旧子卷）。清理后需 re-run update-grub。
- **LVM 路径**：设备路径可能是 `/dev/mapper/xxx-root`，用 `sudo lsblk -f` 确认。
- **fstab 中默认子卷不生效**：内核使用 rootflags 参数挂载根文件系统。默认子卷只影响不带 subvol= 的挂载和不指定 subvol 的 GRUB 引导。
- **Timeshift 通过 fstab 检测子卷**：Timeshift 不直接扫描 btrfs 子卷列表，而是解析 `/etc/fstab` 的 `subvol=` 选项。fstab 错误 → Timeshift 报"unsupported subvolume layout"。重启后 @ 的 fstab 仍是旧快照内容，必须修复。
- **@ 不能是默认子卷**：设 @ 为默认子卷会导致 Timeshift 挂载备份设备时挂在 @ 内部，然后试图 snapshot `@/@` 而失败（"Not a Btrfs subvolume"）。保持 FS_TREE（ID 5）为默认。引导靠 GRUB 内核参数 `rootflags=subvol=@`，非靠默认子卷。

## Timeshift 快照恢复后进 GRUB rescue 的补救方案

### 问题现象

执行 `sudo timeshift --restore --snapshot "xxx" --target-device /dev/mapper/xxx-root --yes` 后重启，系统停在 GRUB rescue 提示符，或报 `unable to mount root fs on /dev/mapper/xxx-root`。

### 根因

Timeshift 的 btrfs restore 过程：
1. 将当前 @ 子卷重命名为备份（如 `@_bak`）
2. 从快照创建新的 @ 子卷
3. 重启后 GRUB 从新的 @ 子卷读取 grub.cfg
4. 若快照中的 GRUB 配置与当前硬件/设备路径不匹配（例如用了旧的内核参数格式），导致无法挂载根文件系统

### 手动引导命令

在 GRUB rescue 提示符下执行：

```grub
# 1. 设置 LVM 根
set root=(lvm/<vg-name>-root)

# 2. 加载内核（用 Tab 补全 vmlinuz 文件名）
linux /@/boot/vmlinuz-<version>-amd64 root=UUID=<btrfs-uuid> ro rootflags=subvol=@ quiet

# 3. 加载 initrd
initrd /@/boot/initrd.img-<version>-amd64

# 4. 启动
boot
```

> **关键技巧**：当 `root=/dev/mapper/xxx-root` 报 `unable to mount` 时，改为 `root=UUID=<btrfs-uuid>`。内核在挂载根文件系统之前可能无法解析 LVM 设备路径，但 UUID 直接从 blkid 读。用 `sudo blkid /dev/mapper/xxx-root` 获取 UUID。

> **查找内核版本**：在 GRUB 提示符输入 `ls /@/boot/` 查看实际文件名，或输入 `linux /@/boot/vmlinuz-` 后按 Tab 补全。

> **磁盘信息**：通过 Tab 补全查看可用 LVM 卷组：`ls` 列出所有磁盘，`ls (lvm/` 后按 Tab 列出 LVM 逻辑卷。

### 进入系统后的修复

```bash
# 确认 fstab 正确
sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab
grep subvol /etc/fstab

# 重新生成 GRUB 配置
sudo update-grub

# 确认 GRUB 内核参数
sudo grep "rootflags=subvol=" /boot/grub/grub.cfg | head -2
# 应显示 rootflags=subvol=@，路径应为 /@/boot/...
```

### 预防措施

恢复快照前：
- 确认当前系统 fstab 和 GRUB 配置是**最终正确的版本**（不是快照中间状态的配置）
- 创建新快照（Timeshift 自动会在 restore 前创建 pre-restore 快照）
- 记下 btrfs UUID 和 LVM 卷组名（可以印在纸条上或记录在手机备忘录）
- **fstab 排版问题导致 Timeshift 识别失败**：Timeshift 的 `is_for_system_directory()`（FsTabEntry.vala）要求设备路径以 `/dev/` 或 `uuid=` 开头。若 fstab 使用了 LABEL/PARTLABEL/PARTUUID 格式的设备名，`is_for_system_directory()` 返回 false，fstab 条目被跳过。用 `cat -A /etc/fstab` 检查空白字符和排版。正确的格式示例：`/dev/mapper/xxx-root / btrfs defaults,subvol=@ 0 0`。
