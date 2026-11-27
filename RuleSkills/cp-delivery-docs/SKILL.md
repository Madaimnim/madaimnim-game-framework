---
name: cp-delivery-docs
description: 瘋玩（CrazyPlay）共用技能：使用者要求成果摘要、改善紀錄或工作交付文件；不自動產報告。
metadata:
  category: "瘋玩"
---

# 瘋玩｜成果文件

這是「自訂 Skill／瘋玩（CrazyPlay）」共用技能，適用當前已接入瘋玩共同規範的專案。先確認本次實際工作區與 AGENTS／PROJECT_RULES，不以技能安裝位置判定遊戲，也不沿用另一案的參數。未接入專案先說明適用範圍，不因選中技能自動改其規範。

優先沿本案 AGENTS 的 Tools/RulesSkills.py。沒有本案讀取器時，依 CODEX_HOME（未設定時用使用者家目錄/.codex）下的 shared-rules.json 的 root（未配置用 CODEX_HOME/shared-rules；CODEX_HOME 未設定用使用者家目錄/.codex）定位同版 RulesSkills.py，以 --project-root <本案實際根> 執行 read delivery-docs。不能硬編 E1 或其他案的路徑。只有已明確啟用的專案使用 project-core／project-read；其他案仍完整讀自身規則。缺件／混版沿本案正式全文入口，不自動啟用按需模式。

透過上述本案或共用讀取器執行 read delivery-docs，完整讀取輸出的適用條款。內容從唯一 COMMON_RULES 正文擷取，不維護規範副本；同版本已讀內容不反覆載入。工具缺少或校驗不符就回到正式全文，不能略過要求。

已啟用按需模式者依任務透過 project-core 索引、project-read 讀本案相關條款；其他案讀自身完整規則。搬刪加 files、文字加 localization、畫面與驗證加 verification，依影響選擇，不整批讀全部模組。沿既有工具與授權執行；技能選中不授權 UI、安裝、進版、上傳或遊戲 Git 操作。
