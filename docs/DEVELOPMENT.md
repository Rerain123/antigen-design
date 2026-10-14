# 开发与验证

## 环境

控制面要求 Python 3.11。以下命令在仓库根目录运行。示例不下载模型、不启动科学任务，也不连接已有部署。

```bash
python -m venv .venv
```

Windows PowerShell 激活与路径设置：

```powershell
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD/src"
```

Linux shell：

```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
```

安装控制面与精选测试所需依赖：

```bash
python -m pip install "jsonschema>=4.23,<5" "PyYAML>=6.0,<7" pytest
python -m pytest
python scripts/t01_runtime.py --help
```

部分进程测试只适用于 Linux，会在其他系统跳过。此处测试覆盖进程管理、结果收据、IEDB 证据映射与投影构建、日志处理、AF3 输入与设备配置等工程行为；不执行实际结构预测或完整抗原设计。

结构解析及工具适配的额外依赖见 `requirements/`；每种科学工具应在其对应环境内配置。容器配方依赖指定的基础镜像与工具资产，不构成公开版一键部署方案。

## 服务与 Worker 入口

Linux 服务入口：

```bash
python -m t01_phase1_real.linux_service --help
```

服务支持 `--host`、`--port` 和必填的 `--runtime-root`。凭据通过 `T01_REAL_SERVICE_CREDENTIALS_FILE` 指向仓库外的绝对路径，或通过 `T01_REAL_SERVICE_CREDENTIALS_JSON` 注入；两者仅配置一个。文件的顶层 `credentials` 数组中，每项包含 `token`、`principal` 和 `scopes`，可用权限为 `submit`、`query`、`control`、`download`、`upload`。令牌至少32字符，应使用安全生成器生成，不提交到 Git。

常驻 Worker 入口：

```bash
python -m t01_phase1_real.resident_worker --help
```

实际启动需要私有运行目录、工具配置、受许可资产及适用科学资料。公开副本不会创建这些资料，也没有生产部署参数。先核对 [公开范围](PUBLIC_SCOPE.md)，再由授权团队配置运行环境。

## 修改原则

保持请求与产物契约、版本隔离、幂等和原件指纹校验。使用合成数据验证工程行为；科学门控的修改需要相应权威依据和验收。不要为了让缺资料的公开副本运行而跳过原件或产物检查。
