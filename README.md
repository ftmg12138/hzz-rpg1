# 雾钟城：第七声

单人浏览器文字冒险 RPG，基于完整剧本包转录。线上地址：[https://rpg.xyzhzz.com](https://rpg.xyzhzz.com)

## 本地预览

```bash
python3 tools/parse-script.py && python3 tools/synthesize-extra.py
cd public && python3 -m http.server 8080
```

打开 `http://127.0.0.1:8080/`。调试面板：`?debug=1`。

## 剧情回归

```bash
npm test
```

该命令会重新生成剧情数据，检查断链与不可达结局，核对明确写出的金钱/道具奖励，回归序章结算，并以高低两种掷骰结果执行全部顶层及嵌套选项。

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
- `tools/wzc_patches.py` 为原剧本补充可执行条件、奖励与状态变更
- `tools/audit-rewards.py` 核对剧情承诺与实际奖励
- `tools/test-all-choices.js` 穷举全部选项的引擎回归测试
- `public/` 静态站点（vanilla JS，无 CDN）
- `public/assets/characters/` 三位主角的独立肖像
- `public/assets/endings/` 每个结局对应的独立象征画

## 说明

- 存档在浏览器 `localStorage`，无后端。
- 检定：`d20 + floor((属性-10)/2) >= DC`。
- 剧情 Markdown 是叙事源文件；解析器与补丁层共同生成浏览器直接运行的数据。
