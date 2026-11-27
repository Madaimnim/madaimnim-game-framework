---
name: cp-fmv-playback
description: 遊戲影片、H5/iOS 片頭、黑屏、卡頓及播放器生命週期的工程診斷。
---

# cp-fmv-playback

定位本案 AGENTS 指定的 Tools/RulesSkills.py，執行 read fmv-playback，完整讀取輸出的適用條款。內容從唯一 COMMON_RULES 正文擷取，不維護規範副本；同版本已讀內容不反覆載入。工具缺少或校驗不符就回到正式全文，不能略過要求。

依任務透過 project-core 索引、project-read 讀本案相關條款。搬刪加 files、文字加 localization、畫面與驗證加 verification，依影響選擇，不整批讀全部模組。沿既有工具與授權執行；技能選中不授權 UI、安裝、進版、上傳或遊戲 Git 操作。

使用本案真實播放器與 H5 作者來源，不套他案結論。只有 Android AVPro 任務另執行 read build-release --heading "AVPro Android 渲染與打包檢查"；診斷 iOS 不讀整套 Android 建置。
