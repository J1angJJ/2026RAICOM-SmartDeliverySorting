# 模型目录

模型文件通常较大，不建议直接提交到仓库。

约定路径：

- `package_letter.pt`：国赛 YOLO26 包裹图片和 A/B/C/D 字母联合检测模型。
- `ABCD.onnx`：投递区 A/B/C/D 字母检测模型，可先从参考例程迁移测试。

当前第一版任务逻辑支持 dry-run；没有模型时仍可跑通流程。正式上板前需要补齐模型并在 CM5 上测试推理耗时。

联合模型类别名固定为：

```text
clothes paper toothbrush apple orange banana A B C D
```

推理端通过 Ultralytics 加载权重并直接接收共享相机的 BGR 原图，`.pt` 和从同一
模型导出的 `.onnx` 都可使用。第一轮先使用训练得到的 `.pt`，确认精度和耗时后
再决定是否导出 ONNX；更换格式只需要修改 `config.json` 中的 `package_model`。
