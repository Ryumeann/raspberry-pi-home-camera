#!/usr/bin/env python3
"""録画トリガー用の軽量Webサーバー（標準ライブラリのみ）"""
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

# 録画スクリプトのパス
RECORD_SCRIPT = "/home/youruser/record.sh"
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
    <iframe src="http://your-pi-hostname.local:8889/cam" allow="autoplay"></iframe>
  </div>
  <button onclick="record()">● 録画（30秒）</button>
  <div id="status"></div>
  <script>
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
        else:
            self._respond(404, "見つかりません", "text/plain")

    def _respond(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), RecordHandler)
    print(f"録画サーバー起動: ポート {PORT} で待機中")
    server.serve_forever()
