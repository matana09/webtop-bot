import asyncio
import logging
import secrets
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from webtop import WebtopClient, WebtopLoginError
from webtop.models import WebtopSession
from config import WEBTOP_USERNAME, WEBTOP_PASSWORD, WEBTOP_DATA, WEBTOP_BASE_URL

DEVICE_JSON = (
    '{"isMobile":false,"isTablet":false,"isDesktop":true,'
    '"getDeviceType":"Desktop","os":"Windows","osVersion":"10",'
    '"browser":"Chrome","browserVersion":"147.0.0.0","browserMajorVersion":147,'
    '"screen_resolution":"1920 x 1080","cookies":true,'
    '"userAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"}'
)
_DEVICE_ID_FILE = Path(__file__).with_name(".device_id")


def _device_id() -> str:
    """A stable per-installation device id.

    SmartSchool wants a UniqueId with the login. Generating one locally on
    first run — instead of shipping a fixed value — keeps every install
    distinct and avoids baking one machine's fingerprint into the repo.
    """
    try:
        return _DEVICE_ID_FILE.read_text().strip()
    except OSError:
        pass
    device_id = secrets.token_hex(20)
    try:
        _DEVICE_ID_FILE.write_text(device_id)
    except OSError:
        logging.getLogger(__name__).warning("Could not persist device id; using a temporary one")
    return device_id


UNIQUE_ID = _device_id()


class PatchedWebtopClient(WebtopClient):
    """Adds UniqueId / captcha / deviceDataJson fields missing from base library."""

    async def login(self) -> WebtopSession:
        logger.info("Patched login: %s", self._username)
        resp = await self._http.post(
            "/server/api/user/LoginByUserNameAndPassword",
            json={
                "UserName": self._username,
                "Password": self._password,
                "Data": self._data,
                "RememberMe": self._remember_me,
                "BiometricLogin": self._biometric_login,
                "UniqueId": UNIQUE_ID,
                "captcha": "",
                "deviceDataJson": DEVICE_JSON,
            },
        )
        if resp.status_code != 200:
            logger.error("Login failed with status %s: %s", resp.status_code, resp.text)
            raise WebtopLoginError(f"Login failed ({resp.status_code}): {resp.text}")

        body = resp.json()
        data = body.get("data", {})
        token = data.get("token", "")

        # Set auth cookie for subsequent requests
        self._http.cookies.set("webToken", token, domain=self._http.base_url.host)

        session = WebtopSession(
            token=token,
            user_id=data.get("userId"),
            student_id=data.get("studentId"),
            school_id=data.get("schoolId"),
            school_name=data.get("schoolName"),
            first_name=data.get("firstName"),
            last_name=data.get("lastName"),
            raw_login_data=data,
        )
        self._session = session
        logger.info("Login OK: %s %s", session.first_name, session.last_name)
        return session

logger = logging.getLogger(__name__)


def _current_study_year() -> int:
    """Israeli academic year ends in the returned year (e.g. 2025-2026 → 2026)."""
    today = date.today()
    return today.year if today.month >= 9 else today.year


SESSION_TTL = 3 * 3600  # re-login every 3 hours


class WebtopService:
    def __init__(self):
        self._client: Optional[WebtopClient] = None
        self._student_data: Dict[str, Any] = {}
        self._period_data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._login_time: float = 0.0

    async def _build_client(self) -> PatchedWebtopClient:
        kwargs: Dict[str, Any] = dict(
            username=WEBTOP_USERNAME,
            password=WEBTOP_PASSWORD,
            auto_login=True,
        )
        if WEBTOP_DATA:
            kwargs["data"] = WEBTOP_DATA
        if WEBTOP_BASE_URL:
            kwargs["base_url"] = WEBTOP_BASE_URL
        return PatchedWebtopClient(**kwargs)

    async def _do_login(self):
        """Create client, login, and load student/period data."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
        self._client = await self._build_client()
        await self._client.login()
        self._login_time = time.monotonic()
        await self._load_student_data()
        await self._load_period_data()

    async def _ensure_client(self) -> WebtopClient:
        age = time.monotonic() - self._login_time
        if self._client is None or age > SESSION_TTL:
            if age > SESSION_TTL and self._client is not None:
                logger.info("Session TTL reached (%.0f min), re-logging in...", age / 60)
            await self._do_login()
        return self._client

    async def _call(self, coro):
        """Run an API coroutine, retrying once on auth/session failure."""
        try:
            return await coro
        except Exception as exc:
            err = str(exc).lower()
            if any(x in err for x in ("401", "403", "unauthorized", "login", "token", "expired", "session")):
                logger.warning("Auth error, resetting session and retrying: %s", exc)
                self._client = None
                self._login_time = 0.0
                await self._ensure_client()
                return await coro
            raise

    async def _load_student_data(self):
        try:
            dashboard = await self._client.get_students()
            logger.debug("Raw dashboard: %s", dashboard)
            if isinstance(dashboard, dict) and "data" in dashboard:
                data = dashboard["data"]
                if isinstance(data, dict) and "childrens" in data:
                    children = data["childrens"]
                    if children and isinstance(children, list):
                        self._student_data = children[0]
                        logger.info(
                            "Student loaded: %s %s | keys: %s",
                            self._student_data.get("firstName"),
                            self._student_data.get("lastName"),
                            list(self._student_data.keys()),
                        )
        except Exception as exc:
            logger.error("Failed to load student data: %s", exc)

    async def _load_period_data(self):
        # Try GetStudyYears first
        try:
            resp = await self._client.request(
                "POST",
                "/server/api/PupilCard/GetStudyYears",
                json={
                    "studentID": self._student_data.get("id", ""),
                    "classCode": self._student_data.get("classCode", ""),
                },
            )
            if resp.status_code == 200:
                body = resp.json()
                years = body.get("data") or []
                study_year = _current_study_year()
                for y in years:
                    if y.get("studyYear") == study_year or y.get("studyYearName"):
                        periods = y.get("periods") or y.get("semesters") or []
                        if periods:
                            p = periods[-1]
                            self._period_data = {
                                "moduleID": y.get("moduleID") or y.get("id") or 0,
                                "periodID": p.get("periodID") or p.get("id") or 0,
                                "periodName": p.get("periodName") or p.get("name") or "",
                                "studyYearName": y.get("studyYearName") or "",
                            }
                            logger.info("Period loaded via GetStudyYears: %s", self._period_data)
                            return
        except Exception:
            pass  # fallback below

        # Fallback: extract period_id from grades
        try:
            resp = await self._client.request(
                "POST",
                "/server/api/PupilCard/GetPupilGrades",
                json={
                    "weekIndex": 0,
                    "viewType": 0,
                    "studyYear": _current_study_year(),
                    "studyYearName": "",
                    "studentID": self._student_data.get("id", ""),
                    "studentName": "",
                    "classCode": self._student_data.get("classCode", ""),
                    "moduleID": 6,
                    "periodID": 0,
                    "periodName": "",
                },
            )
            if resp.status_code == 200:
                body = resp.json()
                grades = body.get("data") or []
                for g in grades:
                    pid = g.get("period_id")
                    if pid:
                        self._period_data = {
                            "moduleID": 10,
                            "periodID": pid,
                            "periodName": "",
                            "studyYearName": "",
                        }
                        logger.info("Period loaded via grades fallback: %s", self._period_data)
                        return
        except Exception as exc:
            logger.warning("Failed to load period data: %s", exc)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_field(self, *candidates: str) -> str:
        for key in candidates:
            val = self._student_data.get(key)
            if val is not None:
                return str(val)
        return ""

    @property
    def encrypted_student_id(self) -> str:
        return self._get_field(
            "id", "encryptedStudentId", "encrypted_student_id", "encryptId", "encryptedId"
        )

    @property
    def class_code(self) -> str:
        return self._get_field("classCode", "class_code", "classId", "classSymbol")

    @property
    def class_number(self) -> int:
        val = self._get_field("classNum", "classNumber", "class_number", "gradeNumber", "grade")
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    @property
    def student_name(self) -> str:
        first = self._student_data.get("firstName", "")
        last = self._student_data.get("lastName", "")
        return f"{first} {last}".strip() or "התלמיד"

    # ── public API ────────────────────────────────────────────────────────────

    async def get_schedule(self, week_index: int = 0) -> Any:
        async with self._lock:
            client = await self._ensure_client()
            study_year = _current_study_year()
            resp = await self._call(client.request(
                "POST",
                "/server/api/PupilCard/GetPupilScheduale",
                json={
                    "weekIndex": week_index,
                    "viewType": 0,
                    "studyYear": study_year,
                    "studyYearName": self._period_data.get("studyYearName", ""),
                    "studentID": self.encrypted_student_id,
                    "studentName": self.student_name,
                    "classCode": self.class_code,
                    "moduleID": self._period_data.get("moduleID", 10),
                    "periodID": self._period_data.get("periodID", 0),
                    "periodName": self._period_data.get("periodName", ""),
                },
            ))
            if resp.status_code != 200:
                raise Exception(f"Schedule request failed ({resp.status_code}): {resp.text[:300]}")
            return resp.json()

    async def get_homework(self, week_index: int = 0) -> Any:
        async with self._lock:
            client = await self._ensure_client()
            resp = await self._call(client.request(
                "POST",
                "/server/api/PupilCard/GetPupilLessonsAndHomework",
                json={
                    "weekIndex": week_index,
                    "viewType": 0,
                    "studyYear": _current_study_year(),
                    "studyYearName": self._period_data.get("studyYearName", ""),
                    "studentID": self.encrypted_student_id,
                    "studentName": self.student_name,
                    "classCode": self.class_code,
                    "moduleID": 11,
                    "periodID": self._period_data.get("periodID", 0),
                    "periodName": self._period_data.get("periodName", ""),
                },
            ))
            if resp.status_code != 200:
                raise Exception(f"GetPupilLessonsAndHomework failed ({resp.status_code})")
            return resp.json()

    async def get_notifications(self) -> Any:
        async with self._lock:
            client = await self._ensure_client()
            return await self._call(client.get_preview_unread_notifications())

    async def get_messages(self, page_id: int = 1) -> Any:
        async with self._lock:
            client = await self._ensure_client()
            return await self._call(client.get_messages_inbox(page_id=page_id))

    async def get_discipline_events(self) -> Any:
        async with self._lock:
            client = await self._ensure_client()
            resp = await client.request(
                "POST",
                "/server/api/PupilCard/GetPupilDiciplineEvents",
                json={
                    "weekIndex": 0,
                    "viewType": 0,
                    "studyYear": _current_study_year(),
                    "studyYearName": self._period_data.get("studyYearName", ""),
                    "studentID": self.encrypted_student_id,
                    "studentName": self.student_name,
                    "classCode": self.class_code,
                    "moduleID": 4,
                    "periodID": self._period_data.get("periodID", 0),
                    "periodName": self._period_data.get("periodName", ""),
                },
            )
            if resp.status_code != 200:
                raise Exception(f"GetPupilDiciplineEvents failed ({resp.status_code})")
            return resp.json()

    async def get_grades(self) -> Any:
        async with self._lock:
            client = await self._ensure_client()
            resp = await client.request(
                "POST",
                "/server/api/PupilCard/GetPupilGrades",
                json={
                    "weekIndex": 0,
                    "viewType": 0,
                    "studyYear": _current_study_year(),
                    "studyYearName": self._period_data.get("studyYearName", ""),
                    "studentID": self.encrypted_student_id,
                    "studentName": self.student_name,
                    "classCode": self.class_code,
                    "moduleID": 6,
                    "periodID": self._period_data.get("periodID", 0),
                    "periodName": self._period_data.get("periodName", ""),
                },
            )
            if resp.status_code != 200:
                raise Exception(f"GetPupilGrades failed ({resp.status_code})")
            return resp.json()

    async def get_raw_dashboard(self) -> Any:
        async with self._lock:
            client = await self._ensure_client()
            return await client.get_students()

    async def reset(self):
        async with self._lock:
            if self._client:
                await self._client.close()
            self._client = None
            self._student_data = {}

    async def close(self):
        if self._client:
            await self._client.close()


# module-level singleton
webtop = WebtopService()
