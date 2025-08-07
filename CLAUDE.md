## プロジェクト概要
Discordの会議を自動で文字起こし→議事録生成するシステム
要件定義:REQUIREMENTS.md
技術設計書:ARCHITECTURE.md
進捗管理:PROGRESS.md

# 開発ディレクティブ
- ~/.claude/development-directives.md
  - こちらの内容をしっかり把握

## ⚠️ 回答送信前必須チェック
□ ユーザー意図を明確化したか
□ TDD原則に従っているか
□ マイアーキテクチャガイドライン を意識しているか
□ 検索する必要がある場合、検索に関する指示を行っているか
□ 選択肢を番号付きで提示したか
上記各内容は詳細: `~/.claude/development-directives.md`参照


## 開発方針

### 型ヒントの使用
Python 3.6以降の型ヒント機能を積極的に使用する。

```python
# 例
from typing import List, Optional, Dict

def process_files(folder_id: str, minutes: int = 5) -> List[Dict[str, str]]:
    """ファイルを処理する関数"""
    pass

class GoogleDriveClient:
    def __init__(self, credentials_path: str) -> None:
        self.credentials_path: str = credentials_path
```

**利点**:
- エディターの補完機能向上
- 実行前のエラー検出
- コードの可読性向上

## 直近で開発した別システムからの知見

### Cloud Run環境でのOpenAI API接続問題
以前のプロジェクトでCloud Runにデプロイした際、OpenAI公式SDKで接続エラーが発生した経験があります。

**発生した問題**: 
- OpenAI SDKを使用するとCloud Run環境でConnection Errorが頻発
- ローカル環境では正常動作するが、デプロイ後にエラー
- SDKの内部HTTPクライアントとCloud Runのコンテナ環境の相性問題

**根本解決策**: 
requestsライブラリによる直接API呼び出しに完全移行

```python
# 問題のあった実装（OpenAI SDK使用）
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(...)

# 解決した実装（requests使用）
import requests
headers = {"Authorization": f"Bearer {api_key}"}
response = requests.post(
    "https://api.openai.com/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=30
)
```

**教訓**: 
- Cloud Runデプロイ予定の場合、最初からrequestsライブラリで実装
- LLM API（OpenAI/Claude）は公式SDKを避け、REST API直接呼び出しを採用
- タイムアウト値の明示的な設定が重要