import csv
import io
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover - optional until MySQL deployment
    pymysql = None
    DictCursor = None


TOTAL_CE_TASKS = 8
COMPLETION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

TYPE_LABELS = {
    "daily": "日常服务为主",
    "balanced": "均衡型",
    "leisure": "休闲体验为主",
}

SCHEMES = {
    "S01": {"density": "高", "type": "daily", "price": 30, "space_compensation": "保留免费休憩区", "revenue_feedback": "无收益反哺"},
    "S02": {"density": "低", "type": "balanced", "price": 10, "space_compensation": "无补偿", "revenue_feedback": "有收益反哺机制"},
    "S03": {"density": "中", "type": "balanced", "price": 30, "space_compensation": "保留免费休憩区", "revenue_feedback": "有收益反哺机制"},
    "S04": {"density": "低", "type": "leisure", "price": 10, "space_compensation": "无补偿", "revenue_feedback": "无收益反哺"},
    "S05": {"density": "低", "type": "balanced", "price": 30, "space_compensation": "保留免费休憩区", "revenue_feedback": "无收益反哺"},
    "S06": {"density": "高", "type": "daily", "price": 10, "space_compensation": "无补偿", "revenue_feedback": "有收益反哺机制"},
    "S07": {"density": "低", "type": "leisure", "price": 30, "space_compensation": "保留免费休憩区", "revenue_feedback": "有收益反哺机制"},
    "S08": {"density": "中", "type": "balanced", "price": 10, "space_compensation": "无补偿", "revenue_feedback": "无收益反哺"},
    "S09": {"density": "中", "type": "leisure", "price": 10, "space_compensation": "保留免费休憩区", "revenue_feedback": "有收益反哺机制"},
    "S10": {"density": "低", "type": "daily", "price": 30, "space_compensation": "无补偿", "revenue_feedback": "无收益反哺"},
    "S11": {"density": "中", "type": "leisure", "price": 30, "space_compensation": "无补偿", "revenue_feedback": "无收益反哺"},
    "S12": {"density": "高", "type": "daily", "price": 10, "space_compensation": "无补偿", "revenue_feedback": "无收益反哺"},
    "S13": {"density": "高", "type": "balanced", "price": 10, "space_compensation": "保留免费休憩区", "revenue_feedback": "无收益反哺"},
    "S14": {"density": "中", "type": "daily", "price": 30, "space_compensation": "无补偿", "revenue_feedback": "有收益反哺机制"},
    "S15": {"density": "中", "type": "daily", "price": 10, "space_compensation": "保留免费休憩区", "revenue_feedback": "无收益反哺"},
    "S16": {"density": "高", "type": "balanced", "price": 30, "space_compensation": "无补偿", "revenue_feedback": "有收益反哺机制"},
}

TASKS = {
    1: {"choice_set_id": "CE-01", "A": "S01", "B": "S02"},
    2: {"choice_set_id": "CE-02", "A": "S03", "B": "S04"},
    3: {"choice_set_id": "CE-03", "A": "S05", "B": "S06"},
    4: {"choice_set_id": "CE-04", "A": "S07", "B": "S08"},
    5: {"choice_set_id": "CE-05", "A": "S09", "B": "S10"},
    6: {"choice_set_id": "CE-06", "A": "S11", "B": "S12"},
    7: {"choice_set_id": "CE-07", "A": "S13", "B": "S14"},
    8: {"choice_set_id": "CE-08", "A": "S15", "B": "S16"},
}

QUESTION_SECTIONS = [
    {"part": 1, "title": "第一部分：基本使用行为", "questions": ["B1", "B5", "B3", "B2"]},
    {"part": 2, "title": "第二部分：公园商业接触经验", "questions": ["C1", "C2", "C3"]},
    {"part": 3, "title": "第三部分：公共空间价值取向量表", "questions": ["PV1", "PV2", "PV3", "PV4"]},
    {"part": 4, "title": "第四部分：情境选择补充题", "questions": ["CE_POST_1"]},
    {"part": 5, "title": "第五部分：消费意愿", "questions": ["A1", "A2"]},
    {"part": 6, "title": "第六部分：基本信息", "questions": ["D1", "D2", "D3", "D4"]},
]

QUESTION_META = {
    "B1": {"display_id": "1-1", "title": "到访频率", "statement": "你平均多久去一次城市公园？"},
    "B5": {"display_id": "1-2", "title": "常去公园", "statement": "您平时最常去的城市公园，更接近下面哪一种？"},
    "B3": {"display_id": "1-3", "title": "同行对象", "statement": "你通常和谁一起去公园？"},
    "B2": {"display_id": "1-4", "title": "主要目的", "statement": "你通常去公园的主要目的是什么？"},
    "C1": {"display_id": "2-1", "title": "消费经历", "statement": "你是否在城市公园内有过消费经历？"},
    "C2": {"display_id": "2-2", "title": "商业化程度感知", "statement": "你认为当前城市公园的整体商业化程度如何？"},
    "C3": {"display_id": "2-3", "title": "分类看法", "statement": "您觉得，不同类型的公园，在商业设置上是否应该有所区别？"},
    "PV1": {"display_id": "3-1", "title": "可达性", "statement": "公园应当让所有人都能自由进入，不应因商业设施而让人产生进入门槛感。"},
    "PV2": {"display_id": "3-2", "title": "包容性", "statement": "公园应当照顾不同收入水平和年龄群体的需求，而不应只服务于有消费能力的人。"},
    "PV3": {"display_id": "3-3", "title": "使用自由", "statement": "在公园里不消费是正常且合理的，公园不应让人感到“不消费就不该久留”的压力。"},
    "PV4": {"display_id": "3-4", "title": "公共归属感", "statement": "无论商业化程度如何，公园的公共属性都不应被削弱。"},
    "CE_POST_1": {"display_id": "4-9", "title": "联想对象", "statement": "在回答后面这些公园方案选择题时，您脑海里想到的，主要是哪一种公园？"},
    "A1": {"display_id": "5-1", "title": "付费意愿", "statement": "在公园游览中，如果商业服务符合我的需求，我愿意为其付费。"},
    "A2": {"display_id": "5-2", "title": "实际支出", "statement": "在一次公园游览中，商业消费的实际支出通常为："},
    "D1": {"display_id": "6-1", "title": "性别", "statement": "您的性别："},
    "D2": {"display_id": "6-2", "title": "年龄", "statement": "您的年龄："},
    "D3": {"display_id": "6-3", "title": "受教育程度", "statement": "您的受教育程度："},
    "D4": {"display_id": "6-4", "title": "月均可支配收入", "statement": "您的月均可支配收入（个人）："},
}

ANSWER_FIELD_MAP = {
    "B1": "b1_visit_frequency",
    "B2": "b2_main_purposes",
    "B3": "b3_companions",
    "B5": "b5_usual_park_type",
    "C1": "c1_commerce_experience",
    "C2": "c2_commercial_level_view",
    "C3": "c3_park_type_view",
    "PV1": "pv1",
    "PV2": "pv2",
    "PV3": "pv3",
    "PV4": "pv4",
    "CE_POST_1": "ce_post_1_park_imagined",
    "A1": "a1_payment_willingness",
    "A2": "a2_actual_spending",
    "D1": "d1_gender",
    "D2": "d2_age",
    "D3": "d3_education",
    "D4": "d4_income",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def serialize_answer_value(value: Any) -> Any:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return value


def normalize_park_type(label: str | None) -> str | None:
    if not label:
        return None
    if "社区" in label or "离家比较近" in label:
        return "社区型"
    if "综合" in label or "面积比较大" in label or "功能很多" in label:
        return "综合型"
    if "专类" in label or "特色" in label or "主题" in label:
        return "专类型"
    if "生态" in label or "绿地" in label or "自然" in label:
        return "生态型"
    if "凭感觉" in label:
        return "凭感觉"
    if "不确定" in label or "说不太清" in label:
        return "不确定"
    return label


def normalize_bool_label(completed: Any) -> str:
    return "completed" if completed else "incomplete"


def format_duration(duration_sec: int | None) -> str:
    if not duration_sec:
        return "0秒"
    minutes, seconds = divmod(int(duration_sec), 60)
    if minutes:
        return f"{minutes}分{seconds}秒"
    return f"{seconds}秒"


def row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return {key: row[key] for key in row.keys()}


def parse_database_target(target: str | Path) -> dict[str, Any]:
    raw = str(target)
    parsed = urlparse(raw)
    if parsed.scheme in {"mysql", "mysql+pymysql"}:
        return {
            "engine": "mysql",
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/"),
        }
    return {"engine": "sqlite", "path": Path(raw)}


class SurveyRepository:
    def __init__(self, db_path: str | Path):
        self.db_target = parse_database_target(db_path)
        self.engine = self.db_target["engine"]
        if self.engine == "sqlite":
            self.db_path = Path(self.db_target["path"])
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.db_path = None
        self._init_db()

    def _connect(self):
        if self.engine == "sqlite":
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection
        if pymysql is None:
            raise RuntimeError("PyMySQL is required for MySQL connections")
        return pymysql.connect(
            host=self.db_target["host"],
            port=self.db_target["port"],
            user=self.db_target["user"],
            password=self.db_target["password"],
            database=self.db_target["database"],
            charset="utf8mb4",
            autocommit=False,
            cursorclass=DictCursor,
        )

    def _placeholder(self) -> str:
        return "?" if self.engine == "sqlite" else "%s"

    def _execute(self, connection, query: str, params: list[Any] | tuple[Any, ...] | None = None):
        cursor = connection.cursor()
        cursor.execute(query, params or ())
        return cursor

    def _fetchone(self, connection, query: str, params: list[Any] | tuple[Any, ...] | None = None):
        cursor = self._execute(connection, query, params)
        try:
            return row_to_dict(cursor.fetchone())
        finally:
            cursor.close()

    def _fetchall(self, connection, query: str, params: list[Any] | tuple[Any, ...] | None = None):
        cursor = self._execute(connection, query, params)
        try:
            return [row_to_dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def _execute_write(self, connection, query: str, params: list[Any] | tuple[Any, ...] | None = None):
        cursor = self._execute(connection, query, params)
        cursor.close()

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    @contextmanager
    def _read(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _init_db(self):
        with self._transaction() as connection:
            if self.engine == "sqlite":
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS respondents (
                      respondent_id TEXT PRIMARY KEY,
                      completion_code TEXT,
                      survey_started_at TEXT,
                      submit_time TEXT,
                      duration_sec INTEGER,
                      completed INTEGER NOT NULL DEFAULT 0,
                      ce_completed_tasks INTEGER NOT NULL DEFAULT 0,
                      total_choice_tasks INTEGER NOT NULL DEFAULT 8,
                      park_type_usual TEXT,
                      park_type_imagined TEXT,
                      park_type_difference_attitude TEXT,
                      b1_visit_frequency TEXT,
                      b2_main_purposes TEXT,
                      b3_companions TEXT,
                      b4_park_visits_count TEXT,
                      b5_usual_park_type TEXT,
                      c1_commerce_experience TEXT,
                      c2_commercial_level_view TEXT,
                      c3_park_type_view TEXT,
                      pv1 INTEGER,
                      pv2 INTEGER,
                      pv3 INTEGER,
                      pv4 INTEGER,
                      ce_post_1_park_imagined TEXT,
                      a1_payment_willingness INTEGER,
                      a2_actual_spending TEXT,
                      d1_gender TEXT,
                      d2_age TEXT,
                      d3_education TEXT,
                      d4_income TEXT,
                      draft_payload_json TEXT,
                      final_payload_json TEXT,
                      client_meta_json TEXT,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS ce_choices (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      respondent_id TEXT NOT NULL,
                      task_id INTEGER NOT NULL,
                      choice_set_id TEXT NOT NULL,
                      option_a_scheme_id TEXT NOT NULL,
                      option_a_density TEXT NOT NULL,
                      option_a_type TEXT NOT NULL,
                      option_a_price INTEGER NOT NULL,
                      option_a_space_compensation TEXT NOT NULL,
                      option_a_revenue_feedback TEXT NOT NULL,
                      option_b_scheme_id TEXT NOT NULL,
                      option_b_density TEXT NOT NULL,
                      option_b_type TEXT NOT NULL,
                      option_b_price INTEGER NOT NULL,
                      option_b_space_compensation TEXT NOT NULL,
                      option_b_revenue_feedback TEXT NOT NULL,
                      chosen_option TEXT NOT NULL,
                      selected_scheme_id TEXT,
                      response_time_ms INTEGER,
                      created_at TEXT NOT NULL,
                      UNIQUE(respondent_id, task_id),
                      FOREIGN KEY (respondent_id) REFERENCES respondents (respondent_id)
                    );
                    """
                )
            else:
                self._execute_write(
                    connection,
                    """
                    CREATE TABLE IF NOT EXISTS respondents (
                      respondent_id VARCHAR(16) PRIMARY KEY,
                      completion_code VARCHAR(16),
                      survey_started_at VARCHAR(64),
                      submit_time VARCHAR(64),
                      duration_sec INT,
                      completed TINYINT NOT NULL DEFAULT 0,
                      ce_completed_tasks INT NOT NULL DEFAULT 0,
                      total_choice_tasks INT NOT NULL DEFAULT 8,
                      park_type_usual VARCHAR(128),
                      park_type_imagined VARCHAR(128),
                      park_type_difference_attitude VARCHAR(255),
                      b1_visit_frequency VARCHAR(128),
                      b2_main_purposes TEXT,
                      b3_companions TEXT,
                      b4_park_visits_count VARCHAR(128),
                      b5_usual_park_type VARCHAR(128),
                      c1_commerce_experience VARCHAR(128),
                      c2_commercial_level_view VARCHAR(128),
                      c3_park_type_view VARCHAR(255),
                      pv1 INT,
                      pv2 INT,
                      pv3 INT,
                      pv4 INT,
                      ce_post_1_park_imagined VARCHAR(255),
                      a1_payment_willingness INT,
                      a2_actual_spending VARCHAR(128),
                      d1_gender VARCHAR(64),
                      d2_age VARCHAR(64),
                      d3_education VARCHAR(128),
                      d4_income VARCHAR(128),
                      draft_payload_json LONGTEXT,
                      final_payload_json LONGTEXT,
                      client_meta_json LONGTEXT,
                      created_at VARCHAR(64) NOT NULL,
                      updated_at VARCHAR(64) NOT NULL
                    ) CHARACTER SET utf8mb4
                    """
                )
                self._execute_write(
                    connection,
                    """
                    CREATE TABLE IF NOT EXISTS ce_choices (
                      id BIGINT PRIMARY KEY AUTO_INCREMENT,
                      respondent_id VARCHAR(16) NOT NULL,
                      task_id INT NOT NULL,
                      choice_set_id VARCHAR(32) NOT NULL,
                      option_a_scheme_id VARCHAR(16) NOT NULL,
                      option_a_density VARCHAR(64) NOT NULL,
                      option_a_type VARCHAR(128) NOT NULL,
                      option_a_price INT NOT NULL,
                      option_a_space_compensation VARCHAR(128) NOT NULL,
                      option_a_revenue_feedback VARCHAR(128) NOT NULL,
                      option_b_scheme_id VARCHAR(16) NOT NULL,
                      option_b_density VARCHAR(64) NOT NULL,
                      option_b_type VARCHAR(128) NOT NULL,
                      option_b_price INT NOT NULL,
                      option_b_space_compensation VARCHAR(128) NOT NULL,
                      option_b_revenue_feedback VARCHAR(128) NOT NULL,
                      chosen_option VARCHAR(8) NOT NULL,
                      selected_scheme_id VARCHAR(16),
                      response_time_ms INT,
                      created_at VARCHAR(64) NOT NULL,
                      UNIQUE KEY uq_respondent_task (respondent_id, task_id),
                      CONSTRAINT fk_ce_respondent FOREIGN KEY (respondent_id) REFERENCES respondents (respondent_id)
                    ) CHARACTER SET utf8mb4
                    """
                )
            self._ensure_respondents_schema(connection)

    def _ensure_respondents_schema(self, connection):
        if self.engine == "sqlite":
            columns = self._fetchall(connection, "PRAGMA table_info(respondents)")
            column_names = {row["name"] for row in columns}
            if "completion_code" not in column_names:
                self._execute_write(connection, "ALTER TABLE respondents ADD COLUMN completion_code TEXT")
        else:
            columns = self._fetchall(
                connection,
                """
                SELECT COLUMN_NAME AS name
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'respondents'
                """,
            )
            column_names = {row["name"] for row in columns}
            if "completion_code" not in column_names:
                self._execute_write(
                    connection,
                    "ALTER TABLE respondents ADD COLUMN completion_code VARCHAR(16) AFTER respondent_id",
                )

    def _next_respondent_id(self, connection) -> str:
        row = self._fetchone(
            connection,
            "SELECT respondent_id FROM respondents ORDER BY respondent_id DESC LIMIT 1",
        )
        current_max = int(str(row["respondent_id"])[1:]) if row and row.get("respondent_id") else 0
        return f"R{current_max + 1:04d}"

    def _next_completion_code(self, connection) -> str:
        p = self._placeholder()
        while True:
            prefix = "".join(secrets.choice(COMPLETION_CODE_ALPHABET) for _ in range(2))
            suffix = "".join(secrets.choice(COMPLETION_CODE_ALPHABET) for _ in range(6))
            completion_code = f"{prefix}-{suffix}"
            existing = self._fetchone(
                connection,
                f"SELECT completion_code FROM respondents WHERE completion_code = {p}",
                (completion_code,),
            )
            if not existing:
                return completion_code

    def start_response(self, started_at: str | None = None) -> str:
        started_at = started_at or now_iso()
        timestamp = now_iso()
        p = self._placeholder()
        with self._transaction() as connection:
            respondent_id = self._next_respondent_id(connection)
            self._execute_write(
                connection,
                f"""
                INSERT INTO respondents (
                  respondent_id, completion_code, survey_started_at, completed, ce_completed_tasks, total_choice_tasks,
                  created_at, updated_at
                ) VALUES ({p}, NULL, {p}, 0, 0, {p}, {p}, {p})
                """,
                (respondent_id, started_at, TOTAL_CE_TASKS, timestamp, timestamp),
            )
            return respondent_id

    def _flatten_payload(self, respondent_id: str, payload: dict[str, Any], completed: bool) -> dict[str, Any]:
        respondent_meta = payload.get("respondent_meta", {})
        answers = {item.get("id"): item for item in payload.get("non_ce_answers", []) if item.get("id")}
        row: dict[str, Any] = {
            "respondent_id": respondent_id,
            "completion_code": None,
            "survey_started_at": respondent_meta.get("started_at"),
            "submit_time": respondent_meta.get("submitted_at"),
            "duration_sec": respondent_meta.get("total_duration_seconds"),
            "completed": 1 if completed else 0,
            "ce_completed_tasks": len(payload.get("ce_answers", [])),
            "total_choice_tasks": TOTAL_CE_TASKS,
            "park_type_usual": normalize_park_type(payload.get("derived_meta", {}).get("frequent_park_type")),
            "park_type_imagined": normalize_park_type(payload.get("derived_meta", {}).get("imagined_park_type")),
            "park_type_difference_attitude": payload.get("derived_meta", {}).get("park_type_difference_attitude"),
        }
        for question_id, field_name in ANSWER_FIELD_MAP.items():
            answer = answers.get(question_id)
            row[field_name] = serialize_answer_value(answer.get("value")) if answer else None
        return row

    def save_draft(self, respondent_id: str, payload: dict[str, Any] | None, client_meta: dict[str, Any] | None = None):
        payload = payload or {}
        row = self._flatten_payload(respondent_id, payload, completed=False)
        existing = self.get_respondent(respondent_id)
        timestamp = now_iso()
        row.update(
            {
                "completion_code": existing.get("completion_code") if existing else None,
                "draft_payload_json": json.dumps(payload, ensure_ascii=False),
                "client_meta_json": json.dumps(client_meta or {}, ensure_ascii=False),
                "updated_at": timestamp,
            }
        )
        self._upsert_respondent_row(row)

    def submit_response(self, respondent_id: str, payload: dict[str, Any], client_meta: dict[str, Any] | None = None):
        row = self._flatten_payload(respondent_id, payload, completed=True)
        existing = self.get_respondent(respondent_id)
        timestamp = now_iso()
        with self._transaction() as connection:
            completion_code = existing.get("completion_code") if existing else None
            if not completion_code:
                completion_code = self._next_completion_code(connection)
            row.update(
                {
                    "completion_code": completion_code,
                    "draft_payload_json": json.dumps(payload, ensure_ascii=False),
                    "final_payload_json": json.dumps(payload, ensure_ascii=False),
                    "client_meta_json": json.dumps(client_meta or {}, ensure_ascii=False),
                    "submit_time": payload.get("respondent_meta", {}).get("submitted_at") or timestamp,
                    "updated_at": timestamp,
                }
            )
        self._upsert_respondent_row(row)
        self._replace_ce_choices(respondent_id, payload.get("ce_answers", []))
        return row["completion_code"]

    def _upsert_respondent_row(self, row: dict[str, Any]):
        existing = self.get_respondent(row["respondent_id"])
        timestamp = now_iso()
        base = {
            "created_at": existing["created_at"] if existing else timestamp,
            "updated_at": row.get("updated_at", timestamp),
            "respondent_id": row["respondent_id"],
        }
        base.update(row)
        columns = [
            "respondent_id",
            "completion_code",
            "survey_started_at",
            "submit_time",
            "duration_sec",
            "completed",
            "ce_completed_tasks",
            "total_choice_tasks",
            "park_type_usual",
            "park_type_imagined",
            "park_type_difference_attitude",
            "b1_visit_frequency",
            "b2_main_purposes",
            "b3_companions",
            "b4_park_visits_count",
            "b5_usual_park_type",
            "c1_commerce_experience",
            "c2_commercial_level_view",
            "c3_park_type_view",
            "pv1",
            "pv2",
            "pv3",
            "pv4",
            "ce_post_1_park_imagined",
            "a1_payment_willingness",
            "a2_actual_spending",
            "d1_gender",
            "d2_age",
            "d3_education",
            "d4_income",
            "draft_payload_json",
            "final_payload_json",
            "client_meta_json",
            "created_at",
            "updated_at",
        ]
        placeholders = ", ".join(self._placeholder() for _ in columns)
        with self._transaction() as connection:
            values = [base.get(column) for column in columns]
            if self.engine == "sqlite":
                self._execute_write(
                    connection,
                    f"""
                    INSERT OR REPLACE INTO respondents ({", ".join(columns)})
                    VALUES ({placeholders})
                    """,
                    values,
                )
            else:
                updates = ", ".join(
                    f"{column}=VALUES({column})" for column in columns if column != "respondent_id"
                )
                self._execute_write(
                    connection,
                    f"""
                    INSERT INTO respondents ({", ".join(columns)})
                    VALUES ({placeholders})
                    ON DUPLICATE KEY UPDATE {updates}
                    """,
                    values,
                )

    def _replace_ce_choices(self, respondent_id: str, ce_answers: list[dict[str, Any]]):
        p = self._placeholder()
        with self._transaction() as connection:
            self._execute_write(connection, f"DELETE FROM ce_choices WHERE respondent_id = {p}", (respondent_id,))
            for item in ce_answers:
                task_id = int(item.get("task_id"))
                task = TASKS.get(task_id)
                if not task:
                    continue
                option_a = SCHEMES[task["A"]]
                option_b = SCHEMES[task["B"]]
                chosen_option = item.get("selected_alt")
                selected_scheme_id = item.get("selected_scheme") or task.get(chosen_option)
                self._execute_write(
                    connection,
                    f"""
                    INSERT INTO ce_choices (
                      respondent_id, task_id, choice_set_id,
                      option_a_scheme_id, option_a_density, option_a_type, option_a_price, option_a_space_compensation, option_a_revenue_feedback,
                      option_b_scheme_id, option_b_density, option_b_type, option_b_price, option_b_space_compensation, option_b_revenue_feedback,
                      chosen_option, selected_scheme_id, response_time_ms, created_at
                    ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                    """,
                    (
                        respondent_id,
                        task_id,
                        task["choice_set_id"],
                        task["A"],
                        option_a["density"],
                        TYPE_LABELS[option_a["type"]],
                        option_a["price"],
                        option_a["space_compensation"],
                        option_a["revenue_feedback"],
                        task["B"],
                        option_b["density"],
                        TYPE_LABELS[option_b["type"]],
                        option_b["price"],
                        option_b["space_compensation"],
                        option_b["revenue_feedback"],
                        chosen_option,
                        selected_scheme_id,
                        item.get("response_time"),
                        now_iso(),
                    ),
                )

    def get_respondent(self, respondent_id: str) -> dict[str, Any] | None:
        with self._read() as connection:
            return self._fetchone(
                connection,
                f"SELECT * FROM respondents WHERE respondent_id = {self._placeholder()}",
                (respondent_id,),
            )

    def list_responses(self, status: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        clauses = []
        values: list[Any] = []
        if status == "completed":
            clauses.append("completed = 1")
        elif status == "incomplete":
            clauses.append("completed = 0")
        if search:
            search_value = f"%{search}%"
            clauses.append(
                f"(respondent_id LIKE {self._placeholder()} OR completion_code LIKE {self._placeholder()})"
            )
            values.extend([search_value, search_value])
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT respondent_id, completion_code, submit_time, survey_started_at, completed, duration_sec, park_type_usual, park_type_imagined,
                   ce_completed_tasks, total_choice_tasks, updated_at
            FROM respondents
            {where_clause}
            ORDER BY CASE WHEN submit_time IS NULL THEN 1 ELSE 0 END ASC,
                     submit_time DESC,
                     updated_at DESC,
                     respondent_id DESC
        """
        with self._read() as connection:
            rows = self._fetchall(connection, query, values)
        result = []
        for row in rows:
            data = row
            data["status"] = normalize_bool_label(data["completed"])
            data["duration_label"] = format_duration(data["duration_sec"])
            data["ce_progress"] = f"{data['ce_completed_tasks']}/{data['total_choice_tasks']}"
            result.append(data)
        return result

    def dashboard_summary(self, status: str | None = None, search: str | None = None) -> dict[str, Any]:
        today_prefix = datetime.now().astimezone().date().isoformat()
        with self._read() as connection:
            total_submissions = self._fetchone(connection, "SELECT COUNT(*) AS count FROM respondents")["count"]
            completed_submissions = self._fetchone(connection, "SELECT COUNT(*) AS count FROM respondents WHERE completed = 1")["count"]
            incomplete_submissions = self._fetchone(connection, "SELECT COUNT(*) AS count FROM respondents WHERE completed = 0")["count"]
            avg_duration_sec = self._fetchone(
                connection,
                "SELECT COALESCE(ROUND(AVG(duration_sec)), 0) AS value FROM respondents WHERE completed = 1"
            )["value"]
            today_new = self._fetchone(
                connection,
                f"SELECT COUNT(*) AS count FROM respondents WHERE created_at LIKE {self._placeholder()}",
                (f"{today_prefix}%",),
            )["count"]
            latest_row = self._fetchone(connection, "SELECT MAX(updated_at) AS latest FROM respondents")

        return {
            "total_submissions": int(total_submissions),
            "completed_submissions": int(completed_submissions),
            "incomplete_submissions": int(incomplete_submissions),
            "avg_duration_sec": int(avg_duration_sec or 0),
            "avg_duration_label": format_duration(int(avg_duration_sec or 0)),
            "today_new": int(today_new),
            "last_updated_at": latest_row["latest"] if latest_row else None,
            "responses": self.list_responses(status=status, search=search),
        }

    def get_response_detail(self, respondent_id: str) -> dict[str, Any] | None:
        respondent = self.get_respondent(respondent_id)
        if respondent is None:
            return None
        payload_raw = respondent.get("final_payload_json") or respondent.get("draft_payload_json")
        payload = json.loads(payload_raw) if payload_raw else {}
        answers_by_id = {item.get("id"): item for item in payload.get("non_ce_answers", []) if item.get("id")}
        p = self._placeholder()

        answer_sections = []
        for section in QUESTION_SECTIONS:
            questions = []
            for question_id in section["questions"]:
                meta = QUESTION_META[question_id]
                answer = answers_by_id.get(question_id)
                questions.append(
                    {
                        "id": question_id,
                        "display_id": meta["display_id"],
                        "title": meta["title"],
                        "statement": meta["statement"],
                        "answer_value": answer.get("value") if answer else None,
                        "answer_display": answer.get("label") if answer else None,
                        "response_time_ms": answer.get("response_time_ms") if answer else None,
                    }
                )
            answer_sections.append(
                {
                    "part": section["part"],
                    "title": section["title"],
                    "questions": questions,
                }
            )

        with self._read() as connection:
            ce_rows = self._fetchall(
                connection,
                f"""
                SELECT respondent_id, task_id, choice_set_id,
                       option_a_scheme_id, option_a_density, option_a_type, option_a_price, option_a_space_compensation, option_a_revenue_feedback,
                       option_b_scheme_id, option_b_density, option_b_type, option_b_price, option_b_space_compensation, option_b_revenue_feedback,
                       chosen_option, selected_scheme_id, response_time_ms, created_at
                FROM ce_choices
                WHERE respondent_id = {p}
                ORDER BY task_id ASC
                """,
                (respondent_id,),
            )
        respondent["status"] = normalize_bool_label(respondent["completed"])
        respondent["duration_label"] = format_duration(respondent["duration_sec"])
        return {
            "respondent": respondent,
            "answer_sections": answer_sections,
            "ce_choices": ce_rows,
            "payload": payload,
        }

    def iter_respondents_export(self) -> list[dict[str, Any]]:
        with self._read() as connection:
            rows = self._fetchall(
                connection,
                """
                SELECT respondent_id, submit_time, duration_sec, completed, survey_started_at,
                       completion_code,
                       park_type_usual, park_type_imagined, park_type_difference_attitude,
                       b1_visit_frequency, b2_main_purposes, b3_companions, b4_park_visits_count, b5_usual_park_type,
                       c1_commerce_experience, c2_commercial_level_view, c3_park_type_view,
                       pv1, pv2, pv3, pv4,
                       ce_post_1_park_imagined,
                       a1_payment_willingness, a2_actual_spending,
                       d1_gender, d2_age, d3_education, d4_income,
                       ce_completed_tasks, total_choice_tasks, created_at, updated_at
                FROM respondents
                ORDER BY COALESCE(submit_time, updated_at) DESC, respondent_id DESC
                """
            )
            return rows

    def iter_ce_export(self) -> list[dict[str, Any]]:
        with self._read() as connection:
            rows = self._fetchall(
                connection,
                """
                SELECT respondent_id, task_id, choice_set_id,
                       option_a_density, option_a_type, option_a_price, option_a_space_compensation, option_a_revenue_feedback,
                       option_b_density, option_b_type, option_b_price, option_b_space_compensation, option_b_revenue_feedback,
                       chosen_option, selected_scheme_id, response_time_ms, created_at
                FROM ce_choices
                ORDER BY respondent_id ASC, task_id ASC
                """
            )
            return rows


def csv_bytes(rows: list[dict[str, Any]], headers: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def export_respondents_csv(repository: SurveyRepository) -> bytes:
    headers = [
        "respondent_id",
        "completion_code",
        "submit_time",
        "duration_sec",
        "completed",
        "survey_started_at",
        "park_type_usual",
        "park_type_imagined",
        "park_type_difference_attitude",
        "b1_visit_frequency",
        "b2_main_purposes",
        "b3_companions",
        "b4_park_visits_count",
        "b5_usual_park_type",
        "c1_commerce_experience",
        "c2_commercial_level_view",
        "c3_park_type_view",
        "pv1",
        "pv2",
        "pv3",
        "pv4",
        "ce_post_1_park_imagined",
        "a1_payment_willingness",
        "a2_actual_spending",
        "d1_gender",
        "d2_age",
        "d3_education",
        "d4_income",
        "ce_completed_tasks",
        "total_choice_tasks",
        "created_at",
        "updated_at",
    ]
    return csv_bytes(repository.iter_respondents_export(), headers)


def export_ce_choices_csv(repository: SurveyRepository) -> bytes:
    headers = [
        "respondent_id",
        "task_id",
        "choice_set_id",
        "option_a_density",
        "option_a_type",
        "option_a_price",
        "option_a_space_compensation",
        "option_a_revenue_feedback",
        "option_b_density",
        "option_b_type",
        "option_b_price",
        "option_b_space_compensation",
        "option_b_revenue_feedback",
        "chosen_option",
        "selected_scheme_id",
        "response_time_ms",
        "created_at",
    ]
    return csv_bytes(repository.iter_ce_export(), headers)
