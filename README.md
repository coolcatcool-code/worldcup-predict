# 世界杯2026 概率预测站

每日自动更新的世界杯胜平负概率与比分预测，三方对照：Fable 5 独立预测 / Opta超级计算机模型 / 博彩市场综合赔率，并对历史预测做命中率与Brier评分回顾。

- `data/predictions/YYYY-MM-DD.json` — 每日预测（18:00生成）
- `data/reviews/YYYY-MM-DD.json` — 赛果回顾（次日13:00生成）
- `data/stats.json` — 累计统计与Brier曲线数据
- `data/index.json` — 日期索引

回顾JSON结构示例：

```json
{
  "date": "2026-06-12",
  "matches": [
    {
      "id": "2026-06-12-CAN-BIH",
      "actualScore": "1-0",
      "outcome": "home",
      "fable5": { "outcomeHit": true, "scoreHit": true, "brier": 0.387 },
      "opta":   { "outcomeHit": true, "brier": 0.351 },
      "market": { "outcomeHit": true, "brier": 0.362 }
    }
  ]
}
```

Brier口径：Σ(预测概率−实际)²，三结果向量，越低越好。

> 本仓库内容为数据分析展示，仅供参考，不构成投注建议。
