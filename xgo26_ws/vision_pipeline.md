# 视觉链路

## 约束

- 只有 `xgo26-camera.service` 可以创建 `Picamera2`，其他模块不得直接打开摄像头。
- 相机固定使用 OV5647 的 `1296x972`、4:3、10-bit 传感器模式，目标帧率 30 FPS。
- 服务持续生成同视场的 `main` 和 `lores` 两路 BGR 图像，并为每帧附加序号和传感器时间戳。
- 算法总是读取最新帧；处理落后时丢弃旧帧，不形成延迟队列。
- ROI 和目标位置优先使用归一化坐标，避免绑定某个输出分辨率。

## 消费者

| 消费者 | 数据流 | 默认尺寸 | 用途 |
| --- | --- | --- | --- |
| 浏览器 | `lores` MJPEG | 640x480 | 远程观察与现场调试 |
| 包裹/字母 YOLO | `main` raw | 1296x972 | 识别区目标检测 |
| 地面循迹 | `lores` raw | 320x240 | 黑线质心与方向修正 |
| 小球识别 | `lores` raw | 320x240 | 颜色分割与抓取对准 |
| 地面字母识别 | 待实测 | 待定 | 可以切换传统视觉或 YOLO |

服务原始帧为 BGR888，Python 客户端不需要 JPEG 解码。浏览器预览单独使用 JPEG，不进入正式算法链路。

## 循迹视觉

`xgo26/line_following.py` 在画面下半部设置三条横向扫描带，从近到远寻找连续黑色区段。候选区段同时受宽度、上一层位置和前一帧位置约束，因此不会仅凭“最大黑色轮廓”选中地板接缝、墙面或圆形地标。

输出包含近端横向误差、远近点形成的方向误差、融合转向误差和置信度。运动层只使用融合误差，并在转向量增大时降低前进速度；连续丢线时按路线配置停车。`tools/test_line_vision.py` 只读取图像并输出标注图，不会初始化机器狗。

## HTTP 接口

```text
GET /health
GET /stream.mjpg?stream=lores
GET /snapshot.jpg?stream=main
GET /frame.raw?stream=lores&after=<sequence>
```

`frame.raw` 响应头包含宽、高、通道数、帧序号和 `SensorTimestamp`。正常任务代码通过 `CameraServiceClient` 使用该接口，不直接解析响应头。

## 服务切换

仓库提供 `deploy/systemd/xgo26-camera.service`。它与厂商 `oumax-camera.service` 都使用摄像头和 8090 端口，不能同时运行。

切换到比赛服务：

```bash
sudo systemctl disable --now oumax-camera.service
sudo install -m 644 deploy/systemd/xgo26-camera.service /etc/systemd/system/xgo26-camera.service
sudo systemctl daemon-reload
sudo systemctl enable --now xgo26-camera.service
```

恢复厂商服务：

```bash
sudo systemctl disable --now xgo26-camera.service
sudo systemctl enable --now oumax-camera.service
```

不要直接修改 `/home/pi/oumax-xgo/picam_mjpeg_server.py`，以便随时回退厂商环境。
