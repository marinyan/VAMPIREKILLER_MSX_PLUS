# VAMPIRE KILLER MSX PLUS

[日本語](README.md) | [English](README.en.md)

MSX2用『悪魔城ドラキュラ／Vampire Killer』の操作と画面端処理を改善するIPSパッチです。

表示タイトルは本体（BIOS）のリージョンに応じて切り替わります。対応するROMは「日本語版」などの表示言語ではなく、下記のサイズとSHA-256で識別してください。

**7種類とも適用後のROMは1Mbit（128 KiB／131,072バイト）です。** 画像・音楽・ステージを削除せず、データの可逆圧縮と重複整理で元の容量内へ収めています。

[パッチ・ソース・検証記録一式をZIPでダウンロード](dist/VAMPIREKILLER_MSX_PLUS_patches.zip)

| パッチ | 落下攻撃 | 画面端 | 盾耐久 |
|---|:---:|:---:|:---:|
| [fall_attack.ips](dist/fall_attack.ips) | ✓ | — | — |
| [screen_edges.ips](dist/screen_edges.ips) | — | ✓ | — |
| [combined.ips](dist/combined.ips) | ✓ | ✓ | — |
| [shield_fix.ips](dist/shield_fix.ips) | — | — | ✓ |
| [fall_attack_shield.ips](dist/fall_attack_shield.ips) | ✓ | — | ✓ |
| [screen_edges_shield.ips](dist/screen_edges_shield.ips) | — | ✓ | ✓ |
| [combined_shield.ips](dist/combined_shield.ips) | ✓ | ✓ | ✓ |

落下攻撃は鞭・剣・斧・十字架・聖水・砂時計を対象にします。画面端は敵の端出現、小ハートの端消失、剣・直進する敵弾の端消失を改善します。盾耐久は通常ステージ移動で残数を持ち越し、ボス撃破後の装備解除と耐久切れを正常に扱います。**3機能すべてを使う場合は `combined_shield.ips` を選んでください。**

**斧と十字架が画面端で反転して戻る動作は維持します。**

## 画面端からの出現例

![左端から出現し、体の一部だけが見えているゾンビ](docs/images/zombie-left-edge.png)

`combined.ips` 適用版を電源投入から通常のキー入力で動かし、ゾンビが左端から入ってくる瞬間を撮影しました。画像はopenMSXの未加工スクリーンショットです。

## 適用方法

1. 手元の無改変ROMのサイズとSHA-256を確認してください。
2. 7つのうち**どれか1つ**のIPSを、無改変ROMのコピーへ適用してください。複数機能を使う場合も、パッチを重ねず対応する組み合わせを選びます。
3. 適用後のROMは元と同じ128 KiBです。エミュレーターでマッパーの指定が必要な場合は **Konami／SCCなし** を選んでください。従来の拡張版を使っていた場合も、無改変の原ROMへあらためて適用してください。

対応する無改変ROMは128 KiB（131,072バイト）で、SHA-256が次のものです。

```text
99eabaaeb2b6c02220e131043d5a6401d0d8c5f413d89204547adcc04d65e7e2
```

IPS自体には入力ROMを識別する仕組みがありません。異なるリビジョンや改変済みROMへ適用しないでください。原ROMと適用済みROMは配布物に含めません。

## 変更の範囲

- 落下攻撃は、歩いて足場を外れた状態の攻撃進行・表示・特殊武器入力を変更します。落下速度、座標の小数、接地判定、着地音は維持します。発射待ちの剣の枠を聖水が上書きする組み合わせも防ぎます。
- 周期出現するゾンビ・コウモリなどの出現座標を左右端へ移します。ゾンビの出現先に床がない場合は元の座標へ戻します。プレイヤーの近くへの出現を避ける条件や出現周期は維持します。全種類の敵や退場条件を一括変更するものではありません。
- 小ハートは横座標を画面内へ制限し、横方向の端判定だけで消去しないようにします。着地時も拾得用の画像を画面内に収めます。揺れ・縦の動き・取得効果・着地後の寿命は変更しません。
- 剣と直進する敵弾は、最後のスプライトが画面外へ出るまで表示を続けます。画面をまたぐ座標の折り返しを識別し、反対側への表示・当たり判定を防ぎます。敵弾の対象は内部種別 `01/02/03/05/0A/0B` です。追尾弾や敵の戻る斧などの専用処理は対象外です。
- 盾は取得時の耐久16回を基準に、通常のステージ移動で残り耐久を持ち越します。ボス撃破後やミス後の装備解除では、盾と耐久を正常に消去します。耐久0の盾を解除して0から255への減算を防ぎ、弾防御の最後の1回を使った際は、その更新内の残りの弾まで防がないようにします。接触軽減用・弾防御用の両タイプを対象にします。

## 検証

openMSX 21.0／C-BIOS MSX2 JPで、原版と7つの改良版をそれぞれ1,653条件・8,875回の関数終了で確認しました。入力RAMとレジスターを設定する関数診断です。移動と着地、BCDハートの消費、武器の枠管理、敵の生成、左右端の描画と消去、小ハートの着地、剣の誤判定、斧・十字架の反転と回収を含みます。

JP は検証時の本体設定を示しています。

別途、各改良版を電源投入から通常のキー入力だけで63.5秒動かし、屋外3画面と城内3画面を通過しました。結果とROMのハッシュは [関数・序盤の検証記録](dist/verification.json) に保存しています。

盾専用の診断は原版と7つの改良版を各478条件・582回の関数終了で確認しました。原版のステージ移動後の0→255を再現し、修正入り4版について、耐久の持ち越し・ボス後の解除・取得時16回・耐久0・残り1回での8発同時衝突・途中にステージ移動を挟んだ16回の防御を検証しています。[盾の検証記録](dist/shield-verification.json)を参照してください。

**落下攻撃＋画面端の2機能版 `combined.ips` は、電源投入から通常キー入力による自動通しプレイでクリアを確認しました。** 全19エリア中139画面、6体のボス、最終ボスの両形態、エンディング全41項目、2周目開始後の右移動まで通過しています。通常の残機再開を1回含みます。途中ステートの復元やゲームRAM・PC・ROMの書換えは使っていません。

同じ入力を別起動で2回再生し、全56,792更新の時刻・入力・ゲーム状態・Rレジスターが記録と一致しました。各再生で追加コード領域を568回照合し、作業RAM 9,344バイトの568サンプルも2回の再生間で一致しました。通しプレイ中には落下と攻撃が同時に進む状態も48更新観測しています。[全編の検証記録](dist/campaign-verification.json) と [再生用入力](dist/campaign-inputs.json.gz) を公開しています。入力ファイルにはROM本体やエミュレーターのステートを含みません。

この全編記録は `combined.ips` が対象です。盾修正入り4版の全編通しプレイ、全分岐・全装備の組み合わせ、全機種、実機の動作は未確認です。

1Mbit化では、7版すべてで全168ポーズの位置・パターン・色を原版と照合し、初期条件を揃えたアイテム・燭台の読み込み後のVRAM全128 KiBも一致しました。12画像の1,536バイトは932バイトへ可逆圧縮しています。[容量と画像の検証記録](dist/compact-verification.json)を参照してください。

## ビルドと再検証

Python 3の標準ライブラリーだけでパッチを生成できます。

```powershell
python tools/build_patches.py path/to/original.rom
python tools/verify_patch_files.py path/to/original.rom
```

`dist/` にIPSとハッシュ一覧、`build/` に適用済みROMとコードの一覧を生成します。ビルダーは入力ROMのハッシュが異なる場合に停止します。

エミュレーターの診断を再実行する場合は、openMSXのポータブル版を用意してください。

```powershell
python tools/verify_emulator.py path/to/original.rom --openmsx path/to/openmsx.exe
python tools/verify_compact_rom.py path/to/original.rom --openmsx path/to/openmsx.exe
python tools/verify_shield.py path/to/original.rom --openmsx path/to/openmsx.exe
```

両機能版の全編入力を、手元の適用済みROMと新しい電源投入状態で再検証できます。

```powershell
python tools/verify_campaign.py --rom build/combined.rom --inputs dist/campaign-inputs.json.gz --openmsx path/to/openmsx.exe --out build/campaign-replay
```

`--out` には未作成のフォルダーを指定します。結果はその中の `report.json` に保存されます。再生環境はopenMSX 21.0／C-BIOS MSX2 JPです。配布ZIPにもパッチ、ソース、入力、検証記録をまとめています。

出現例のスクリーンショットも通常操作から再撮影できます。

```powershell
python tools/capture_edge_screenshot.py --rom build/combined.rom --openmsx path/to/openmsx.exe
```

撮影画像は `build/screenshot/` に保存します。掲載画像は `zombie-left-01.png` です。

実装は [tools/patches.py](tools/patches.py)、可逆圧縮と表示データの整理は [tools/compact_assets.py](tools/compact_assets.py) にあります。追加コードは原ROMのバンク6内へ収め、起動時にRAM `$E618–E7FF` と `$F100–F1C8` 内へ配置します。3機能版の追加コードは683バイトで、再配置したROM領域には113バイトの余裕があります。通常の更新中に追加コード用のバンク切替は行いません。

RAMの利用範囲は、[MSX2 Technical Handbookのカートリッジ作業領域の説明](https://konamiman.github.io/MSX2-Technical-Handbook/md/Chapter5b.html)と、原作のスタック・変数・画像バッファの配置を確認して選んでいます。
