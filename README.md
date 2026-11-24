# 农贸市场摊位客流相关性

把澄湾农贸市场的摊位档案、时段客流、活动标签与招商复核串成一条可追溯流程。系统由 FastAPI + MySQL + Redis worker + 原生 HTML/CSS/JS 组成。

## 主要功能

- 摊位档案维护、区域与铺位利用率查看
- 客流采样录入，自动标记客流不足与促销标签冲突
- 活动归属更正，按摊位区域和采样时段核对活动，保留原始计数与复核记录
- Spearman 偏相关与 -2…+2 滞后相关矩阵
- 运营复核、招商简报草稿与管理员发出
- JWT 三角色、审计日志、请求限流

## 快速启动

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

前端地址 http://127.0.0.1:18241，后端地址 http://127.0.0.1:19241/docs。演示账号 `admin@demo.local`、`analyst@demo.local`、`viewer@demo.local`，密码统一为 `Demo123!`。

## 活动归属复核

用分析师账号进入「客流采样 → 活动归属复核」。演示数据中的西棚 B-12 样本挂了东棚活动。核对收银登记和摊主回执后，可提交更正为日常客流。若样本确实参加了活动，则须选择覆盖该摊位且包含该采样时刻的活动窗口。

用管理员账号填写复核意见并批准或退回。退回后，分析师可以补证并重新提交。批准会生成保留原计数的更正样本，后续默认分析采用这条记录。原始样本与复核记录可供追溯，已完成的分析继续引用原始样本 ID。观察员可查看更正记录及复核结果。

## 目录

- `backend/src/models/market.py` 领域实体
- `backend/src/services/analysis_engine.py` 统计算法
- `backend/src/routes/` 业务接口
- `frontend/src/main.js` 工作台与既有业务页面
- `frontend/src/attribution.js` 活动归属提交与复核页面
- `backend/scripts/seed_demo.py` 幂等演示数据

既有状态枚举见 `backend/src/constants/enums.py` 和前端 `frontend/src/main.js` 的 `statusText`。活动归属复核状态见 `backend/src/models/attribution.py` 和前端 `frontend/src/attribution.js`。收尾执行 `docker compose down -v --remove-orphans`。
