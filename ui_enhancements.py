"""
版本：20260827-UX-FIXES-ROUND15
更新內容：focusableInputs() 排除反灰鎖定（disabled）的欄位——員工清單自動帶入比對
成功後，姓名/單位/職務等欄位會反灰鎖定禁止編輯，Enter/Tab 應該直接跳到下一個「真正
還能填」的欄位，不該把鎖定中的欄位也算進可移動範圍。

---（以下為 ROUND10 紀錄）---
修正 Enter／Tab 跳欄位的「順序」問題——使用者反映 Step 1 兩欄並排的表單，
按 Enter/Tab 應該要「由左而右、由上而下」（同一列先跳右邊，再換下一列），但先前的
`focusableInputs()` 是照 HTML 文件裡的原始順序排，而 Streamlit 的 st.columns() 在
HTML 裡是「整個左欄的所有欄位先出現，整個右欄的欄位才出現」，不是像畫面看起來那樣
一列一列交錯——導致 Enter 鍵會先跳完左欄全部欄位才跳到右欄，跟畫面直覺完全不符。
新增 visualOrder()：改成抓每個欄位的實際畫面座標（top/left），由上而下抓「列」
（同一列用跟該列第一個元素的 top 座標比對，避免誤差累加），列內再由左而右排序，
Enter 鍵跳格用這個順序。另外原生 Tab 鍵不會經過我們的 keydown 監聽器，改用明確設定
每個欄位的 tabindex（依同一套視覺順序）讓 Tab 鍵也照這個順序走，並定期重算（Step 3/4
動態增減欄位時，畫面位置會變動）。

---（以下為 ROUND6 紀錄）---
修正 Enter 鍵跳欄位的第三個根因——中文輸入法（IME）干擾。使用者實測發現只有
「打中文的欄位」（單位、出差事由、姓名、職務）會跳錯，純英數字欄位（員工編號）正常，
這正是輸入法選字確認鍵的典型症狀：用注音/拼音等輸入法打完中文按 Enter，第一下通常是
「確認選字」而不是使用者真的要送出/跳欄位，瀏覽器會把這種 Enter 標記成 isComposing=true
（舊版瀏覽器則是 keyCode 229），原本的邏輯完全沒有排除這種情況，會誤判成「使用者要跳
下一格」而搶著跳走，這時候輸入法選字都還沒確認完，畫面看起來就是亂跳或沒反應。修法：
keydown 一開始先檢查 isComposing／keyCode 229，是的話完全不處理，讓輸入法自己吃掉這次
Enter；使用者選字confirm完，真的要跳欄位時再按一次 Enter，那次事件才會正常被抓到。

---（以下為 ROUND2/ROUND3 紀錄）---
修正 Enter 鍵跳欄位的第二個根因——即使改成用「位置索引」定位下一格（見下方
ROUND2 紀錄），Step 4 巢狀欄位（st.columns 裡的欄位）還是會跳錯或整個沒反應。原因：
負責重試搶焦點的計時器綁在我們注入的隱藏 iframe 自己的 setTimeout 上，但 Streamlit
按 Enter 後會整個重繪畫面，連這個 iframe 都會被換掉，舊 iframe 一從 DOM 移除，瀏覽器
就直接砍光它排定中的計時器，重試還沒來得及跳到下一格就被連根拔起。改成把計時器
（包含定期重套用 autocomplete=off 那個）都掛在外層 Streamlit 主頁面的 window 上
（不會被 rerun 換掉的那個），並用旗標確保整個 session 只掛一次、不會每次 rerun 都疊加。

---（以下為 ROUND2 紀錄）---
修正 Enter 鍵跳欄位邏輯——Step 4 人工複核每一列都有相同 aria-label 的欄位
（例如每列都有一個「幣別」欄位），舊版用 aria-label 找「下一個欄位」在有重複標籤時會
抓到錯誤的那一個，導致按 Enter 後跳到不相關的欄位，還因為每 60ms 持續搶焦點回錯誤欄位，
表現得像鍵盤卡住。改成單純用按下 Enter 當下欄位在畫面上的「位置索引」定位下一格，
不再依賴標籤文字，杜絕重複標籤造成的誤判。

inject_theme_css()——卡片化各 Step 區塊、加圓角陰影、統一間距。這是 Streamlit 能力
範圍內的畫面美化（Shadcn/Tailwind 是 React 建置工具鏈的東西，Streamlit 沒有對應的建置
流程可以接，所以改用調整既有元件樣式的方式），顏色一律用 Streamlit 自己的 CSS 變數
（如 var(--background-color)），會跟著使用者的亮／暗主題自動切換。

純瀏覽器端 best-effort 小工具：關閉表單欄位的瀏覽器自動完成建議、讓 Enter 鍵也能像
Tab 一樣跳到下一個欄位。這兩個都是瀏覽器行為，Streamlit 沒有原生開關，用注入 JS 的
方式盡量處理，不保證所有瀏覽器 100% 生效。

這是純畫面體驗的輔助元件，不含任何商業邏輯，可以安全放進任何 Streamlit 頁面。
"""
import streamlit as st
import streamlit.components.v1 as components


def inject_theme_css() -> None:
    """卡片化區塊樣式，只調整外觀不影響任何互動邏輯。顏色用 Streamlit 內建 CSS 變數，
    自動跟著亮／暗主題切換，不寫死顏色值。"""
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
        }
        div[data-testid="stExpander"] {
            border-radius: 10px;
            overflow: hidden;
        }
        div[data-testid="stFileUploaderDropzone"] {
            border-radius: 10px;
        }
        div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {
            border-radius: 8px;
            font-weight: 600;
        }
        h1, h2, h3 {
            letter-spacing: 0.01em;
        }
        div[data-testid="stAlert"] {
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_form_navigation_helpers() -> None:
    """關閉瀏覽器自動完成建議 + 讓 Enter 鍵跳到下一個欄位（Tab 鍵瀏覽器本來就支援）。

    技術說明：這段 JS 是透過 components.html 產生的隱藏 iframe 執行，再用
    window.parent.document 反過來操作 Streamlit 主頁面的實際輸入框。因為 Streamlit
    每次互動都會重新渲染部分 DOM，所以用 setInterval 每隔一段時間重新套用一次
    autocomplete="off"，並且用旗標避免重複掛上多個 keydown 監聽器。

    按下 Enter 後，Streamlit 會先跑一輪 rerun 把值存進 session_state，rerun 結束後它自己
    也會把焦點還原回剛剛編輯的欄位（避免使用者輸入到一半失焦的內建行為），這跟我們想跳到
    下一格的目的互相打架，所以不是 focus 一次就結束，而是在接下來約 3 秒內持續搶回焦點，
    直到使用者自己開始在新欄位輸入為止。

    「下一格」是誰：用按下 Enter 當下該欄位在畫面上所有可聚焦欄位裡的「位置索引」決定
    （index + 1），不是用 aria-label 文字去找同名欄位——Step 4 人工複核每一列都有同樣
    文字的欄位（每列都有「幣別」「金額」等），用標籤找永遠只會抓到文件裡第一個同名欄位，
    在有很多列的情況下會跳到不相關的欄位。
    """
    components.html(
        """
        <script>
        (function() {
            function getDoc() {
                try { return window.parent.document; } catch (e) { return null; }
            }

            function disableAutofill() {
                const doc = getDoc();
                if (!doc) return;
                const inputs = doc.querySelectorAll(
                    'input[type="text"], input[type="number"], input[type="date"]'
                );
                inputs.forEach(function(el, i) {
                    el.setAttribute('autocomplete', 'off');
                    if (!el.dataset.noAutofillPatched) {
                        el.setAttribute('name', 'field-' + i + '-' + Math.random().toString(36).slice(2));
                        el.dataset.noAutofillPatched = '1';
                    }
                });
            }

            function visualOrder(elements) {
                // 用「視覺閱讀順序」（由上而下、同一列再由左而右）排序，不是文件裡的
                // 原始順序——Streamlit 的 st.columns() 在 HTML 裡是「整個左欄先出現、
                // 整個右欄才出現」，不是像畫面看起來那樣一列一列交錯；如果照文件順序，
                // Enter/Tab 會先跳完左欄所有欄位才跳到右欄，跟畫面上「這一列填完換右邊」
                // 的直覺完全不符。做法：抓每個欄位的畫面座標，先由上而下抓出「列」
                // （同一列的判斷用跟該列第一個元素的 top 座標比對，而不是兩兩比對，
                // 避免誤差累加把同一列誤判成好幾列），列內再由左而右排序。
                const rowTolerancePx = 15;
                const withRects = elements.map(function(el) {
                    const rect = el.getBoundingClientRect();
                    return {el: el, top: rect.top, left: rect.left};
                });
                withRects.sort(function(a, b) { return a.top - b.top; });
                const rows = [];
                withRects.forEach(function(item) {
                    let row = rows.find(function(r) { return Math.abs(r[0].top - item.top) <= rowTolerancePx; });
                    if (!row) { row = []; rows.push(row); }
                    row.push(item);
                });
                rows.forEach(function(row) { row.sort(function(a, b) { return a.left - b.left; }); });
                const ordered = [];
                rows.forEach(function(row) { row.forEach(function(item) { ordered.push(item.el); }); });
                return ordered;
            }

            function focusableInputs(doc) {
                const elements = Array.from(
                    doc.querySelectorAll('input[type="text"], input[type="number"], input[type="date"], textarea')
                ).filter(function(el) {
                    if (el.offsetParent === null) return false;
                    // 反灰鎖定的欄位（例如員工清單自動帶入後鎖定的欄位）不該排進 Enter/Tab
                    // 的可移動範圍——使用者本來就不能編輯，游標停在那裡或跳過去都沒有意義，
                    // 應該直接跳到下一個「真正還能填」的欄位。
                    if (el.disabled) return false;
                    // Streamlit 的日期選擇元件內部會藏一個「畫面外」的原生
                    // <input type="date">（給無障礙工具/瀏覽器原生日期選擇器用，實際
                    // 顯示的是另一個自訂樣式的元素）——這個元素尺寸正常（不是 0），
                    // 純粹是用負座標（例如 top:-1px; left:-1px）移到畫面外，offsetParent
                    // 也不是 null，光靠尺寸濾不掉；這種元素不該排進視覺順序（會被排到
                    // 最前面，因為 top 座標是負的、比任何正常欄位都小），要濾掉。
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.left >= 0;
                });
                return visualOrder(elements);
            }

            function syncTabOrder(doc) {
                // 原生 Tab 鍵是瀏覽器自己處理的，不會經過我們的 keydown 監聽器，要讓 Tab
                // 也照「由左而右、由上而下」排序，只能明確設定 tabindex（瀏覽器對有明確
                // tabindex 的元素，會照 tabindex 數字大小決定 Tab 順序，不是照文件順序）。
                const fields = focusableInputs(doc);
                fields.forEach(function(el, i) { el.tabIndex = i + 1; });
            }

            function persistFocus(pwin, doc, targetIndex, ticksLeft) {
                const fields = focusableInputs(doc);
                const el = fields[targetIndex];
                if (!el) {
                    if (ticksLeft > 0) pwin.setTimeout(function() { persistFocus(pwin, doc, targetIndex, ticksLeft - 1); }, 60);
                    return;
                }
                if (doc.activeElement !== el) {
                    el.focus();
                    if (typeof el.select === 'function') el.select();
                }
                if (!el.dataset.enterNavGiveUpBound) {
                    el.dataset.enterNavGiveUpBound = '1';
                    el.addEventListener('input', function onInput() {
                        el.removeEventListener('input', onInput);
                        el.dataset.enterNavGiveUpBound = '';
                    });
                }
                if (ticksLeft > 0) {
                    pwin.setTimeout(function() { persistFocus(pwin, doc, targetIndex, ticksLeft - 1); }, 60);
                }
            }

            function attachEnterNavigation() {
                const doc = getDoc();
                if (!doc || doc.__enterNavAttached) return;
                doc.__enterNavAttached = true;
                doc.addEventListener('keydown', function(e) {
                    // 輸入中文（注音/拼音等輸入法）時，按 Enter 常常是「確認選字」，不是
                    // 使用者真的要跳下一格——這種情況瀏覽器會把事件標成 isComposing（或舊版
                    // 瀏覽器用 keyCode 229 表示「輸入法處理中」），這時候完全不要攔截，讓
                    // 輸入法自己把這次 Enter 用掉；使用者選字確認完，再按一次 Enter 才會是
                    // 真的要跳欄位，那次事件 isComposing 會是 false，會正常被抓到。
                    if (e.isComposing || e.keyCode === 229) return;
                    const isEnter = e.key === 'Enter' || e.keyCode === 13 || e.which === 13 || e.code === 'Enter' || e.code === 'NumpadEnter';
                    if (!isEnter) return;
                    const active = doc.activeElement;
                    if (!active || active.tagName !== 'INPUT') return;
                    const fields = focusableInputs(doc);
                    const idx = fields.indexOf(active);
                    if (idx === -1 || idx >= fields.length - 1) return;
                    // 重試計時器一定要掛在外層 Streamlit 主頁面的 window 上（doc.defaultView），
                    // 不能用這段 script 自己所在的隱藏 iframe 的 setTimeout——Streamlit 按 Enter
                    // 後會整個重繪畫面，連我們注入的這個 components.html iframe 都會被換掉，
                    // 舊 iframe 一旦從 DOM 移除，瀏覽器會直接砍光它排定中的計時器，重試還沒
                    // 來得及跳到下一格就被連根拔起，焦點就掉空、看起來像亂跳或沒反應。外層
                    // window 本身不會被 Streamlit 換掉，掛在那裡計時器才能撐過整個 rerun。
                    persistFocus(doc.defaultView, doc, idx + 1, 50);
                }, true);
            }

            function refreshPeriodicTasks() {
                const doc = getDoc();
                if (!doc) return;
                disableAutofill();
                syncTabOrder(doc);
            }

            disableAutofill();
            syncTabOrder(getDoc());
            attachEnterNavigation();
            // 同理，這個定期重套用 autocomplete=off／tabindex 的計時器也要掛在外層
            // window，且用旗標確保整個 session 只掛一次——外層 window 不會被 rerun
            // 換掉，每次 iframe 重新注入這段 script 時如果沒有這個旗標，會不斷疊加新的
            // setInterval 永遠不會停。tabindex 需要定期重算，是因為 Streamlit 動態增減
            // 欄位（例如 Step 3/4 上傳/複核清單的列數會變）時，畫面位置跟著變動。
            const doc0 = getDoc();
            const pwin0 = doc0 && doc0.defaultView;
            if (pwin0 && !doc0.__autofillIntervalAttached) {
                doc0.__autofillIntervalAttached = true;
                pwin0.setInterval(refreshPeriodicTasks, 800);
            }
        })();
        </script>
        """,
        height=0,
    )
