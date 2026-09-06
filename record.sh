#!/bin/bash
# 録画時間(秒)
DURATION=30

# 保存先フォルダ
DIR="/home/youruser/recordings"

# ファイル名に日時を入れて重複を防ぐ
FILENAME="rec_$(date +%Y-%m-%d_%H%M%S).mp4"

# 録画実行(RTSPストリームから、再エンコードなしでコピー保存)
ffmpeg -i rtsp://localhost:8554/cam -t "$DURATION" -c copy "$DIR/$FILENAME"

# 完了メッセージ
echo "録画完了: $DIR/$FILENAME"
