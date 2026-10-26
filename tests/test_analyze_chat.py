import json
from pathlib import Path
import struct
import tempfile
import unittest

from chat_backup.analyze_chat import analyze, authored_text, call_info, load_chats, render_markdown


class ChatAnalysisTests(unittest.TestCase):
    def test_generated_archive_payload_is_data(self):
        chats = [{"name": "Example", "entries": [{"sender": "Alex", "text": "</script><script>example</script>"}]}]
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "index.html"
            archive.write_text("const D=" + json.dumps(json.dumps(chats).replace("<", "\\u003c")) + ";\nconst C=JSON.parse(D)", encoding="utf-8")
            self.assertEqual(load_chats(archive), chats)

    def test_counts_actual_senders_and_skips_system_or_deleted_prose(self):
        chat = {"name": "Group title", "entries": [
            {"sender": "You", "text": "Hello Alex", "media": []},
            {"sender": "Alex", "text": "Hi https://example.test", "media": []},
            {"sender": "Priya", "text": "Voice call 2 min", "media": []},
            {"sender": "You", "text": "This message was deleted.", "media": []},
        ]}
        rows, stats = analyze(chat, Path("index.html"))
        self.assertEqual(list(stats), ["You", "Alex", "Priya"])
        self.assertEqual(stats["You"]["Entries"], 2)
        self.assertEqual(stats["You"]["Written messages"], 1)
        self.assertEqual(stats["Alex"]["Links"], 1)
        self.assertEqual(stats["Priya"]["Connected-call time"], 120)
        self.assertEqual(stats["Priya"]["Written messages"], 0)
        report = render_markdown(chat["name"], rows, stats)
        self.assertIn("| All-time metric | You | Alex | Priya |", report)

    def test_call_and_message_markers(self):
        self.assertEqual(call_info("Missed Video call No answer"), ("video", "missed", None))
        self.assertEqual(authored_text({"text": "Hello <This message was edited>"}), "Hello")
        self.assertEqual(authored_text({"text": "Messages and calls are end-to-end encrypted"}), "")

    def test_voice_duration_and_media_paths_stay_inside_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root / "media"
            media.mkdir()
            page = bytearray(27)
            page[:4] = b"OggS"
            struct.pack_into("<q", page, 6, 30 * 48_000)
            (media / "voice.opus").write_bytes(page)
            entry = {"sender": "Alex", "text": "", "media": [{"path": "media/voice.opus", "contentType": "audio/opus"}]}
            chat = {"name": "Example", "entries": [entry]}
            _, stats = analyze(chat, root / "index.html")
            self.assertEqual(stats["Alex"]["Voice-message minutes"], 0.5)
            self.assertEqual(stats["Alex"]["Voice messages"], 1)
            entry["media"][0]["path"] = "../outside.opus"
            with self.assertRaisesRegex(ValueError, "Unsafe archived media path"):
                analyze(chat, root / "index.html")


if __name__ == "__main__":
    unittest.main()
