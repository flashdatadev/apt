# FlashData APT 软件源

[English](README.md) · [FlashData 官网](https://flashdata.dev) · [API 文档](https://flashdata.dev/docs) · [CLI 仓库](https://github.com/flashdatadev/flashdata-cli)

开源 FlashData CLI 的官方签名 APT 软件源。[FlashData](https://flashdata.dev) 提供结构化 Google 搜索和 YouTube 数据；CLI 支持安全的凭据配置、后台任务、批量导出及持久化执行恢复。

支持 **Ubuntu 22.04/24.04、Debian 12/13**，架构为 **amd64 和 arm64**。`flashdata` 软件包 **1.2.1-1** 包含未经修改的 CLI **1.2.1** 可执行文件；`-1` 是 Debian 打包修订号。无需安装 Go、Python 或 Node.js 运行时。

## 安装

使用具有 sudo 权限的账户运行以下 Bash 命令。命令会安装 HTTPS/GPG 依赖、核对公钥指纹、为该软件源单独配置信任和包选择规则，然后安装 CLI：

```bash
(
  set -eu
  arch="$(dpkg --print-architecture)"
  case "$arch" in amd64|arm64) ;; *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; esac
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  work_dir="$(mktemp -d)"
  trap 'rm -rf -- "$work_dir"' EXIT
  curl --fail --location https://flashdatadev.github.io/apt/flashdata.asc --output "$work_dir/flashdata.asc"
  expected=19F337AC01C5F5B646A5583A04C7934A11D38FFA
  actual="$(gpg --batch --show-keys --with-colons "$work_dir/flashdata.asc" 2>/dev/null | awk -F: '$1 == "fpr" { print $10; exit }')"
  test "$actual" = "$expected"
  sudo install -d -m 0755 /etc/apt/keyrings
  sudo install -m 0644 "$work_dir/flashdata.asc" /etc/apt/keyrings/flashdata.asc
  sudo tee /etc/apt/sources.list.d/flashdata.sources >/dev/null <<EOF
Types: deb
URIs: https://flashdatadev.github.io/apt/
Suites: stable
Components: main
Architectures: $arch
Signed-By: /etc/apt/keyrings/flashdata.asc $expected
EOF
  sudo tee /etc/apt/preferences.d/flashdata >/dev/null <<'EOF'
Package: flashdata
Pin: release o=FlashData
Pin-Priority: 500

Package: *
Pin: release o=FlashData
Pin-Priority: -1
EOF
  sudo apt-get update
  sudo apt-get install -y flashdata
  flashdata --version
  flashdata --help
)
```

软件源地址为 `https://flashdatadev.github.io/apt/`，发行套件为 `stable`，组件为 `main`。专用签名证书指纹为 **`19F337AC01C5F5B646A5583A04C7934A11D38FFA`**，身份是 `FlashData APT Signing <support@flashdata.dev>`。[公钥](keys/flashdata.asc)和[指纹](keys/fingerprint.txt)也记录在本源码仓库中。请勿禁用签名验证，也不要将此公钥导入 APT 全局信任密钥环。

安装后，设置 agent：

```bash
flashdata setup
```

设置会选择 Codex、Claude Code 或 Cursor，安装随附技能并验证访问，不执行付费查询。技能内容查询默认使用纯文本；批量导出保持 JSONL。CLI v1.2.1 为主技能和五个 YouTube 技能随附批量指南。升级后重新运行 `flashdata setup` 更新未修改的技能；MCP 可选。使用已有密钥时，设置前运行 `flashdata auth login`。uv 安装方式见 [CLI 设置指南](https://github.com/flashdatadev/flashdata-cli/blob/main/README.zh-CN.md)。

安装及离线版本/帮助检查无需 API 密钥；提交 API 查询和任务按正常 FlashData 规则计费。查询、接入、批量任务及恢复流程参见 [English CLI README](https://github.com/flashdatadev/flashdata-cli#readme) 和[简体中文](https://github.com/flashdatadev/flashdata-cli/blob/main/README.zh-CN.md)。

## 升级

```bash
sudo apt-get update
sudo apt-get install --only-upgrade flashdata
flashdata --version
```

新的 CLI 版本或 Debian 打包修订发布后，即可通过 APT 升级。可执行文件报告的是 CLI 上游版本；可通过以下命令查看打包修订号：

```bash
dpkg-query -W -f='${Version}\n' flashdata
apt-cache policy flashdata
```

如果之前通过 Homebrew 或独立归档安装，请先运行 `command -v flashdata`。PATH 中靠前的旧版本可能遮蔽 `/usr/bin/flashdata`；请卸载或移走旧可执行文件，或调整 PATH。保留 CLI 状态目录，并重启终端或运行 `hash -r`。

## 文档与卸载

```bash
ls /usr/share/doc/flashdata/examples
ls /usr/share/doc/flashdata/docs
man flashdata
```

软件包包含示例、中英文版本文档、构建来源记录及第三方许可证声明。这些文档是 v1.2.1 发布快照；最新安装说明位于本仓库及 CLI 仓库。

```bash
sudo apt-get remove flashdata
```

卸载或清除软件包不会撤销 API 密钥，也不会删除用户配置和执行历史。如需移除某个配置中已保存的凭据，请在卸载前为该配置运行 `flashdata auth logout`。详见[凭据存储说明](https://github.com/flashdatadev/flashdata-cli/blob/main/docs/security.md)。

如需同时移除软件源配置：

```bash
sudo rm -f /etc/apt/sources.list.d/flashdata.sources /etc/apt/preferences.d/flashdata /etc/apt/keyrings/flashdata.asc
sudo apt-get update
```

## 验证与维护

[GitHub Actions](https://github.com/flashdatadev/apt/actions) 从校验和锁定的发布归档复现两个架构的软件包，签署 APT 索引，在部署前测试 Ubuntu 22.04/24.04 与 Debian 12/13 的两个架构，并在发布后通过真实 HTTPS 软件源重复安装和升级检查。测试包含重新安装、卸载、用户状态保留，以及拒绝错误公钥、篡改签名和被修改的软件包内容。

升级测试从真实旧版 **1.2.0-1** 通过 APT 升级到 **1.2.1-1**，验证新可执行文件哈希并保留用户状态。另用 `1.2.1-1~upgradetest` 专用包验证打包修订升级，该测试包不进入公开索引。原有两个架构的 1.0.0 软件包保持不变并继续提供。

签名元数据有效期为 30 天。发布工作流每周刷新一次，也可手动运行；签名密钥距到期不足 30 天时，工作流会拒绝发布。详见[维护说明](docs/maintaining.md)及[签名与安全](SECURITY.md)。更新软件包必须使用新的 Debian 版本号；已发布版本的软件包及上游标签须保持不变。

打包问题：[软件源 issues](https://github.com/flashdatadev/apt/issues)。CLI 问题：[CLI issues](https://github.com/flashdatadev/flashdata-cli/issues)。账户支持：[support@flashdata.dev](mailto:support@flashdata.dev)。
