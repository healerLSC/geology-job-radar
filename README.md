# 地质招聘雷达

面向 **2027 届地质学硕士（非地质工程方向）** 的公开招聘监控网站。项目不依赖 ChatGPT 登录、订阅或付费 API，由 GitHub Actions 每天自动核查公开来源，并通过 GitHub Pages 提供可直接访问的静态网站。

## 监控原则

- 名册内 349 个集团、子公司、矿区、研究院、技术中心、地勘和工程单位全部保留监控。
- 集团统一校招与二、三级单位单独公告分别核查；集团岗位表会继续识别实际用人单位。
- 只有面向 2027 届校园招聘、提前批、统一招聘、补录、实习转正等信息才进入候选。
- 以公告专业原文为准，区分“地质学”和“地质工程、资源勘查工程、勘查技术与工程、物探、采矿工程”。
- 来源失败时保留上一次核实结果并标注异常，避免把抓取失败误判为岗位下线。
- 官方信息、权威平台和非官方线索分级保存，重复公告合并。

## 自动运行

`.github/workflows/monitor.yml` 每天北京时间 19:00 左右运行：

1. 校验单位和来源名册；
2. 抓取公开可访问的招聘网页与 PDF、Word、Excel 附件；
3. 识别招聘届别、专业要求、截止时间和实际用人单位；
4. 合并重复公告，将已截止岗位移入历史记录；
5. 更新 `data/radar.json` 和来源状态；
6. 提交变化并触发 GitHub Pages 重新部署。

GitHub 定时任务可能因平台排队而延迟几分钟。需要立即核查时，可在 Actions 页面手动运行 **Monitor Radar**。

## 本地验证

需要 Node.js 22 和 Python 3.12：

```bash
npm ci
python -m pip install -r monitor/requirements.txt
PYTHONPATH=. python -m pytest monitor/tests -q
npm test
npm run lint
```

本地启动：

```bash
npm run dev
```

手动执行公开来源监控：

```bash
python -m monitor.run
```

## 数据与限制

- `monitor/units.json`：独立监控单位名册。
- `monitor/sources.json`：公开招聘来源及其信任级别。
- `data/radar.json`：网站读取的岗位、历史记录、覆盖统计和来源健康数据。
- `monitor/state.json`：用于识别页面内容变化的指纹状态。

完全依赖登录、验证码、小程序或不可公开检索的微信公众号内容会显示为受限来源；网站不会把无法验证的线索伪装成官方结论。报名资格、专业目录和截止时间最终以招聘单位官方公告为准。
