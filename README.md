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
- `tools/wzc_phase3_pass.py` 生成城市双主角深谈、矿区同行/救援、结局状态变体
- `tools/audit-rewards.py` 核对剧情承诺与实际奖励
- `tools/test-all-choices.js` 穷举全部选项的引擎回归测试
- `public/` 静态站点（vanilla JS，无 CDN）
- `public/assets/characters/` 三位主角的独立肖像
- `public/assets/endings/` 每个结局对应的独立象征画

目前是可玩的持续修订版。完整剧本 Markdown 约 9.3 万汉字；“数十万字”的文本目标尚未完成。自动测试覆盖选项执行与状态回归，尚需按角色进行浏览器人工通关和剧情润色。

## 说明

- 存档在浏览器 `localStorage`，无后端。
- 检定：`d20 + floor((属性-10)/2) >= DC`。
- 剧情 Markdown 是叙事源文件；解析器与补丁层共同生成浏览器直接运行的数据。

## 情欲折叠块（fold）

露骨描写默认折叠。节点里使用结构化块（由 `tools/wzc_patches.py` 的 `FOLD()` 写入）：

```json
{"t":"fold","label":"情欲描写","blocks":[{"t":"p","text":"……"}]}
```

界面渲染为「▸ 情欲描写」，点击展开；主叙述保持可读的淡写。可选 `cond` 与普通块相同。

