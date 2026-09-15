# 模型目录

模型文件通常较大，不建议直接提交到仓库。

约定路径：

- `package_letter.onnx`：国赛 YOLO26 包裹图片和 A/B/C/D 字母联合检测模型。
- `ABCD.onnx`：投递区 A/B/C/D 字母检测模型，可先从参考例程迁移测试。

当前第一版任务逻辑支持 dry-run；没有模型时仍可跑通流程。正式上板前需要补齐模型并在 CM5 上测试推理耗时。

联合模型类别名固定为：

```text
clothes paper toothbrush apple orange banana A B C D
```

推理端直接接收共享相机的 BGR 原图。`.onnx` 使用板端现有 ONNX Runtime，避免
依赖训练环境中的 Torch；`.pt` 仍可通过 Ultralytics 加载，但当前板端 Torch 与
Torchvision 版本不匹配，暂不作为正式部署格式。队员训练 YOLO26 后需要同时导出
ONNX，并保留类别 metadata；更换格式只需修改 `config.json` 的 `package_model`。
