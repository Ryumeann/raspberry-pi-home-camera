#!/usr/bin/env python3
"""録画トリガー用の軽量Webサーバー（標準ライブラリのみ）"""
import subprocess
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 録画スクリプトのパス
RECORD_SCRIPT = "/home/ryumean/record.sh"
RECORDINGS_DIR = "/home/ryumean/recordings"
# 待ち受けポート（MediaMTXが使う番号と被らないものを選ぶ）
PORT = 8080

# ダッシュボードのHTML（ライブ映像＋録画ボタン）
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Home Camera</title>
  <style>
    body { font-family: sans-serif; text-align: center; background: #1a1a1a; color: #eee; margin: 0; padding: 16px; }
    h1 { font-size: 1.2rem; }
    .video-wrap { max-width: 640px; margin: 0 auto; }
    iframe { width: 100%; aspect-ratio: 4 / 3; border: none; border-radius: 8px; background: #000; }
    button { font-size: 1.1rem; padding: 12px 32px; margin-top: 16px; border: none; border-radius: 8px; background: #e04040; color: #fff; cursor: pointer; }
    button:active { background: #b03030; }
    #status { margin-top: 12px; min-height: 1.4em; color: #6fd66f; }
  </style>
</head>
<body>
  <h1>Home Camera</h1>
  <div class="video-wrap">
    <iframe src="http://homecam.local:8889/cam" allow="autoplay"></iframe>
  </div>
  <button onclick="record()">● 録画（30秒）</button>
  <div id="status"></div>
  
  <h2 style="font-size: 1rem; margin-top: 32px;">録画一覧</h2>
  <div id="recordings">読み込み中...</div>
  
  <script>
    // 録画を開始するボタン
    async function record() {
      const status = document.getElementById("status");
      const button = document.querySelector("button");
      try {
        const res = await fetch("/record");
        await res.text();               // サーバーの応答（開始通知）は受け取るだけ
        button.disabled = true;         // 録画中はボタンを押せなくする
        let remaining = 30;             // 録画時間（秒）
        status.textContent = `録画中... 残り ${remaining} 秒`;
        const timer = setInterval(() => {
          remaining--;
          if (remaining > 0) {
            status.textContent = `録画中... 残り ${remaining} 秒`;
          } else {
            clearInterval(timer);       // カウントダウン終了
            status.textContent = "録画完了しました";
            button.disabled = false;    // ボタンを再び押せるように
          }
        }, 1000);                       // 1000ミリ秒（1秒）ごとに実行
      } catch (e) {
        status.textContent = "エラー: " + e;
      }
    }

    // 録画一覧を取得して画面に描画する
    async function loadRecordings() {
      const container = document.getElementById("recordings");
      try {
        const res = await fetch("/recordings");
        const files = await res.json();        // JSONを配列として受け取る
        if (files.length === 0) {
          container.textContent = "録画はまだありません";
          return;
        }
        // 各録画を1行ずつHTMLに組み立てる
        container.innerHTML = files.map(f =>
          `<div style="padding: 8px; border-bottom: 1px solid #333;">
             ${f.name} <span style="color:#888;">(${f.size_mb} MB)</span>
             <a href="/video?file=${encodeURIComponent(f.name)}" target="_blank"
                style="color:#6fa0ff; margin-left:8px;">再生</a>
           </div>`
        ).join("");
      } catch (e) {
        container.textContent = "一覧の取得に失敗しました: " + e;
      }
    }

    // ページを開いたときに一覧を読み込む
    loadRecordings();
  </script>
</body>
</html>"""


class RecordHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._respond(200, DASHBOARD_HTML, "text/html")
        elif self.path == "/record":
            # record.sh をバックグラウンドで起動（完了を待たない＝即応答）
            subprocess.Popen([RECORD_SCRIPT])
            self._respond(200, "録画を開始しました（30秒）", "text/plain")
        elif self.path == "/recordings":
            self._respond(200, self._list_recordings(), "application/json")
        elif self.path.startswith("/video?"):
            self._serve_video()
        else:
            self._respond(404, "見つかりません", "text/plain")

    def _list_recordings(self):
        """録画フォルダ内の.mp4ファイルの一覧をjson文字列で返す"""
        files = []
        for name in os.listdir(RECORDINGS_DIR):
            if name.endswith(".mp4"):
                path = os.path.join(RECORDINGS_DIR, name)
                size_mb = round(os.path.getsize(path) / (1024 * 1024), 1)
                files.append({"name":name, "size_mb":size_mb})
        files.sort(key=lambda x: x["name"], reverse=True)
        # 新しい順に並べる（ファイル名に日時が入っているので名前の降順）
        return json.dumps(files, ensure_ascii=False)
      
    def _serve_video(self):
        """指定された録画ファイルを配信する（トラバーサル対策込み）"""

        # URLからクエリパラメータ file を取り出す
        query = parse_qs(urlparse(self.path).query)
        filename = query.get("file", [""])[0]

        # ★セキュリティ検証★ ファイル名だけを取り出し、余計なパスを排除
        safe_name = os.path.basename(filename)
        # .mp4 以外、または名前が変わってしまう入力は拒否
        if not safe_name.endswith(".mp4") or safe_name != filename:
            self._respond(400, "不正なファイル名です", "text/plain")
            return

        filepath = os.path.join(RECORDINGS_DIR, safe_name)
        print(f"[DEBUG] filename={filename!r}, safe_name={safe_name!r}, filepath={filepath!r}")
        # 実在しなければ404
        if not os.path.isfile(filepath):
            self._respond(404, "ファイルが見つかりません", "text/plain")
            return

        # ファイルを読み込んで動画として返す
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.end_headers()
        self.wfile.write(data)
    

    def _respond(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), RecordHandler)
    print(f"録画サーバー起動: ポート {PORT} で待機中")
    server.serve_forever()