# STYLE-003｜2D 敵人少幀動畫風格比較

狀態：跨專案製作試驗，13 種畫風樣片。角色是用於比較的原創苔甲獨角蟲。這是一個比較案例，並非單一正式畫風。

## 看圖

- [十三種動畫並排](https://github.com/Madaimnim/madaimnim-game-framework/releases/download/rules-2026-11-17.1/STYLE-003-comparison.gif)
- [十三種靜態對照](https://github.com/Madaimnim/madaimnim-game-framework/releases/download/rules-2026-11-17.1/STYLE-003-comparison.png)
- [Release 校驗檔](https://github.com/Madaimnim/madaimnim-game-framework/releases/download/rules-2026-11-17.1/SHA256SUMS.txt)

每種四張原創姿勢。順序是待機、蓄力、頂撞、受擊，再重播待機。比較版播放時間依序為 380、230、110、160、360 毫秒。正常尺寸與棋盤縮圖同步播放。

## 樣片索引

| 編號 | 畫風 | 測試描述 |
| --- | --- | --- |
| 1 | 粗線剪紙 | 粗黑輪廓、平塗色塊、局部印刷感 |
| 2 | 木刻版畫 | 深色塊、刻線、低飽和點色 |
| 3 | 粗像素 | 有限色盤、硬邊和粗像素比例 |
| 4 | 大色塊像素 | 少色階、大面積像素群、低表面細節 |
| 5 | 暗黑細節像素 | 深色陰影、輪廓內較密集的像素細節 |
| 6 | 復古橡皮管 | 柔軟四肢、誇張拉伸、手繪動畫輪廓 |
| 7 | 彩色鉛筆 | 彩色細線和輪廓內的紙面筆觸 |
| 8 | 中世紀手稿 | 平塗水粉、棕色墨線、金色裝飾 |
| 9 | 黑線著色本 | 清楚外線、大片純色、節制陰影 |
| 10 | 單色抖色像素 | 黑白反差、以抖色疏密表現明暗 |
| 11 | 幾何平面 | 用圓形、三角形等基本形狀概括造型 |
| 12 | 水彩暈染 | 輪廓內的分層洗色、柔和過渡 |
| 13 | 平面剪影 | 深色剪影加少量亮色標記 |

## 生成方式

1. 用內建 ImageGen 分別生成每種畫風，每版一張等分 2×2 的實心洋紅底圖。固定同一組角色描述與四個動作，不使用商業遊戲截圖當輸入。不同風格獨立生成，造型比例會有小差異。
2. 正式重用時，優先選一張被接受的角色母圖當參考，鎖定眼睛、角、背殼標記與足底。這次樣片為文字共用規格，沒有用母圖逐版轉繪。
3. 使用 generate2dsprite 腳本去背與切格。輸出 224×224 透明影格、透明圖表和循環 GIF。同一版內採共同縮放、足底對齊與最大連通主體。橡皮管版的角尖靠近切格邊界，切格前加寬中間留白保住角尖。
4. 比較圖用 Pillow 合成，四個姿勢套用同一組橫向偏移與速度。像素三版用最近鄰縮放，其他版本以 Lanczos 縮放。
5. 目視檢查縮圖是否仍辨識眼、角、腳與攻擊方向。把瞄準、範圍、命中之類的視覺訊號視為可重用獨立圖層。這批驗證了敵人影格及離線播放。

### 可重用提示模板

> One 2D game enemy sprite sheet. Exactly four equal cells in a 2×2 grid. Solid flat #FF00FF background. Style: [one style description]. Same compact enemy in all four cells: [silhouette, body markers, palette and props]. Fixed three-quarter view facing right, same body scale, same feet line, torso centered, full body inside the central 66% of each cell. In reading order: neutral, crouched anticipation, horizontal in-place attack, recoil. No text, dividers, floor, shadows, or detached FX.

本次共用造型為圓殼苔甲、向右的缺口象牙角、背殼淺色斜痕、兩個暖黃眼睛和短深色腳。其作用是讓同一組辨識特徵跨畫風可比較。

## 製作評估

- 一般小怪先驗證 **黑線著色本**。大色塊、硬邊陰影與固定線粗讓縮小後的輪廓更清楚。借用 **粗線剪紙**的造型節奏，把不規則筆觸留在少數輪廓部位。
- **幾何平面**適合戰鬥提示和技能圖層。以弧、線、環、火花、碎片組出出手和命中，程式負責朝向、尺度、位移、時序與顏色。
- 大量動態單位可從一張母圖＋引擎位移、縮放、閃白起步。需要清楚預警的敵人，優先補蓄力與攻擊姿勢。
- 刻線、鉛筆紋理和水彩過渡適合放大圖。縮成棋盤單位時，先看外輪廓是否保得住，再判斷要保留多少材質細節。

來源為本次生成的原創比較樣片。商業遊戲參考畫面未收入這份素材包。評估依離線動畫，尚待引擎內實玩確認。原始影格和各版獨立 GIF 沿本機參考區提供。
