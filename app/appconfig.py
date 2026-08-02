import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".yolo26_detector"
CONFIG_FILE = CONFIG_DIR / "config.json"


class AppConfig:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.data = {"recent_projects": [], "settings": {}}
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                self.data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        self.data.setdefault("recent_projects", [])
        self.data.setdefault("settings", {})
        self.data["recent_projects"] = [p for p in self.data["recent_projects"] if Path(p).exists()]

    def save(self):
        CONFIG_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_recent_projects(self):
        return self.data["recent_projects"]

    def add_recent_project(self, path):
        path = str(path)
        if path in self.data["recent_projects"]:
            self.data["recent_projects"].remove(path)
        self.data["recent_projects"].insert(0, path)
        self.data["recent_projects"] = self.data["recent_projects"][:10]
        self.save()

    # ---------- 自动保存 ----------
    def get_auto_save(self) -> bool:
        return bool(self.data["settings"].get("auto_save", False))

    def set_auto_save(self, enabled: bool):
        self.data["settings"]["auto_save"] = bool(enabled)
        self.save()
