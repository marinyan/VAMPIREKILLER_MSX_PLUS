# 修正の追加と配布

[日本語](adding-fixes.md) | [English](adding-fixes.en.md)

このプロジェクトは、利用者の原ROMから必要なIPSを生成するツールです。修正項目ごとに処理を管理し、全組み合わせを事前生成しません。配布ZIPにも生成済みIPSやROMを入れません。

## 登録方法

1. `tools/fixes/` に修正モジュールを作ります。
2. `Fix` へ安定したID、日英の名前・要約・バグ説明を付けます。IDは小文字の英数字とアンダースコアで、先頭は英字です。
3. `tools/feature_catalog.py` の `CATALOG` へ登録します。CLIと画面は自動的に項目を表示します。
4. 原版での再現、修正後の動作、無効時と関連項目との併用を `tools/verify_bugs.py` などで検証します。

新しい修正は `extended_helpers=True` で拡張構成を選びます。`stairs.py` などが実例です。共通の説明定義は `bug_descriptions.py` にあり、同ファイルの `bug_fix` も利用できます。

```python
from fixes import Explanation, Fix


def emit_helpers(c):
    # c.label("your_fix_entry")
    # c.emit("...", "対応するZ80命令")
    pass


def apply(edit, hook, c):
    # hook(offset, expected_bytes, "your_fix_entry", "変更理由")
    # edit(offset, expected_bytes, replacement_bytes, "変更理由")
    pass


FIX = Fix(
    id="your_fix", title_ja="修正名", title_en="Fix title",
    description_ja="一覧用の要約", description_en="List summary",
    explanation=Explanation(
        symptom_ja="現象とプレイへの影響", symptom_en="Symptom and impact",
        trigger_ja="発生する場面・操作・装備", trigger_en="Triggering situation, inputs, or equipment",
        correction_ja="修正後の動作", correction_en="Corrected behavior",
        notes_ja="補足", notes_en="Notes",
    ),
    extended_helpers=True, bug_ids=("msx.your_fix",),
    emit_helpers=emit_helpers, apply=apply,
    requires=(), conflicts=(),
)
```

`Explanation` の現象・発生条件・修正後の動作は日英の両方を書きます。複数のバグを1項目にまとめる場合はそれぞれを説明し、`bug_ids` も複数指定します。挙動改善を区別するには `behavior_change=True` を付けます。全文をtips・詳細・CLI `--list` へ共通表示します。

件数は固定しません。既存IDを維持すれば、表示順や説明が変わっても保存済み設定は同じ修正を指定できます。新しい項目は古い設定へ自動追加しません。

## 依存・競合と変更の検査

`requires=("other_fix",)` は依存先を自動追加し、依存先から生成します。`conflicts=("other_fix",)` は片方で指定するだけでも同時選択を拒否します。未知ID、重複登録、参照先の欠落、循環もエラーになります。

`edit` はROMファイル先頭からのオフセット、同じ長さの元バイト・置換バイト、変更理由を受け取ります。`bytes` と16進文字列を使えます。`hook` は原則3バイトのCALLを生成し、最後に `0xC3` を指定するとJPです。元バイトと重複範囲は必ず検査します。

同じ位置へ複数の処理を後勝ちで書きません。共通処理へ整理し、`c.enabled` の選択IDで各部分を生成してください。現在は投擲の予約、所有権、斧の壁通知、剣の画面端マーカーの共有を調整しています。

## 拡張構成の配置

`tools/expanded_rom.py` は2Mbitの出力を組み立てます。原ROMのデータ用バンク4〜15はそのままです。物理8KiBバンク16へ修正コードと常駐コードの保存用コピーを置き、原作の画像・音楽・ステージを複製したり圧縮し直したりしません。

従来3項目のヘルパーはRAM `$E618–E7FF` と `$F100–F1C8` を使用します。拡張コードへの呼び出し口とバンク復帰処理は `$F1C9–F37F` 内へ置きます。起動時にロードし、バンク切替の前後でレジスター・戻り値・スタックと呼び出し元の割込許可状態を保存します。コード用バンク、予約RAM、起動ローダーがあふれたら生成を止めます。

拡張用の `emit_helpers(c)` ではラベルがCPU窓 `$8000–9FFF` を指します。`c.call("label")` は同じ拡張バンク内を呼び、`c.call(0x1234)` は原作のバンク2へ戻して呼びます。`c.jp(数値)` も原作呼び出し後に戻る末尾呼び出しになります。原作ループのフック位置へ数値で戻り続ける実装は、呼び出しが入れ子になるため避けてください。必要なループ全体をヘルパー内へ移し、成功・失敗の境界で原作へ戻します。

拡張バンク実行中に `$8000–9FFF` の原作データを直接読むと、修正コードを読んでしまいます。データ参照が必要なら、元のバンクで動くルーチンへ処理を渡してください。新しい拡張ヘルパーへ手動の `org` は指定しません。

RAMの上限は [MSX2 Technical Handbookのカートリッジ作業領域](https://konamiman.github.io/MSX2-Technical-Handbook/md/Chapter5b.html)と原作の利用範囲を確認したものです。実機は未検証です。

## 互換構成と配布

元の3項目だけを選んだ構成は、従来の1Mbit版を再現します。この場合だけ `compact_assets.py` の画像整理・圧縮を使います。入力は必ず利用者の原ROMです。`VARIANTS` は従来7構成の再現・ハッシュ照合用で、新しい修正の組み合わせを追加する必要はありません。

`build_patches.py` の既定出力はローカルの `build/patches/` と `build/` です。`dist/manifest.json` は互換ハッシュなどの検証用メタデータです。生成記録には元データのバイト列を残しません。

関数診断、拡張版の画像・序盤操作、盾の診断、選択ツールの検証を実行してから `python tools/package_patches.py` でZIPを更新します。パッケージ処理は生成済みIPSを検出したら停止します。ZIPはソース・説明・検証記録だけを収めます。ゲーム内の再現と、修正後の関数診断・序盤操作・全編攻略は、それぞれ実行した範囲だけを記録してください。
