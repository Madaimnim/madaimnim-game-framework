---
name: cp-localization
description: 玩家文字、翻譯、TMP、缺字、字型及 Localization Table。
---

# cp-localization

定位本案 AGENTS 指定的 Tools/RulesSkills.py，執行 read localization，完整讀取輸出的適用條款。內容從唯一 COMMON_RULES 正文擷取，不維護規範副本；同版本已讀內容不反覆載入。工具缺少或校驗不符就回到正式全文，不能略過要求。

依任務透過 project-core 索引、project-read 讀本案相關條款。搬刪加 files、文字加 localization、畫面與驗證加 verification，依影響選擇，不整批讀全部模組。沿既有工具與授權執行；技能選中不授權 UI、安裝、進版、上傳或遊戲 Git 操作。
