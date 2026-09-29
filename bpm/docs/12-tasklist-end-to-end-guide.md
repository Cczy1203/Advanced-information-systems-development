# 36 个表单在 Tasklist 上连贯跑通（人工点界面版）

> 适用：Camunda 8 c8run（localhost:8080），医院转诊预约系统 v14（9 个池 + 36 个表单）。
> 本文的目标形态：**人坐在 Tasklist 界面上，一个接一个把 36 个表单填完**，脚本只负责派活、等待、记账。

---

## 1. 两种跑法先分清

| 跑法 | 命令 | 谁填表单 | 用途 |
| --- | --- | --- | --- |
| 全自动 | `python3 auto_driver.py --all` | 脚本调 API 代填 | 回归验证、快速证明 36/36 |
| **界面人工** | `python3 auto_driver.py --all --manual-forms` | **你在 Tasklist 里手点** | 演示 / 答辩 / 截图取证 |

`--manual-forms` 的行为：脚本**绝不**调用 completion 接口，只把待办"播报"出来，谁在界面上完成，脚本就把它记入覆盖清单；跑满 timeout 还没人做，就记为 missing 并继续下一个场景。

---

## 2. 前置检查（30 秒）

```bash
# 1) 引擎活着（应返回 gatewayVersion 8.10.0-alpha5）
curl -s http://localhost:8080/v2/topology | head -c 120

# 2) Java worker 只留一个副本（多开会互相抢 job，日志难读）
ps aux | grep hospital-external-workers | grep -v grep

# 3) 打开面板
open http://localhost:8080/tasklist
```

- worker 建议：`cd ~/Desktop/v13.1/workers && java -jar target/hospital-external-workers-1.0.0.jar`
- 引擎与 worker 的终端窗口**全程不要关**；关掉 worker，service task 会停在原地，表单就永远不出现。

---

## 3. 一条命令开跑

```bash
cd ~/Desktop/v13.1/tools
python3 auto_driver.py --all --manual-forms --timeout 600 --report driver_report_manual.json
```

- `--timeout 600`：每个场景最多等你 10 分钟（默认；可用 `--timeout` 调小）。
- 启动后会打印：

```
MANUAL MODE: user tasks stay open. Finish them in Camunda Tasklist
== SEC-pack  (medical-secretaries)
  >> Tasklist task: Check referral pack against the document checklist form=check-referral-pack pool=medical-secretaries
  form DONE check-referral-pack                        (Tasklist)
  -> PASS  gained=['check-referral-pack'] missing=[]
```

- `>>` 开头 = **当前场景正等的那个表单**，优先做它；没有 `>>` 的待办是别的池顺路挂出来的，之后也会轮到。
- `form DONE` = 你已经点完，脚本已记账。
- 只要 `gained` 覆盖完该场景的 `forms`，脚本立刻推进下一个场景，**不浪费你剩下的等待时间**。

## 4. 界面上的标准动作

Tasklist 里对每个任务都走同一套：

1. 顶部筛选 **Assigned to me / Unassigned**，状态选 **Created**；
2. 打开任务 → 右上角 **Assign to me** → 按表单字段填；
3. 点 **Complete** → 界面自动跳/刷新，下一个待办出现；
4. 回到终端确认那行 `form DONE ...` 已经打出来（没打出来说明你刚点的是别的池的任务，正常，继续做 `>>` 那个）。

> 表单字段没有标准答案也不用怕：driver 会把业务变量铺好（患者引用、金额、优先级等），界面里多数字段已有可选项，按语义选一个合理值即可。

## 5. 跑完怎么算成功

终端结尾：

```
--- coverage ---
forms covered: 36 / 36
```

`36 / 36` 且没有 `missing forms` 一行，就是 36 个表单全部在界面上被真实走完。报告的 JSON 里还逐条记录了每个表单对应的任务名、池、流程实例 key、完成时刻，可直接贴进测试证据文档（`docs/09` / `docs/10`）。

---

## 6. 常见状况

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 终端只打印 `started(...)`，界面迟迟不出现任务 | Java worker 没跑，或 worker 副本被关了 | 重启 worker，保持 1 个副本 |
| 某场景等满 timeout，`missing=[...]` | 你在界面漏点了那个表单 | 重跑该场景：`--scenario <场景id> --manual-forms`；场景 id 见 `--list` |
| Tasklist 里待办越积越多 | 前面测试留下的旧实例仍在 ACTIVE | Operate 里按实例 key 取消，或见下方清理命令 |
| Operate 里实例标红 incident | service task 抛错（多为 worker 版本不匹配） | 打开 incident 看错误栈，修完在 Operate 里 Retry |
| 同一表单出现两个同名待办 | 重复发布 start 消息留下多实例 | 见 `--list` 后只跑需要的场景；清理多余实例 |

清理多余实例（**先看清 key 再执行**，取消后无法恢复）：

```bash
curl -s -X POST http://localhost:8080/v2/process-instances/search \
  -H 'Content-Type: application/json' \
  -d '{"filter":{"state":"ACTIVE"},"page":{"limit":20}}' | python3 -m json.tool | grep processInstanceKey

# 确认某个 key 确实是要扔掉的那个之后再执行：
# curl -X POST http://localhost:8080/v2/process-instances/<key>/cancellation
```

## 7. 为什么是"连贯"的

- 9 个池各自独立起实例，池与池之间靠**消息接力**（上游投递 → 下游 message start / 中间捕获事件），不是一条大流程。
- 因此"连贯"分两层：
  - **数据层**：driver 的 `replay_messages` 一直把接力消息补齐，下游池该起的实例都会起；
  - **界面层**：所有池的待办都汇到同一个 Tasklist 列表，你按顺序点完就是 36/36。
- 单个池走完自己的 `end event` 就结束（例如 `outpatient-bookings` 结束不发消息），所以 Operate 里看到某个实例"跑完就没了"是正常的，不代表链条断了。
*（内容由AI生成，仅供参考）*
