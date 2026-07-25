# 公开BT索引器（PublicBtIndexer）

自动把公开 BT 站点注册进 MoviePilot **原生搜索**，首期仅支持 **Nyaa.si**，不依赖 Jackett。

## 功能

- 启用后自动调用 `SitesHelper().add_indexer()` 注册 Nyaa 索引配置
- 自动创建/更新站点表中的 Nyaa 记录（`public=1`）
- 可选自动加入 `IndexerSites` 搜索范围
- 禁用时默认只移出搜索列表，不删除站点记录
- 可选危险操作：禁用时删除本插件托管的站点记录

## 前置条件

1. MoviePilot v2
2. 已安装 **MoviePilot-Resources**（`app/helper/sites.*` / SitesHelper）
3. 可访问 `https://nyaa.si/`（建议开启代理）

## 安装

### 方式 A：本地插件仓库

1. 将本插件目录放到你的 MoviePilot-Plugins 本地仓库：
   `plugins.v2/publicbtindexer/`
2. 在 `package.v2.json` 中已声明 `PublicBtIndexer` 元数据
3. MoviePilot 配置 `PLUGIN_LOCAL_REPO_PATHS` 指向该插件仓库
4. 在插件市场安装/同步后启用

### 方式 B：直接放入运行目录

复制到 MoviePilot 运行目录：

```text
app/plugins/publicbtindexer/
```

然后安装/重载插件并启用。

## 配置项

| 配置 | 默认 | 说明 |
|---|---|---|
| 启用插件 | 关 | 打开后注册 Nyaa |
| 使用系统代理 | 开 | 对应索引器 `proxy` |
| 超时秒数 | 30 | 搜索超时 |
| 自动加入搜索站点 | 开 | 写入 `IndexerSites` |
| 禁用时移出搜索列表 | 开 | 安全回滚 |
| 禁用时删除站点记录 | 关 | 危险操作，仅删本插件托管站点 |

## 验证

1. 启用插件
2. 打开插件详情页，确认站点记录与搜索列表状态
3. 在 MoviePilot 原生搜索中搜索关键词
4. 结果中应出现来源为 Nyaa 的资源，且可下载 magnet

## 后续规划

- DMHY（RSS 适配）
- 1337x（详情页 magnet，实验性）
- 更多公开站 Profile

## 免责

仅供学习与合法用途。请遵守目标站点服务条款与当地法律法规。
