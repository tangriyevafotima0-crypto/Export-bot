# 🛠️ TeleExport — Dasturchi uchun Texnik Reja

> **Product:** Telegram chatlar, guruhlar va kanallarni chiroyli eksport qiluvchi desktop ilova
> **Arxitektura:** Client-side only, MTProto (User API), Electron + Python Backend
> **Sana:** 2026-06-06
> **Versiya:** MVP 1.0

---

## 📐 ARXITEKTURA (High-Level)

```
┌──────────────────────────────────────────────────────────┐
│                   ELECTRON DESKTOP APP                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   Renderer    │  │   Preload    │  │   Main Process │  │
│  │  (React/TS)  │  │   (Bridge)   │  │   (Node.js)   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                   │          │
│         └─────────┬───────┘                   │          │
│                   │ IPC                       │          │
│         ┌─────────▼─────────┐                 │          │
│         │   Python Backend  │◄──child_process─┘          │
│         │   (Telethon)     │                             │
│         │   - Auth         │                             │
│         │   - Export       │                             │
│         │   - Format       │                             │
│         └─────────┬────────┘                             │
│                   │ MTProto (TCP)                        │
│         ┌─────────▼────────┐                             │
│         │  Telegram DC     │                             │
│         │  (Data Centers)  │                             │
│         └──────────────────┘                             │
└──────────────────────────────────────────────────────────┘
```

### Nima uchun bu arxitektura?

| Komponent | Tanlov | Sababi |
|---|---|---|
| **Frontend** | Electron + React + TypeScript | Cross-platform (Win/Mac/Linux), boy UI, xavfsiz IPC |
| **Backend engine** | Python + Telethon (child_process) | Eng tezkor MTProto library, 1200 msg/sec benchmark, aktiv rivojlanish |
| **IPC** | JSON-RPC over stdin/stdout | Oddiy, debug qilish oson, progress streaming |
| **Export format** | HTML (birlamchi), JSON, PDF | HTML — Telegram Desktop'nikidan ham chiroyli, browserda ochiladi |
| **Auth** | MTProto session fayli, mahalliy saqlanadi | Token hech qachon tashqariga chiqmaydi |
| **Media saqlash** | Mahalliy filesystem | `~/TeleExport/exports/` papkasiga |

---

## 🧱 TEXNOLOGIYA STEKI

### Frontend (Electron + React)

```json
{
  "electron": "^33.0.0",
  "react": "^19.0.0",
  "typescript": "^5.6.0",
  "tailwindcss": "^4.0.0",
  "zustand": "^5.0.0",
  "react-router-dom": "^7.0.0",
  "lucide-react": "^0.460.0",
  "recharts": "^2.15.0",
  "@tanstack/react-query": "^5.0.0",
  "electron-builder": "^25.0.0",
  "electron-updater": "^6.0.0",
  "vite": "^6.0.0"
}
```

### Python Backend

```toml
# pyproject.toml
[project]
dependencies = [
    "telethon>=2.0.0",
    "jinja2>=3.1.0",
    "pillow>=11.0.0",
    "python-magic>=0.4.27",
    "cryptg>=0.4.0",        # Telethon encryption accelerator
    "orjson>=3.10.0",        # Tezkor JSON
    "aiofiles>=24.0.0",
    "tqdm>=4.66.0",          # Progress bar (debug)
    "emoji>=2.14.0",         # Emoji parsing
    "python-dateutil>=2.9.0",
    "colorama>=0.4.6"
]
```

---

## 📁 LOYIHA STRUKTURASI

```
teleexport/
├── package.json                    # Root: Electron app
├── electron-builder.yml            # Build config
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
│
├── src/                           # === FRONTEND (Renderer) ===
│   ├── main.tsx                   # React entry
│   ├── App.tsx
│   ├── index.css                  # Tailwind globals
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx       # Main layout
│   │   │   ├── Sidebar.tsx        # Navigation
│   │   │   └── TitleBar.tsx       # Custom titlebar (frameless)
│   │   │
│   │   ├── auth/
│   │   │   ├── AuthScreen.tsx     # Phone + Code + 2FA
│   │   │   ├── PhoneInput.tsx
│   │   │   ├── CodeInput.tsx
│   │   │   └── PasswordInput.tsx
│   │   │
│   │   ├── dashboard/
│   │   │   ├── Dashboard.tsx      # Asosiy ekran
│   │   │   ├── ChatList.tsx       # Barcha chatlar ro'yxati
│   │   │   ├── ChatCard.tsx       # Bitta chat kartasi
│   │   │   ├── SearchBar.tsx      # Chat qidirish
│   │   │   └── StatsOverview.tsx  # Statistikalar
│   │   │
│   │   ├── export/
│   │   │   ├── ExportWizard.tsx   # Export sozlash wizard
│   │   │   ├── ChatSelector.tsx   # Chat tanlash (checkbox)
│   │   │   ├── FormatSelector.tsx # HTML/JSON/PDF tanlash
│   │   │   ├── DateRangePicker.tsx
│   │   │   ├── MediaOptions.tsx   # Media turlari
│   │   │   └── ExportProgress.tsx # Progress bar + log
│   │   │
│   │   └── shared/
│   │       ├── Button.tsx
│   │       ├── Modal.tsx
│   │       ├── ProgressBar.tsx
│   │       ├── Badge.tsx
│   │       └── Skeleton.tsx
│   │
│   ├── stores/
│   │   ├── auth.store.ts          # Auth state (Zustand)
│   │   ├── chats.store.ts         # Chatlar ro'yxati
│   │   ├── export.store.ts        # Export holati
│   │   └── settings.store.ts      # Sozlamalar
│   │
│   ├── hooks/
│   │   ├── useIPC.ts              # IPC bridge helper
│   │   ├── useExportProgress.ts   # Progress stream
│   │   └── useChats.ts            # Chat ma'lumotlari
│   │
│   └── types/
│       ├── chat.types.ts
│       ├── export.types.ts
│       └── ipc.types.ts           # IPC message tiplari
│
├── electron/                      # === MAIN PROCESS ===
│   ├── main.ts                    # Electron entry
│   ├── preload.ts                 # Context bridge
│   ├── ipc-handlers.ts           # IPC handlerlar
│   ├── python-bridge.ts           # Python bilan muloqot
│   ├── updater.ts                 # Auto-update
│   ├── menu.ts                    # App menu
│   └── window-manager.ts          # Oyna boshqaruvi
│
├── python/                        # === PYTHON BACKEND ===
│   ├── __init__.py
│   ├── main.py                    # Entry: stdin/stdout JSON-RPC server
│   ├── pyproject.toml
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── client.py              # Telethon client wrapper
│   │   ├── auth.py                # Auth: login, 2FA, session
│   │   ├── session_manager.py     # Session fayllari
│   │   └── config.py              # Constants & settings
│   │
│   ├── export/
│   │   ├── __init__.py
│   │   ├── engine.py              # Asosiy export engine
│   │   ├── chat_scanner.py        # Chatlarni skanerlash
│   │   ├── message_fetcher.py     # Xabarlarni olish
│   │   ├── media_downloader.py    # Media fayllarni yuklash
│   │   └── progress.py            # Progress hisoboti
│   │
│   ├── formatters/
│   │   ├── __init__.py
│   │   ├── html_formatter.py      # Chiroyli HTML
│   │   ├── json_formatter.py      # JSON export
│   │   ├── csv_formatter.py       # CSV export
│   │   ├── pdf_formatter.py       # PDF export
│   │   └── templates/
│   │       ├── base.html          # Asosiy HTML template
│   │       ├── chat.html          # Bitta chat sahifasi
│   │       ├── message.html       # Bitta xabar komponenti
│   │       ├── media.html         # Media elementlar
│   │       ├── styles.css         # CSS (inline qilinadi)
│   │       └── assets/
│   │           └── icons/         # SVG ikonkalar
│   │
│   ├── ipc/
│   │   ├── __init__.py
│   │   ├── server.py              # JSON-RPC server
│   │   ├── protocol.py            # Xabar protokoli
│   │   └── handlers.py            # RPC handlerlar
│   │
│   └── utils/
│       ├── __init__.py
│       ├── sanitizer.py           # HTML sanitizatsiya
│       ├── file_utils.py          # Fayl operatsiyalari
│       ├── logger.py              # Python log
│       └── rate_limiter.py        # Rate limit boshqaruvi
│
├── resources/                     # Build resurslar
│   ├── icon.icns                  # macOS icon
│   ├── icon.ico                   # Windows icon
│   └── icon.png                   # Linux icon
│
├── tests/                         # Testlar
│   ├── python/
│   │   ├── test_export_engine.py
│   │   ├── test_html_formatter.py
│   │   └── test_auth.py
│   └── frontend/
│       └── components/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── IPC_PROTOCOL.md
    ├── BUILD.md
    └── SECURITY.md
```

---

## 🔄 IPC PROTOKOL (Electron ↔ Python)

### JSON-RPC over stdin/stdout

Har bir xabar yangi qatorda, JSON formatda:

```typescript
// IPC Message Types
type IPCMessage = 
  | { id: string; method: string; params: Record<string, unknown> }  // Request
  | { id: string; result: unknown }                                   // Success
  | { id: string; error: { code: number; message: string } }          // Error
  | { id: null; event: string; data: unknown }                        // Stream event
```

### Barcha RPC metodlar:

```yaml
# ============ AUTH ============
auth.check_session:
  description: "Mavjud session bor-yo'qligini tekshirish"
  params: {}
  returns: { has_session: bool, phone_hint?: string }

auth.send_code:
  params: { phone: string, api_id: int, api_hash: string }
  returns: { phone_code_hash: string, timeout: int }
  events: ["auth.code_sent"]

auth.sign_in:
  params: { phone: string, code: string, phone_code_hash: string }
  returns: { success: bool, user?: object }
  events: ["auth.signed_in"]

auth.check_2fa:
  params: {}
  returns: { has_2fa: bool, hint?: string }

auth.sign_in_2fa:
  params: { password: string }
  returns: { success: bool }

auth.logout:
  params: {}
  returns: { success: bool }

# ============ CHATS ============
chats.list:
  description: "Barcha chatlarni ro'yxatini olish"
  params: { limit?: int, offset?: int, search?: string }
  returns: { chats: Chat[], total: int }
  events: ["chats.progress"]  # Katta ro'yxat uchun progress

chats.get_details:
  params: { chat_id: int }
  returns: { chat: ChatDetailed }

# ============ EXPORT ============
export.start:
  params:
    chat_ids: int[]
    format: "html" | "json" | "csv" | "pdf"
    date_from?: string    # ISO 8601
    date_to?: string
    media_types: MediaType[]
    output_dir: string
    include_replies: bool
    include_forwards: bool
    max_file_size_mb?: int
  returns: { export_id: string }
  events:
    - "export.progress"    # { export_id, chat_id, chat_name, percent, messages_done, messages_total }
    - "export.media_progress"  # { file_name, percent, downloaded_bytes, total_bytes }
    - "export.chat_complete"   # { chat_id, messages_exported, media_count }
    - "export.complete"        # { export_id, total_chats, total_messages, total_media, output_path }
    - "export.error"           # { chat_id, error_message, recoverable: bool }

export.cancel:
  params: { export_id: string }
  returns: { success: bool }

export.get_status:
  params: { export_id: string }
  returns: { status: ExportStatus }

# ============ SETTINGS ============
settings.get:
  params: {}
  returns: { settings: AppSettings }

settings.set:
  params: { settings: Partial<AppSettings> }
  returns: { success: bool }
```

### Event stream namunasi:

```json
{"id":null,"event":"export.progress","data":{"export_id":"exp_001","chat_id":123456789,"chat_name":"Ali","percent":45.2,"messages_done":4520,"messages_total":10000}}
{"id":null,"event":"export.media_progress","data":{"export_id":"exp_001","file_name":"IMG_4520.jpg","percent":78,"downloaded_bytes":3912345,"total_bytes":5000000}}
{"id":null,"event":"export.chat_complete","data":{"export_id":"exp_001","chat_id":123456789,"messages_exported":10000,"media_count":342}}
{"id":null,"event":"export.complete","data":{"export_id":"exp_001","total_chats":5,"total_messages":48500,"total_media":1520,"output_path":"/home/user/TeleExport/exports/export_2026-06-06/"}}
```

---

## 🐍 PYTHON BACKEND — MUHIM MODULLAR

### 1. `core/client.py` — Telethon wrapper

```python
import os
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from .config import SESSION_DIR, CONFIG_DIR

class TeleExportClient:
    def __init__(self, session_name: str = "default"):
        self.session_path = SESSION_DIR / f"{session_name}.session"
        self.client: TelegramClient | None = None
        
    async def init(self, api_id: int, api_hash: str):
        """Telethon mijozini ishga tushirish"""
        self.client = TelegramClient(
            str(self.session_path),
            api_id,
            api_hash,
            device_model="TeleExport Desktop",
            system_version="1.0.0",
            app_version="1.0.0",
            lang_code="en",
            system_lang_code="en"
        )
        
    async def connect(self) -> bool:
        """Faqat ulanish (login qilmasdan)"""
        await self.client.connect()
        return await self.client.is_user_authorized()
        
    async def send_code(self, phone: str) -> tuple[str, int]:
        """Kod jo'natish"""
        return await self.client.send_code_request(phone)
        
    async def sign_in(self, phone: str, code: str, phone_code_hash: str):
        """Kod bilan kirish"""
        return await self.client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        
    async def sign_in_with_password(self, password: str):
        """2FA parol bilan kirish"""
        return await self.client.sign_in(password=password)
        
    async def get_me(self):
        return await self.client.get_me()
        
    async def disconnect(self):
        await self.client.disconnect()
```

### 2. `export/engine.py` — Asosiy eksport dvigateli

```python
import asyncio
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Optional

from telethon.tl.types import (
    Message, MessageMediaPhoto, MessageMediaDocument,
    MessageMediaGeo, MessageMediaContact, MessageMediaPoll
)

from ..core.client import TeleExportClient
from .message_fetcher import MessageFetcher
from .media_downloader import MediaDownloader
from ..formatters.html_formatter import HTMLFormatter
from ..formatters.json_formatter import JSONFormatter
from .progress import ExportProgress

@dataclass
class ExportConfig:
    chat_ids: list[int]
    output_dir: Path
    format: str = "html"  # html | json | csv | pdf
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    media_types: set[str] = field(default_factory=lambda: {
        "photo", "video", "audio", "document", 
        "voice", "sticker", "animation", "video_note"
    })
    include_replies: bool = True
    include_forwards: bool = True
    max_file_size_mb: int = 500
    batch_size: int = 100  # Bir iterationda nechta xabar

class ExportEngine:
    def __init__(
        self,
        client: TeleExportClient,
        config: ExportConfig,
        progress_callback: Optional[Callable] = None
    ):
        self.client = client
        self.config = config
        self.progress = ExportProgress(progress_callback)
        self.cancelled = False
        
    def cancel(self):
        self.cancelled = True
        
    async def run(self, export_id: str):
        """To'liq eksport jarayoni"""
        output_dir = self.config.output_dir / f"export_{datetime.now():%Y-%m-%d_%H-%M-%S}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        total_stats = {
            "export_id": export_id,
            "total_chats": 0,
            "total_messages": 0,
            "total_media": 0,
            "chats": []
        }
        
        for idx, chat_id in enumerate(self.config.chat_ids):
            if self.cancelled:
                break
                
            chat_stats = await self._export_chat(chat_id, output_dir)
            total_stats["chats"].append(chat_stats)
            total_stats["total_messages"] += chat_stats["messages_count"]
            total_stats["total_media"] += chat_stats["media_count"]
            total_stats["total_chats"] += 1
            
        # Umumiy index.html
        if self.config.format == "html":
            self._write_index_html(output_dir, total_stats)
            
        # Metadata
        meta_path = output_dir / "export_metadata.json"
        meta_path.write_text(json.dumps(total_stats, indent=2, ensure_ascii=False))
        
        return total_stats
        
    async def _export_chat(self, chat_id: int, output_dir: Path) -> dict:
        """Bitta chatni eksport qilish"""
        entity = await self.client.client.get_entity(chat_id)
        chat_name = entity.title if hasattr(entity, 'title') else (
            f"{entity.first_name or ''} {entity.last_name or ''}".strip()
        )
        
        # Papka yaratish
        safe_name = "".join(c for c in chat_name if c.isalnum() or c in ' _-')[:50]
        chat_dir = output_dir / safe_name
        chat_dir.mkdir(exist_ok=True)
        media_dir = chat_dir / "media"
        media_dir.mkdir(exist_ok=True)
        
        # Xabarlarni olish
        fetcher = MessageFetcher(
            self.client.client,
            entity,
            date_from=self.config.date_from,
            date_to=self.config.date_to,
            batch_size=self.config.batch_size
        )
        
        # Media downloader
        media_dl = MediaDownloader(
            self.client.client,
            media_dir,
            max_file_size=self.config.max_file_size_mb * 1024 * 1024,
            media_types=self.config.media_types
        )
        
        messages = []
        media_count = 0
        
        async for batch in fetcher.iter_batches():
            if self.cancelled:
                break
                
            for msg in batch:
                # Media yuklash
                if msg.media and self._should_download_media(msg.media):
                    media_path = await media_dl.download(msg)
                    if media_path:
                        media_count += 1
                        
                messages.append(msg)
                
            # Progress
            self.progress.update_chat(chat_id, chat_name, fetcher.processed, fetcher.total)
            
        # Formatlash
        formatter = self._get_formatter(chat_dir)
        output_path = formatter.format(chat_name, entity, messages, media_dir)
        
        return {
            "chat_id": chat_id,
            "chat_name": chat_name,
            "chat_type": "private" if entity.is_private else "group" if hasattr(entity, 'megagroup') and entity.megagroup else "channel",
            "messages_count": len(messages),
            "media_count": media_count,
            "output_file": str(output_path)
        }
        
    def _should_download_media(self, media) -> bool:
        """Media turini tekshirish"""
        if isinstance(media, MessageMediaPhoto):
            return "photo" in self.config.media_types
        if isinstance(media, MessageMediaDocument):
            doc = media.document
            mime = doc.mime_type or ""
            for t in self.config.media_types:
                if t in mime:
                    return True
        return False
        
    def _get_formatter(self, chat_dir: Path):
        formats = {
            "html": HTMLFormatter(chat_dir),
            "json": JSONFormatter(chat_dir),
        }
        return formats[self.config.format]
```

### 3. `export/message_fetcher.py` — Xabarlarni batchlab olish

```python
import asyncio
from typing import AsyncIterator, Optional
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.types import InputPeer

class MessageFetcher:
    """Xabarlarni samarali batchlab olish.
    
    Telegram limiti: 30 msg/sec global, 
    1 msg/sec per private chat,
    20 msg/min per group/channel.
    
    Eng katta tezlik uchun: takeout session + wait_time sozlash.
    """
    
    def __init__(
        self,
        client: TelegramClient,
        entity,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        batch_size: int = 100
    ):
        self.client = client
        self.entity = entity
        self.date_from = date_from
        self.date_to = date_to
        self.batch_size = batch_size
        self.processed = 0
        self.total = None
        
    async def count_total(self) -> int:
        """Umumiy xabarlar sonini hisoblash"""
        if self.total is None:
            count = 0
            async for _ in self.client.iter_messages(
                self.entity, 
                offset_date=self.date_to,
                offset_id=0,
                limit=None
            ):
                if self.date_from and _.date < self.date_from:
                    break
                count += 1
            self.total = count
        return self.total
        
    async def iter_batches(self) -> AsyncIterator[list]:
        """Xabarlarni batchlab olish (takeout session orqali)"""
        try:
            # Takeout session — pastroq flood wait, tezroq eksport
            async with self.client.takeout() as takeout:
                messages = []
                async for msg in takeout.iter_messages(
                    self.entity,
                    offset_date=self.date_to,
                    limit=None,
                    wait_time=0  # Takeout ichida kutish kerak emas
                ):
                    if self.date_from and msg.date < self.date_from:
                        if messages:
                            yield messages
                        break
                        
                    messages.append(msg)
                    self.processed += 1
                    
                    if len(messages) >= self.batch_size:
                        yield messages
                        messages = []
                        await asyncio.sleep(0.05)  # Rate limiting
                        
                if messages:
                    yield messages
                    
        except Exception as e:
            # Takeout ishlamasa, oddiy iter_messages
            async for batch in self._iter_without_takeout():
                yield batch
                
    async def _iter_without_takeout(self) -> AsyncIterator[list]:
        """Takeoutsiz, standard iter_messages"""
        # Rate limitni boshqarish
        per_chat_delay = 1.0  # Private chat uchun 1 sec
        if hasattr(self.entity, 'broadcast') and self.entity.broadcast:
            per_chat_delay = 3.0  # Kanal uchun 3 sec (20/min limit)
            
        messages = []
        async for msg in self.client.iter_messages(
            self.entity,
            offset_date=self.date_to,
            limit=None
        ):
            if self.date_from and msg.date < self.date_from:
                if messages:
                    yield messages
                break
                
            messages.append(msg)
            self.processed += 1
            
            if len(messages) >= self.batch_size:
                yield messages
                messages = []
                await asyncio.sleep(per_chat_delay)
                
        if messages:
            yield messages
```

### 4. `export/media_downloader.py` — Media fayllarni yuklash

```python
import asyncio
import hashlib
from pathlib import Path
from typing import Optional

class MediaDownloader:
    def __init__(
        self,
        client,
        output_dir: Path,
        max_file_size: int = 500 * 1024 * 1024,
        media_types: set[str] = None
    ):
        self.client = client
        self.output_dir = output_dir
        self.max_file_size = max_file_size
        self.media_types = media_types or set()
        self._downloaded = {}  # file_id -> path (dedup kesh)
        
    async def download(self, message) -> Optional[Path]:
        """Media faylni yuklash (dedup bilan)"""
        try:
            # Fayl hajmini tekshirish
            file_size = getattr(message.media, 'size', 0) if message.media else 0
            if file_size and file_size > self.max_file_size:
                return None  # Juda katta
                
            # Dedup tekshiruvi
            file_id = self._get_file_id(message)
            if file_id and file_id in self._downloaded:
                return self._downloaded[file_id]
                
            # Fayl nomini generatsiya qilish
            filename = self._generate_filename(message)
            filepath = self.output_dir / filename
            
            # Agar fayl mavjud bo'lsa, qayta yuklamaymiz
            if filepath.exists():
                self._downloaded[file_id] = filepath
                return filepath
                
            # Yuklash
            downloaded = await message.download_media(file=str(filepath))
            
            if downloaded:
                self._downloaded[file_id] = filepath
                return filepath
                
        except Exception:
            pass  # Xatolik bo'lsa o'tkazib yuborish
            
        return None
        
    def _get_file_id(self, message) -> Optional[str]:
        """Fayl ID olish (dedup uchun)"""
        if message.photo:
            return f"photo_{message.photo.id}"
        if message.document:
            return f"doc_{message.document.id}"
        return None
        
    def _generate_filename(self, message) -> str:
        """Fayl nomi: sana + original nom yoki hash"""
        date_str = message.date.strftime("%Y-%m-%d_%H-%M-%S")
        msg_id = message.id
        
        # Original nom
        if message.file and message.file.name:
            orig = message.file.name.replace('/', '_')[:100]
            return f"{date_str}_{msg_id}_{orig}"
            
        # Mime turiga qarab extension
        if message.photo:
            ext = "jpg"
        elif message.video:
            ext = "mp4"
        elif message.audio:
            ext = "mp3"
        elif message.voice:
            ext = "ogg"
        else:
            ext = "bin"
            
        return f"{date_str}_{msg_id}_media.{ext}"
```

### 5. `formatters/html_formatter.py` — Chiroyli HTML

```python
import json
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

class HTMLFormatter:
    """Telegram Desktop'dan ham chiroyli HTML eksport"""
    
    def __init__(self, templates_dir: Path = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        # Custom filterlar
        self.env.filters['format_date'] = self._format_date
        self.env.filters['format_time'] = self._format_time
        self.env.filters['message_type'] = self._get_message_type
        
    def format(
        self, 
        chat_name: str,
        entity,
        messages: list,
        media_dir: Path,
    ) -> Path:
        """Bitta chatni HTMLga formatlash"""
        # Xabarlarni guruhlash (sana bo'yicha)
        grouped = self._group_by_date(messages)
        
        # Participantlarni yig'ish
        participants = self._collect_participants(messages)
        
        template = self.env.get_template("chat.html")
        html = template.render(
            chat_name=chat_name,
            chat_type=self._get_chat_type(entity),
            grouped_messages=grouped,
            participants=participants,
            media_relative_path="media/",
            export_date=datetime.now(),
            total_messages=len(messages)
        )
        
        output_path = media_dir.parent / f"{chat_name}.html"
        output_path.write_text(html, encoding='utf-8')
        
        return output_path
        
    def _group_by_date(self, messages: list) -> dict:
        """Xabarlarni sana bo'yicha guruhlash"""
        groups = {}
        for msg in sorted(messages, key=lambda m: m.date):
            date_key = msg.date.strftime("%Y-%m-%d")
            if date_key not in groups:
                groups[date_key] = []
            groups[date_key].append(msg)
        return groups
        
    def _collect_participants(self, messages: list) -> dict:
        """Barcha ishtirokchilarni yig'ish"""
        participants = {}
        seen = set()
        for msg in messages:
            sender = msg.sender_id
            if sender and sender not in seen:
                seen.add(sender)
                participants[sender] = {
                    "id": sender,
                    "name": getattr(msg, 'sender_name', 'Unknown'),
                }
        return participants
        
    @staticmethod
    def _format_date(dt: datetime) -> str:
        return dt.strftime("%B %d, %Y")
        
    @staticmethod
    def _format_time(dt: datetime) -> str:
        return dt.strftime("%H:%M")
        
    @staticmethod
    def _get_message_type(msg) -> str:
        """Xabar turi"""
        if msg.photo: return "photo"
        if msg.video: return "video"
        if msg.audio: return "audio"
        if msg.voice: return "voice"
        if msg.sticker: return "sticker"
        if msg.document: return "document"
        if msg.contact: return "contact"
        if msg.poll: return "poll"
        if msg.geo: return "location"
        return "text"
        
    @staticmethod
    def _get_chat_type(entity) -> str:
        if hasattr(entity, 'broadcast') and entity.broadcast:
            return "channel"
        if hasattr(entity, 'megagroup') and entity.megagroup:
            return "group"
        return "private"
```

### 6. `formatters/templates/chat.html` — HTML template

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ chat_name }} — Telegram Export</title>
<style>
  /* Messenger-uslubidagi dizayn */
  :root {
    --bg: #0f172a;
    --surface: #1e293b;
    --surface-hover: #334155;
    --bubble-self: #3b82f6;
    --bubble-other: #334155;
    --text: #f1f5f9;
    --text-secondary: #94a3b8;
    --accent: #60a5fa;
    --border: #334155;
    --radius: 16px;
  }
  
  * { margin: 0; padding: 0; box-sizing: border-box; }
  
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  
  .container { max-width: 800px; margin: 0 auto; padding: 20px; }
  
  /* Header */
  .chat-header {
    position: sticky; top: 0; z-index: 100;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    padding: 16px 0;
    margin-bottom: 24px;
  }
  
  .chat-header h1 { font-size: 24px; font-weight: 700; }
  .chat-header .meta { color: var(--text-secondary); font-size: 14px; margin-top: 4px; }
  
  /* Date separator */
  .date-separator {
    display: flex; align-items: center; gap: 12px;
    margin: 24px 0 16px;
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  .date-separator::before,
  .date-separator::after {
    content: ''; flex: 1; height: 1px;
    background: var(--border);
  }
  
  /* Message bubble */
  .message {
    display: flex; gap: 10px;
    padding: 6px 0;
    position: relative;
  }
  
  .message:hover { background: var(--surface-hover); border-radius: 8px; }
  
  .message-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--surface); flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-weight: 600; font-size: 14px; color: var(--accent);
  }
  
  .message-body { flex: 1; min-width: 0; }
  
  .message-header {
    display: flex; align-items: baseline; gap: 8px;
    margin-bottom: 2px;
  }
  
  .message-sender { font-weight: 600; font-size: 14px; color: var(--accent); }
  .message-time { font-size: 12px; color: var(--text-secondary); }
  
  .message-text { 
    font-size: 15px; word-wrap: break-word; white-space: pre-wrap;
  }
  
  /* Reply context */
  .reply-context {
    border-left: 2px solid var(--accent);
    padding: 4px 8px;
    margin-bottom: 4px;
    font-size: 13px;
    color: var(--text-secondary);
    background: var(--surface);
    border-radius: 0 6px 6px 0;
  }
  
  .reply-context .reply-sender { font-weight: 600; color: var(--accent); }
  
  /* Forwarded */
  .forwarded-label {
    font-size: 12px; color: var(--text-secondary);
    margin-bottom: 2px;
  }
  
  /* Media */
  .message-media {
    margin-top: 6px; max-width: 400px;
    border-radius: 12px; overflow: hidden;
  }
  
  .message-media img {
    width: 100%; border-radius: 12px;
  }
  
  .message-media video {
    width: 100%; border-radius: 12px;
  }
  
  .media-document {
    display: flex; align-items: center; gap: 12px;
    background: var(--surface); padding: 12px 16px;
    border-radius: 12px;
  }
  
  .media-document .doc-icon { font-size: 32px; }
  .media-document .doc-name { font-size: 14px; font-weight: 500; }
  .media-document .doc-size { font-size: 12px; color: var(--text-secondary); }
  
  /* Sticker */
  .message-sticker img { max-width: 128px; max-height: 128px; }
  
  /* TOC (sidebar) */
  .toc {
    position: fixed; right: 20px; top: 20px;
    background: var(--surface); border-radius: 12px;
    padding: 12px 16px; font-size: 13px;
    max-width: 200px; max-height: 80vh; overflow-y: auto;
  }
  
  .toc a { color: var(--text-secondary); text-decoration: none; display: block; padding: 2px 0; }
  .toc a:hover { color: var(--accent); }
  
  /* Mobile responsive */
  @media (max-width: 600px) {
    .container { padding: 12px; }
    .message-media { max-width: 100%; }
    .toc { display: none; }
  }
  
  /* Print styles */
  @media print {
    body { background: white; color: black; }
    .chat-header { position: static; }
    .toc { display: none; }
    .message:hover { background: transparent; }
  }
</style>
</head>
<body>
<div class="container">
  
  <div class="chat-header">
    <h1>{{ chat_name }}</h1>
    <div class="meta">
      {{ chat_type | capitalize }} • {{ total_messages }} messages • 
      Exported {{ export_date.strftime('%B %d, %Y') }}
    </div>
  </div>
  
  {% for date_key, msgs in grouped_messages.items() %}
  <div class="date-separator" id="date-{{ date_key }}">
    <span>{{ date_key | replace('-', ' ') }}</span>
  </div>
  
  {% for msg in msgs %}
  <div class="message" id="msg-{{ msg.id }}">
    <div class="message-avatar">
      {{ (msg.sender_name or '?')[0] | upper }}
    </div>
    <div class="message-body">
      <div class="message-header">
        <span class="message-sender">{{ msg.sender_name or 'Unknown' }}</span>
        <span class="message-time">{{ msg.date.strftime('%H:%M') }}</span>
      </div>
      
      {% if msg.reply_to_msg_id %}
      <div class="reply-context">
        ↱ <span class="reply-sender">Replying to message #{{ msg.reply_to_msg_id }}</span>
      </div>
      {% endif %}
      
      {% if msg.fwd_from %}
      <div class="forwarded-label">↪ Forwarded</div>
      {% endif %}
      
      {% if msg.text %}
      <div class="message-text">{{ msg.text }}</div>
      {% endif %}
      
      {% if msg.photo %}
      <div class="message-media">
        <a href="media/{{ msg.id }}.jpg" target="_blank">
          <img src="media/{{ msg.id }}_thumb.jpg" 
               alt="Photo" 
               loading="lazy"
               onerror="this.style.display='none'">
        </a>
      </div>
      {% endif %}
      
      {% if msg.video %}
      <div class="message-media">
        <video controls preload="metadata" poster="media/{{ msg.id }}_thumb.jpg">
          <source src="media/{{ msg.id }}.mp4" type="video/mp4">
        </video>
      </div>
      {% endif %}
      
      {% if msg.document and not msg.photo and not msg.video %}
      <div class="media-document">
        <span class="doc-icon">📄</span>
        <div>
          <div class="doc-name">{{ msg.file.name or 'Document' }}</div>
          <div class="doc-size">{{ (msg.file.size / 1024 / 1024) | round(1) }} MB</div>
        </div>
      </div>
      {% endif %}
      
      {% if msg.sticker %}
      <div class="message-sticker">
        <img src="media/{{ msg.id }}.webp" alt="Sticker" loading="lazy">
      </div>
      {% endif %}
      
      {% if msg.poll %}
      <div class="message-poll">
        📊 <strong>Poll:</strong> {{ msg.poll.question }}
      </div>
      {% endif %}
    </div>
  </div>
  {% endfor %}
  
  {% endfor %}
  
  <!-- Sidebar TOC -->
  <div class="toc">
    <strong style="color: var(--text)">Jump to date</strong>
    {% for date_key in grouped_messages.keys() %}
    <a href="#date-{{ date_key }}">{{ date_key }}</a>
    {% endfor %}
  </div>
  
</div>
</body>
</html>
```

### 7. `ipc/server.py` — JSON-RPC stdin/stdout server

```python
import sys
import json
import asyncio
import traceback
from typing import Callable, Dict, Any

class IPCServer:
    """stdin/stdout orqali Electron bilan muloqot"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self._running = False
        self._event_queue = asyncio.Queue()
        
    def register(self, method: str, handler: Callable):
        """Handler ro'yxatdan o'tkazish"""
        self.handlers[method] = handler
        
    async def start(self):
        """Serverni ishga tushirish"""
        self._running = True
        reader = asyncio.StreamReader()
        
        # stdin dan o'qish event loop da
        loop = asyncio.get_event_loop()
        
        async def read_stdin():
            while self._running:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                line = line.strip()
                if line:
                    await self._handle_message(line)
                    
        async def send_events():
            while self._running:
                event = await self._event_queue.get()
                sys.stdout.write(json.dumps(event, ensure_ascii=False) + '\n')
                sys.stdout.flush()
                
        await asyncio.gather(read_stdin(), send_events())
        
    async def _handle_message(self, raw: str):
        """Kiruvchi xabarni qayta ishlash"""
        try:
            msg = json.loads(raw)
            msg_id = msg.get('id')
            method = msg.get('method')
            params = msg.get('params', {})
            
            handler = self.handlers.get(method)
            if not handler:
                self._send_error(msg_id, -32601, f"Method not found: {method}")
                return
                
            # Handlerni chaqirish
            result = await handler(params, msg_id)
            
            # Agar handler natija qaytarsa (event stream emas)
            if result is not None:
                self._send_result(msg_id, result)
                
        except json.JSONDecodeError:
            self._send_error(None, -32700, "Parse error")
        except Exception as e:
            self._send_error(msg.get('id'), -32603, str(e))
            traceback.print_exc()
            
    def send_event(self, event_name: str, data: Any):
        """Event streamga xabar qo'shish"""
        self._event_queue.put_nowait({
            "id": None,
            "event": event_name,
            "data": data
        })
        
    def _send_result(self, msg_id: str, result: Any):
        sys.stdout.write(json.dumps({
            "id": msg_id,
            "result": result
        }, ensure_ascii=False, default=str) + '\n')
        sys.stdout.flush()
        
    def _send_error(self, msg_id: str | None, code: int, message: str):
        sys.stdout.write(json.dumps({
            "id": msg_id,
            "error": {"code": code, "message": message}
        }, ensure_ascii=False) + '\n')
        sys.stdout.flush()
```

### 8. `python/main.py` — Python entry point

```python
#!/usr/bin/env python3
"""TeleExport Python Backend — JSON-RPC over stdin/stdout"""
import sys
import os
import asyncio
import signal

# Path sozlash
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ipc.server import IPCServer
from ipc.handlers import register_handlers
from core.client import TeleExportClient
from core.config import setup_dirs

class App:
    def __init__(self):
        self.server = IPCServer()
        self.client = TeleExportClient()
        self.current_export = None  # ExportEngine instance (cancel uchun)
        
    async def run(self):
        setup_dirs()
        register_handlers(self.server, self)
        
        # Graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.shutdown)
            
        await self.server.start()
        
    def shutdown(self):
        self.server._running = False
        if self.current_export:
            self.current_export.cancel()

if __name__ == "__main__":
    app = App()
    asyncio.run(app.run())
```

---

## ⚛️ FRONTEND (Electron + React) — Muhim qismlar

### 1. `electron/main.ts`

```typescript
import { app, BrowserWindow, ipcMain, shell, Menu } from 'electron';
import path from 'path';
import { PythonBridge } from './python-bridge';
import { registerIPCHandlers } from './ipc-handlers';
import { buildMenu } from './menu';

let mainWindow: BrowserWindow | null = null;
let pythonBridge: PythonBridge | null = null;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0f172a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  // Python backendni ishga tushirish
  pythonBridge = new PythonBridge();
  await pythonBridge.start();
  
  // IPC handlerlarni ro'yxatdan o'tkazish
  registerIPCHandlers(ipcMain, pythonBridge);
  
  // Menu
  Menu.setApplicationMenu(buildMenu());

  // Dev yoki production
  if (process.env.VITE_DEV_SERVER_URL) {
    await mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools();
  } else {
    await mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  pythonBridge?.stop();
  app.quit();
});
```

### 2. `electron/python-bridge.ts`

```typescript
import { ChildProcess, spawn } from 'child_process';
import path from 'path';
import { EventEmitter } from 'events';

interface IPCMessage {
  id: string | null;
  method?: string;
  params?: Record<string, unknown>;
  result?: unknown;
  error?: { code: number; message: string };
  event?: string;
  data?: unknown;
}

export class PythonBridge extends EventEmitter {
  private process: ChildProcess | null = null;
  private pending = new Map<string, { resolve: Function; reject: Function }>();
  private buffer = '';

  async start() {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
    const scriptPath = path.join(__dirname, '..', 'python', 'main.py');
    
    this.process = spawn(pythonPath, [scriptPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });

    this.process.stdout!.on('data', (data: Buffer) => {
      this.buffer += data.toString();
      const lines = this.buffer.split('\n');
      this.buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg: IPCMessage = JSON.parse(line);
          this.handleMessage(msg);
        } catch (e) {
          console.error('Failed to parse Python message:', line);
        }
      }
    });

    this.process.stderr!.on('data', (data: Buffer) => {
      console.error('Python stderr:', data.toString());
    });
  }

  async call(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    const id = crypto.randomUUID();
    
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      
      const request = JSON.stringify({ id, method, params }) + '\n';
      this.process!.stdin!.write(request);
      
      // Timeout (5 daqiqa — export uchun ko'p vaqt kerak)
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`Timeout: ${method}`));
        }
      }, 300_000);
    });
  }

  private handleMessage(msg: IPCMessage) {
    if (msg.id && this.pending.has(msg.id)) {
      const { resolve, reject } = this.pending.get(msg.id)!;
      this.pending.delete(msg.id);
      
      if (msg.error) {
        reject(new Error(msg.error.message));
      } else {
        resolve(msg.result);
      }
    }
    
    // Event stream
    if (msg.event) {
      this.emit(msg.event, msg.data);
    }
  }

  stop() {
    this.process?.kill();
  }
}
```

### 3. `electron/preload.ts`

```typescript
import { contextBridge, ipcRenderer } from 'electron';

const api = {
  // Python bridge proxy
  python: {
    call: (method: string, params?: Record<string, unknown>) =>
      ipcRenderer.invoke('python:call', method, params),
      
    onEvent: (event: string, callback: (data: unknown) => void) => {
      const handler = (_: unknown, data: unknown) => callback(data);
      ipcRenderer.on(`python:event:${event}`, handler);
      return () => ipcRenderer.removeListener(`python:event:${event}`, handler);
    },
    
    offEvent: (event: string) => {
      ipcRenderer.removeAllListeners(`python:event:${event}`);
    }
  },
  
  // Platform info
  platform: process.platform,
  
  // File dialoglar
  dialog: {
    selectDirectory: () => ipcRenderer.invoke('dialog:selectDirectory'),
    openFile: (path: string) => ipcRenderer.invoke('shell:openFile', path),
  },
  
  // App info
  app: {
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
    checkUpdate: () => ipcRenderer.invoke('app:checkUpdate'),
  }
};

contextBridge.exposeInMainWorld('teleexport', api);
```

### 4. `electron/ipc-handlers.ts`

```typescript
import { IpcMain, dialog } from 'electron';
import { PythonBridge } from './python-bridge';
import { shell } from 'electron';

export function registerIPCHandlers(ipcMain: IpcMain, bridge: PythonBridge) {
  // Python call proxy
  ipcMain.handle('python:call', async (_, method: string, params?: Record<string, unknown>) => {
    return bridge.call(method, params);
  });
  
  // Python eventlarni renderer ga forward qilish
  const forwardedEvents = [
    'export.progress',
    'export.media_progress',
    'export.chat_complete',
    'export.complete',
    'export.error',
    'auth.code_sent',
    'auth.signed_in',
    'chats.progress'
  ];
  
  for (const event of forwardedEvents) {
    bridge.on(event, (data) => {
      // Barcha windowlarga yuborish
      const windows = require('electron').BrowserWindow.getAllWindows();
      for (const win of windows) {
        win.webContents.send(`python:event:${event}`, data);
      }
    });
  }
  
  // Directory selector
  ipcMain.handle('dialog:selectDirectory', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory', 'createDirectory'],
      title: 'Export papkasini tanlang'
    });
    return result.canceled ? null : result.filePaths[0];
  });
  
  // Faylni ochish
  ipcMain.handle('shell:openFile', async (_, filePath: string) => {
    return shell.openPath(filePath);
  });
}
```

### 5. React: `src/stores/auth.store.ts`

```typescript
import { create } from 'zustand';

interface User {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  phone?: string;
}

interface AuthState {
  // State
  user: User | null;
  isLoggedIn: boolean;
  isCheckingSession: boolean;
  authStep: 'phone' | 'code' | 'password' | 'done';
  phoneCodeHash: string | null;
  error: string | null;
  
  // Actions
  checkSession: () => Promise<void>;
  sendCode: (phone: string) => Promise<void>;
  verifyCode: (code: string) => Promise<void>;
  verifyPassword: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoggedIn: false,
  isCheckingSession: true,
  authStep: 'phone',
  phoneCodeHash: null,
  error: null,
  
  checkSession: async () => {
    try {
      const result = await window.teleexport.python.call('auth.check_session');
      if (result?.has_session) {
        // Session bor, to'g'ridan-to'g'ri kirish
        set({ isLoggedIn: true, authStep: 'done', isCheckingSession: false });
      } else {
        set({ authStep: 'phone', isCheckingSession: false });
      }
    } catch {
      set({ authStep: 'phone', isCheckingSession: false });
    }
  },
  
  sendCode: async (phone: string) => {
    try {
      const result = await window.teleexport.python.call('auth.send_code', { phone });
      set({ 
        phoneCodeHash: result.phone_code_hash, 
        authStep: 'code',
        error: null 
      });
    } catch (e: any) {
      set({ error: e.message });
    }
  },
  
  verifyCode: async (code: string) => {
    try {
      const { phoneCodeHash } = get();
      const result = await window.teleexport.python.call('auth.sign_in', {
        phone: '',  // Telefon sessionda saqlanadi
        code,
        phone_code_hash: phoneCodeHash
      });
      
      if (result.success) {
        // 2FA tekshirish
        const twoFA = await window.teleexport.python.call('auth.check_2fa');
        if (twoFA.has_2fa) {
          set({ authStep: 'password', error: null });
        } else {
          set({ user: result.user, isLoggedIn: true, authStep: 'done', error: null });
        }
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },
  
  verifyPassword: async (password: string) => {
    try {
      const result = await window.teleexport.python.call('auth.sign_in_2fa', { password });
      if (result.success) {
        const me = await window.teleexport.python.call('auth.get_me');
        set({ user: me, isLoggedIn: true, authStep: 'done', error: null });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },
  
  logout: async () => {
    await window.teleexport.python.call('auth.logout');
    set({ user: null, isLoggedIn: false, authStep: 'phone' });
  },
  
  clearError: () => set({ error: null })
}));
```

### 6. React: `src/stores/export.store.ts`

```typescript
import { create } from 'zustand';

interface ExportProgress {
  exportId: string;
  chatId: number;
  chatName: string;
  percent: number;
  messagesDone: number;
  messagesTotal: number;
  currentFile?: string;
  filePercent?: number;
}

interface ExportState {
  // Config
  selectedChatIds: number[];
  format: 'html' | 'json' | 'csv' | 'pdf';
  dateFrom: string | null;
  dateTo: string | null;
  mediaTypes: string[];
  outputDir: string | null;
  
  // Status
  isExporting: boolean;
  exportId: string | null;
  progress: ExportProgress | null;
  chatProgress: Map<number, ExportProgress>;
  error: string | null;
  lastExportPath: string | null;
  
  // Actions
  setConfig: (config: Partial<Pick<ExportState, 
    'selectedChatIds' | 'format' | 'dateFrom' | 'dateTo' | 
    'mediaTypes' | 'outputDir'>>) => void;
  startExport: () => Promise<void>;
  cancelExport: () => Promise<void>;
  resetExport: () => void;
}

export const useExportStore = create<ExportState>((set, get) => ({
  selectedChatIds: [],
  format: 'html',
  dateFrom: null,
  dateTo: null,
  mediaTypes: ['photo', 'video', 'audio', 'document', 'voice', 'sticker'],
  outputDir: null,
  
  isExporting: false,
  exportId: null,
  progress: null,
  chatProgress: new Map(),
  error: null,
  lastExportPath: null,
  
  setConfig: (config) => set(config),
  
  startExport: async () => {
    const { selectedChatIds, format, dateFrom, dateTo, mediaTypes, outputDir } = get();
    
    if (!outputDir || selectedChatIds.length === 0) return;
    
    set({ isExporting: true, error: null });
    
    try {
      // Event listenerlarni o'rnatish
      window.teleexport.python.onEvent('export.progress', (data: any) => {
        const cp = get().chatProgress;
        cp.set(data.chat_id, data);
        set({ 
          progress: data,
          chatProgress: new Map(cp)
        });
      });
      
      window.teleexport.python.onEvent('export.complete', (data: any) => {
        set({ 
          isExporting: false, 
          lastExportPath: data.output_path,
          exportId: null
        });
      });
      
      window.teleexport.python.onEvent('export.error', (data: any) => {
        set({ error: data.error_message });
        if (!data.recoverable) {
          set({ isExporting: false });
        }
      });
      
      const result = await window.teleexport.python.call('export.start', {
        chat_ids: selectedChatIds,
        format,
        date_from: dateFrom,
        date_to: dateTo,
        media_types: mediaTypes,
        output_dir: outputDir
      });
      
      set({ exportId: result.export_id as string });
      
    } catch (e: any) {
      set({ error: e.message, isExporting: false });
    }
  },
  
  cancelExport: async () => {
    const { exportId } = get();
    if (exportId) {
      await window.teleexport.python.call('export.cancel', { export_id: exportId });
    }
    set({ isExporting: false });
  },
  
  resetExport: () => set({
    isExporting: false,
    progress: null,
    chatProgress: new Map(),
    error: null,
    exportId: null
  })
}));
```

---

## 📅 RIVOJLANISH BOSQICHLARI

### 1-HAFTA: Foundation

| Kun | Vazifa | Taxminiy vaqt |
|---|---|---|
| 1-2 | Loyiha strukturasi, Electron + React scaffold, Vite sozlash | 4 soat |
| 2-3 | Python backend strukturasi, Telethon integratsiyasi | 4 soat |
| 3-4 | JSON-RPC IPC protocol implementatsiyasi (Python + Electron) | 4 soat |
| 4-5 | Auth flow: Telefon → Kod → 2FA → Session | 6 soat |
| 5-6 | Electron oyna, frameless deraza, custom titlebar | 2 soat |
| 6-7 | Test: Auth flow ishlashini to'liq tekshirish | 2 soat |

### 2-HAFTA: Core Export

| Kun | Vazifa | Taxminiy vaqt |
|---|---|---|
| 8-9 | Chat skanerlash: `iter_dialogs`, chat turlari, ismlar | 3 soat |
| 9-10 | Message fetcher: `iter_messages`, batch, date filter | 4 soat |
| 10-11 | Media downloader: photo, video, document, sticker | 5 soat |
| 11-12 | Progress tracker: real-time progress eventlar | 3 soat |
| 12-13 | HTML formatter: Jinja2 template, CSS | 5 soat |
| 13-14 | JSON formatter | 2 soat |

### 3-HAFTA: UI

| Kun | Vazifa | Taxminiy vaqt |
|---|---|---|
| 15-16 | Dashboard: chat ro'yxati, qidiruv, statistikalar | 5 soat |
| 16-17 | Export Wizard: chat tanlash, format, sana, media | 4 soat |
| 17-18 | Progress UI: progress bar, chat statusi, log | 3 soat |
| 18-19 | Auth UI: telefon kiritish, kod, parol | 4 soat |
| 19-20 | Dark theme polish, loading states, error handling | 4 soat |
| 20-21 | Responsive design, animatsiyalar | 3 soat |

### 4-HAFTA: Polish + Ship

| Kun | Vazifa | Taxminiy vaqt |
|---|---|---|
| 22-23 | CSV + PDF formatter | 4 soat |
| 23-24 | Cancel, pause/resume | 3 soat |
| 24-25 | Electron build (Win/Mac/Linux) | 4 soat |
| 25-26 | Auto-updater sozlash | 2 soat |
| 26-27 | Test: katta chatlar (10k+ xabar), media | 4 soat |
| 27-28 | Bug fix, perf optimizatsiya, release | 5 soat |

---

## ⚡ PERFORMANCE OPTIMIZATSIYA

### Benchmark targetlari:

| Metrika | Target |
|---|---|
| Xabar olish tezligi | ~1000 msg/sec (takeout session) |
| Media yuklash | 2-5 MB/sec (parallel 3 ta) |
| HTML generatsiya | 10,000 xabar / 2 soniya |
| Xotira | 500MB dan kam (50k xabar uchun) |
| App ishga tushish | 3 soniyadan kam |

### Optimizatsiya usullari:

```python
# 1. Takeout session (eng muhimi!)
async with client.takeout() as takeout:
    # 10x tezroq, flood wait minimal
    async for msg in takeout.iter_messages(chat, wait_time=0):
        ...

# 2. Parallel media download
async def download_batch(messages, max_concurrent=3):
    sem = asyncio.Semaphore(max_concurrent)
    async def dl(msg):
        async with sem:
            return await msg.download_media()
    return await asyncio.gather(*[dl(m) for m in messages])

# 3. Streaming JSON (xotirani tejash)
async def write_json_stream(messages, filepath):
    async with aiofiles.open(filepath, 'w') as f:
        await f.write('{"messages":[\n')
        first = True
        async for msg in messages:
            if not first:
                await f.write(',\n')
            first = False
            await f.write(orjson.dumps(msg_to_dict(msg)).decode())
        await f.write('\n]}')

# 4. cryptg — encryption acceleration
# pip install cryptg
# Telethon avtomatik ishlatadi, 2-3x tezroq

# 5. Fayl dedup
# file_id orqali, qayta yuklamaslik
```

---

## 🔒 XAVFSIZLIK

### Muhim printsiplar:

| # | Qoida |
|---|---|
| 1 | **Hech qachon** foydalanuvchi ma'lumotlari serverga jo'natilmaydi |
| 2 | Session fayllar faqat mahalliy diskda, `chmod 600` |
| 3 | `api_id` va `api_hash` ochiq kodda qolmasligi kerak (build vaqtida inject qilish) |
| 4 | Python process sandboxlangan, tarmoqqa faqat Telegram DC larga chiqadi |
| 5 | Export fayllar foydalanuvchi tanlagan papkaga yoziladi |
| 6 | Auto-update HTTPS orqali, checksum tekshiruvi bilan |
| 7 | Crash reportlar faqat opt-in, hech qanday shaxsiy ma'lumotsiz |

### `api_id` va `api_hash` ni himoyalash:

```typescript
// electron-builder.yml da environment variable orqali
extraMetadata:
  TELEGRAM_API_ID: ${TELEGRAM_API_ID}
  TELEGRAM_API_HASH: ${TELEGRAM_API_HASH}
```

```bash
# Build vaqtida
TELEGRAM_API_ID=12345678 TELEGRAM_API_HASH=abcdef123456 npm run build
```

---

## 🧪 TESTING

### Python testlar:

```python
# tests/python/test_html_formatter.py
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from python.formatters.html_formatter import HTMLFormatter

class TestHTMLFormatter:
    def test_formats_single_message(self, tmp_path):
        formatter = HTMLFormatter()
        msg = MagicMock()
        msg.id = 1
        msg.text = "Salom dunyo!"
        msg.date = datetime(2026, 6, 6, 12, 0)
        msg.sender_name = "Ali"
        msg.photo = None
        msg.video = None
        
        result = formatter.format(
            "Ali", 
            MagicMock(is_private=True),
            [msg],
            tmp_path / "media"
        )
        
        html = result.read_text()
        assert "Salom dunyo!" in html
        assert "Ali" in html

# tests/python/test_export_engine.py
@pytest.mark.asyncio
async def test_export_chat(mock_client, tmp_path):
    config = ExportConfig(
        chat_ids=[123],
        output_dir=tmp_path,
        format="html"
    )
    engine = ExportEngine(mock_client, config)
    stats = await engine._export_chat(123, tmp_path)
    
    assert stats["messages_count"] > 0
    assert (tmp_path / "Test Chat.html").exists()
```

### Frontend testlar:

```typescript
// tests/frontend/ExportWizard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ExportWizard } from '../../src/components/export/ExportWizard';

describe('ExportWizard', () => {
  it('shows chat selector', () => {
    render(<ExportWizard />);
    expect(screen.getByText('Chatlarni tanlang')).toBeInTheDocument();
  });
  
  it('validates at least one chat selected', async () => {
    render(<ExportWizard />);
    const startBtn = screen.getByText('Export qilish');
    fireEvent.click(startBtn);
    expect(await screen.findByText('Kamida 1 ta chat tanlang')).toBeInTheDocument();
  });
});
```

---

## 📦 BUILD VA RELEASE

### `electron-builder.yml`:

```yaml
appId: com.teleexport.app
productName: TeleExport
copyright: Copyright © 2026

directories:
  output: release
  buildResources: resources

files:
  - dist/**/*
  - python/**/*
  - node_modules/**/*
  - package.json

extraResources:
  - from: python
    to: python
    filter:
      - "**/*"
      - "!__pycache__/**"
      - "!*.pyc"

# Python embed
asarUnpack:
  - python/**

mac:
  category: public.app-category.utilities
  hardenedRuntime: true
  gatekeeperAssess: false
  entitlements: entitlements.mac.plist
  target:
    - dmg
    - zip

win:
  target:
    - nsis
    - portable
  sign: false

nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true

linux:
  target:
    - AppImage
    - deb
  category: Utility

publish:
  provider: github
  owner: your-org
  repo: teleexport
```

---

## 💰 MONETIZATSIYA INTEGRATSIYASI

```typescript
// Litsenziya tekshiruvi
interface LicenseCheck {
  isValid: boolean;
  plan: 'free' | 'pro' | 'unlimited';
  features: {
    maxChatsPerExport: number;     // free: 1, pro: 10, unlimited: ∞
    maxMessagesPerChat: number;    // free: 1000, pro: 100k, unlimited: ∞
    formats: string[];             // free: ["html"], pro: ["html","json","csv"]
    mediaDownload: boolean;        // free: false, pro: true
    autoBackup: boolean;           // free: false, unlimited: true
    dateRange: boolean;            // free: false, pro: true
    supportPriority: 'none' | 'email' | 'chat';
  };
}
```

---

## ✅ MVP CHECKLIST

- [ ] Foydalanuvchi telefon raqam bilan kiradi
- [ ] Kod va 2FA tekshiruvi
- [ ] Session eslab qolinadi
- [ ] Barcha chatlar ro'yxati ko'rinadi
- [ ] Chatlarni qidirish
- [ ] Bir nechta chat tanlab eksport qilish
- [ ] HTML formatda chiroyli eksport
- [ ] Media fayllar (rasm, video, hujjat)
- [ ] Reply va forward konteksti
- [ ] Sana bo'yicha filter
- [ ] Real-time progress bar
- [ ] Cancel qilish imkoniyati
- [ ] Export papkasini ochish tugmasi
- [ ] Dark theme
- [ ] Windows + macOS + Linux build
- [ ] Auto-update
- [ ] Litsenziya tizimi (pul to'lash)
- [ ] Landing page

---

## 🚀 KEYINGI BOSQICHLAR (v1.5+)

- [ ] Telegram Mini App versiyasi (WebView)
- [ ] End-to-end encrypted cloud backup (ixtiyoriy)
- [ ] Avtomatik backup (har 24 soat)
- [ ] Incremental backup (faqat yangi xabarlar)
- [ ] Qidiruv (eksport qilingan fayllar ichida)
- [ ] Statistika va analitika (kim ko'p yozgan, eng aktiv vaqtlar)
- [ ] iOS/Android companion app (eksport preview uchun)
- [ ] Bir nechta akkaunt qo'llab-quvvatlash
- [ ] WhatsApp/WeChat import qilish
- [ ] Chat analitikasi (so'z buluti, emoji statistikasi)

---

**Tayyor! Shu reja asosida 4 haftada MVP tayyor bo'ladi. 🎯**
