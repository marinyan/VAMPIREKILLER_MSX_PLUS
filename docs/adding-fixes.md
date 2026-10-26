# 修正項目の追加

[日本語](adding-fixes.md) | [English](adding-fixes.en.md)

選択ツールは、登録された修正だけを統合して原ROMからIPSを1枚生成します。IPSの重ね当てや、全組み合わせの事前生成は行いません。

## ファイルの役割

| ファイル | 役割 |
|---|---|
| `tools/fixes/__init__.py` | `Fix` の定義。ID、日英の説明、依存・競合、生成処理 |
| `tools/fixes/*.py` | 各修正の追加コードとROM変更 |
| `tools/feature_catalog.py` | 登録順、依存解決、選択の検証 |
| `tools/patches.py` | Z80コードの統合、ラベル解決、配置、元バイトと変更範囲の検査 |
| `tools/selection_build.py` | 1枚のIPS、生成記録、選択JSONの入出力 |
| `tools/patch_selector.py` / `tools/selector_gui.py` | CLIと画面。項目の一覧は登録内容から自動生成 |

## 新しい項目を登録する

1. `tools/fixes/` にモジュールを作ります。`shield_fix.py` は短い実例です。
2. 安定したID（小文字の英数字とアンダースコア、先頭は英字）と日英の名前・要約・バグ説明を `Fix` に記述します。
3. `tools/feature_catalog.py` で `FIX` をインポートし、`CATALOG` へ追加します。既存の登録順は維持します。CLIと画面への個別追加は不要です。
4. 単体と関連項目の診断を追加し、容量・競合と実際のゲーム動作を確認します。

項目数は固定しません。新しい修正が増えても既存のIDは維持してください。保存した選択JSONはIDを参照するため、項目の表示順や説明が変わっても同じ修正を指定できます。新しい項目が追加されても、以前保存した選択へ自動的に追加はしません。

モジュールの形は次のとおりです。コメントの箇所には、原ROMで確認した追加コードと変更を実装します。

```python
from fixes import Explanation, Fix


def emit_helpers(c):
    # c.label("your_fix_entry")
    # c.emit("...", "対応するZ80命令")
    # c.call("共有ラベル") / c.jp(...) / c.jr(...)
    pass


def apply(edit, hook, c):
    # edit(offset, expected_bytes, replacement_bytes, "変更理由")
    # hook(offset, expected_bytes, "your_fix_entry", "変更理由")
    pass


FIX = Fix(
    id="your_fix",
    title_ja="修正名", title_en="Fix title",
    description_ja="挙動の説明", description_en="Behavior description",
    explanation=Explanation(
        symptom_ja="何が起きてプレイにどう影響するか", symptom_en="The symptom and its effect on play",
        trigger_ja="どの場面・操作・装備で発生するか", trigger_en="The situation, inputs, or equipment that trigger it",
        correction_ja="有効にするとどう変わるか", correction_en="How enabling this fix changes the behavior",
        notes_ja="対象や維持する動作など", notes_en="Scope and behavior that stays the same",
    ),
    emit_helpers=emit_helpers, apply=apply,
    requires=(), conflicts=(),
)
```

追加コードが不要な修正は `emit_helpers` を省略できます。追加コードを持たない項目だけを選んでも、長さ0のRAM転送は生成しません。ラベルは他の項目と重複しない名前を使います。

`description_ja/en` は一覧の短い要約です。`Explanation` にはバグの現象、発生条件、修正後の動作を省略せず書き、必要なら補足を加えます。複数のバグをまとめた項目では、それぞれを分けて説明します。全文はマウスオーバーのtips、「詳細」、CLIの `--list` に共通で表示します。単なる挙動改善なら `behavior_change=True` を指定し、バグ修正として誤表示しないようにします。登録項目に日英の説明が揃っていることも `verify_selector.py` で確認します。

`edit` のアドレスはROMファイル先頭からのオフセットです。元バイトと置換バイトは同じ長さにし、`bytes` または16進文字列で渡します。`hook` は原則3バイトのCALLを作り、JPなら最後の引数を `0xC3` にします。呼び出し先ラベルのアドレスは統合後に解決されます。

## 依存と競合

`requires=("other_fix",)` を指定すると、依存先も自動的に選ばれ、依存先から追加コードとROM変更を生成します。画面でもチェックへ反映します。選択順によらず、同じ項目から同じIPSを生成します。

同時に有効にできない項目は `conflicts=("other_fix",)` で宣言します。片方の宣言だけでも同時選択を拒否します。不明なID、登録の重複、参照先の欠落、依存の循環もエラーになります。

同じROM範囲への変更は、同じバイトを書くだけでも拒否します。後勝ちで上書きすることはありません。両立させる場合は共通フックをコアへまとめるか、両方を扱う共有モジュールへ整理し、必要な依存関係を定義してください。

## 容量と配置

出力は1Mbitのままです。共通の画像再配置・展開処理は1回だけ組み込みます。追加コードの使用先は現在 `$E618–E7FF` と `$F100–F1C8` に限られます。画面端の修正は途中から `$F100` を使うため、その後の項目も続きへ配置されます。

ROMバンク6の残量、各RAM区間の上限と重複、起動ローダーの容量を生成時に確認します。新しいコードが収まらない場合は、実装を小さくするか、使用範囲を調査したうえで配置設計を更新する必要があります。生成ツールが自動的にROMを拡張することはありません。残量は `.ips.json` の `bank6_free_bytes`、RAM配置は `ram_chunks`、各変更の担当項目は `changes[].owner` で確認できます。

## 検証と配布

```powershell
python tools/patch_selector.py --list
python tools/patch_selector.py path/to/original.rom --enable your_fix --out build/your-fix.ips
python tools/patch_selector.py path/to/original.rom --all --out build/all-fixes.ips
python tools/verify_selector.py path/to/original.rom
```

`verify_selector.py` は現在の3項目について既存7種類との一致を検証し、CLI、Tcl/Tkの操作処理、設定の再現、依存・競合・容量制限を確認します。20個の仮の直接修正を登録する拡張テストも含みます。これは登録・統合処理のテストで、20個のゲーム修正を実装したという意味ではありません。

新しい修正には挙動を確認する診断を追加し、関係する組み合わせと全修正入りを確認してください。すべての組み合わせを自動的に検証したとは扱いません。既存の `VARIANTS` と `build_patches.py` は従来7種類の再生成・検証用として残しており、新しい項目ごとに組み合わせを追加する必要はありません。

`python tools/package_patches.py` は項目モジュールを含むソース、日英の説明、選択ツールの検証記録をZIPへ収めます。ROMとエミュレーターステートは配布しません。
