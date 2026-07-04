20:04:09 INFO starsavior: 日志系统已初始化，日志目录: D:\starsavior-trainer-v2\logs
character_class=(unknown)
[调试模式] 每帧详细日志已启用（识别 payload + 决策 Action）
profile=pc-2560x1440-client-draft resolution=2560x1440 regions=371
mode=rapid execute=yes
character=(auto) build_profile=balanced
build=journey-visual-guard-20260520a
game window: starsavior-trainer-v2 迁移… - starsavior-trainer-v2 - Visual Studio Code (1936x1216)
20:04:10 INFO starsavior.pause: F11 暂停热键已启用。
F11 暂停热键已启用：实跑中按 F11 可暂停/恢复（夺回控制权）。

--- iteration 1 ---
20:04:11 INFO starsavior.live_loop: classified screen=training_hub confidence=0.86
20:04:11 INFO starsavior.behavior: [识别] 画面=training_hub 置信度=0.86
20:04:11 INFO starsavior.screens.training: 训练大厅: 耐力 100%, 心情 NORMAL
  current_round=1
  [debug 识别] 画面=training_hub  置信度=0.86
  [画面] 训练大厅 TRAINING_HUB
  [HUD ] 耐力(endurance)=100%  心情(mood)=NORMAL  金币(coins)=30
  [告警] 受理讨伐委托=False  商店到货=False  可学技能=False  ✨闪光训练=False
  [回合] 日期='3月上旬'  RANK=None  潜质点=None
  [按钮] 训练=Rect(2230,545,250,95)  委托=Rect(2230,700,250,95)  休息=Rect(2230,858,250,95)  商店=None  技能=Rect(1710,1350,220,80)
20:04:11 INFO starsavior.live_loop: decision: click target=Rect(x=246, y=61, width=60, height=40) reason=hub: 点目标按钮读 N/45 校准回合数
20:04:11 INFO starsavior.behavior: [决策] click → Rect(x=246, y=61, width=60, height=40) | 理由: hub: 点目标按钮读 N/45 校准回合数
  [debug 决策] click → Rect(246,61,60,40) | hub: 点目标按钮读 N/45 校准回合数
  screen_target=Rect(x=246, y=61, width=60, height=40)
20:04:11 INFO starsavior.live_loop: executed: click point=(276, 81) executed=True
20:04:11 INFO starsavior.behavior: [执行] click @ (276, 81) (真点)

--- iteration 2 ---
20:04:12 INFO starsavior.live_loop: classified screen=goal_dialog confidence=1.00
20:04:12 INFO starsavior.behavior: [识别] 画面=goal_dialog 置信度=1.00
  [回合校准] 目标弹窗 N/45=1
  current_round=1
  [debug 识别] 画面=goal_dialog  置信度=1.00
  round = 1
  close_button = Rect(x=2005, y=313, width=42, height=41)
  title = '旅程信息'
20:04:12 INFO starsavior.live_loop: decision: click target=Rect(x=2005, y=313, width=42, height=41) reason=goal dialog (round=1), click ✕ to close
20:04:12 INFO starsavior.behavior: [决策] click → Rect(x=2005, y=313, width=42, height=41) | 理由: goal dialog (round=1), click ✕ to close
  [debug 决策] click → Rect(2005,313,42,41) | goal dialog (round=1), click ✕ to close
  screen_target=Rect(x=2005, y=313, width=42, height=41)
20:04:13 INFO starsavior.live_loop: executed: click point=(2026, 333) executed=True
20:04:13 INFO starsavior.behavior: [执行] click @ (2026, 333) (真点)

--- iteration 3 ---
20:04:14 INFO starsavior.live_loop: classified screen=training_hub confidence=0.86
20:04:14 INFO starsavior.behavior: [识别] 画面=training_hub 置信度=0.86
20:04:14 INFO starsavior.screens.training: 训练大厅: 耐力 100%, 心情 NORMAL
  current_round=1
  [debug 识别] 画面=training_hub  置信度=0.86
  [画面] 训练大厅 TRAINING_HUB
  [HUD ] 耐力(endurance)=100%  心情(mood)=NORMAL  金币(coins)=30
  [告警] 受理讨伐委托=False  商店到货=False  可学技能=False  ✨闪光训练=False
  [回合] 日期='3月上旬'  RANK=None  潜质点=None
  [按钮] 训练=Rect(2230,545,250,95)  委托=Rect(2230,700,250,95)  休息=Rect(2230,858,250,95)  商店=None  技能=Rect(1710,1350,220,80)
20:04:14 INFO starsavior.live_loop: decision: click target=Rect(x=2230, y=545, width=250, height=95) reason=training hub, enter training (普通训练)
20:04:14 INFO starsavior.behavior: [决策] click → Rect(x=2230, y=545, width=250, height=95) | 理由: training hub, enter training (普通训练)
  [debug 决策] click → Rect(2230,545,250,95) | training hub, enter training (普通训练)
  screen_target=Rect(x=2230, y=545, width=250, height=95)
20:04:14 INFO starsavior.live_loop: executed: click point=(2355, 592) executed=True
20:04:14 INFO starsavior.behavior: [执行] click @ (2355, 592) (真点)

--- iteration 4 ---
20:04:15 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:15 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=16  环(ring)=blue  失败率=0%  选中=True  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=7  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
  training_inspector_records={} pending=None
20:04:15 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=338, width=650, height=112) reason=early game inspect heads: power
20:04:15 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=338, width=650, height=112) | 理由: early game inspect heads: power
  [debug 决策] click → Rect(1750,338,650,112) | early game inspect heads: power
  screen_target=Rect(x=1750, y=338, width=650, height=112)
20:04:16 INFO starsavior.live_loop: executed: click point=(2075, 394) executed=True
20:04:16 INFO starsavior.behavior: [执行] click @ (2075, 394) (真点)

--- iteration 5 ---
20:04:17 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:17 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=16  环(ring)=blue  失败率=0%  选中=True  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=7  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:04:18 INFO starsavior.behavior: [训练检视] power 作数人头=0
  training_inspector_records={} pending=None
20:04:18 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=487, width=650, height=112) reason=early game inspect heads: stamina
20:04:18 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=487, width=650, height=112) | 理由: early game inspect heads: stamina
  [debug 决策] click → Rect(1750,487,650,112) | early game inspect heads: stamina
  screen_target=Rect(x=1750, y=487, width=650, height=112)
20:04:18 INFO starsavior.live_loop: executed: click point=(2075, 543) executed=True
20:04:18 INFO starsavior.behavior: [执行] click @ (2075, 543) (真点)

--- iteration 6 ---
20:04:20 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:20 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=22  环(ring)=none  失败率=0%  选中=True  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=8  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:04:21 INFO starsavior.behavior: [训练检视] stamina 作数人头=0
  training_inspector_records={} pending=None
20:04:21 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=635, width=650, height=112) reason=early game inspect heads: guts
20:04:21 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=635, width=650, height=112) | 理由: early game inspect heads: guts
  [debug 决策] click → Rect(1750,635,650,112) | early game inspect heads: guts
  screen_target=Rect(x=1750, y=635, width=650, height=112)
20:04:21 INFO starsavior.live_loop: executed: click point=(2075, 691) executed=True
20:04:21 INFO starsavior.behavior: [执行] click @ (2075, 691) (真点)

--- iteration 7 ---
20:04:23 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:23 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=6  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=6  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=13  环(ring)=blue  失败率=0%  选中=True  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:04:23 INFO starsavior.behavior: [训练检视] guts 作数人头=0
  training_inspector_records={} pending=None
20:04:23 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=780, width=650, height=114) reason=early game inspect heads: wisdom
20:04:23 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=780, width=650, height=114) | 理由: early game inspect heads: wisdom
  [debug 决策] click → Rect(1750,780,650,114) | early game inspect heads: wisdom
  screen_target=Rect(x=1750, y=780, width=650, height=114)
20:04:24 INFO starsavior.live_loop: executed: click point=(2075, 837) executed=True
20:04:24 INFO starsavior.behavior: [执行] click @ (2075, 837) (真点)

--- iteration 8 ---
20:04:25 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:25 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=100%
  [卡] power: 训练值(gain)=13  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=18  环(ring)=gold  失败率=0%  选中=True  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:04:26 INFO starsavior.behavior: [训练检视] wisdom 作数人头=2
  training_inspector_records={} pending=None
20:04:26 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=929, width=650, height=112) reason=early game inspect heads: speed
20:04:26 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=929, width=650, height=112) | 理由: early game inspect heads: speed
  [debug 决策] click → Rect(1750,929,650,112) | early game inspect heads: speed
  screen_target=Rect(x=1750, y=929, width=650, height=112)
20:04:26 INFO starsavior.live_loop: executed: click point=(2075, 985) executed=True
20:04:26 INFO starsavior.behavior: [执行] click @ (2075, 985) (真点)

--- iteration 9 ---
20:04:28 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:28 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=100%
  [卡] power: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=4  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: ✨闪光 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: ✨闪光 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=11  环(ring)=gold  失败率=0%  选中=True  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:04:29 INFO starsavior.behavior: [训练检视] speed 作数人头=0
20:04:29 INFO starsavior.behavior: [训练决策] 早期游戏 选 wisdom（作数人头 2 最多，攒支援卡羁绊）
  training_inspector_records={} pending=None
20:04:29 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=780, width=650, height=114) reason=early game choose wisdom: heads=2
20:04:29 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=780, width=650, height=114) | 理由: early game choose wisdom: heads=2
  [debug 决策] click → Rect(1750,780,650,114) | early game choose wisdom: heads=2
  screen_target=Rect(x=1750, y=780, width=650, height=114)
20:04:29 INFO starsavior.live_loop: executed: click point=(2075, 837) executed=True
20:04:29 INFO starsavior.behavior: [执行] click @ (2075, 837) (真点)

--- iteration 10 ---
20:04:30 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:30 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=100%
  [卡] power: 训练值(gain)=13  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=18  环(ring)=gold  失败率=0%  选中=True  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
  training_inspector_records={} pending=None
20:04:30 INFO starsavior.live_loop: decision: click target=Rect(x=2080, y=1252, width=400, height=95) reason=early game confirm wisdom
20:04:30 INFO starsavior.behavior: [决策] click → Rect(x=2080, y=1252, width=400, height=95) | 理由: early game confirm wisdom
  [debug 决策] click → Rect(2080,1252,400,95) | early game confirm wisdom
  screen_target=Rect(x=2080, y=1252, width=400, height=95)
20:04:31 INFO starsavior.live_loop: executed: click point=(2280, 1299) executed=True
20:04:31 INFO starsavior.behavior: [执行] click @ (2280, 1299) (真点)

--- iteration 11 ---
20:04:34 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:04:34 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=1
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=100%
  [卡] power: 训练值(gain)=13  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: ✨闪光 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: ✨闪光 训练值(gain)=18  环(ring)=gold  失败率=0%  选中=True  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: ✨闪光 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
  training_inspector_records={} pending=None
20:04:34 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=338, width=650, height=112) reason=early game inspect heads: power
20:04:34 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=338, width=650, height=112) | 理由: early game inspect heads: power
  [debug 决策] click → Rect(1750,338,650,112) | early game inspect heads: power
  screen_target=Rect(x=1750, y=338, width=650, height=112)
20:04:34 INFO starsavior.live_loop: executed: click point=(2075, 394) executed=True
20:04:34 INFO starsavior.behavior: [执行] click @ (2075, 394) (真点)

--- iteration 12 ---
20:04:36 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:04:36 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=1
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 2 项]
  [0] EventOption(text='还是老实认错反省吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='阿尔克那事件 文书工作总是晴转阴')
  [1] EventOption(text='既然这样，也只能试着装可怜蒙混 过去了!', target=Rect(x=1720, y=990, width=660, height=92), event_title='阿尔克那事件 文书工作总是晴转阴')
20:04:36 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=894, width=660, height=92) reason=unknown option: 还是老实认错反省吧！
20:04:36 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=894, width=660, height=92) | 理由: unknown option: 还是老实认错反省吧！
  [debug 决策] click → Rect(1720,894,660,92) | unknown option: 还是老实认错反省吧！
  screen_target=Rect(x=1720, y=894, width=660, height=92)
20:04:36 INFO starsavior.live_loop: executed: click point=(2050, 940) executed=True
20:04:36 INFO starsavior.behavior: [执行] click @ (2050, 940) (真点)

--- iteration 13 ---
20:04:39 INFO starsavior.live_loop: classified screen=dialogue confidence=1.00
20:04:39 INFO starsavior.behavior: [识别] 画面=dialogue 置信度=1.00
  current_round=1
  [debug 识别] 画面=dialogue  置信度=1.00
  skip_button = Rect(x=1180, y=660, width=200, height=120)
  variant = 'arcana_center'
  text_area = None
20:04:39 INFO starsavior.live_loop: decision: click target=Rect(x=1180, y=660, width=200, height=120) reason=dialogue arcana_center, click skip
20:04:39 INFO starsavior.behavior: [决策] click → Rect(x=1180, y=660, width=200, height=120) | 理由: dialogue arcana_center, click skip
  [debug 决策] click → Rect(1180,660,200,120) ×3 | dialogue arcana_center, click skip
  screen_target=Rect(x=1180, y=660, width=200, height=120)
20:04:40 INFO starsavior.live_loop: executed: click point=(1280, 720) executed=True
20:04:40 INFO starsavior.behavior: [执行] click @ (1280, 720) (真点)

--- iteration 14 ---
20:04:42 INFO starsavior.live_loop: classified screen=dialogue confidence=1.00
20:04:42 INFO starsavior.behavior: [识别] 画面=dialogue 置信度=1.00
  current_round=1
  [debug 识别] 画面=dialogue  置信度=1.00
  skip_button = Rect(x=1180, y=660, width=200, height=120)
  variant = 'arcana_center'
  text_area = None
20:04:42 INFO starsavior.live_loop: decision: click target=Rect(x=1180, y=660, width=200, height=120) reason=dialogue arcana_center, click skip
20:04:42 INFO starsavior.behavior: [决策] click → Rect(x=1180, y=660, width=200, height=120) | 理由: dialogue arcana_center, click skip
  [debug 决策] click → Rect(1180,660,200,120) ×3 | dialogue arcana_center, click skip
  screen_target=Rect(x=1180, y=660, width=200, height=120)
20:04:43 INFO starsavior.live_loop: executed: click point=(1280, 720) executed=True
20:04:43 INFO starsavior.behavior: [执行] click @ (1280, 720) (真点)

--- iteration 15 ---
20:04:45 INFO starsavior.live_loop: classified screen=dialogue confidence=1.00
20:04:45 INFO starsavior.behavior: [识别] 画面=dialogue 置信度=1.00
  current_round=1
  [debug 识别] 画面=dialogue  置信度=1.00
  skip_button = Rect(x=1855, y=54, width=78, height=65)
  variant = 'journey_hud'
  text_area = Rect(x=640, y=1160, width=1280, height=170)
20:04:45 INFO starsavior.live_loop: decision: click target=Rect(x=1855, y=54, width=78, height=65) reason=dialogue journey_hud, click skip
20:04:45 INFO starsavior.behavior: [决策] click → Rect(x=1855, y=54, width=78, height=65) | 理由: dialogue journey_hud, click skip
  [debug 决策] click → Rect(1855,54,78,65) ×3 | dialogue journey_hud, click skip
  screen_target=Rect(x=1855, y=54, width=78, height=65)
20:04:46 INFO starsavior.live_loop: executed: click point=(1894, 86) executed=True
20:04:46 INFO starsavior.behavior: [执行] click @ (1894, 86) (真点)
