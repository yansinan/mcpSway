# Timeshift 恢复后的完整修复流程（Debian 13 btrfs + LVM）

## 现象

`sudo timeshift --restore` 后重启报 `unable to mount root fs`，掉进 BusyBox 或 GRUB rescue。

## 根因

Timeshift restore 将 @ 子卷替换为快照时的内容，导致三个问题：

1. **fstab 回到快照状态** — 可能有 `subvol=@rootfs` 残留
2. **GRUB 配置回到快照状态** — 可能有 `root=/dev/mapper/...` 而非 UUID
3. **initramfs 回到快照状态** — 可能没有 LVM 模块
4. **GRUB 核心镜像前缀** — 指向旧子卷路径

## BusyBox 临时恢复

```sh
lvm vgchange -ay
exit
```

## 完整修复（进入系统后）

```bash
# 1. 修复 fstab
sudo sed -i 's/subvol=@rootfs/subvol=@/' /etc/fstab

# 2. 获取 UUID
sudo blkid /dev/mapper/x1tablet--vg-root
# → UUID=142fb829-1fd4-4b70-82eb-e63e7864b561

# 3. 配置 GRUB 内核参数
sudo sed -i 's|GRUB_CMDLINE_LINUX=""|GRUB_CMDLINE_LINUX="root=UUID=142fb829-1fd4-4b70-82eb-e63e7864b561 rootflags=subvol=@"|' /etc/default/grub

# 4. 重装 GRUB（修 EFI 前缀）
sudo grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Debian --recheck

# 5. initramfs 加 LVM 支持
echo "LVM=y" | sudo tee /etc/initramfs-tools/conf.d/lvm

# 6. 重建配置
sudo update-grub
sudo update-initramfs -u -k all
```

## GRUB rescue 手动引导

```grub
set root=(lvm/x1tablet--vg-root)
linux /@/boot/vmlinuz-6.12.90+deb13.1-amd64 root=UUID=142fb829-1fd4-4b70-82eb-e63e7864b561 ro rootflags=subvol=@ quiet
initrd /@/boot/initrd.img-6.12.90+deb13.1-amd64
boot
```

用 `root=UUID=...` 而非 `root=/dev/mapper/...`（LVM 未激活时设备路径不可用）。
