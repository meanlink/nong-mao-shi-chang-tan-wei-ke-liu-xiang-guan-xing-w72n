# 农贸市场摊位客流相关性

把澄湾农贸市场的摊位档案、时段客流、活动标签与招商复核串成一条可追溯流程。系统由 FastAPI + MySQL + Redis worker + 原生 HTML/CSS/JS 组成。

## 主要功能

- 摊位档案维护、区域与铺位利用率查看
- 客流采样录入，自动标记客流不足与促销标签冲突
- 补采认领：按摊位和时段认领，共用管理员设定的当日名额，并发不超额、同摊位时段仅一张待补单
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

## 补采认领

早市巡场人手有限，补采按「摊位 + 日期 + 时段」在「补采认领」页认领，全员共用管理员当日设定的名额。

- 管理员在补采认领页设定某日名额，系统按固定座位池管理；并发认领由数据库条件更新原子占位，绝不超额。同一摊位同一时段只保留一张待补或已核销单据（部分唯一索引兜底），重复认领返回 409。
- 在「客流采样」页补录样本时选择对应待补单。样本的摊位、日期、时段与认领单一致且为有效样本时才核销；异常样本（时段不足、标签冲突等）只留档，单据保持待补。
- 撤销只允许未核销单据，立即退回名额；已核销单据不能撤销、名额不退。撤销后补交的迟到样本照样留档，不会抵扣后来新建的认领单。
- 补录携带 `submission_key` 幂等键，同次补录重试返回原样本，不重复核销；前端自动生成该键。
- 页面可查当日余量（总量/已占用/剩余）与每张单据状态（待补采/已核销/已撤销）。

## 目录

- `backend/src/models/market.py` 领域实体
- `backend/src/models/resampling.py` 补采名额、认领单与名额座位池
- `backend/src/services/resampling.py` 名额原子占位、认领、核销与撤销规则
- `backend/src/services/analysis_engine.py` 统计算法
- `backend/src/routes/` 业务接口
- `frontend/src/main.js` 工作台与既有业务页面
- `frontend/src/resampling.js` 补采认领与当日余量页面
- `frontend/src/attribution.js` 活动归属提交与复核页面
- `backend/scripts/seed_demo.py` 幂等演示数据

既有状态枚举见 `backend/src/constants/enums.py` 和前端 `frontend/src/main.js` 的 `statusText`。活动归属复核状态见 `backend/src/models/attribution.py` 和前端 `frontend/src/attribution.js`。收尾执行 `docker compose down -v --remove-orphans`。
