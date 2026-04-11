# outputs 目录说明

`outputs/` 不再是“一刀切全部忽略”。

现在分成三层：

## 1. 工作产物层

位置：

- `outputs/` 根目录

用途：

- 放每次运行生成的 `.docx`
- 放单次处理过程中的局部日志

Git 策略：

- 默认忽略
- 不直接进入版本历史

原因：

- 这部分产物数量多、变动快
- 直接进 Git 会污染主链历史

## 2. 输出索引层

位置：

- `outputs/index/`

用途：

- 记录当前有哪些输出产物
- 记录文件名、修改时间、大小
- 让 Git 能“看见结果”，但不强制追踪所有二进制文件

Git 策略：

- 纳入版本控制

更新方式：

```bash
python3 scripts/output_versioning.py manifest
```

## 3. 里程碑产物层

位置：

- `outputs/milestones/`

用途：

- 只保留少量有代表性的阶段成果
- 例如某次参考文献主链验证版、图规则验证版

Git 策略：

- 可进入版本控制
- 只收少量关键文件

提升方式：

```bash
python3 scripts/output_versioning.py promote outputs/某个文件.docx --note "用途说明"
```

## 使用原则

- 日常生成文件放在 `outputs/` 根目录即可
- 需要让 Git 看见当前结果时，更新 `outputs/index/`
- 只有确实值得长期保留的成果，才提升到 `outputs/milestones/`
- 不要把每一篇论文的每一步中间产物都提升成里程碑
