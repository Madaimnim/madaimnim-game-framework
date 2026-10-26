# madaimnim game framework

跨專案共用規範及同步工具。遊戲專用設定、帳密與成果文件留在各自專案。

## 美術生成與組裝

統一規則位於 [COMMON_RULES.md「美術生成與組裝」](COMMON_RULES.md#美術生成與組裝)，涵蓋參考分析、生成素材、裝飾與留白、組裝重用、實際驗收與AI感修正；不限特定專案或畫風。各專案沿用同一RulesSource與更新器即可讀到，不另複製一份永久規則。

要讓尚無專案規範的新任務也套用，須在該執行環境的Codex使用者層級AGENTS.md配置本節核心要求及本來源。可將本節以有版本標記的區塊同步至全域入口；正式維護來源仍只有本儲存庫。新機／不同CODEX_HOME／雲端須另外配置，不能只上傳GitHub就宣稱所有環境生效。專案初始化時再接入RulesSource／RulesMaintenance與既有Tools/UpdateRules.py，不覆蓋專案專用內容。
## 維護共用內容

先讀 [AGENTS.md](AGENTS.md) 及 [COMMON_RULES.md](COMMON_RULES.md)。使用者明確要求維護共用規範時，依入口完成比對、測試、提交、推送、Release 與回讀驗證；一般專案下載不觸發發布。

- 主分支：維護來源。
- GitHub Release：各專案正式下載來源。
- `.github/workflows/publish-rules.yml`：主分支規範／工具變更後，自動測試及發布不可覆寫的版本化 Release。
- 只推送不等於完成：需等發布成功，核對 latest 下載內容、雜湊及來源提交。

## 專案入口

專案 Git 根目錄的 AGENTS.md 保留自己的專案指引，加入以下來源及維護入口；不要讓下載器覆蓋整份專案入口。

```text
RulesSource: https://github.com/Madaimnim/madaimnim-game-framework/releases/latest/download/COMMON_RULES.md
RulesMaintenance: https://github.com/Madaimnim/madaimnim-game-framework/blob/main/AGENTS.md
```

將 Release 的 UpdateRules.py 放在專案既有 `Tools/UpdateRules.py`，新工作對話開始檢查一次：

```text
python ./Tools/UpdateRules.py
```

更新後完整閱讀 COMMON_RULES.md；目前對話不反覆下載。維護規範任務另先讀上述共用維護入口。

## 工具升級與保護

Release 提供 COMMON_RULES.md、UpdateRules.py、AGENTS.md、SHA256SUMS.txt。舊工具沒有 `--version` 時，取得同一 Release 的工具、核對 checksum 後原地更新，並保留原命令列入口。版本與工具升級規則詳見 AGENTS.md。

新工具保護降版、同版不同內容及本機未發布修改。同步基線僅存於本機 Git 目錄，不提交；非 Git 專案或無法判定基線時，不自動覆蓋已存在且內容不同的檔案。明確核對並保留差異後才使用 `--accept-local-replacement`。

```text
python ./Tools/UpdateRules.py --source-path <已核對的共用來源>
python ./Tools/UpdateRules.py --version
```

## 測試

```text
python -m unittest discover -s tests -v
```

檢查涵蓋首次同步、不重寫相同內容、格式與來源限制、拒絕降版、同版衝突、本機修改保護及 Git 同步基線。離線測試不代表 Release 已發布；發布後仍需實際回讀。

## 新作品沿用同一套架構

COMMON_RULES.md 的「跨作品共用架構與 AI 實作契約」是正式標準，包含模組責任、唯一文字來源、可編輯 UI、模板盤點與驗證。這是架構／實作規範，並非已交付可執行的遊戲程式模板。

新專案 AGENTS.md 在保留作品入口的前提下，加入上方 RulesSource／RulesMaintenance，要求先執行 Tools/UpdateRules.py 並完整閱讀 COMMON_RULES.md、PROJECT_RULES.md；不要另複製一份永久分岔的文字規則。

PROJECT_RULES.md 維護以下現行資訊（不要只留歷史流水帳）：

- 程式模板來源與 commit、引擎／套件、產品識別及內容根。
- 功能／正式來源／編輯入口／執行讀取者／產物與驗證／差異或待辦的架構表。
- 固定 UI 的 Table Collection、Entry 命名與語系；劇情／字幕的作者資料與編譯入口。
- Scene／Prefab、字型與圖片、平台／存檔、建置入口與輸出政策。
- 確認過的基底能力、未驗收／舊版殘留與遷移缺口，不能把規範當成已完成實作。

已定義的來源與分工由 AI 主動核對，不再每次要求使用者重複確認；仍未知或與本次需求有實質衝突者才提出具體問題。

## 一次同步工作區所有專案

使用同一個正式更新器，不另建第二套批次工具。從共用維護 checkout 執行：

```text
python UpdateRules.py --workspace-root <工作區根> --sync-updater
python UpdateRules.py --workspace-root <工作區根> --sync-updater --apply
```

第一行只預覽；第二行寫入。探索會依正式 RulesSource 找入口，支援外層 Git 根管理內層 Unity 根。固定下載同一 Release 並核對 checksum；不更動遊戲內容與專案專屬規範，不清除快取、不跟隨連結。updated/current/blocked 逐案回報，有受阻項目退出非零。

首次接軌的未知基線須先人工／AI逐項比對；核對後可提供本機 JSON：`{"專案絕對路徑":{"rulesSha256":"正規化雜湊","updaterSha256":"正規化雜湊"}}`，用 `--reviewed-baselines <本機清單>`，僅接受完全相符的內容。這不是忽略衝突；清單與私人路徑不要提交。後續有正式同步基線時不需這個參數。

使用者已授權整個工作區同步後，每次共同規範維護發布都包含以上預覽、套用及回讀，不重問已知範圍；目前仍不符合或受阻的專案會明列。

## 個人美術風格庫

先讀 [ArtStyles/manifest.json](ArtStyles/manifest.json)，再讀 [風格1 紙境工坊](ArtStyles/STYLE-001.md) 或 [風格2 清線冒險](ArtStyles/STYLE-002.md)。角色畫法、可替換元素、密度及試繪流程均在獨立風格檔。圖片可用性與來源狀態見索引；目前商業遊戲原截圖僅本機保存，未上傳。

同一 Release 會發布 ArtStyles_manifest.json 及各風格 .md，既有更新器會校驗並同步到各專案 ArtStyles。新工作對話沿用原本更新命令。風格檔更新須連同版本、發布及已授權專案同步完成，尚未安裝背景自動上傳服務。
