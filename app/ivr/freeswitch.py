"""FreeSWITCH ESL outbound IVR client.

Connects to a self-hosted FreeSWITCH via its Event Socket Library (port 8021),
originates calls, and drives the full IVR flow inline — no webhook round-trips.

DRY_RUN when FS_ESL_HOST is blank or FS_ESL_PASSWORD starts with 'change-me'.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import asyncpg

from app.config import settings
from app.ivr.state_machine import transition

log = logging.getLogger(__name__)

# Module-level task set prevents fire-and-forget tasks from being GC'd mid-run
_bg_tasks: set[asyncio.Task[Any]] = set()


def _fire_and_forget(coro: Coroutine[Any, Any, Any]) -> None:
    t: asyncio.Task[Any] = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


_DRY_RUN = not (settings.fs_esl_host and not settings.fs_esl_password.startswith("change-me"))

# IVR prompt text per flow and language
_PROMPTS: dict[str, dict[str, str]] = {
    "flowA": {
        "ta": "நீங்கள் மருந்து எடுத்திருந்தால் 1 அழுத்தவும். எடுக்கவில்லை என்றால் 2 அழுத்தவும்.",
        "hi": "दवाई ली है तो 1 दबाएं। नहीं ली है तो 2 दबाएं।",
        "en": "Press 1 if you have taken your medication. Press 2 if you have not.",
    },
    "flowB": {
        "ta": "அவசர செய்தி. தொடர 1 அழுத்தவும்.",
        "hi": "जरूरी संदेश। जारी रखने के लिए 1 दबाएं।",
        "en": "Urgent message from your care team. Press 1 to continue.",
    },
    "flowC": {
        "ta": "உங்கள் உடல் நலம் எப்படி உள்ளது? நலமாக இருந்தால் 1 அழுத்தவும்.",
        "hi": "आपकी तबियत कैसी है? ठीक हैं तो 1 दबाएं।",
        "en": "How are you feeling? Press 1 if you are well. Press 2 to report symptoms.",
    },
}


# ---------------------------------------------------------------------------
# Minimal asyncio ESL client (no third-party deps)
# ---------------------------------------------------------------------------


class _ESL:
    """Asyncio-native FreeSWITCH Event Socket client.

    Uses a single reader loop started inside connect() so that command replies
    and async events never race for the same StreamReader.  All commands after
    connect() go through _send_and_wait() which dequeues the next reply.
    """

    def __init__(self, host: str, port: int, password: str) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._handlers: dict[str, list[Callable[..., Any]]] = {}
        self._reply_q: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._running = False
        self._bg_tasks: set[asyncio.Task[None]] = set()

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        # Auth before the reader loop starts so there is no concurrent read.
        await self._read_packet()  # auth/request
        self._write(f"auth {self._password}\n\n")
        reply = await self._read_packet()
        if "+OK accepted" not in reply.get("Reply-Text", ""):
            raise ValueError("ESL authentication failed — check FS_ESL_PASSWORD")
        # Start the single reader loop; all further I/O goes through _reply_q.
        t: asyncio.Task[None] = asyncio.create_task(self._reader_loop())
        self._bg_tasks.add(t)
        t.add_done_callback(self._bg_tasks.discard)

    def _write(self, data: str) -> None:
        assert self._writer is not None
        self._writer.write(data.encode())

    async def _flush(self) -> None:
        assert self._writer is not None
        await self._writer.drain()

    async def _read_packet(self) -> dict[str, str]:
        """Read one ESL envelope: headers + optional body."""
        assert self._reader is not None
        headers: dict[str, str] = {}
        while True:
            raw = await self._reader.readline()
            line = raw.decode(errors="replace").rstrip("\r\n")
            if not line:
                break
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip()] = v.strip()

        if length := headers.get("Content-Length"):
            body_bytes = await self._reader.readexactly(int(length))
            body = body_bytes.decode(errors="replace")
            if headers.get("Content-Type") == "text/event-plain":
                event: dict[str, str] = {}
                for line in body.splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        event[k.strip()] = unquote(v.strip())
                headers.update(event)
            else:
                headers["Body"] = body

        return headers

    async def _reader_loop(self) -> None:
        """Single reader: routes command/api replies to _reply_q, events to handlers."""
        self._running = True
        while self._running:
            try:
                packet = await self._read_packet()
                ct = packet.get("Content-Type", "")
                if ct in ("command/reply", "api/response"):
                    await self._reply_q.put(packet)
                elif ct == "text/event-plain":
                    name = packet.get("Event-Name", "")
                    for fn in self._handlers.get(name, []):
                        t: asyncio.Task[None] = asyncio.create_task(fn(packet))
                        self._bg_tasks.add(t)
                        t.add_done_callback(self._bg_tasks.discard)
                # text/disconnect-notice and others are intentionally dropped
            except (asyncio.IncompleteReadError, ConnectionResetError):
                break
            except Exception as exc:
                log.debug("esl_reader_loop_err %s", exc)

    async def _send_and_wait(self, data: str, timeout: float = 10.0) -> dict[str, str]:
        self._write(data)
        await self._flush()
        return await asyncio.wait_for(self._reply_q.get(), timeout=timeout)

    async def subscribe(self, *event_names: str) -> None:
        await self._send_and_wait(f"event plain {' '.join(event_names)}\n\n")

    async def bgapi(self, command: str) -> str:
        """Send a background API command; returns job UUID."""
        reply = await self._send_and_wait(f"bgapi {command}\n\n")
        return reply.get("Job-UUID", "")

    async def execute(self, channel_uuid: str, app: str, arg: str = "") -> None:
        """Execute a dialplan app on a parked channel."""
        msg = (
            f"sendmsg {channel_uuid}\n"
            f"call-command: execute\n"
            f"execute-app-name: {app}\n"
            f"execute-app-arg: {arg}\n\n"
        )
        await self._send_and_wait(msg)

    async def api(self, command: str) -> str:
        """Send a synchronous API command."""
        reply = await self._send_and_wait(f"api {command}\n\n")
        return reply.get("Body", "")

    def on(self, event_name: str, handler: Callable[..., Any]) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def close(self) -> None:
        self._running = False
        if self._writer:
            self._writer.close()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def place_outbound(
    to_e164: str,
    flow: str,
    language: str,
    senior_id: uuid.UUID,
    *,
    call_id: uuid.UUID | None = None,
) -> str:
    """Originate an outbound IVR call via FreeSWITCH ESL.

    Fires-and-forgets a background task that drives the full IVR flow.
    Returns the channel UUID (used as call_sid).
    """
    call_id = call_id or uuid.uuid4()

    if _DRY_RUN:
        sid = f"dry_run_fs_{call_id}"
        log.info(
            "ivr_dry_run provider=freeswitch to=%s flow=%s lang=%s call_id=%s",
            to_e164,
            flow,
            language,
            call_id,
        )
        await _persist_call_log(call_id, senior_id, sid, flow, language, "queued")
        return sid

    sid = str(call_id)
    await _persist_call_log(call_id, senior_id, sid, flow, language, "queued")
    _fire_and_forget(
        _drive_call(
            call_id=call_id,
            senior_id=senior_id,
            to_e164=to_e164,
            flow=flow,
            language=language,
        )
    )
    return sid


async def _drive_call(
    *,
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    to_e164: str,
    flow: str,
    language: str,
) -> None:
    """Connect to FS ESL, originate call, drive IVR, transition state machine."""
    channel_uuid = str(call_id)
    answered = asyncio.Event()
    hangup = asyncio.Event()
    dtmf_q: asyncio.Queue[str] = asyncio.Queue()
    exec_complete: asyncio.Event = asyncio.Event()
    exec_result: dict[str, str] = {}

    esl = _ESL(settings.fs_esl_host, settings.fs_esl_port, settings.fs_esl_password)

    try:
        await esl.connect()

        async def on_answer(ev: dict[str, str]) -> None:
            if ev.get("Unique-ID") == channel_uuid:
                answered.set()

        async def on_hangup(ev: dict[str, str]) -> None:
            if ev.get("Unique-ID") == channel_uuid:
                hangup.set()

        async def on_dtmf(ev: dict[str, str]) -> None:
            if ev.get("Unique-ID") == channel_uuid and (d := ev.get("DTMF-Digit", "")):
                await dtmf_q.put(d)

        async def on_execute_complete(ev: dict[str, str]) -> None:
            if (
                ev.get("Unique-ID") == channel_uuid
                and ev.get("Application") == "play_and_get_digits"
            ):
                exec_result.update(ev)
                exec_complete.set()

        esl.on("CHANNEL_ANSWER", on_answer)
        esl.on("CHANNEL_HANGUP", on_hangup)
        esl.on("DTMF", on_dtmf)
        esl.on("CHANNEL_EXECUTE_COMPLETE", on_execute_complete)

        # Reader loop already started inside connect(); just subscribe to events.
        await esl.subscribe("CHANNEL_ANSWER", "CHANNEL_HANGUP", "DTMF", "CHANNEL_EXECUTE_COMPLETE")

        # Originate
        gw = settings.fs_sip_gateway or "default"
        cli = settings.fs_caller_id or "saath"
        originate = (
            f"originate {{"
            f"origination_uuid={channel_uuid},"
            f"originate_timeout=30,"
            f"origination_caller_id_number={cli}"
            f"}}sofia/gateway/{gw}/{to_e164} &park()"
        )
        await esl.bgapi(originate)
        log.info("ivr_originate_sent call_id=%s to=%s flow=%s", call_id, to_e164, flow)

        # Wait for answer
        try:
            await asyncio.wait_for(answered.wait(), timeout=33)
        except TimeoutError:
            log.warning("ivr_no_answer call_id=%s", call_id)
            await transition(call_id, "failed")
            return

        await transition(call_id, "in_progress")

        # Drive IVR: play prompt + collect DTMF via play_and_get_digits
        digit = await _play_and_collect(
            esl, channel_uuid, flow, language, exec_complete, exec_result, hangup
        )

        if digit:
            log.info("ivr_digit_received call_id=%s digit=%s", call_id, digit)
            await _persist_dtmf(call_id, senior_id, digit, flow)
            await transition(call_id, "resolved")
        else:
            await transition(call_id, "partial")

        await esl.api(f"uuid_kill {channel_uuid}")

    except Exception as exc:
        log.warning("ivr_freeswitch_error call_id=%s err=%s", call_id, exc)
        import contextlib

        with contextlib.suppress(Exception):
            await transition(call_id, "failed")
    finally:
        esl.close()


async def _play_and_collect(
    esl: _ESL,
    channel_uuid: str,
    flow: str,
    language: str,
    exec_complete: asyncio.Event,
    exec_result: dict[str, str],
    hangup: asyncio.Event,
) -> str | None:
    """Execute play_and_get_digits on the channel; return the digit or None."""
    from app.ivr.tts import get_tts_url

    lang = language if language in ("ta", "hi", "en") else "en"
    prompt = _PROMPTS.get(flow, _PROMPTS["flowA"]).get(lang, "Press 1 to confirm.")
    audio_url = get_tts_url(prompt, lang, call_id=channel_uuid)

    # play_and_get_digits args: min max tries timeout terminator file invalid_file var_name regexp
    pgd = f"1 1 3 8000 # {audio_url} silence_stream://500 ivr_digit \\d"
    await esl.execute(channel_uuid, "play_and_get_digits", pgd)

    # Wait for execute complete or hangup (30s hard timeout)
    exec_task = asyncio.create_task(exec_complete.wait())
    hang_task = asyncio.create_task(hangup.wait())
    done, pending = await asyncio.wait(
        {exec_task, hang_task}, timeout=30.0, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()

    if exec_task in done:
        digit = exec_result.get("variable_ivr_digit", "").strip()
        return digit or None
    return None


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


async def _persist_call_log(
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    call_sid: str,
    flow: str,
    language: str,
    status: str,
) -> None:
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        await conn.execute(
            """INSERT INTO ivr_call_log
               (id, senior_id, provider, call_sid, flow, language, status, started_at)
               VALUES ($1,$2,'freeswitch',$3,$4,$5,$6,$7)
               ON CONFLICT DO NOTHING""",
            call_id,
            senior_id,
            call_sid,
            flow,
            language,
            status,
            datetime.now(UTC),
        )
    finally:
        await conn.close()


async def _persist_dtmf(
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    digit: str,
    flow: str,
) -> None:
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        event = "taken_via_ivr" if digit == "1" else "skipped_via_ivr"
        await conn.execute(
            """UPDATE ivr_call_log
               SET dtmf_responses = COALESCE(dtmf_responses,'{}')::jsonb || $2::jsonb
               WHERE id=$1""",
            call_id,
            f'{{"digit":"{digit}","event":"{event}"}}',
        )
        if digit == "1" and flow == "flowA":
            await conn.execute(
                """INSERT INTO med_reminder_event
                   (senior_id, medication_id, scheduled_for, event, event_at)
                   SELECT $1, m.id, NOW(), 'taken_via_ivr', NOW()
                   FROM medication m WHERE m.senior_id=$1 LIMIT 1""",
                senior_id,
            )
    finally:
        await conn.close()
