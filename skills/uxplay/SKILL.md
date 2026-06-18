---
name: uxplay
source: https://github.com/FDH2/UxPlay
description: "Full configuration reference for UxPlay — the open-source AirPlay mirroring server for Linux. Covers all 40+ CLI options organized by function, Debian install, sway/Wayland integration, and verified x1tablet config."
---

# UxPlay — 配置项完整参考

> 官方文档：https://github.com/FDH2/UxPlay （README Usage 节）
> 配置文件优先级：命令行参数 > `~/.uxplayrc` > `~/.config/uxplayrc` > `$UXPLAYRC`
> `~/.uxplayrc` 格式：每行一个选项，去掉前导 `-`，`#` 开头为注释

## When to load

- 需要配置 uxplay 的任何参数
- 排查连接/画面/音频问题
- sway/Wayland 集成调优

## Install (Debian 13+)

```bash
sudo apt install uxplay
```

**依赖**：~65 包（gstreamer 插件、avahi、VA-API 等），~167 MB 磁盘。

## 所有可配置项

### 一、服务标识

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-n name` | UxPlay | AirPlay 显示名称，客户端看到 "name@hostname" |
| `-nh` | — | 不追加 `@hostname` |

### 二、视频分辨率与帧率

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-s wxh` | 1920×1080 | 请求分辨率，如 `-s 3840x2160`。仅建议，客户端不一定遵守。高度 h 决定流格式，宽度自动适配横竖屏 |
| `-s wxh@r` | @60 | 附加刷新率，如 `-s 1920x1080@120`。r < 256 |
| `-h265` | — | 启用 HEVC，默认分辨率升至 3840×2160。需要 M1/M2+ Apple 设备 |
| `-fps n` | 30 | 请求帧率上限，如 `-fps 60`。仅建议，n < 256 |
| `-o` | — | 过扫描模式。**不推荐** |

### 三、窗口与全屏

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-fs` | — | 全屏模式（支持 Wayland/X11/KMS/D3D11） |
| `-vs videosink` | autovideosink | GStreamer 视频输出插件。常用：`waylandsink`, `glimagesink`, `xvimagesink`, `kmssink`。可用 `-vs "waylandsink fullscreen=true"` 传递 videosink 属性 |
| `-vs 0` | — | 禁止视频显示（仅音频，头显服务器用） |
| `-nc` | — | 客户端发 Stop Mirroring 时不关闭窗口（macOS 默认启用） |
| `-nofreeze` | — | 重置后关闭视频窗口（默认保持打开便于重连） |

### 四、GStreamer 管道（视频编解码）

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-avdec` | — | 强制软件 h264 解码（avdec_h264） |
| `-vp parser` | h264parse | h264 解析器元素 |
| `-vd decoder` | decodebin | h264 解码器。硬件：`vah264dec`, `nvh264dec`, `v4l2h264dec` |
| `-vc converter` | videoconvert | 视频转换器。GPU 转换：`-vc v4l2convert` |
| `-v4l2` | — | 等效 `-vd v4l2h264dec -vc v4l2convert` |
| `-bt709` | — | bt709 全色域兼容补丁（Pi + GStreamer >= 1.22） |
| `-srgb` | — | 全范围 8-bit 颜色补丁（Linux/*BSD 默认启用）。`-srgb no` 禁用 |

### 五、GStreamer 管道（音频）

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-as audiosink` | autoaudiosink | 音频输出插件。常用：`pulsesink`, `alsasink`, `pipewiresink`。可带属性如 `-as "alsasink device=..."` |
| `-as 0` / `-a` | — | 静音，仅显示视频 |
| `-al x` | 0.25s | 报告给客户端的音频延迟 [0.0, 10.0]。**客户端可能忽略** |

### 六、音视频同步

| 选项 | 说明 |
|------|------|
| `-vsync` | **（默认）** 镜像模式用时间戳同步音视频。可选毫秒延迟：`-vsync 20.5` |
| `-vsync no` | 关闭时间戳同步（无帧丢弃，适合直播/第二屏幕） |
| `-async` | 纯音频(ALAC)模式用时间戳同步。可选毫秒延迟 |
| `-async no` | **（默认）** 纯音频模式关闭时间戳同步 |

### 七、音量控制

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-vol v` | 1.0 | 初始音量，[0.0=静音, 1.0=最大] |
| `-db low[:high]` | -30:0 | 重映射音量范围。`low` 负值，`high` ≤ +20 |
| `-taper` | — | 渐进式音量曲线（shairport-sync 兼容） |

### 八、网络安全与访问控制

| 选项 | 说明 |
|------|------|
| `-pin [nnnn]` | 随机 PIN（无参数）或固定 PIN（如 `-pin 3939`） |
| `-pw pwd` | 密码认证（≥ 6 字符）。与 `-pin` 互斥，后指定覆盖前者 |
| `-reg [filename]` | 记录已认证客户端到 `~/.uxplay.register`（需配合 `-pin`） |
| `-restrict` | 启用客户端白名单 |
| `-restrict no` | 关闭白名单（**默认**） |
| `-allow id` | 添加 deviceID 到白名单 |
| `-block id` | 黑名单指定 deviceID |
| `-nohold` | 允许新客户端踢掉当前连接（默认独占直到断开） |
| `-m [mac]` | 设置 MAC 地址(DeviceID)。无参数则随机生成 |

### 九、网络端口

| 选项 | 说明 |
|------|------|
| `-p` | 固定端口：TCP 7100/7000/7001, UDP 6000/6001/7011 |
| `-p n` | 起始端口 n，使用 n, n+1, n+2 |
| `-p n1,n2,n3` | 分别指定各端口 |
| `-p tcp n` / `-p udp n` | 仅固定 TCP 或 UDP 端口 |
| 默认（无 `-p`） | 动态随机分配，**防火墙后不可用** |

### 十、HLS 视频流（YouTube）

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-hls [v]` | 3 | 启用 HLS，YouTube app 直接串流。v=playbin 版本（2 或 3） |
| `-lang [list]` | $LANGUAGE | 语言偏好，如 `-lang fr:es:en` |

### 十一、录制与调试

| 选项 | 说明 |
|------|------|
| `-mp4 [fn]` | 录制镜像/音频到 mp4，默认 `recording.n.format.mp4` |
| `-ca` | 显示 Apple Music 封面（音频模式） |
| `-ca filename` | 导出封面到文件（搭配 `feh -R 1 filename`） |
| `-md filename` | 导出音频元数据（歌手/标题）到文件 |
| `-d [n]` | 调试输出，n=1 隐藏音视频包数据 |
| `-FPSdata` | 显示客户端报告的流性能数据（1 秒间隔） |
| `-vdmp [n] [fn]` | 转储 h264 视频到文件 |
| `-admp [n] [fn]` | 转储音频到文件 |
| `-reset n` | 客户端心跳超时（秒），默认 15。n=0 无限等待 |
| `-dacp [fn]` | 导出 DACP-ID / Active-Remote key 到文件 |

### 十二、画面变换

| 选项 | 说明 |
|------|------|
| `-f H` | 水平翻转（镜像） |
| `-f V` | 垂直翻转 |
| `-f I` | 180° 旋转（H+V） |
| `-r R` | 顺时针 90° 旋转 |
| `-r L` | 逆时针 90° 旋转 |

### 十三、RTP 转发

| 选项 | 说明 |
|------|------|
| `-vrtp pipeline` | 转发解密后的 RTP 视频到外部（如 OBS Studio） |
| `-artp pipeline` | 转发解码的 PCM 音频 RTP 流到外部 |

### 十四、其他

| 选项 | 说明 |
|------|------|
| `-scrsv n` | 屏保抑制（D-Bus）：0=关, 1=播放时开, 2=始终开 |
| `-key [fn]` | 安全密钥存储到 `~/.uxplay.pem`（**不再推荐**） |
| `-ble [fn]` | 启用 BLE 蓝牙信标服务发现 |
| `-rc file` | 指定启动配置文件路径 |

### 环境变量

| 变量 | 说明 |
|------|------|
| `$UXPLAYRC` | 配置文件路径 |
| `$LANGUAGE` | HLS 语言偏好，被 `-lang` 覆盖 |
| `GST_DEBUG` | GStreamer 调试级别：2=错误/警告, 4=INFO, 5=DEBUG |

---

## sway / Wayland 集成

### 窗口控制

`-vs "waylandsink fullscreen=true"` 是文档指定的写法——引号将 videosink 名和属性作为单个参数传入。在 sway 上三层全屏可共存：

| 层 | 方式 | 说明 |
|----|------|------|
| GStreamer | `-vs "waylandsink fullscreen=true"` | waylandsink 窗口创建即全屏 |
| uxplay | `-fs` | uxplay 自身请求全屏 |
| sway | `for_window [app_id="uxplay"] fullscreen enable` | 窗口规则兜底 |

### 推荐组合（x1tablet 实测）

```bash
uxplay -n 餐桌 -s 1920x1080 -fps 60 -hls -fs -vs "waylandsink fullscreen=true"
```

> ⚠️ **重点：`exec_always` + `pkill` 模式是 reload 防重的必要条件**
>
> sway/i3 官方文档中 `exec_always` 的定义仅仅是"reload 后再次执行该命令"——**没有任何内置的进程去重或自动 kill 机制**。社区普遍采用的方案就是在命令外面包一层 `bash -c 'pkill -x <name>; exec <name>'` 来手工保证唯一进程。
>
> 来源：sway(5) man page：*"Like exec, but the shell command will be executed again after reload."*

```ini
exec_always bash -c 'pkill -x uxplay 2>/dev/null; sleep 0.2; exec uxplay -n 餐桌 -s 1920x1080 -fps 60 -hls -fs -vs "waylandsink fullscreen=true"'
for_window [app_id="uxplay"] fullscreen enable
```

### 基本用法

```bash
uxplay                              # 默认启动
uxplay -n "AirPlay Server"          # 自定义名称
uxplay -nh                          # 不追加 @hostname
```

---

## 要求

- **同一 LAN**：AirPlay 依赖 Bonjour/mDNS，iPhone 和 Linux 必须在同一广播域。VPN 不传 mDNS
- **avahi-daemon** 必须运行
- **防火墙**：固定端口开 TCP/UDP 7000/7001/6000/6001/7011；动态端口需要查日志确定

## 常见问题

- **不是守护进程**：uxplay 前台运行。可用 `systemd --user` 包装，或用终端后台运行
- **需要 XWayland**：检查 `dpkg -l xwayland`，缺失则 `sudo apt install xwayland`
- **音频无声**：检查 `pactl info` 确认 PipeWire/PulseAudio 正常运行
- **iOS 找不到**：确认 `avahi-browse -a` 能看到服务，检查防火墙
- **一次只能连一个客户端**
