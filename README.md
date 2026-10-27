# 雾钟城：第七声

单人浏览器文字冒险 RPG，基于完整剧本包转录。线上地址：[https://rpg.xyzhzz.com](https://rpg.xyzhzz.com)

## 本地预览

```bash
python3 tools/parse-script.py && python3 tools/synthesize-extra.py
cd public && python3 -m http.server 8080
```

打开 `http://127.0.0.1:8080/`。调试面板：`?debug=1`。

## 部署

```bash
export CLOUDFLARE_API_TOKEN=...
./scripts/deploy.sh
```

Cloudflare Pages 项目名：`xyzhzz-rpg`，自定义域：`rpg.xyzhzz.com`。

## 推送备份

仓库：`https://github.com/ftmg12138/hzz-rpg1`（私有）

```bash
export GITHUB_BACKUP_TOKEN=...
./scripts/push.sh "说明"
```

## 结构

- `script/` 剧本 Markdown 源文件
- `tools/parse-script.py` 转录为 `public/data/nodes.json`
- `public/` 静态站点（vanilla JS，无 CDN）

## 说明

- 存档在浏览器 `localStorage`，无后端。
- 检定：`d20 + floor((属性-10)/2) >= DC`。
- 部分枢纽节点的选项经手工补丁连通；未完全解析的岔路会进入提示节点而非静默卡死。
