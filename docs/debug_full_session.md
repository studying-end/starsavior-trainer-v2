20:32:46 INFO starsavior: 日志系统已初始化，日志目录: D:\starsavior-trainer-v2\logs
character_class=(unknown)
[调试模式] 每帧详细日志已启用（识别 payload + 决策 Action）
profile=pc-2560x1440-client-draft resolution=2560x1440 regions=371
mode=rapid execute=yes
character=(auto) build_profile=balanced
build=journey-visual-guard-20260520a
game window: starsavior-trainer-v2 迁移… - starsavior-trainer-v2 - Visual Studio Code (1936x1216)
20:32:47 INFO starsavior.pause: F11 暂停热键已启用。
F11 暂停热键已启用：实跑中按 F11 可暂停/恢复（夺回控制权）。

--- iteration 1 ---
20:32:49 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:32:49 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=None
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 3 项]
  [0] EventOption(text='对攻击有帮助的训练教材', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 训练的方向性')
  [1] EventOption(text='对生存有帮助的训练教材', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 训练的方向性')
  [2] EventOption(text='有助于应对各种状况的训练教材', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 训练的方向性')
20:32:49 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=798, width=660, height=92) reason=build balanced -> attack training: 对攻击有帮助的训练教材
20:32:49 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=798, width=660, height=92) | 理由: build balanced -> attack training: 对攻击有帮助的训练教材
  [debug 决策] click → Rect(1720,798,660,92) | build balanced -> attack training: 对攻击有帮助的训练教材
  screen_target=Rect(x=1720, y=798, width=660, height=92)
20:32:49 INFO starsavior.live_loop: executed: click point=(2050, 844) executed=True
20:32:49 INFO starsavior.behavior: [执行] click @ (2050, 844) (真点)

--- iteration 2 ---
20:32:51 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:32:51 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=None
  [debug 识别] 画面=event_choice  置信度=1.00
  (无 payload 解析)
20:32:51 INFO starsavior.live_loop: decision: pause target=None reason=event screen missing options
20:32:51 INFO starsavior.behavior: [决策] pause → None | 理由: event screen missing options
  [debug 决策] pause → None | event screen missing options
20:32:51 INFO starsavior.live_loop: executed: pause point=None executed=False
20:32:51 INFO starsavior.behavior: [执行] pause @ None (dry-run)

--- iteration 3 ---
20:32:52 INFO starsavior.live_loop: classified screen=reward confidence=1.00
20:32:52 INFO starsavior.behavior: [识别] 画面=reward 置信度=1.00
  current_round=None
  [debug 识别] 画面=reward  置信度=1.00
  (无 payload 解析)
20:32:52 INFO starsavior.live_loop: decision: click target=Rect(x=1180, y=1250, width=230, height=64) reason=reward obtained (获得奖励), click 点击以继续 to advance
20:32:52 INFO starsavior.behavior: [决策] click → Rect(x=1180, y=1250, width=230, height=64) | 理由: reward obtained (获得奖励), click 点击以继续 to advance
  [debug 决策] click → Rect(1180,1250,230,64) | reward obtained (获得奖励), click 点击以继续 to advance
  screen_target=Rect(x=1180, y=1250, width=230, height=64)
20:32:53 INFO starsavior.live_loop: executed: click point=(1295, 1282) executed=True
20:32:53 INFO starsavior.behavior: [执行] click @ (1295, 1282) (真点)

--- iteration 4 ---
20:32:54 INFO starsavior.live_loop: classified screen=unknown confidence=0.00
20:32:54 INFO starsavior.behavior: [识别] 画面=unknown 置信度=0.00
  unknown screen, click centre to advance (1)

--- iteration 5 ---
20:32:56 INFO starsavior.live_loop: classified screen=training_hub confidence=0.86
20:32:56 INFO starsavior.behavior: [识别] 画面=training_hub 置信度=0.86
20:32:56 INFO starsavior.screens.training: 训练大厅: 耐力 100%, 心情 NORMAL
  current_round=1
  [debug 识别] 画面=training_hub  置信度=0.86
  [画面] 训练大厅 TRAINING_HUB
  [HUD ] 耐力(endurance)=100%  心情(mood)=NORMAL  金币(coins)=30
  [告警] 受理讨伐委托=False  商店到货=False  可学技能=False  ✨闪光训练=False
  [回合] 日期='3月中旬'  RANK=None  潜质点=None
  [按钮] 训练=Rect(2230,545,250,95)  委托=Rect(2230,700,250,95)  休息=Rect(2230,858,250,95)  商店=None  技能=Rect(1710,1350,220,80)
20:32:56 INFO starsavior.live_loop: decision: click target=Rect(x=246, y=61, width=60, height=40) reason=hub: 点目标按钮读 N/45 校准回合数
20:32:56 INFO starsavior.behavior: [决策] click → Rect(x=246, y=61, width=60, height=40) | 理由: hub: 点目标按钮读 N/45 校准回合数
  [debug 决策] click → Rect(246,61,60,40) | hub: 点目标按钮读 N/45 校准回合数
  screen_target=Rect(x=246, y=61, width=60, height=40)
20:32:56 INFO starsavior.live_loop: executed: click point=(276, 81) executed=True
20:32:56 INFO starsavior.behavior: [执行] click @ (276, 81) (真点)

--- iteration 6 ---
20:32:57 INFO starsavior.live_loop: classified screen=goal_dialog confidence=1.00
20:32:57 INFO starsavior.behavior: [识别] 画面=goal_dialog 置信度=1.00
  [回合校准] 目标弹窗 N/45=2
  current_round=2
  [debug 识别] 画面=goal_dialog  置信度=1.00
  round = 2
  close_button = Rect(x=2005, y=313, width=42, height=41)
  title = '旅程信息'
20:32:57 INFO starsavior.live_loop: decision: click target=Rect(x=2005, y=313, width=42, height=41) reason=goal dialog (round=2), click ✕ to close
20:32:57 INFO starsavior.behavior: [决策] click → Rect(x=2005, y=313, width=42, height=41) | 理由: goal dialog (round=2), click ✕ to close
  [debug 决策] click → Rect(2005,313,42,41) | goal dialog (round=2), click ✕ to close
  screen_target=Rect(x=2005, y=313, width=42, height=41)
20:32:58 INFO starsavior.live_loop: executed: click point=(2026, 333) executed=True
20:32:58 INFO starsavior.behavior: [执行] click @ (2026, 333) (真点)

--- iteration 7 ---
20:32:59 INFO starsavior.live_loop: classified screen=training_hub confidence=0.86
20:32:59 INFO starsavior.behavior: [识别] 画面=training_hub 置信度=0.86
20:32:59 INFO starsavior.screens.training: 训练大厅: 耐力 100%, 心情 NORMAL
  current_round=2
  [debug 识别] 画面=training_hub  置信度=0.86
  [画面] 训练大厅 TRAINING_HUB
  [HUD ] 耐力(endurance)=100%  心情(mood)=NORMAL  金币(coins)=30
  [告警] 受理讨伐委托=False  商店到货=False  可学技能=False  ✨闪光训练=False
  [回合] 日期='3月中旬'  RANK=None  潜质点=None
  [按钮] 训练=Rect(2230,545,250,95)  委托=Rect(2230,700,250,95)  休息=Rect(2230,858,250,95)  商店=None  技能=Rect(1710,1350,220,80)
20:32:59 INFO starsavior.live_loop: decision: click target=Rect(x=2230, y=545, width=250, height=95) reason=training hub, enter training (普通训练)
20:32:59 INFO starsavior.behavior: [决策] click → Rect(x=2230, y=545, width=250, height=95) | 理由: training hub, enter training (普通训练)
  [debug 决策] click → Rect(2230,545,250,95) | training hub, enter training (普通训练)
  screen_target=Rect(x=2230, y=545, width=250, height=95)
20:32:59 INFO starsavior.live_loop: executed: click point=(2355, 592) executed=True
20:32:59 INFO starsavior.behavior: [执行] click @ (2355, 592) (真点)

--- iteration 8 ---
20:33:00 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:00 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=21  环(ring)=blue  失败率=2%  选中=True  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=8  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
  training_inspector_records={} pending=None
20:33:00 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=338, width=650, height=112) reason=early game inspect heads: power
20:33:00 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=338, width=650, height=112) | 理由: early game inspect heads: power
  [debug 决策] click → Rect(1750,338,650,112) | early game inspect heads: power
  screen_target=Rect(x=1750, y=338, width=650, height=112)
20:33:01 INFO starsavior.live_loop: executed: click point=(2075, 394) executed=True
20:33:01 INFO starsavior.behavior: [执行] click @ (2075, 394) (真点)

--- iteration 9 ---
20:33:02 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:02 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=21  环(ring)=blue  失败率=2%  选中=True  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=8  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:33:03 INFO starsavior.behavior: [训练检视] power 作数人头=0
  training_inspector_records={} pending=None
20:33:03 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=487, width=650, height=112) reason=early game inspect heads: stamina
20:33:03 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=487, width=650, height=112) | 理由: early game inspect heads: stamina
  [debug 决策] click → Rect(1750,487,650,112) | early game inspect heads: stamina
  screen_target=Rect(x=1750, y=487, width=650, height=112)
20:33:03 INFO starsavior.live_loop: executed: click point=(2075, 543) executed=True
20:33:03 INFO starsavior.behavior: [执行] click @ (2075, 543) (真点)

--- iteration 10 ---
20:33:05 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:05 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=25  环(ring)=none  失败率=2%  选中=True  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=6  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:33:06 INFO starsavior.behavior: [训练检视] stamina 作数人头=3
  training_inspector_records={} pending=None
20:33:06 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=635, width=650, height=112) reason=early game inspect heads: guts
20:33:06 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=635, width=650, height=112) | 理由: early game inspect heads: guts
  [debug 决策] click → Rect(1750,635,650,112) | early game inspect heads: guts
  screen_target=Rect(x=1750, y=635, width=650, height=112)
20:33:06 INFO starsavior.live_loop: executed: click point=(2075, 691) executed=True
20:33:06 INFO starsavior.behavior: [执行] click @ (2075, 691) (真点)

--- iteration 11 ---
20:33:07 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:07 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=11  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=7  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=17  环(ring)=blue  失败率=2%  选中=True  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=blue  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:33:08 INFO starsavior.behavior: [训练检视] guts 作数人头=0
  training_inspector_records={} pending=None
20:33:08 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=780, width=650, height=114) reason=early game inspect heads: wisdom
20:33:08 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=780, width=650, height=114) | 理由: early game inspect heads: wisdom
  [debug 决策] click → Rect(1750,780,650,114) | early game inspect heads: wisdom
  screen_target=Rect(x=1750, y=780, width=650, height=114)
20:33:09 INFO starsavior.live_loop: executed: click point=(2075, 837) executed=True
20:33:09 INFO starsavior.behavior: [执行] click @ (2075, 837) (真点)

--- iteration 12 ---
20:33:10 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:10 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=100%
  [卡] power: 训练值(gain)=4  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=11  环(ring)=gold  失败率=2%  选中=True  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:33:11 INFO starsavior.behavior: [训练检视] wisdom 作数人头=0
  training_inspector_records={} pending=None
20:33:11 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=929, width=650, height=112) reason=early game inspect heads: speed
20:33:11 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=929, width=650, height=112) | 理由: early game inspect heads: speed
  [debug 决策] click → Rect(1750,929,650,112) | early game inspect heads: speed
  screen_target=Rect(x=1750, y=929, width=650, height=112)
20:33:11 INFO starsavior.live_loop: executed: click point=(2075, 985) executed=True
20:33:11 INFO starsavior.behavior: [执行] click @ (2075, 985) (真点)

--- iteration 13 ---
20:33:12 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:12 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=100%
  [卡] power: 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=5  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: ✨闪光 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: ✨闪光 训练值(gain)=0  环(ring)=gold  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=15  环(ring)=gold  失败率=2%  选中=True  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
20:33:13 INFO starsavior.behavior: [训练检视] speed 作数人头=1
20:33:13 INFO starsavior.behavior: [训练决策] 早期游戏 选 stamina（作数人头 3 最多，攒支援卡羁绊）
  training_inspector_records={} pending=None
20:33:13 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=487, width=650, height=112) reason=early game choose stamina: heads=3
20:33:13 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=487, width=650, height=112) | 理由: early game choose stamina: heads=3
  [debug 决策] click → Rect(1750,487,650,112) | early game choose stamina: heads=3
  screen_target=Rect(x=1750, y=487, width=650, height=112)
20:33:14 INFO starsavior.live_loop: executed: click point=(2075, 543) executed=True
20:33:14 INFO starsavior.behavior: [执行] click @ (2075, 543) (真点)

--- iteration 14 ---
20:33:15 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:15 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=25  环(ring)=none  失败率=2%  选中=True  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=6  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
  training_inspector_records={} pending=None
20:33:15 INFO starsavior.live_loop: decision: click target=Rect(x=2080, y=1252, width=400, height=95) reason=early game confirm stamina
20:33:15 INFO starsavior.behavior: [决策] click → Rect(x=2080, y=1252, width=400, height=95) | 理由: early game confirm stamina
  [debug 决策] click → Rect(2080,1252,400,95) | early game confirm stamina
  screen_target=Rect(x=2080, y=1252, width=400, height=95)
20:33:16 INFO starsavior.live_loop: executed: click point=(2280, 1299) executed=True
20:33:16 INFO starsavior.behavior: [执行] click @ (2280, 1299) (真点)

--- iteration 15 ---
20:33:18 INFO starsavior.live_loop: classified screen=training_select confidence=0.90
20:33:18 INFO starsavior.behavior: [识别] 画面=training_select 置信度=0.90
  current_round=2
  [debug 识别] 画面=training_select  置信度=0.90
  [画面] 训练选择 TRAINING_SELECT  候选卡数=5  当前耐力=84%
  [卡] power: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,338,650,112)  确认=Rect(2080,1252,400,95)
  [卡] stamina: 训练值(gain)=1  环(ring)=none  失败率=2%  选中=True  目标=Rect(1750,487,650,112)  确认=Rect(2080,1252,400,95)
  [卡] guts: 训练值(gain)=9  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,635,650,112)  确认=Rect(2080,1252,400,95)
  [卡] wisdom: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,780,650,114)  确认=Rect(2080,1252,400,95)
  [卡] speed: 训练值(gain)=0  环(ring)=none  失败率=None%  选中=False  目标=Rect(1750,929,650,112)  确认=Rect(2080,1252,400,95)
  training_inspector_records={} pending=None
20:33:18 INFO starsavior.live_loop: decision: click target=Rect(x=1750, y=338, width=650, height=112) reason=early game inspect heads: power
20:33:18 INFO starsavior.behavior: [决策] click → Rect(x=1750, y=338, width=650, height=112) | 理由: early game inspect heads: power
  [debug 决策] click → Rect(1750,338,650,112) | early game inspect heads: power
  screen_target=Rect(x=1750, y=338, width=650, height=112)
20:33:18 INFO starsavior.live_loop: executed: click point=(2075, 394) executed=True
20:33:18 INFO starsavior.behavior: [执行] click @ (2075, 394) (真点)

--- iteration 16 ---
20:33:19 INFO starsavior.live_loop: classified screen=unknown confidence=0.00
20:33:19 INFO starsavior.behavior: [识别] 画面=unknown 置信度=0.00
  unknown screen, click centre to advance (1)

--- iteration 17 ---
20:33:22 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:22 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 3 项]
  [0] EventOption(text='今天到此为止！', target=Rect(x=1720, y=798, width=660, height=92), event_title='训练事件 训练失败')
  [1] EventOption(text='好，全部破坏掉吧，干脆一点！', target=Rect(x=1720, y=894, width=660, height=92), event_title='训练事件 训练失败')
  [2] EventOption(text='拿出活力药水。', target=Rect(x=1720, y=990, width=660, height=92), event_title='训练事件 训练失败')
20:33:22 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=798, width=660, height=92) reason=event db: 训练事件 训练失败 build=balanced -> option 1: 今天到此为止！
20:33:22 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=798, width=660, height=92) | 理由: event db: 训练事件 训练失败 build=balanced -> option 1: 今天到此为止！
  [debug 决策] click → Rect(1720,798,660,92) | event db: 训练事件 训练失败 build=balanced -> option 1: 今天到此为止！
  screen_target=Rect(x=1720, y=798, width=660, height=92)
20:33:22 INFO starsavior.live_loop: executed: click point=(2050, 844) executed=True
20:33:22 INFO starsavior.behavior: [执行] click @ (2050, 844) (真点)

--- iteration 18 ---
20:33:24 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:24 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  (无 payload 解析)
20:33:24 INFO starsavior.live_loop: decision: pause target=None reason=event screen missing options
20:33:24 INFO starsavior.behavior: [决策] pause → None | 理由: event screen missing options
  [debug 决策] pause → None | event screen missing options
20:33:24 INFO starsavior.live_loop: executed: pause point=None executed=False
20:33:24 INFO starsavior.behavior: [执行] pause @ None (dry-run)

--- iteration 19 ---
20:33:26 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:26 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  (无 payload 解析)
20:33:26 INFO starsavior.live_loop: decision: pause target=None reason=event screen missing options
20:33:26 INFO starsavior.behavior: [决策] pause → None | 理由: event screen missing options
  [debug 决策] pause → None | event screen missing options
20:33:26 INFO starsavior.live_loop: executed: pause point=None executed=False
20:33:26 INFO starsavior.behavior: [执行] pause @ None (dry-run)

--- iteration 20 ---
20:33:27 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:27 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧。', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:27 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:27 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:28 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:28 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 21 ---
20:33:29 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:29 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:29 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:29 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:29 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:29 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 22 ---
20:33:30 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:30 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:30 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:30 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:31 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:31 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 23 ---
20:33:32 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:32 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:32 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:32 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:32 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:32 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 24 ---
20:33:33 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:33 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:33 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:33 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:34 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:34 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 25 ---
20:33:35 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:35 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:35 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:35 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:35 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:35 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 26 ---
20:33:36 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:36 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:36 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:36 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:37 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:37 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 27 ---
20:33:38 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:38 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:38 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:38 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:38 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:38 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

--- iteration 28 ---
20:33:39 INFO starsavior.live_loop: classified screen=event_choice confidence=1.00
20:33:39 INFO starsavior.behavior: [识别] 画面=event_choice 置信度=1.00
  current_round=2
  [debug 识别] 画面=event_choice  置信度=1.00
  [列表 4 项]
  [0] EventOption(text='一起去吃限定甜点吧！ ?', target=Rect(x=1720, y=700, width=660, height=92), event_title='旅程事件 闲暇时间')
  [1] EventOption(text='一起去看新上映的电影吧！', target=Rect(x=1720, y=798, width=660, height=92), event_title='旅程事件 闲暇时间')
  [2] EventOption(text='我们去露营吧！', target=Rect(x=1720, y=894, width=660, height=92), event_title='旅程事件 闲暇时间')
  [3] EventOption(text='今天就这样好好休息吧', target=Rect(x=1720, y=990, width=660, height=92), event_title='旅程事件 闲暇时间')
20:33:39 INFO starsavior.live_loop: decision: click target=Rect(x=1720, y=700, width=660, height=92) reason=event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
20:33:39 INFO starsavior.behavior: [决策] click → Rect(x=1720, y=700, width=660, height=92) | 理由: event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  [debug 决策] click → Rect(1720,700,660,92) | event db: 旅程事件 闲暇时间 build=balanced -> option 1: 一起去吃限定甜点吧！ ?
  screen_target=Rect(x=1720, y=700, width=660, height=92)
20:33:40 INFO starsavior.live_loop: executed: click point=(2050, 746) executed=True
20:33:40 INFO starsavior.behavior: [执行] click @ (2050, 746) (真点)

[急停] 鼠标移到屏幕角落，已停止 bot，控制权交还。
