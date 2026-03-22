#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cgi
import cgitb

# CGIのエラーをブラウザに表示する設定
cgitb.enable()

print("Content-Type: text/html; charset=utf-8")
print()

# フォームデータの取得
form = cgi.FieldStorage()

# --- 項目定義（グループ化） ---
buff_groups = [
    ("セット魔力", [
        ("belt", "ベルト"), ("boots", "靴")
    ]),
    ("装備魔力", [
        ("head", "頭部"), ("chest", "鎧"), ("pants", "下衣")
    ]),
    ("ルーン", [
        ("rune_head", "頭部"), ("rune_shoulder", "肩当て")
    ]),
    ("レジェ宝石", [
        ("pebble", "祝福の小石")
    ]),
    ("再鍛錬", [
        ("reforge_head", "頭部"), ("reforge_chest", "鎧"), ("reforge_shoulder", "肩当て"),
        ("reforge_pants", "下衣"), ("reforge_mh1", "メインハンド1"), ("reforge_mh2", "メインハンド2"),
        ("reforge_oh1", "オフハンド1"), ("reforge_oh2", "オフハンド2")
    ]),
    ("残滓", [
        ("remnant", "時の略奪者")
    ])
]

# 入力値の取得（空欄や文字列が来た場合のエラー回避用関数）
def get_float_safe(form, key, default):
    try:
        val = form.getvalue(key, str(default))
        if val == "": return 0.0
        return float(val)
    except ValueError:
        return default

base_duration = get_float_safe(form, "base_duration", 6.0)
base_cooldown = get_float_safe(form, "base_cooldown", 12.0)
cdr = get_float_safe(form, "cdr", 15.0)
# 実態に合わせてデフォルトを30%に変更
pvp_reduction = get_float_safe(form, "pvp_reduction", 60.0)
vithu_val = get_float_safe(form, "vithu", 30.0)

# バフ項目の数値取得と計算用リスト作成、およびUI描画用のHTML生成
buff_values = []
total_sum_bonus = 0.0 # 装備バフの合計（ヴィス抜き）
inputs_html = ""

for group_name, fields in buff_groups:
    inputs_html += f'<div class="buff-category">\n    <h4>{group_name}</h4>\n    <div class="buff-grid">\n'
    for field_id, label in fields:
        val = get_float_safe(form, field_id, 0.0)
        buff_values.append(val)
        total_sum_bonus += val

        # フォームに現在の値を表示するためのHTML生成
        val_str = form.getvalue(field_id, "0")
        inputs_html += f"""        <div class="form-sub-group">
            <label for="{field_id}">{label}</label>
            <input type="text" id="{field_id}" name="{field_id}" value="{val_str}">
        </div>\n"""
    inputs_html += '    </div>\n</div>\n'


# --- 計算ロジック ---

# 1. 実際のクールダウン計算 (PvEとPvPで分離)
actual_cooldown_pve = base_cooldown * (1.0 - cdr / 100.0)
# 戦場補正: 入力されたCDR効果が30%（0.3倍）になる
actual_cooldown_pvp = base_cooldown * (1.0 - (cdr * 0.30) / 100.0) 

# --- PvE 計算 ---
# 旧仕様（PvE）：装備・ルーン・再鍛錬などの合計値に、ヴィスの効果を「乗算」
old_multiplier = (1.0 + total_sum_bonus / 100.0) * (1.0 + vithu_val / 100.0)
old_duration_pve = base_duration * old_multiplier

# 新仕様（PvE）：すべての項目（ヴィス含む）を合計してから「加算」
total_sum_bonus_all = total_sum_bonus + vithu_val

# PvE上限100%（元の2.0倍まで）の判定
surplus_bonus = 0.0
if total_sum_bonus_all > 100.0:
    surplus_bonus = total_sum_bonus_all - 100.0
    is_capped = True
    new_multiplier_capped = 2.0
else:
    is_capped = False
    new_multiplier_capped = 1.0 + (total_sum_bonus_all / 100.0)

new_duration_pve = base_duration * new_multiplier_capped

# --- PvP 計算 ---
# 戦場では装備バフ（total_sum_bonus）のみが減少し、ベース時間とヴィスは減少しない
pvp_coeff = 1.0 - (pvp_reduction / 100.0)
total_sum_bonus_pvp = total_sum_bonus * pvp_coeff

# 旧仕様（PvP）
old_multiplier_pvp = (1.0 + total_sum_bonus_pvp / 100.0) * (1.0 + vithu_val / 100.0)
old_duration_pvp = base_duration * old_multiplier_pvp

# 新仕様（PvP）
total_sum_bonus_all_pvp = total_sum_bonus_pvp + vithu_val
surplus_bonus_pvp = 0.0
if total_sum_bonus_all_pvp > 100.0:
    surplus_bonus_pvp = total_sum_bonus_all_pvp - 100.0
    is_capped_pvp = True
    new_multiplier_capped_pvp = 2.0
else:
    is_capped_pvp = False
    new_multiplier_capped_pvp = 1.0 + (total_sum_bonus_all_pvp / 100.0)

new_duration_pvp = base_duration * new_multiplier_capped_pvp

# --- 差分とダウンタイムの計算 ---
# 持続時間の減少具合
duration_diff_pve = old_duration_pve - new_duration_pve
duration_diff_pvp = old_duration_pvp - new_duration_pvp

# ダウンタイム（空白の時間）の計算
downtime_old_pve = max(0.0, actual_cooldown_pve - old_duration_pve)
downtime_new_pve = max(0.0, actual_cooldown_pve - new_duration_pve)
downtime_old_pvp = max(0.0, actual_cooldown_pvp - old_duration_pvp)
downtime_new_pvp = max(0.0, actual_cooldown_pvp - new_duration_pvp)

# ダウンタイムの悪化具合
downtime_diff_pve = downtime_new_pve - downtime_old_pve
downtime_diff_pvp = downtime_new_pvp - downtime_old_pvp

# --- HTMLパーツ生成（警告ボックス） ---
def get_cap_html(capped, total_all, surplus):
    if capped:
        return f"""
        <div class="cap-box warning">
            <strong>⚠️ オーバーキャップ警告</strong><br>
            バフ延長の合計が <span class="diff">{total_all:.1f}%</span> に達しています。<br>
            上限100%を超えた <span class="diff" style="font-size: 1.2em;">{surplus:.1f}% 分が無駄になっています。</span><br>
            <small>※再鍛錬やルーンを他のステータスに変更する余地があります。</small>
        </div>
        """
    else:
        return f"""
        <div class="cap-box safe">
            <strong>✅ 効率的なビルド</strong><br>
            現在の合計ボーナス: {total_all:.1f}%<br>
            <small>上限100%まであと {(100.0 - total_all):.1f}% 余裕があります。</small>
        </div>
        """

cap_info_html_pve = get_cap_html(is_capped, total_sum_bonus_all, surplus_bonus)
cap_info_html_pvp = get_cap_html(is_capped_pvp, total_sum_bonus_all_pvp, surplus_bonus_pvp)

# --- タイムラインバー HTML生成 ---
def get_timeline_bar_html(duration, cooldown, downtime, spec):
    """spec: 'old' or 'new'"""
    if cooldown <= 0:
        return ""
    pct_active = min(duration / cooldown, 1.0) * 100
    pct_gap = max(0.0, 100.0 - pct_active)
    seg_css = "tl-old" if spec == "old" else "tl-new"
    txt_css = "tl-old-text" if spec == "old" else "tl-new-text"
    active_inner = f"<span class='tl-seg-text'>{duration:.1f}秒</span>" if pct_active >= 14 else ""
    gap_inner = f"<span class='tl-seg-text'>{downtime:.1f}秒</span>" if (downtime > 0 and pct_gap >= 14) else ""
    if downtime <= 0:
        bar = f'<div class="tl-seg {seg_css}" style="width:100%"><span class="tl-seg-text">{duration:.1f}秒</span></div>'
        info = (
            f'<div class="tl-info">'
            f'<span class="tl-info-active {txt_css}">発動中: {duration:.2f}秒</span>'
            f'<span class="tl-info-none">空白: なし（常時維持）</span>'
            f'<span class="tl-info-cd">再利用まで: {cooldown:.2f}秒</span>'
            f'</div>'
        )
    else:
        bar = (
            f'<div class="tl-seg {seg_css}" style="width:{pct_active:.1f}%">{active_inner}</div>'
            f'<div class="tl-seg tl-gap" style="width:{pct_gap:.1f}%">{gap_inner}</div>'
        )
        info = (
            f'<div class="tl-info">'
            f'<span class="tl-info-active {txt_css}">発動中: {duration:.2f}秒</span>'
            f'<span class="tl-info-gap">空白: {downtime:.2f}秒</span>'
            f'<span class="tl-info-cd">再利用まで: {cooldown:.2f}秒</span>'
            f'</div>'
        )
    return f'<div class="tl-wrap"><div class="tl-bar">{bar}</div>{info}</div>'

timeline_old_pve = get_timeline_bar_html(old_duration_pve, actual_cooldown_pve, downtime_old_pve, "old")
timeline_new_pve = get_timeline_bar_html(new_duration_pve, actual_cooldown_pve, downtime_new_pve, "new")
timeline_old_pvp = get_timeline_bar_html(old_duration_pvp, actual_cooldown_pvp, downtime_old_pvp, "old")
timeline_new_pvp = get_timeline_bar_html(new_duration_pvp, actual_cooldown_pvp, downtime_new_pvp, "new")

# --- HTML出力 ---
html_body = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>もぐらリサーチ - ヴィス・CDR 総合計算機</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; max-width: 1000px; margin: auto; background-color: #f4f7f6; color: #333; }}
        h1 {{ font-size: 1.5em; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; color: #2c3e50; text-align: center; }}
        .form-container {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}

        .layout-flex {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }}
        .col-basic {{ flex: 1; min-width: 250px; background: #fafafa; padding: 15px; border-radius: 6px; border: 1px solid #ddd; }}
        .col-buffs {{ flex: 2; min-width: 300px; background: #f9f9f9; padding: 15px; border-radius: 6px; border: 1px solid #ddd; }}

        /* グループ化用のCSS */
        .buff-category {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .buff-category h4 {{ margin: 0 0 10px 0; font-size: 0.95em; color: #2c3e50; border-bottom: 1px solid #f0f0f0; padding-bottom: 5px; }}

        .buff-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }}
        .form-group {{ margin-bottom: 15px; }}
        .form-sub-group {{ margin-bottom: 5px; }}
        label {{ display: block; font-size: 0.9em; font-weight: bold; color: #555; margin-bottom: 3px; }}
        input[type="text"] {{ width: 100%; padding: 8px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }}

        button {{ padding: 15px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1.1em; width: 100%; font-weight: bold; transition: background 0.3s; }}
        button:hover {{ background-color: #2980b9; }}

        .results-container {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .result-box {{ flex: 1; min-width: 300px; background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-top: 4px solid #3498db; }}
        .result-box.pvp {{ border-top-color: #e74c3c; }}

        h2 {{ margin-top: 0; font-size: 1.2em; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
        .highlight-cd {{ display: inline-block; background: #e8f4f8; padding: 5px 10px; border-radius: 4px; font-weight: bold; color: #0056b3; margin-bottom: 15px; border: 1px solid #bce8f1; }}
        .detail-row {{ margin-bottom: 10px; padding: 10px; background: #f9f9f9; border-radius: 4px; border-left: 3px solid #ddd; }}

        .old-spec {{ color: #e67e22; font-weight: bold; font-size: 1.1em; }}
        .new-spec {{ color: #27ae60; font-weight: bold; font-size: 1.1em; }}
        .downtime {{ color: #8e44ad; font-weight: bold; }}
        .zero-downtime {{ color: #2980b9; font-weight: bold; }}
        .diff {{ color: #c0392b; font-weight: bold; }}

        .cap-box {{ margin-top: 15px; padding: 12px; border-radius: 4px; font-size: 0.95em; }}
        .cap-box.warning {{ background: #fff5f5; border: 1px solid #feb2b2; }}
        .cap-box.safe {{ background: #f0fff4; border: 1px solid #9ae6b4; }}

        .tl-wrap {{ margin: 10px 0 4px 0; }}
        .tl-bar {{ display: flex; height: 44px; border-radius: 5px; overflow: hidden; border: 1px solid #bbb; }}
        .tl-seg {{ display: flex; align-items: center; justify-content: center; overflow: hidden; min-width: 0; }}
        .tl-seg-text {{ font-size: 0.85em; font-weight: bold; white-space: nowrap; color: white; padding: 0 8px; text-shadow: 0 1px 3px rgba(0,0,0,0.45); }}
        .tl-old {{ background: linear-gradient(135deg, #e67e22, #d35400); }}
        .tl-new {{ background: linear-gradient(135deg, #27ae60, #1e8449); }}
        .tl-gap {{ background: linear-gradient(135deg, #c0392b, #922b21); }}
        .tl-info {{ display: flex; justify-content: space-between; margin-top: 5px; font-size: 0.82em; flex-wrap: wrap; gap: 4px; padding: 0 2px; }}
        .tl-info-active {{ font-weight: bold; }}
        .tl-old-text {{ color: #d35400; }}
        .tl-new-text {{ color: #1e8449; }}
        .tl-info-gap {{ color: #c0392b; font-weight: bold; }}
        .tl-info-none {{ color: #2980b9; font-weight: bold; }}
        .tl-info-cd {{ color: #555; }}
    </style>
</head>
<body>

    <h1>もぐらリサーチ - ヴィス・CDR 総合計算機</h1>

    <div class="form-container">
        <form method="GET" action="">
            <div class="form-group">
                <a href="https://moleresearch.blogspot.com/2026/02/2026226-update.html#more" target="_blank">📄 仕様変更に関する説明を読む</a>
            </div>

            <div class="layout-flex">
                <div class="col-basic">
                    <label style="font-size: 1.1em; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 10px;">📊 基本ステータス</label>
                    <div class="form-group">
                        <label for="base_duration">スキルの持続時間 (秒)</label>
                        <input type="text" id="base_duration" name="base_duration" value="{form.getvalue('base_duration', '6.0')}">
                    </div>
                    <div class="form-group">
                        <label for="base_cooldown">スキルのクールダウン時間 (秒)</label>
                        <input type="text" id="base_cooldown" name="base_cooldown" value="{form.getvalue('base_cooldown', '12.0')}">
                    </div>
                    <div class="form-group">
                        <label for="cdr">クールダウン短縮 (%)</label>
                        <input type="text" id="cdr" name="cdr" value="{form.getvalue('cdr', '15.0')}">
                    </div>
                    <div class="form-group">
                        <label for="pvp_reduction">戦場(PvP)でのバフ減少率 (%)</label>
                        <input type="text" id="pvp_reduction" name="pvp_reduction" value="{form.getvalue('pvp_reduction', '60.0')}">
                    </div>
                    <div class="form-group" style="margin-top: 20px; padding-top: 15px; border-top: 1px dashed #ccc;">
                        <label for="vithu" style="color:#e67e22;">ヴィス2セット/4セット効果 (%)</label>
                        <input type="text" id="vithu" name="vithu" value="{form.getvalue('vithu', '30.0')}">
                    </div>
                </div>

                <div class="col-buffs">
                    <label style="font-size: 1.1em; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 10px;">✨ 各部位のバフ延長効果 (%)</label>
                    <p style="font-size: 0.85em; color: #666; margin-bottom: 10px;">※付与されている数値を個別に入力してください。0の場合は空欄か0で構いません。</p>

                    {inputs_html}

                </div>
            </div>

            <button type="submit">計算して比較する</button>
        </form>
    </div>

    <div class="results-container">
        <div class="result-box">
            <h2>⚔️ PvE (通常エリア / ダンジョン)</h2>
            <div class="highlight-cd">実際のCD: {actual_cooldown_pve:.2f} 秒 <span style="font-size: 0.8em; font-weight: normal;">(CDR {cdr:.1f}%)</span></div>

            <div class="detail-row">
                <strong>旧仕様（装備加算＋ヴィス乗算）:</strong><br>
                最終持続時間: <span class="old-spec">{old_duration_pve:.2f} 秒</span><br>
                空白の時間: {"<span class='zero-downtime'>0.00 秒 (常時維持)</span>" if downtime_old_pve == 0.0 else f"<span class='downtime'>{downtime_old_pve:.2f} 秒</span>"}
                {timeline_old_pve}
            </div>

            <div class="detail-row">
                <strong>新仕様（すべて加算）:</strong><br>
                最終持続時間: <span class="new-spec">{new_duration_pve:.2f} 秒</span><br>
                空白の時間: {"<span class='zero-downtime'>0.00 秒 (常時維持)</span>" if downtime_new_pve == 0.0 else f"<span class='downtime'>{downtime_new_pve:.2f} 秒</span>"}
                {timeline_new_pve}
            </div>

            {cap_info_html_pve}

            <hr style="border: 0; border-top: 1px dashed #ccc; margin: 15px 0;">
            <p style="font-size: 0.9em; color: #555;">
            ⚠️ <strong>アップデートによる影響:</strong><br>
            持続時間: {"変化なし" if abs(duration_diff_pve) < 0.005 else f"<span class='diff'>{abs(duration_diff_pve):.2f} 秒減少</span>"}<br>
            空白の時間: {"変化なし" if abs(downtime_diff_pve) < 0.005 else f"<span class='diff'>{abs(downtime_diff_pve):.2f} 秒増加</span>"}
            </p>
        </div>

        <div class="result-box pvp">
            <h2>🛡️ PvP (戦場など)</h2>
            <div class="highlight-cd">戦場での実CD: {actual_cooldown_pvp:.2f} 秒 <span style="font-size: 0.8em; font-weight: normal;">(補正後 {(cdr * 0.3):.1f}%)</span></div>

            <div class="detail-row">
                <strong>旧仕様（装備加算＋ヴィス乗算）:</strong><br>
                最終持続時間: <span class="old-spec">{old_duration_pvp:.2f} 秒</span><br>
                空白の時間: {"<span class='zero-downtime'>0.00 秒 (常時維持)</span>" if downtime_old_pvp == 0.0 else f"<span class='downtime'>{downtime_old_pvp:.2f} 秒</span>"}
                {timeline_old_pvp}
            </div>

            <div class="detail-row">
                <strong>新仕様（すべて加算）:</strong><br>
                最終持続時間: <span class="new-spec">{new_duration_pvp:.2f} 秒</span><br>
                空白の時間: {"<span class='zero-downtime'>0.00 秒 (常時維持)</span>" if downtime_new_pvp == 0.0 else f"<span class='downtime'>{downtime_new_pvp:.2f} 秒</span>"}
                {timeline_new_pvp}
            </div>

            {cap_info_html_pvp}

            <hr style="border: 0; border-top: 1px dashed #ccc; margin: 15px 0;">
            <p style="font-size: 0.9em; color: #555;">
            ⚠️ <strong>アップデートによる影響:</strong><br>
            持続時間: {"変化なし" if abs(duration_diff_pvp) < 0.005 else f"<span class='diff'>{abs(duration_diff_pvp):.2f} 秒減少</span>"}<br>
            空白の時間: {"変化なし" if abs(downtime_diff_pvp) < 0.005 else f"<span class='diff'>{abs(downtime_diff_pvp):.2f} 秒増加</span>"}
            </p>
        </div>
    </div>

</body>
</html>
"""

print(html_body)
