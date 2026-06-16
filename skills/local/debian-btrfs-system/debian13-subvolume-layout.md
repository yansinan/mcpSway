# Debian 13 (trixie) btrfs 子卷布局参考

## 典型布局（Debian 13 installer 默认）

```
Device: /dev/mapper/x1tablet--vg-root (LVM)
UUID:   142fb829-1fd4-4b70-82eb-e63e7864b561
Size:   224.54GiB (used: ~1.86GiB on fresh install)

Subvolume layout:
ID 256 gen 218 top level 5   path @rootfs    # 容器子卷，挂在 /
ID 257 gen 150 top level 256 path @           # 嵌套在 @rootfs 下
ID 258 gen 150 top level 256 path @home
ID 259 gen 150 top level 256 path @var
ID 260 gen 150 top level 256 path @log
ID 261 gen 151 top level 256 path @cache

Default subvolume: ID 5 (FS_TREE)
```

## 挂载配置（/etc/fstab）

```
/dev/mapper/x1tablet--vg-root /  btrfs  defaults,subvol=@rootfs  0  0
UUID=5286-D2BA /boot/efi vfat umask=0077 0 1
/dev/mapper/x1tablet--vg-swap_1 none swap sw 0 0
```

SSD 挂载选项（运行中）: `rw,relatime,ssd,discard=async,space_cache=v2,subvolid=256,subvol=/@rootfs`

## 分区结构

```
nvme0n1
  +-- nvme0n1p1  vfat   FAT32   /boot/efi     965MB
  +-- nvme0n1p2  ext4   1.0     (未挂载)       ~几百MB
  +-- nvme0n1p3  LVM2
        +-- x1tablet--vg-root   btrfs  /       224.54GiB
        +-- x1tablet--vg-swap_1 swap   [SWAP]  交换分区
```

## 与 Ubuntu 布局的区别

| 特性 | Debian 13 | Ubuntu 标准 |
|------|-----------|-------------|
| 根子卷 | @rootfs（容器） | @（顶级） |
| 嵌套 | @/@home 等是 @rootfs 子辈 | @/@home 是同级兄弟 |
| 默认 subvol | FS_TREE (ID 5) | @ (ID 257+) |
| Timeshift 兼容 | 不兼容，需迁移 | 开箱即用 |

## Timeshift 错误表现

```
$ sudo timeshift --list
Mounted '/dev/dm-0 (nvme0n1p3)' at '/run/timeshift/5827/backup'
Device : /dev/dm-0 (nvme0n1p3)
UUID   : 142fb829-1fd4-4b70-82eb-e63e7864b561
Path   : /run/timeshift/5827/backup
Mode   : BTRFS
Status : Selected snapshot device is not a system disk
Select BTRFS system disk with root subvolume (@)
```

## 排查命令速查

```bash
# 文件系统
sudo lsblk -f

# 子卷结构
sudo btrfs subvolume list /
sudo btrfs subvolume get-default /
sudo btrfs filesystem show

# 挂载选项
mount | grep btrfs

# fstab
cat /etc/fstab
```
