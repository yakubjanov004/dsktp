from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from filters.role_filter import RoleFilter
from database.basic.language import get_user_language
from config import settings
import asyncio
import datetime
import os
import tempfile
import logging

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("admin"))


def _build_pg_dump_command(db_url: str, out_path: str) -> list:
    # Expecting settings.DB_URL like: postgres://user:pass@host:port/dbname
    # Convert to pg_dump args for reliability
    # If pg_dump reads DATABASE_URL, we can also call: pg_dump "%DB_URL%" -Fc -f file
    return ["pg_dump", db_url, "-f", out_path]


@router.message(F.text.in_(["🗄️ Baza backup (.sql)", "🗄️ Бэкап базы (.sql)"]))
async def handle_db_backup(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_language(message.from_user.id) or "uz"

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"db_backup_{ts}.sql"

    # Create temp file path
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, filename)
        cmd = _build_pg_dump_command(settings.DB_URL, out_path)

        try:
            # Run pg_dump
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0 or not os.path.exists(out_path):
                err = stderr.decode() if stderr else ""
                await message.answer(
                    ("❌ Zaxira olishda xatolik yuz berdi." if lang == "uz" else "❌ Ошибка при создании бэкапа.")
                    + (f"\n{err}" if err else "")
                )
                return

            # Read file and send
            with open(out_path, "rb") as f:
                data = f.read()
            file_to_send = BufferedInputFile(data, filename=filename)
            await message.answer_document(
                document=file_to_send,
                caption=(
                    "🗄️ Baza zaxira nusxasi tayyor." if lang == "uz" else "🗄️ Бэкап базы готов."
                ),
            )
        except FileNotFoundError:
            await message.answer(
                ("❌ pg_dump topilmadi. Serverda pg_dump o'rnatilganligini tekshiring." if lang == "uz" else "❌ pg_dump не найден. Установите pg_dump на сервере.")
            )
        except Exception as e:
            await message.answer(
                ("❌ Zaxira olishda kutilmagan xatolik." if lang == "uz" else "❌ Непредвиденная ошибка при бэкапе.") + f"\n{e}"
            )

