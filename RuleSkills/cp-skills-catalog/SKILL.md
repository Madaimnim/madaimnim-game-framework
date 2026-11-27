---
name: cp-skills-catalog
description: 瘋玩（CrazyPlay）共用技能：詢問有哪些 Skill、可用哪些技能、某類任務可選項或本次讀過哪些 Skill。
metadata:
  category: "瘋玩"
---

# 瘋玩｜技能目錄

這是「自訂 Skill／瘋玩（CrazyPlay）」共用技能，適用當前已接入瘋玩共同規範的專案。先確認本次實際工作區與 AGENTS／PROJECT_RULES，不以技能安裝位置判定遊戲，也不沿用另一案的參數。未接入專案先說明適用範圍，不因選中技能自動改其規範。

優先沿本案 AGENTS 的 Tools/RulesSkills.py。沒有本案讀取器時，依 CODEX_HOME（未設定時用使用者家目錄/.codex）下的 shared-rules.json 的 root（未配置用 CODEX_HOME/shared-rules；CODEX_HOME 未設定用使用者家目錄/.codex）定位同版 RulesSkills.py，以 --project-root <本案實際根> 執行 list。不能硬編 E1 或其他案的路徑。只有已明確啟用的專案使用 project-core／project-read；其他案仍完整讀自身規則。缺件／混版沿本案正式全文入口，不自動啟用按需模式。

先以本次 available skills 清單列實際可用技能，再透過上述本案或共用讀取器執行 list 核對瘋玩共用技能目錄；使用者層實際安裝另核對 CODEX_HOME/crazyplay-skills-installed.json。只顯示名稱、用途、情境與來源，不開全部 SKILL.md。已安裝但本次清單未列入者，明示需新對話確認，不能說已在本次載入。回報本次讀過哪些技能以真實讀取紀錄為準。指定類別只列相關項目，不執行它們。

列目錄時將本組歸為「自訂 Skill → 瘋玩（CrazyPlay）」，其他內建／插件技能另列；這是共同分類名稱，不宣稱介面支援自訂子分類。以本次可用清單為準，不替其他對話宣稱已刷新。
