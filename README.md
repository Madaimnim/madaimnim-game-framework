# 共用規範唯一入口

正式維護來源為本GitHub儲存庫；各環境只保留一份COMMON_RULES.md正文。先讀AGENTS.md的維護／發布流程，通用條文見COMMON_RULES.md，不在遊戲專案維護副本。

## 開始工作

每個新工作對話從專案根執行 `python Tools/UpdateRules.py`。更新器比對GitHub正式Release與SHA256SUMS，本機落後才下載至共用位置，相同不重寫；依輸出路徑完整閱讀正文。僅查位置用 `--show-location`，不代表已驗證遠端最新。來源衝突或網路失敗保留內容並報錯，不能假稱已同步。

## 本機位置與換機

機器專用位置記在CODEX_HOME/shared-rules.json：`{"root":"<本機共用目錄的絕對路徑>"}`，不提交私人設定。未配置的新環境預設使用CODEX_HOME/shared-rules（CODEX_HOME未指定時為使用者家目錄/.codex）；工具會從已校驗的Release初始化必要檔案。換機需要Python3.8以上及GitHub連線，讀取前實際驗證，不能假定另一台電腦已安裝。

各專案COMMON_RULES.md僅為短指標，AGENTS.md及更新工具保持可攜；PROJECT_RULES.md只保存本案識別、資料／場景／工具入口、特有契約、例外與待辦。共用風格由唯一正文旁ArtStyles讀取，實際參考圖另依私有映射取得。

## 修改與發布

使用者要求維護通用規範時，依AGENTS.md核對遠端及本機修改，合併、測試、升RulesVersion與風格manifest版本、提交／推送；主分支workflow發布不可覆寫的rules-版本。回讀Release對應提交、內容及雜湊後才稱完成。正常工作檢查更新不自動提交遊戲或無關檔案。共用規範維護已獲授權的內容不能只停留本機。

## 舊專案轉為短入口

從共用維護目錄執行 `python UpdateRules.py --workspace-root <工作區> --sync-updater` 預覽，再加 `--apply`。依已登記授權處理；一致或已校驗基線才替換舊正文，先更新工具再寫指標。未知／修改／同版衝突保留，不用強制覆寫；手動比對後可給限定雜湊的--reviewed-baselines。回讀每個入口解析到同一正文，不搬資產、不提交遊戲Git。

## 測試

`python -m unittest discover -s tests -v`

保留既有下載／降版／本機修改與風格校驗回歸，另驗證唯一正文、初次初始化、指標遷移預覽／衝突／重複執行與私人位置配置。

## 索引

通用規範涵蓋權限、資料歸屬與舊美術日期留存、美術生成／圖片None與九宮格、Unity/UI結構、文字唯一來源、內容版本／淺層Builds、證據與成果文件。個人風格索引在ArtStyles/manifest.json；跨專案角色只保存已授權最小定位，不發布私人原圖或設定。登記工作區與本機映射只記本機Git私有狀態。
